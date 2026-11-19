"""Tuần 3: Chuẩn hóa PB 04.00 (-1000 offset từ 2022-01-25), Resample về 10m và lọc mây SCL."""

from __future__ import annotations

from datetime import date, datetime

import numpy as np

from src.config import INVALID_SCL_CLASSES, S2_BOA_ADD_OFFSET, S2_PB0400_CUTOFF_DATE


def _is_pb0400_or_later(year_or_date: int | str | date | datetime) -> bool:
    """Kiểm tra mốc thời gian ảnh có thuộc ESA Processing Baseline 04.00+ (>= 2022-01-25) hay không."""
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
    year_or_date: int | str | date | datetime,
) -> np.ndarray:
    """Áp dụng bù trừ BOA_ADD_OFFSET (-1000) và clip về >= 0 cho ảnh Sentinel-2 từ 25/01/2022 trở đi."""
    arr = dn_array.astype(np.float32, copy=True)
    if _is_pb0400_or_later(year_or_date):
        arr = np.maximum(arr + S2_BOA_ADD_OFFSET, 0.0)
    return arr


def mask_clouds_scl(band_array: np.ndarray, scl_array: np.ndarray) -> np.ndarray:
    """Che (NaN) các pixel thuộc lớp mây, bóng mây, cirrus dựa trên lớp SCL."""
    invalid_mask = np.isin(scl_array, INVALID_SCL_CLASSES)
    return np.where(invalid_mask, np.nan, band_array.astype(np.float32))
