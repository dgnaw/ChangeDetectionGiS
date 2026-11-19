"""Router trả về AOI và thống kê chuỗi thời gian (Người B)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.schemas import TimeseriesResponse

router = APIRouter(prefix="/api/v1", tags=["AOI & Analytics"])

CONTRACTS_DIR = Path(__file__).resolve().parents[4] / "contracts"


@router.get("/aoi")
def get_aoi() -> dict[str, Any]:
    return json.loads((CONTRACTS_DIR / "aoi.geojson").read_text(encoding="utf-8"))


@router.get("/analytics/timeseries", response_model=TimeseriesResponse)
def get_timeseries() -> TimeseriesResponse:
    raw = json.loads((CONTRACTS_DIR / "mock" / "timeseries_summary.json").read_text(encoding="utf-8"))
    return TimeseriesResponse(**raw)
