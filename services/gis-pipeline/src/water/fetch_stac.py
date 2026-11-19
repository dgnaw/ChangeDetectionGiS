"""Tuần 2: Truy vấn Planetary Computer STAC API & cắt ảnh Sentinel-2 L2A trên lưới gốc EPSG:32648."""

from __future__ import annotations

from pathlib import Path

from src.config import DRY_SEASON_WINDOW, MAX_CLOUD_COVER_PCT


def fetch_sentinel2_for_year(
    aoi_path: Path,
    year: int,
    out_dir: Path,
    max_cloud_pct: float = MAX_CLOUD_COVER_PCT,
    season_window: tuple[str, str] = DRY_SEASON_WINDOW,
) -> Path:
    """Tìm cảnh Sentinel-2 L2A mùa khô (eo:cloud_cover < max_cloud_pct) và cắt B03, B11, SCL trên EPSG:32648."""
    raise NotImplementedError("TODO (Tuần 2): Implement Planetary Computer STAC windowed read on native EPSG:32648.")
