"""Router trả về lớp GeoJSON mặt nước và dân cư, truy vấn trực tiếp PostGIS (Người B)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PopulationGrid, WaterPolygon
from app.routers._common import YEAR_DESCRIPTION, YEAR_ERROR_RESPONSES, feature_collection_query, validate_year

router = APIRouter(prefix="/api/v1/layers", tags=["Spatial Layers"])

GEOJSON_EXAMPLE = {"application/json": {"example": {"type": "FeatureCollection", "features": []}}}


def _not_seeded(layer: str, year: int) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=f"Chưa có dữ liệu lớp '{layer}' năm {year} trong PostGIS. Hãy chạy `python scripts/seed.py`.",
    )


@router.get(
    "/water",
    summary="Lớp đa giác mặt nước (GeoJSON FeatureCollection, EPSG:4326)",
    responses={200: {"content": GEOJSON_EXAMPLE}, **YEAR_ERROR_RESPONSES},
)
def get_water_layer(
    year: int = Query(2020, description=YEAR_DESCRIPTION),
    db: Session = Depends(get_db),
) -> Response:
    validate_year(year)
    m = WaterPolygon
    stmt = feature_collection_query(
        m,
        m.water_id,
        [m.water_id, m.year, m.area_km2, m.perimeter_km, m.mean_mndwi, m.otsu_threshold, m.change_type],
        m.year == year,
    )
    geojson, n = db.execute(stmt).one()
    if n == 0:
        raise _not_seeded("water", year)
    return Response(content=geojson, media_type="application/json")


@router.get(
    "/population",
    summary="Lớp lưới dân cư 250m (GeoJSON FeatureCollection, EPSG:4326)",
    responses={200: {"content": GEOJSON_EXAMPLE}, **YEAR_ERROR_RESPONSES},
)
def get_population_layer(
    year: int = Query(2020, description=YEAR_DESCRIPTION),
    only_buffer: bool = Query(False, description="Chỉ trả các ô dân cư nằm trong vùng đệm 500m quanh mặt nước"),
    db: Session = Depends(get_db),
) -> Response:
    validate_year(year)
    m = PopulationGrid
    where = [m.year == year]
    if only_buffer:
        where.append(m.in_water_buffer_500m.is_(True))
    stmt = feature_collection_query(
        m,
        m.grid_id,
        [m.grid_id, m.year, m.pop_count, m.density_per_km2, m.in_water_buffer_500m, m.dist_to_water_m],
        *where,
    )
    geojson, n = db.execute(stmt).one()
    # only_buffer=true có thể hợp lệ mà rỗng → chỉ báo 404 khi cả năm chưa được seed
    if n == 0 and not db.execute(select(exists().where(m.year == year))).scalar():
        raise _not_seeded("population", year)
    return Response(content=geojson, media_type="application/json")
