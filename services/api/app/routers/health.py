"""Router kiểm tra trạng thái API + PostGIS (Người B)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import HealthResponse

router = APIRouter(prefix="/api/v1", tags=["Health"])

SERVICE_NAME = "gis-change-detection-api"

COUNT_SQL = text(
    """
    SELECT
      (SELECT count(*) FROM water_polygons)     AS water_polygons,
      (SELECT count(*) FROM population_grids)   AS population_grids,
      (SELECT count(*) FROM timeseries_metrics) AS timeseries_metrics
    """
)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Trạng thái API & cơ sở dữ liệu PostGIS",
    responses={503: {"model": HealthResponse, "description": "Không kết nối được PostGIS."}},
)
def health_check(db: Session = Depends(get_db)) -> HealthResponse | JSONResponse:
    try:
        postgis_version = db.execute(text("SELECT postgis_lib_version()")).scalar()
    except SQLAlchemyError as exc:
        body = HealthResponse(status="error", service=SERVICE_NAME, database="unreachable", detail=str(exc.orig or exc))
        return JSONResponse(status_code=503, content=body.model_dump())

    try:
        records = dict(db.execute(COUNT_SQL).mappings().one())
        database = "ok"
    except SQLAlchemyError:
        db.rollback()
        records, database = None, "schema_missing"  # DB sống nhưng chưa chạy seed.py

    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        database=database,
        postgis_version=postgis_version,
        records=records,
    )
