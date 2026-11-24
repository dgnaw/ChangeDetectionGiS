"""Unified unit tests for Người A's GIS pipeline (STAC fetch, MNDWI, PB 04.00 offset, IoU, population, schemas)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from jsonschema import validate
from shapely.geometry import box, mapping

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from src.config import CRS_METRIC, CRS_STORAGE
from src.population.build_timeseries import build_timeseries_summary
from src.population.clip_population import compute_ghsl_tile_id, interpolate_population_grid
from src.population.grid_to_geojson import aggregate_100m_to_250m, export_population_grid_geojson
from src.population.spatial_overlay import compute_pop_in_water_buffer
from src.validate_outputs import audit_processed_outputs
from src.water.fetch_stac import (
    build_datetime_range,
    compute_combined_clear_coverage,
    compute_scl_stats_from_array,
    filter_and_rank_items,
    load_aoi,
)
from src.water.mndwi_otsu import compute_mndwi, threshold_otsu_water
from src.water.preprocess import apply_pb0400_offset, compute_median_composite
from src.water.validate_jrc import compute_iou, compute_validation_metrics
from src.water.vectorize import classify_water_change_masks, vectorize_water_mask

ROOT = PIPELINE_ROOT.parents[1]


def test_load_aoi_projects_to_32648() -> None:
    aoi_4326, aoi_32648 = load_aoi(ROOT / "contracts/aoi.geojson")
    assert aoi_4326.crs.to_string() == CRS_STORAGE
    assert aoi_32648.crs.to_string() == CRS_METRIC
    area_km2 = float(aoi_32648.geometry.area.sum() / 1_000_000.0)
    assert 230.0 <= area_km2 <= 255.0


def test_build_datetime_range() -> None:
    assert build_datetime_range(2020) == "2020-01-01/2020-04-30"


def test_filter_and_rank_items_prefers_32648_and_low_cloud() -> None:
    aoi_geom = box(105.78, 21.01, 105.93, 21.15)
    full_tile = mapping(box(105.5, 20.8, 106.2, 21.4))
    partial_tile = mapping(box(105.5, 20.8, 105.82, 21.05))

    items = [
        SimpleNamespace(id="partial_low_cloud", geometry=partial_tile, properties={"proj:code": "EPSG:32648", "eo:cloud_cover": 0.5, "datetime": "2020-02-01T03:25:00Z"}),
        SimpleNamespace(id="wrong_crs_low_cloud", geometry=full_tile, properties={"proj:code": "EPSG:32649", "eo:cloud_cover": 1.0, "datetime": "2020-02-05T03:25:00Z"}),
        SimpleNamespace(id="good_5pct", geometry=full_tile, properties={"proj:code": "EPSG:32648", "eo:cloud_cover": 5.0, "datetime": "2020-03-01T03:25:00Z"}),
        SimpleNamespace(id="good_2pct_old", geometry=full_tile, properties={"proj:code": "EPSG:32648", "eo:cloud_cover": 2.0, "datetime": "2020-02-10T03:25:00Z"}),
        SimpleNamespace(id="good_2pct_reprocessed", geometry=full_tile, properties={"proj:code": "EPSG:32648", "eo:cloud_cover": 2.0, "datetime": "2020-02-10T03:25:00Z"}),
    ]
    ranked = filter_and_rank_items(items, aoi_geom, max_scenes=2)
    assert [it.id for it in ranked] == ["good_2pct_reprocessed", "good_5pct"]


def test_compute_scl_cloud_stats_and_combined_coverage() -> None:
    # Scene 1: nửa trái quang mây (SCL=6 nước, SCL=4 thảm thực vật), nửa phải bị mây (SCL=9)
    scl1 = np.array([[6, 4, 9, 9], [6, 4, 8, 3]], dtype=np.uint8)
    # Scene 2: nửa trái bị mây (SCL=9), nửa phải quang mây (SCL=6, SCL=5)
    scl2 = np.array([[9, 9, 6, 5], [8, 3, 6, 5]], dtype=np.uint8)

    clear1, cloud1, valid1 = compute_scl_stats_from_array(scl1)
    clear2, cloud2, valid2 = compute_scl_stats_from_array(scl2)
    assert cloud1 == 50.0 and valid1 == 50.0
    assert cloud2 == 50.0 and valid2 == 50.0
    # Gộp 2 cảnh bù trừ chéo -> phủ sạch 100% AOI
    combined = compute_combined_clear_coverage([clear1, clear2], inside_aoi=(scl1 > 0))
    assert combined == 100.0


def test_compute_mndwi_basic() -> None:
    b03 = np.array([[0.3, 0.2]], dtype=np.float32)
    b11 = np.array([[0.1, 0.6]], dtype=np.float32)
    mndwi = compute_mndwi(b03, b11)
    assert np.isclose(mndwi[0, 0], 0.5)
    assert np.isclose(mndwi[0, 1], -0.5)


def test_apply_pb0400_offset() -> None:
    raw_dn = np.array([[800, 1500, 3200]], dtype=np.float32)
    pre_2022 = apply_pb0400_offset(raw_dn, 2020)
    post_2022 = apply_pb0400_offset(raw_dn, "2022-02-10")
    assert np.allclose(pre_2022, np.array([[800.0, 1500.0, 3200.0]], dtype=np.float32))
    assert np.allclose(post_2022, np.array([[0.0, 500.0, 2200.0]], dtype=np.float32))


def test_apply_pb0400_offset_respects_processing_baseline() -> None:
    raw_dn = np.array([[450.0, 1600.0]], dtype=np.float32)
    # Cảnh đầu năm 2022 (2022-01-18) có PB 03.00 -> KHÔNG trừ 1000
    jan_2022_pb03 = apply_pb0400_offset(raw_dn, year_or_date="2022-01-18", processing_baseline="03.00")
    assert np.allclose(jan_2022_pb03, raw_dn)
    # Cảnh tái xử lý PB 05.10 -> CÓ trừ 1000
    reprocessed_pb05 = apply_pb0400_offset(raw_dn, year_or_date="2022-04-03", processing_baseline="05.10")
    assert np.allclose(reprocessed_pb05, np.array([[0.0, 600.0]], dtype=np.float32))


def test_composite_masks_clouds_seamlessly() -> None:
    scene1 = np.array([[0.4, np.nan], [-0.2, np.nan]], dtype=np.float32)
    scene2 = np.array([[np.nan, 0.5], [-0.3, -0.1]], dtype=np.float32)
    comp = compute_median_composite([scene1, scene2])
    assert np.allclose(comp, np.array([[0.4, 0.5], [-0.25, -0.1]], dtype=np.float32))


def test_threshold_otsu_water_bimodal_and_bounds() -> None:
    rng = np.random.default_rng(42)
    land = rng.normal(loc=-0.20, scale=0.05, size=890).astype(np.float32)
    water = rng.normal(loc=0.35, scale=0.05, size=110).astype(np.float32)
    arr = np.concatenate([land, water]).reshape(20, 50)
    arr[0, 0] = np.nan

    mask, clamped_t, raw_t = threshold_otsu_water(arr)
    assert 0.0 <= clamped_t <= 0.15
    assert -0.20 < raw_t < 0.35
    assert mask[0, 0] == 255
    # Số pixel nước tách được phải xấp xỉ 110 pixel
    assert 100 <= int((mask == 1).sum()) <= 120


def test_compute_iou() -> None:
    pred = np.array([[1, 1], [0, 0]])
    ref = np.array([[1, 0], [0, 0]])
    assert np.isclose(compute_iou(pred, ref), 0.5)


def test_compute_jrc_validation_metrics() -> None:
    pred = np.array([[1, 1], [0, 0]], dtype=np.uint8)
    ref = np.array([[1, 0], [1, 0]], dtype=np.uint8)
    m = compute_validation_metrics(pred, ref, pixel_area_km2=0.01)
    assert np.isclose(m["iou"], 1 / 3, atol=1e-4)
    assert np.isclose(m["precision"], 0.5)
    assert np.isclose(m["recall"], 0.5)
    assert np.isclose(m["f1_score"], 0.5)
    assert np.isclose(m["overall_accuracy"], 0.5)
    assert np.isclose(m["pred_area_km2"], 0.02)


def test_clean_and_classify_water_change_masks() -> None:
    base = np.zeros((30, 30), dtype=np.uint8)
    curr = np.zeros((30, 30), dtype=np.uint8)

    # Vùng nước ổn định 10x10 = 100 px (>= 50 px)
    base[2:12, 2:12] = 1
    curr[2:12, 2:12] = 1

    # Vùng nước mất đi (loss) 8x8 = 64 px (>= 50 px) ở góc trên phải
    base[2:10, 18:26] = 1

    # Vùng nước mới (gain) 8x8 = 64 px (>= 50 px) ở góc dưới trái
    curr[18:26, 2:10] = 1

    # Hạt nhiễu 1x1 ở curr -> phải bị lọc bỏ hoàn toàn
    curr[28, 28] = 1

    masks = classify_water_change_masks(curr_mask_uint8=curr, base_mask_uint8=base, min_pixels=50)
    assert int(masks["stable"].sum()) == 100
    assert int(masks["gain"].sum()) == 64
    assert int(masks["loss"].sum()) == 64
    assert not masks["stable"][28, 28] and not masks["gain"][28, 28]


def test_vectorize_water_output_matches_contract_schema(tmp_path: Path) -> None:
    import rasterio
    from rasterio.transform import from_origin
    from shapely.geometry import shape as shp_shape

    arr = np.zeros((30, 30), dtype=np.uint8)
    arr[5:15, 5:15] = 1  # 10x10 pixels at 10m = 10,000 m² = 0.01 km² (>= 0.005 km²)
    mndwi = np.full((30, 30), -0.2, dtype=np.float32)
    mndwi[5:15, 5:15] = 0.45

    transform = from_origin(585000.0, 2335000.0, 10.0, 10.0)
    mask_tif = tmp_path / "water_mask_2020.tif"
    mndwi_tif = tmp_path / "mndwi_2020.tif"
    out_geojson = tmp_path / "water_2020.geojson"

    with rasterio.open(
        mask_tif,
        "w",
        driver="GTiff",
        height=30,
        width=30,
        count=1,
        dtype="uint8",
        crs=CRS_METRIC,
        transform=transform,
        nodata=255,
    ) as dst:
        dst.write(arr, 1)

    with rasterio.open(
        mndwi_tif,
        "w",
        driver="GTiff",
        height=30,
        width=30,
        count=1,
        dtype="float32",
        crs=CRS_METRIC,
        transform=transform,
        nodata=np.nan,
    ) as dst:
        dst.write(mndwi, 1)

    summary = vectorize_water_mask(
        mask_path=mask_tif,
        year=2020,
        out_geojson=out_geojson,
        mndwi_path=mndwi_tif,
        otsu_threshold=0.0955,
    )
    assert summary["polygon_counts"]["total"] == 1
    assert np.isclose(summary["water_area_km2"], 0.01, atol=1e-3)

    fc = json.loads(out_geojson.read_text(encoding="utf-8"))
    water_schema = json.loads((ROOT / "contracts/schemas/water_layer.schema.json").read_text(encoding="utf-8"))
    validate(instance=fc, schema=water_schema)
    geom = shp_shape(fc["features"][0]["geometry"])
    assert geom.is_valid
    # Kiểm tra tọa độ đã chiếu sang EPSG:4326 (kinh độ Hà Nội ~105.8, vĩ độ ~21.1)
    minx, miny, maxx, maxy = geom.bounds
    assert 105.0 < minx < 107.0 and 20.0 < miny < 22.0


def test_interpolate_population_grid() -> None:
    g2015 = np.array([[100.0, 200.0]], dtype=np.float32)
    g2020 = np.array([[150.0, 300.0]], dtype=np.float32)
    g2018 = interpolate_population_grid(g2015, g2020, 2015, 2020, 2018)
    assert np.allclose(g2018, np.array([[130.0, 260.0]], dtype=np.float32))


def test_ghsl_tile_id_for_hanoi() -> None:
    assert compute_ghsl_tile_id(105.855, 21.08) == "R7_C29"


def test_aggregate_100m_to_250m_preserves_total_pop() -> None:
    from rasterio.transform import from_origin

    rng = np.random.default_rng(7)
    pop_100m = rng.uniform(10.0, 80.0, size=(10, 15)).astype(np.float32)
    pop_100m[0, 0] = -1.0  # NoData pixel
    t_100m = from_origin(580000.0, 2340000.0, 100.0, 100.0)

    agg_250m, t_250m = aggregate_100m_to_250m(pop_100m, t_100m)
    expected_sum = float(pop_100m[pop_100m > 0].sum())
    assert agg_250m.shape == (4, 6)
    assert t_250m.a == 250.0 and t_250m.e == -250.0
    assert np.isclose(float(agg_250m.sum()), expected_sum, rtol=1e-5)


def test_spatial_overlay_and_pop_geojson_schema(tmp_path: Path) -> None:
    import geopandas as gpd
    import rasterio
    from rasterio.transform import from_origin

    # Tạo raster dân số 100m kích thước 10x10 (1 km x 1 km), mỗi ô = 20 người -> tổng = 2000 người
    pop_arr = np.full((10, 10), 20.0, dtype=np.float32)
    t_100m = from_origin(585000.0, 2335000.0, 100.0, 100.0)
    pop_tif = tmp_path / "pop_100m_2020.tif"
    with rasterio.open(
        pop_tif,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype="float32",
        crs=CRS_METRIC,
        transform=t_100m,
        nodata=-1.0,
    ) as dst:
        dst.write(pop_arr, 1)

    # Tạo 1 đa giác nước hiện hữu (stable) ở góc trên trái và 1 đa giác loss ở góc dưới phải (phải bị bỏ qua!)
    w_gdf = gpd.GeoDataFrame(
        {
            "water_id": ["w_1", "w_2"],
            "year": [2020, 2020],
            "change_type": ["stable", "loss"],
            "geometry": [
                box(585000.0, 2334900.0, 585100.0, 2335000.0),
                box(585900.0, 2334000.0, 586000.0, 2334100.0),
            ],
        },
        crs=CRS_METRIC,
    ).to_crs(CRS_STORAGE)
    water_geojson = tmp_path / "water_2020.geojson"
    w_gdf.to_file(water_geojson, driver="GeoJSON")

    overlay_res = compute_pop_in_water_buffer(
        water_geojson=water_geojson,
        pop_raster_path=pop_tif,
        buffer_m=300.0,
    )
    assert overlay_res["total_pop"] == 2000
    assert 0 < overlay_res["pop_in_buffer_500m"] < 2000

    out_pop_geojson = tmp_path / "pop_2020.geojson"
    grid_res = export_population_grid_geojson(
        raster_path=pop_tif,
        year=2020,
        out_geojson=out_pop_geojson,
        water_geojson=water_geojson,
    )
    assert grid_res["cell_count"] == 16  # 1000m / 250m = 4x4 = 16 ô
    pop_fc = json.loads(out_pop_geojson.read_text(encoding="utf-8"))
    pop_schema = json.loads((ROOT / "contracts/schemas/pop_layer.schema.json").read_text(encoding="utf-8"))
    validate(instance=pop_fc, schema=pop_schema)


def test_build_timeseries_summary_schema(tmp_path: Path) -> None:
    (tmp_path / "water_change_metrics.json").write_text(
        json.dumps(
            {
                "aoi_area_km2": 241.35,
                "years": [
                    {
                        "year": 2020,
                        "water_area_km2": 24.15,
                        "water_ratio_pct": 10.0,
                        "water_gain_km2": 1.19,
                        "water_loss_km2": 2.61,
                        "otsu_threshold": 0.0955,
                        "cloud_cover_pct": 0.86,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "jrc_validation_summary.json").write_text(
        json.dumps({"years": {"2020": {"jrc_iou_score": 0.7485}}}),
        encoding="utf-8",
    )
    (tmp_path / "pop_overlay_metrics.json").write_text(
        json.dumps(
            {
                "years": {
                    "2020": {
                        "total_pop": 1050000,
                        "pop_in_buffer_500m": 310000,
                        "pop_buffer_ratio_pct": 29.52,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    out_ts = tmp_path / "timeseries_summary.json"
    doc = build_timeseries_summary(processed_dir=tmp_path, out_json=out_ts)
    assert doc["series"][0]["jrc_iou_score"] == 0.7485
    assert out_ts.exists()


def test_processed_outputs_pass_full_audit() -> None:
    import pytest

    processed_dir = ROOT / "data" / "processed"
    if not (processed_dir / "timeseries_summary.json").exists():
        pytest.skip("Real processed outputs not yet generated on this machine.")

    report = audit_processed_outputs(processed_dir=processed_dir)
    assert report["status"] == "PASSED"
    assert report["contract_files_verified"] == 11
    assert report["unique_water_polygons"] > 1000
    assert report["unique_population_cells"] > 10000


def test_mock_contracts_match_schemas() -> None:
    water_schema = json.loads((ROOT / "contracts/schemas/water_layer.schema.json").read_text(encoding="utf-8"))
    water_mock = json.loads((ROOT / "contracts/mock/water_2020.geojson").read_text(encoding="utf-8"))
    validate(instance=water_mock, schema=water_schema)

    pop_schema = json.loads((ROOT / "contracts/schemas/pop_layer.schema.json").read_text(encoding="utf-8"))
    pop_mock = json.loads((ROOT / "contracts/mock/pop_2020.geojson").read_text(encoding="utf-8"))
    validate(instance=pop_mock, schema=pop_schema)

    ts_schema = json.loads((ROOT / "contracts/schemas/timeseries.schema.json").read_text(encoding="utf-8"))
    ts_mock = json.loads((ROOT / "contracts/mock/timeseries_summary.json").read_text(encoding="utf-8"))
    validate(instance=ts_mock, schema=ts_schema)
