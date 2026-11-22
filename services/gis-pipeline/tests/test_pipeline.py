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
from src.population.clip_population import interpolate_population_grid
from src.water.fetch_stac import (
    build_datetime_range,
    compute_combined_clear_coverage,
    compute_scl_stats_from_array,
    filter_and_rank_items,
    load_aoi,
)
from src.water.mndwi_otsu import compute_mndwi, threshold_otsu_water
from src.water.preprocess import apply_pb0400_offset, compute_median_composite
from src.water.validate_jrc import compute_iou

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


def test_interpolate_population_grid() -> None:
    g2015 = np.array([[100.0, 200.0]], dtype=np.float32)
    g2020 = np.array([[150.0, 300.0]], dtype=np.float32)
    g2018 = interpolate_population_grid(g2015, g2020, 2015, 2020, 2018)
    assert np.allclose(g2018, np.array([[130.0, 260.0]], dtype=np.float32))


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
