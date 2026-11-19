"""Tuần 4: Khử nhiễu, Polygonize & lọc diện tích trên EPSG:32648 gốc, rồi simplify & chiếu 1 lần sang EPSG:4326."""

from __future__ import annotations

from pathlib import Path

from src.config import (
    CRS_METRIC,
    CRS_STORAGE,
    MIN_WATER_AREA_KM2,
    SIMPLIFY_TOLERANCE_DEG,
)


def vectorize_water_mask(mask_path: Path, year: int, out_geojson: Path) -> Path:
    """Chuyển raster nhị phân mặt nước (EPSG:32648) -> GeoJSON EPSG:4326 chuẩn water_layer.schema.json."""
    _ = (CRS_METRIC, CRS_STORAGE, MIN_WATER_AREA_KM2, SIMPLIFY_TOLERANCE_DEG)
    raise NotImplementedError(
        "TODO (Tuần 4): Clean 3x3, polygonize & filter <0.005 km² on native EPSG:32648, then to_crs(EPSG:4326) + simplify + make_valid."
    )
