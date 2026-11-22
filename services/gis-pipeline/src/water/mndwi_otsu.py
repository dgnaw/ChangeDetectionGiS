"""Tuần 3: Tính chỉ số MNDWI = (B03 - B11) / (B03 + B11) và phân ngưỡng động Otsu có kẹp biên vật lý."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from skimage.filters import threshold_otsu

from src.config import (
    CRS_METRIC,
    OTSU_CLAMP_MAX,
    OTSU_CLAMP_MIN,
    OTSU_WINDOW_MAX,
    OTSU_WINDOW_MIN,
    WATER_MASK_NODATA,
)


def compute_mndwi(b03_green: np.ndarray, b11_swir: np.ndarray) -> np.ndarray:
    """Tính MNDWI theo Xu (2006), tránh chia cho 0 và bảo toàn NaN."""
    g = b03_green.astype(np.float32)
    s = b11_swir.astype(np.float32)
    denom = g + s
    with np.errstate(divide="ignore", invalid="ignore"):
        mndwi = np.where((denom > 0) & np.isfinite(denom), (g - s) / denom, np.nan)
    return mndwi.astype(np.float32)


def threshold_otsu_water(
    mndwi: np.ndarray,
    window_min: float = OTSU_WINDOW_MIN,
    window_max: float = OTSU_WINDOW_MAX,
    clamp_min: float = OTSU_CLAMP_MIN,
    clamp_max: float = OTSU_CLAMP_MAX,
) -> tuple[np.ndarray, float, float]:
    """Áp dụng Otsu trên cửa sổ giao thoa Nước–Đất [-0.30, +0.60] và kẹp ngưỡng trong [0.00, 0.15].

    Returns:
        (water_mask_uint8, clamped_threshold, raw_otsu_threshold)
        Trong đó water_mask_uint8: 1 = Nước, 0 = Đất, 255 = NoData (NaN).
    """
    finite_mask = np.isfinite(mndwi)
    if not np.any(finite_mask):
        raise ValueError("Mảng MNDWI không có pixel hợp lệ nào để phân ngưỡng Otsu.")

    window_pixels = mndwi[finite_mask & (mndwi >= window_min) & (mndwi <= window_max)]
    if window_pixels.size < 100:
        window_pixels = mndwi[finite_mask]

    raw_otsu = float(threshold_otsu(window_pixels))
    clamped_otsu = float(np.clip(raw_otsu, clamp_min, clamp_max))

    water_mask = np.full(mndwi.shape, WATER_MASK_NODATA, dtype=np.uint8)
    water_mask[finite_mask] = (mndwi[finite_mask] >= clamped_otsu).astype(np.uint8)
    return water_mask, round(clamped_otsu, 4), round(raw_otsu, 4)


def run_mndwi_otsu_for_year(year_dir: Path) -> dict[str, Any]:
    """Đọc composite/mndwi_{year}.tif, tách mặt nước bằng Otsu và xuất water_mask + mndwi_stats JSON."""
    manifest = json.loads((year_dir / "manifest.json").read_text(encoding="utf-8"))
    year = int(manifest["year"])
    comp_dir = year_dir / "composite"
    mndwi_tif = comp_dir / f"mndwi_{year}.tif"

    with rasterio.open(mndwi_tif) as src:
        mndwi = src.read(1)
        profile = src.profile.copy()
        res_x, res_y = src.res
        crs_str = src.crs.to_string() if src.crs else CRS_METRIC

    water_mask, otsu_thresh, raw_otsu = threshold_otsu_water(mndwi)

    mask_tif = comp_dir / f"water_mask_{year}.tif"
    mask_profile = profile.copy()
    mask_profile.update(
        {
            "driver": "GTiff",
            "dtype": "uint8",
            "count": 1,
            "nodata": WATER_MASK_NODATA,
            "compress": "deflate",
            "tiled": True,
        }
    )
    with rasterio.open(mask_tif, "w", **mask_profile) as dst:
        dst.write(water_mask, 1)

    valid_mask = water_mask != WATER_MASK_NODATA
    is_water = water_mask == 1
    valid_count = int(valid_mask.sum())
    water_count = int(is_water.sum())
    pixel_area_km2 = float(abs(res_x * res_y)) / 1_000_000.0

    stats = {
        "year": year,
        "crs": crs_str,
        "resolution_m": round(float(res_x), 2),
        "shape": [int(mndwi.shape[0]), int(mndwi.shape[1])],
        "valid_pixel_count": valid_count,
        "valid_coverage_pct": float(manifest.get("combined_clear_coverage_pct", 0.0)),
        "mean_aoi_cloud_cover_pct": float(manifest.get("mean_aoi_cloud_cover_pct", 0.0)),
        "raw_otsu_threshold": raw_otsu,
        "otsu_threshold": otsu_thresh,
        "water_pixel_count": water_count,
        "raw_water_area_km2": round(water_count * pixel_area_km2, 3),
        "mean_water_mndwi": round(float(np.nanmean(mndwi[is_water])), 4) if water_count > 0 else 0.0,
        "median_water_mndwi": round(float(np.nanmedian(mndwi[is_water])), 4) if water_count > 0 else 0.0,
    }

    stats_path = comp_dir / f"mndwi_stats_{year}.json"
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats
