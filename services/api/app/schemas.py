"""Pydantic v2 schemas khớp contracts/schemas/."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "error"]
    service: str
    database: Literal["connected", "schema_missing", "unreachable"]
    postgis_version: str | None = None
    records: dict[str, int] | None = None
    detail: str | None = None


class TimeseriesPoint(BaseModel):
    year: int
    water_area_km2: float
    water_ratio_pct: float
    water_gain_km2: float
    water_loss_km2: float
    otsu_threshold: float
    cloud_cover_pct: float
    total_pop: int
    pop_in_buffer_500m: int
    pop_buffer_ratio_pct: float
    jrc_iou_score: float | None = None


class TimeseriesResponse(BaseModel):
    aoi_name: str
    aoi_area_km2: float
    crs_storage: Literal["EPSG:4326"] = "EPSG:4326"
    crs_metric: Literal["EPSG:32648"] = "EPSG:32648"
    years: list[int]
    series: list[TimeseriesPoint]
