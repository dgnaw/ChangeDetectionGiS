"""Mô hình bảng không gian PostGIS (EPSG:4326 + chỉ mục GIST).

Luật CLAUDE.md §5.2-5: cột hình học dùng `Geometry(geometry_type="GEOMETRY", srid=4326)`
để nhận cả Polygon lẫn MultiPolygon (đảo nổi Hồ Tây, bãi giữa Sông Hồng...).

Khóa tự nhiên (year, water_id) / (year, grid_id) có UNIQUE constraint để seed.py
chạy lại nhiều lần bằng `INSERT ... ON CONFLICT DO UPDATE` mà không sinh bản ghi trùng.
"""

from __future__ import annotations

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, CheckConstraint, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _geom_4326() -> Geometry:
    # spatial_index=False: tự khai báo GIST index tường minh trong __table_args__ (tránh tạo trùng).
    return Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False)


class WaterPolygon(Base):
    """Đa giác mặt nước theo năm (`water_{year}.geojson`)."""

    __tablename__ = "water_polygons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    water_id: Mapped[str] = mapped_column(String(64), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    area_km2: Mapped[float] = mapped_column(Float, nullable=False)
    perimeter_km: Mapped[float] = mapped_column(Float, nullable=False)
    mean_mndwi: Mapped[float] = mapped_column(Float, nullable=False)
    otsu_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    change_type: Mapped[str] = mapped_column(String(16), nullable=False)
    geom = mapped_column(_geom_4326(), nullable=False)

    __table_args__ = (
        UniqueConstraint("year", "water_id", name="uq_water_polygons_year_water_id"),
        CheckConstraint("change_type IN ('stable', 'gain', 'loss')", name="ck_water_polygons_change_type"),
        Index("idx_water_polygons_year", "year"),
        Index("idx_water_polygons_geom", "geom", postgresql_using="gist"),
    )


class PopulationGrid(Base):
    """Ô lưới dân cư 250m theo năm (`pop_{year}.geojson`)."""

    __tablename__ = "population_grids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grid_id: Mapped[str] = mapped_column(String(64), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    pop_count: Mapped[float] = mapped_column(Float, nullable=False)
    density_per_km2: Mapped[float] = mapped_column(Float, nullable=False)
    in_water_buffer_500m: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dist_to_water_m: Mapped[float] = mapped_column(Float, nullable=False)
    geom = mapped_column(_geom_4326(), nullable=False)

    __table_args__ = (
        UniqueConstraint("year", "grid_id", name="uq_population_grids_year_grid_id"),
        # Phục vụ truy vấn `WHERE year = ? [AND in_water_buffer_500m]`
        Index("idx_population_grids_year_buffer", "year", "in_water_buffer_500m"),
        Index("idx_population_grids_geom", "geom", postgresql_using="gist"),
    )


class TimeseriesMetric(Base):
    """Một dòng thống kê / năm (`timeseries_summary.json` → series[])."""

    __tablename__ = "timeseries_metrics"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Metadata AOI cấp file (lặp lại mỗi dòng để endpoint dựng lại đúng contract)
    aoi_name: Mapped[str] = mapped_column(String(255), nullable=False)
    aoi_area_km2: Mapped[float] = mapped_column(Float, nullable=False)
    water_area_km2: Mapped[float] = mapped_column(Float, nullable=False)
    water_ratio_pct: Mapped[float] = mapped_column(Float, nullable=False)
    water_gain_km2: Mapped[float] = mapped_column(Float, nullable=False)
    water_loss_km2: Mapped[float] = mapped_column(Float, nullable=False)
    otsu_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    cloud_cover_pct: Mapped[float] = mapped_column(Float, nullable=False)
    total_pop: Mapped[int] = mapped_column(Integer, nullable=False)
    pop_in_buffer_500m: Mapped[int] = mapped_column(Integer, nullable=False)
    pop_buffer_ratio_pct: Mapped[float] = mapped_column(Float, nullable=False)
    jrc_iou_score: Mapped[float | None] = mapped_column(Float, nullable=True)
