"""Tuần 4: Đối chứng độ khớp (IoU) giữa mặt nước MNDWI và JRC Global Surface Water."""

from __future__ import annotations

import numpy as np


def compute_iou(pred_mask: np.ndarray, ref_mask: np.ndarray) -> float:
    """Tính chỉ số Intersection over Union (IoU) giữa 2 mảng nhị phân."""
    pred = pred_mask.astype(bool)
    ref = ref_mask.astype(bool)
    union = np.logical_or(pred, ref).sum()
    if union == 0:
        return 0.0
    intersection = np.logical_and(pred, ref).sum()
    return float(intersection / union)
