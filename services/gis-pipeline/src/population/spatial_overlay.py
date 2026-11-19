"""Tuần 5: Tạo vùng đệm Buffer 500m quanh mặt nước trên EPSG:32648 & đếm dân số bằng rasterio.mask."""

from __future__ import annotations

from pathlib import Path

from src.config import BUFFER_RADIUS_METERS, CRS_METRIC


def compute_pop_in_water_buffer(
    water_geojson: Path,
    pop_raster_path: Path,
    buffer_m: float = BUFFER_RADIUS_METERS,
) -> dict[str, float]:
    """Tính tổng dân số toàn AOI và dân số nằm trong hành lang Buffer 500m quanh mặt nước."""
    _ = CRS_METRIC
    raise NotImplementedError("TODO (Tuần 5): Implement EPSG:32648 buffer + rasterio.mask zonal sum.")
