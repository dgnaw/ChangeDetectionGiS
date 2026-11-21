"""Router trả về AOI và thống kê chuỗi thời gian (Người B)."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import AOI_PATH
from app.db import get_db
from app.models import TimeseriesMetric
from app.schemas import TimeseriesPoint, TimeseriesResponse

router = APIRouter(prefix="/api/v1", tags=["AOI & Analytics"])


@lru_cache(maxsize=1)
def _load_aoi() -> dict[str, Any]:
    return json.loads(AOI_PATH.read_text(encoding="utf-8"))


@router.get("/aoi", summary="Ranh giới khu vực nghiên cứu (contracts/aoi.geojson, EPSG:4326)")
def get_aoi() -> dict[str, Any]:
    if not AOI_PATH.is_file():
        raise HTTPException(status_code=404, detail=f"Không tìm thấy AOI tại {AOI_PATH}")
    return _load_aoi()


@router.get(
    "/analytics/timeseries",
    response_model=TimeseriesResponse,
    summary="Chuỗi thời gian 2016–2024 (diện tích mặt nước, dân số vùng đệm 500m...)",
    responses={404: {"description": "Bảng timeseries_metrics chưa được seed."}},
)
def get_timeseries(db: Session = Depends(get_db)) -> TimeseriesResponse:
    rows = db.execute(select(TimeseriesMetric).order_by(TimeseriesMetric.year)).scalars().all()
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Chưa có dữ liệu chuỗi thời gian trong PostGIS. Hãy chạy `python scripts/seed.py`.",
        )
    fields = TimeseriesPoint.model_fields.keys()
    return TimeseriesResponse(
        aoi_name=rows[0].aoi_name,
        aoi_area_km2=rows[0].aoi_area_km2,
        years=[r.year for r in rows],
        series=[TimeseriesPoint(**{f: getattr(r, f) for f in fields}) for r in rows],
    )
