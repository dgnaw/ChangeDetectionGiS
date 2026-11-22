"""Tuần 3: Chuẩn hóa PB 04.00 (-1000 offset), Resample 10m, lọc mây SCL và gộp Median Composite."""

from __future__ import annotations

import json
import warnings
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import Resampling

from src.config import INVALID_SCL_CLASSES, S2_BOA_ADD_OFFSET, S2_PB0400_CUTOFF_DATE
from src.water.mndwi_otsu import compute_mndwi


def _is_pb0400_or_later(
    year_or_date: int | str | date | datetime | None = None,
    processing_baseline: str | float | None = None,
) -> bool:
    """Ưu tiên kiểm tra processing_baseline >= 4.0; nếu thiếu mới xét ngày chụp >= 2022-01-25."""
    if processing_baseline is not None and str(processing_baseline).strip() != "":
        try:
            return float(processing_baseline) >= 4.0
        except ValueError:
            pass

    if year_or_date is None:
        return False

    cutoff = date.fromisoformat(S2_PB0400_CUTOFF_DATE)
    if isinstance(year_or_date, int):
        return year_or_date >= 2022
    if isinstance(year_or_date, datetime):
        return year_or_date.date() >= cutoff
    if isinstance(year_or_date, date):
        return year_or_date >= cutoff
    if isinstance(year_or_date, str):
        parsed = date.fromisoformat(year_or_date[:10])
        return parsed >= cutoff
    raise TypeError(f"Unsupported year_or_date type: {type(year_or_date)!r}")


def apply_pb0400_offset(
    dn_array: np.ndarray,
    year_or_date: int | str | date | datetime | None = None,
    processing_baseline: str | float | None = None,
) -> np.ndarray:
    """Áp dụng bù trừ BOA_ADD_OFFSET (-1000) và clip về >= 0 cho ảnh Sentinel-2 PB 04.00+."""
    arr = dn_array.astype(np.float32, copy=True)
    if _is_pb0400_or_later(year_or_date=year_or_date, processing_baseline=processing_baseline):
        arr = np.maximum(arr + S2_BOA_ADD_OFFSET, 0.0)
    return arr


def mask_clouds_scl(band_array: np.ndarray, scl_array: np.ndarray) -> np.ndarray:
    """Che (NaN) các pixel thuộc lớp mây, bóng mây, cirrus dựa trên lớp SCL."""
    invalid_mask = np.isin(scl_array, INVALID_SCL_CLASSES)
    return np.where(invalid_mask, np.nan, band_array.astype(np.float32))


def load_and_preprocess_scene(
    scene_dir: Path,
    scene_meta: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    """Đọc 1 cảnh Sentinel-2, resample B11/SCL về 10m, bù PB 04.00, lọc mây SCL và tính MNDWI cảnh."""
    with rasterio.open(scene_dir / "B03.tif") as src_b03:
        b03_raw = src_b03.read(1)
        height, width = b03_raw.shape
        ref_profile = src_b03.profile.copy()

    with rasterio.open(scene_dir / "B11.tif") as src_b11:
        b11_raw = src_b11.read(1, out_shape=(height, width), resampling=Resampling.bilinear)

    with rasterio.open(scene_dir / "SCL.tif") as src_scl:
        scl_10m = src_scl.read(1, out_shape=(height, width), resampling=Resampling.nearest)

    valid_aoi = (b03_raw > 0) & (b11_raw > 0)

    dt_str = scene_meta.get("datetime")
    pb_val = scene_meta.get("processing_baseline")

    b03_corr = apply_pb0400_offset(b03_raw, year_or_date=dt_str, processing_baseline=pb_val)
    b11_corr = apply_pb0400_offset(b11_raw, year_or_date=dt_str, processing_baseline=pb_val)

    b03_clean = mask_clouds_scl(b03_corr, scl_10m)
    b11_clean = mask_clouds_scl(b11_corr, scl_10m)

    b03_clean = np.where(valid_aoi, b03_clean, np.nan).astype(np.float32)
    b11_clean = np.where(valid_aoi, b11_clean, np.nan).astype(np.float32)

    mndwi_scene = compute_mndwi(b03_clean, b11_clean)
    return b03_clean, b11_clean, mndwi_scene, ref_profile


def _write_float_geotiff(out_path: Path, array: np.ndarray, ref_profile: dict[str, Any]) -> Path:
    """Lưu mảng float32 (EPSG:32648, 10m) dạng GeoTIFF nén deflate với NoData=NaN."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    profile = ref_profile.copy()
    profile.update(
        {
            "driver": "GTiff",
            "dtype": "float32",
            "count": 1,
            "nodata": np.nan,
            "compress": "deflate",
            "tiled": True,
        }
    )
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(array.astype(np.float32), 1)
    return out_path


def compute_median_composite(arrays: list[np.ndarray]) -> np.ndarray:
    """Tính trung vị theo từng pixel (bỏ qua NaN) từ danh sách mảng đồng kích thước."""
    stack = np.stack(arrays, axis=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        median = np.nanmedian(stack, axis=0)
    return median.astype(np.float32)


def build_year_composite(year_dir: Path, overwrite: bool = False) -> dict[str, Path]:
    """Gộp đa cảnh Sentinel-2 của 1 năm thành MNDWI Median Composite liền mạch (không vết ghép mây)."""
    manifest_path = year_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Không tìm thấy manifest.json tại {year_dir}. Hãy chạy --step fetch trước.")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    year = int(manifest["year"])
    comp_dir = year_dir / "composite"
    comp_dir.mkdir(parents=True, exist_ok=True)

    outputs = {
        "mndwi": comp_dir / f"mndwi_{year}.tif",
        "b03": comp_dir / f"b03_median_{year}.tif",
        "b11": comp_dir / f"b11_median_{year}.tif",
    }

    if not overwrite and all(p.exists() for p in outputs.values()):
        return outputs

    b03_list: list[np.ndarray] = []
    b11_list: list[np.ndarray] = []
    mndwi_list: list[np.ndarray] = []
    ref_profile: dict[str, Any] | None = None

    for scene_meta in manifest["scenes"]:
        scene_dir = year_dir / scene_meta["scene_id"]
        b03_c, b11_c, mndwi_c, profile = load_and_preprocess_scene(scene_dir, scene_meta)
        b03_list.append(b03_c)
        b11_list.append(b11_c)
        mndwi_list.append(mndwi_c)
        if ref_profile is None:
            ref_profile = profile

    if ref_profile is None:
        raise RuntimeError(f"Năm {year} không có cảnh nào trong manifest.json.")

    mndwi_med = compute_median_composite(mndwi_list)
    b03_med = compute_median_composite(b03_list)
    b11_med = compute_median_composite(b11_list)

    _write_float_geotiff(outputs["mndwi"], mndwi_med, ref_profile)
    _write_float_geotiff(outputs["b03"], b03_med, ref_profile)
    _write_float_geotiff(outputs["b11"], b11_med, ref_profile)
    return outputs
