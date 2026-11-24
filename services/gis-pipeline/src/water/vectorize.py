"""Tuần 4: Khử nhiễu 3x3, phân loại biến động (stable/gain/loss), Polygonize trên EPSG:32648, chiếu 1 lần sang EPSG:4326 + simplify + make_valid."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import rasterio
from jsonschema import validate
from rasterio.features import rasterize, shapes
from scipy import ndimage
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, mapping, shape
from shapely.ops import unary_union

from src.config import (
    CRS_METRIC,
    CRS_STORAGE,
    MIN_WATER_AREA_KM2,
    REPO_ROOT,
    SIMPLIFY_TOLERANCE_DEG,
    WATER_MASK_NODATA,
)
from src.water.fetch_stac import load_aoi

WATER_SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "water_layer.schema.json"
MORPH_KERNEL_3X3 = np.ones((3, 3), dtype=bool)


def clean_binary_water_mask(binary_mask: np.ndarray, min_pixels: int = 50) -> np.ndarray:
    """Khử nhiễu hình thái học 3x3 (opening + closing) và loại bỏ cụm liên thông < min_pixels."""
    opened = ndimage.binary_opening(binary_mask.astype(bool), structure=MORPH_KERNEL_3X3)
    closed = ndimage.binary_closing(opened, structure=MORPH_KERNEL_3X3)
    labeled, num_features = ndimage.label(closed)
    if num_features == 0:
        return np.zeros_like(closed, dtype=bool)

    counts = np.bincount(labeled.ravel())
    keep = counts >= min_pixels
    keep[0] = False
    return keep[labeled]


def classify_water_change_masks(
    curr_mask_uint8: np.ndarray,
    base_mask_uint8: np.ndarray | None = None,
    min_pixels: int = 50,
) -> dict[str, np.ndarray]:
    """Tách 3 mặt nạ nhị phân stable, gain, loss trên cùng lưới EPSG:32648 không sinh rác viền bờ."""
    clean_curr = clean_binary_water_mask(curr_mask_uint8 == 1, min_pixels=min_pixels)
    if base_mask_uint8 is None:
        empty = np.zeros_like(clean_curr, dtype=bool)
        return {"stable": clean_curr, "gain": empty, "loss": empty}

    clean_base = clean_binary_water_mask(base_mask_uint8 == 1, min_pixels=min_pixels)
    valid_both = (curr_mask_uint8 != WATER_MASK_NODATA) & (base_mask_uint8 != WATER_MASK_NODATA)

    # Vùng mở rộng thật (gain): khử viền co giãn 1-2px bằng binary_opening(3x3) & lọc cụm >= min_pixels
    raw_gain = clean_curr & (~clean_base) & valid_both
    opened_gain = ndimage.binary_opening(raw_gain, structure=MORPH_KERNEL_3X3)
    labeled_gain, n_gain = ndimage.label(opened_gain)
    if n_gain > 0:
        gain_counts = np.bincount(labeled_gain.ravel())
        keep_gain = gain_counts >= min_pixels
        keep_gain[0] = False
        sig_gain = keep_gain[labeled_gain] & clean_curr
    else:
        sig_gain = np.zeros_like(clean_curr, dtype=bool)

    # Phần mặt nước hiện hữu còn lại của năm Y là stable -> hợp (stable | gain) bảo toàn mặt nước năm Y
    stable = clean_curr & (~sig_gain)

    # Vùng thu hẹp/san lấp thật (loss): nước năm gốc 2016 nay đã thành đất ở năm Y
    raw_loss = clean_base & (~clean_curr) & valid_both
    opened_loss = ndimage.binary_opening(raw_loss, structure=MORPH_KERNEL_3X3)
    labeled_loss, n_loss = ndimage.label(opened_loss)
    if n_loss > 0:
        loss_counts = np.bincount(labeled_loss.ravel())
        keep_loss = loss_counts >= min_pixels
        keep_loss[0] = False
        sig_loss = keep_loss[labeled_loss]
    else:
        sig_loss = np.zeros_like(clean_curr, dtype=bool)

    return {"stable": stable, "gain": sig_gain, "loss": sig_loss}


def _extract_polygonal(geom: Any) -> Polygon | MultiPolygon | None:
    """Đảm bảo hình học sau simplify + make_valid chỉ thuộc kiểu Polygon hoặc MultiPolygon hợp lệ."""
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    if isinstance(geom, GeometryCollection):
        polys = [g for g in geom.geoms if isinstance(g, (Polygon, MultiPolygon)) and not g.is_empty]
        if not polys:
            return None
        merged = unary_union(polys)
        return merged if isinstance(merged, (Polygon, MultiPolygon)) and not merged.is_empty else None
    return None


def _round_coords(coords: Any, precision: int = 6) -> Any:
    """Làm tròn tọa độ EPSG:4326 về 6 chữ số thập phân (~0.11m) để giảm dung lượng GeoJSON."""
    if isinstance(coords[0], (int, float)):
        return [round(float(coords[0]), precision), round(float(coords[1]), precision)]
    return [_round_coords(c, precision=precision) for c in coords]


def _compute_zonal_mean_mndwi(
    geoms_32648: list[Any],
    mndwi_arr: np.ndarray | None,
    transform: Any,
) -> list[float]:
    """Tính nhanh giá trị trung bình MNDWI bên trong từng đa giác bằng 1 lượt rasterize + bincount."""
    if mndwi_arr is None or not geoms_32648:
        return [0.0 for _ in geoms_32648]

    zone_ids = rasterize(
        [(geom, idx) for idx, geom in enumerate(geoms_32648, start=1)],
        out_shape=mndwi_arr.shape,
        transform=transform,
        fill=0,
        dtype="int32",
    )
    valid = np.isfinite(mndwi_arr) & (zone_ids > 0)
    if not np.any(valid):
        return [0.0 for _ in geoms_32648]

    z_idx = zone_ids[valid]
    m_vals = mndwi_arr[valid].astype(np.float64)
    sums = np.bincount(z_idx, weights=m_vals, minlength=len(geoms_32648) + 1)
    counts = np.bincount(z_idx, minlength=len(geoms_32648) + 1)

    means: list[float] = []
    for idx in range(1, len(geoms_32648) + 1):
        if counts[idx] > 0:
            val = float(np.clip(sums[idx] / counts[idx], -1.0, 1.0))
            means.append(round(val, 4))
        else:
            means.append(0.0)
    return means


def vectorize_water_mask(
    mask_path: Path,
    year: int,
    out_geojson: Path,
    mndwi_path: Path | None = None,
    otsu_threshold: float = 0.0,
    baseline_mask_path: Path | None = None,
    min_area_km2: float = MIN_WATER_AREA_KM2,
    simplify_tol_deg: float = SIMPLIFY_TOLERANCE_DEG,
    schema_path: Path = WATER_SCHEMA_PATH,
) -> dict[str, Any]:
    """Chuyển raster nhị phân mặt nước (EPSG:32648) -> GeoJSON EPSG:4326 chuẩn water_layer.schema.json."""
    with rasterio.open(mask_path) as src:
        curr_mask = src.read(1)
        transform = src.transform
        src_crs = src.crs.to_string() if src.crs else CRS_METRIC
        pixel_area_m2 = abs(float(src.res[0] * src.res[1]))

    if src_crs != CRS_METRIC:
        raise ValueError(f"Expected native {CRS_METRIC} water mask, got {src_crs}.")

    base_mask: np.ndarray | None = None
    if baseline_mask_path is not None and baseline_mask_path.exists():
        if baseline_mask_path.resolve() != mask_path.resolve():
            with rasterio.open(baseline_mask_path) as base_src:
                base_mask = base_src.read(1)

    mndwi_arr: np.ndarray | None = None
    if mndwi_path is not None and mndwi_path.exists():
        with rasterio.open(mndwi_path) as m_src:
            mndwi_arr = m_src.read(1)

    min_pixels = max(1, int(round((min_area_km2 * 1_000_000.0) / pixel_area_m2)))
    change_masks = classify_water_change_masks(
        curr_mask_uint8=curr_mask,
        base_mask_uint8=base_mask,
        min_pixels=min_pixels,
    )

    raw_records: list[dict[str, Any]] = []
    for change_type in ("stable", "gain", "loss"):
        bmask = change_masks[change_type]
        if not np.any(bmask):
            continue
        for geom_dict, val in shapes(bmask.astype(np.uint8), mask=bmask, connectivity=4, transform=transform):
            if val != 1:
                continue
            geom_m = shape(geom_dict)
            area_km2 = float(geom_m.area) / 1_000_000.0
            if area_km2 < min_area_km2:
                continue
            perimeter_km = float(geom_m.length) / 1_000.0
            raw_records.append(
                {
                    "change_type": change_type,
                    "area_km2": round(area_km2, 4),
                    "perimeter_km": round(perimeter_km, 3),
                    "geometry": geom_m,
                }
            )

    # Sắp xếp giảm dần theo diện tích để water_id đánh số từ các thủy vực lớn nhất (Sông Hồng, Hồ Tây...)
    raw_records.sort(key=lambda r: (r["change_type"] != "stable", -r["area_km2"]))

    features: list[dict[str, Any]] = []
    if raw_records:
        gdf_32648 = gpd.GeoDataFrame(raw_records, crs=CRS_METRIC)
        mean_mndwis = _compute_zonal_mean_mndwi(
            list(gdf_32648.geometry),
            mndwi_arr=mndwi_arr,
            transform=transform,
        )
        gdf_32648["mean_mndwi"] = mean_mndwis

        # Chiếu đúng 1 lần sang EPSG:4326 -> simplify -> make_valid
        gdf_4326 = gdf_32648.to_crs(CRS_STORAGE)
        simplified = gdf_4326.geometry.simplify(simplify_tol_deg, preserve_topology=True).make_valid()

        seq = 1
        for idx, row in gdf_4326.iterrows():
            clean_geom = _extract_polygonal(simplified.loc[idx])
            if clean_geom is None:
                continue
            geom_json = mapping(clean_geom)
            geom_json = {
                "type": geom_json["type"],
                "coordinates": _round_coords(geom_json["coordinates"], precision=6),
            }
            features.append(
                {
                    "type": "Feature",
                    "geometry": geom_json,
                    "properties": {
                        "water_id": f"w_{year}_{seq:04d}",
                        "year": int(year),
                        "area_km2": float(row["area_km2"]),
                        "perimeter_km": float(row["perimeter_km"]),
                        "mean_mndwi": float(row["mean_mndwi"]),
                        "otsu_threshold": round(float(otsu_threshold), 4),
                        "change_type": str(row["change_type"]),
                    },
                }
            )
            seq += 1

    fc = {"type": "FeatureCollection", "features": features}

    if schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validate(instance=fc, schema=schema)

    out_geojson.parent.mkdir(parents=True, exist_ok=True)
    out_geojson.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    stable_km2 = sum(f["properties"]["area_km2"] for f in features if f["properties"]["change_type"] == "stable")
    gain_km2 = sum(f["properties"]["area_km2"] for f in features if f["properties"]["change_type"] == "gain")
    loss_km2 = sum(f["properties"]["area_km2"] for f in features if f["properties"]["change_type"] == "loss")
    counts_by_type = {
        t: sum(1 for f in features if f["properties"]["change_type"] == t)
        for t in ("stable", "gain", "loss")
    }

    return {
        "year": int(year),
        "out_geojson": str(out_geojson),
        "water_area_km2": round(stable_km2 + gain_km2, 3),
        "water_stable_km2": round(stable_km2, 3),
        "water_gain_km2": round(gain_km2, 3),
        "water_loss_km2": round(loss_km2, 3),
        "otsu_threshold": round(float(otsu_threshold), 4),
        "polygon_counts": {**counts_by_type, "total": len(features)},
    }


def run_vectorize_all_years(
    raw_dir: Path,
    out_dir: Path,
    aoi_path: Path,
    years: list[int],
    baseline_year: int = 2016,
) -> dict[str, Any]:
    """Vector hóa mặt nước toàn bộ các năm (so với năm gốc 2016) và lưu water_change_metrics.json."""
    _, aoi_32648 = load_aoi(aoi_path)
    aoi_area_km2 = round(float(aoi_32648.geometry.area.sum()) / 1_000_000.0, 3)

    base_mask_tif = raw_dir / "sentinel2" / str(baseline_year) / "composite" / f"water_mask_{baseline_year}.tif"
    if not base_mask_tif.exists() and years:
        fallback_base = years[0]
        base_mask_tif = raw_dir / "sentinel2" / str(fallback_base) / "composite" / f"water_mask_{fallback_base}.tif"

    year_summaries: list[dict[str, Any]] = []
    for yr in years:
        comp_dir = raw_dir / "sentinel2" / str(yr) / "composite"
        mask_tif = comp_dir / f"water_mask_{yr}.tif"
        mndwi_tif = comp_dir / f"mndwi_{yr}.tif"
        stats_json = comp_dir / f"mndwi_stats_{yr}.json"

        if not mask_tif.exists():
            raise FileNotFoundError(f"Thiếu {mask_tif}. Hãy chạy --step preprocess cho năm {yr} trước.")

        stats = json.loads(stats_json.read_text(encoding="utf-8")) if stats_json.exists() else {}
        otsu_t = float(stats.get("otsu_threshold", 0.0))
        cloud_pct = float(stats.get("mean_aoi_cloud_cover_pct", 0.0))

        out_geojson = out_dir / f"water_{yr}.geojson"
        res = vectorize_water_mask(
            mask_path=mask_tif,
            year=yr,
            out_geojson=out_geojson,
            mndwi_path=mndwi_tif,
            otsu_threshold=otsu_t,
            baseline_mask_path=None if yr == baseline_year else base_mask_tif,
        )
        res["water_ratio_pct"] = round(res["water_area_km2"] / aoi_area_km2 * 100.0, 2) if aoi_area_km2 > 0 else 0.0
        res["cloud_cover_pct"] = round(cloud_pct, 2)
        year_summaries.append(res)

        pc = res["polygon_counts"]
        size_kb = out_geojson.stat().st_size / 1024.0
        print(
            f"[vectorize] {yr} | active_water={res['water_area_km2']:.2f} km² ({res['water_ratio_pct']:.2f}%) | "
            f"gain={res['water_gain_km2']:.2f} km² | loss={res['water_loss_km2']:.2f} km² | "
            f"polys={pc['total']} (S:{pc['stable']}, G:{pc['gain']}, L:{pc['loss']}) | {size_kb:.1f} KB"
        )

    metrics_doc = {
        "aoi_area_km2": aoi_area_km2,
        "baseline_year": baseline_year,
        "crs_storage": CRS_STORAGE,
        "crs_metric": CRS_METRIC,
        "years": year_summaries,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "water_change_metrics.json").write_text(
        json.dumps(metrics_doc, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metrics_doc
