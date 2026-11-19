"""Tuần 5: Cắt raster dân số GHSL (2015, 2020, 2025) theo AOI & nội suy tuyến tính cho 2016..2024."""

from __future__ import annotations

import numpy as np


def interpolate_population_grid(
    grid_start: np.ndarray,
    grid_end: np.ndarray,
    year_start: int,
    year_end: int,
    target_year: int,
) -> np.ndarray:
    """Nội suy tuyến tính theo từng pixel giữa 2 mốc năm GHSL liền kề."""
    if year_end == year_start:
        return grid_start.astype(np.float32)
    weight = (target_year - year_start) / (year_end - year_start)
    return ((1.0 - weight) * grid_start + weight * grid_end).astype(np.float32)
