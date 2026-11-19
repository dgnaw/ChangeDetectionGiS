"""Router trả về lớp GeoJSON mặt nước và dân cư (Người B hoàn thiện truy vấn PostGIS ở Tuần 3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/layers", tags=["Spatial Layers"])

MOCK_DIR = Path(__file__).resolve().parents[4] / "contracts" / "mock"
VALID_YEARS = {2016, 2018, 2020, 2022, 2024}


@router.get("/water")
def get_water_layer(year: int = Query(2020, description="Năm phân tích (2016, 2018, 2020, 2022, 2024)")) -> dict[str, Any]:
    if year not in VALID_YEARS:
        raise HTTPException(status_code=404, detail=f"Year {year} not available. Choose from {sorted(VALID_YEARS)}.")
    mock_file = MOCK_DIR / f"water_{year}.geojson"
    return json.loads(mock_file.read_text(encoding="utf-8"))


@router.get("/population")
def get_population_layer(
    year: int = Query(2020, description="Năm phân tích (2016, 2018, 2020, 2022, 2024)"),
    only_buffer: bool = Query(False, description="Chỉ lọc các ô dân cư trong vùng đệm 500m quanh mặt nước"),
) -> dict[str, Any]:
    if year not in VALID_YEARS:
        raise HTTPException(status_code=404, detail=f"Year {year} not available. Choose from {sorted(VALID_YEARS)}.")
    mock_file = MOCK_DIR / f"pop_{year}.geojson"
    data = json.loads(mock_file.read_text(encoding="utf-8"))
    if only_buffer:
        data["features"] = [f for f in data["features"] if f["properties"].get("in_water_buffer_500m") is True]
    return data
