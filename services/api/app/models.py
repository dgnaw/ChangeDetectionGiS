"""Mô hình bảng không gian PostGIS (EPSG:4326 + chỉ mục GIST)."""

from __future__ import annotations

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class WaterPolygon(Base):
    __tablename__ = "water_polygons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    water_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    year: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    area_km2: Mapped[float] = mapped_column(Float, nullable=False)
    perimeter_km: Mapped[float] = mapped_column(Float, nullable=False)
    mean_mndwi: Mapped[float] = mapped_column(Float, nullable=False)
    otsu_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    change_type: Mapped[str] = mapped_column(String(16), nullable=False)
    geom = mapped_column(Geometry(geometry_type="GEOMETRY", srid=4326), nullable=False)

    __table_args__ = (Index("idx_water_polygons_geom", "geom", postgresql_using="gist"),)


class PopulationGrid(Base):
    __tablename__ = "population_grids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grid_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    year: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    pop_count: Mapped[float] = mapped_column(Float, nullable=False)
    density_per_km2: Mapped[float] = mapped_column(Float, nullable=False)
    in_water_buffer_500m: Mapped[bool] = mapped_column(Boolean, index=True, nullable=False)
    dist_to_water_m: Mapped[float] = mapped_column(Float, nullable=False)
    geom = mapped_column(Geometry(geometry_type="POLYGON", srid=4326), nullable=False)

    __table_args__ = (Index("idx_population_grids_geom", "geom", postgresql_using="gist"),)


class TimeseriesMetric(Base):
    __tablename__ = "timeseries_metrics"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
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
