"""Tuần 3: Tính chỉ số MNDWI = (B03 - B11) / (B03 + B11) và phân ngưỡng động Otsu."""

from __future__ import annotations

import numpy as np


def compute_mndwi(b03_green: np.ndarray, b11_swir: np.ndarray) -> np.ndarray:
    """Tính MNDWI theo Xu (2006), tránh chia cho 0."""
    g = b03_green.astype(np.float32)
    s = b11_swir.astype(np.float32)
    denom = g + s
    return np.where(denom == 0, np.nan, (g - s) / denom)


def threshold_otsu_water(mndwi: np.ndarray) -> tuple[np.ndarray, float]:
    """Áp dụng phân ngưỡng Otsu trên các pixel hợp lệ để tách mặt nước."""
    raise NotImplementedError("TODO (Tuần 3): Implement skimage.filters.threshold_otsu on valid pixels.")
