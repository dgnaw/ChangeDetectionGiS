"""Tuần 5: Gộp lưới dân số 100m lên 250m (lọc ô < 5 người) và xuất GeoJSON EPSG:4326."""

from __future__ import annotations

from pathlib import Path

from src.config import (
    CRS_METRIC,
    CRS_STORAGE,
    MIN_POP_PER_CELL,
    POP_GRID_AGG_METERS,
)


def export_population_grid_geojson(raster_path: Path, year: int, out_geojson: Path) -> Path:
    """Chuyển lưới dân số 250m sang GeoJSON khớp contracts/schemas/pop_layer.schema.json."""
    _ = (CRS_STORAGE, CRS_METRIC, POP_GRID_AGG_METERS, MIN_POP_PER_CELL)
    raise NotImplementedError("TODO (Tuần 5): Aggregate 100m -> 250m grid and export GeoJSON.")
