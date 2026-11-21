"""Tiện ích dùng chung cho routers: kiểm tra năm & dựng FeatureCollection ngay trong PostGIS."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import JSON, Select, Text, cast, func, literal_column, select
from sqlalchemy.dialects.postgresql import aggregate_order_by

from app.config import SCHEMA_YEAR_MAX, SCHEMA_YEAR_MIN, VALID_YEARS

YEAR_DESCRIPTION = f"Năm phân tích, một trong {list(VALID_YEARS)}"
GEOJSON_MAX_DECIMALS = 6  # ~0.1 m tại Hà Nội — đủ cho hiển thị, giảm ~30% dung lượng payload

YEAR_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"description": f"Năm ngoài miền hợp lệ của schema ({SCHEMA_YEAR_MIN}–{SCHEMA_YEAR_MAX}), ví dụ `year=1999`."},
    404: {"description": f"Năm hợp lệ nhưng không phải mốc phân tích {list(VALID_YEARS)} hoặc chưa được seed vào DB."},
}


def validate_year(year: int) -> int:
    """400 nếu năm sai miền schema (vd 1999), 404 nếu không phải mốc phân tích (vd 2019)."""
    if not SCHEMA_YEAR_MIN <= year <= SCHEMA_YEAR_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"Năm {year} không hợp lệ: phải nằm trong {SCHEMA_YEAR_MIN}–{SCHEMA_YEAR_MAX} "
            f"và thuộc các mốc {list(VALID_YEARS)}.",
        )
    if year not in VALID_YEARS:
        raise HTTPException(
            status_code=404,
            detail=f"Không có dữ liệu năm {year}. Các mốc khả dụng: {list(VALID_YEARS)}.",
        )
    return year


def feature_collection_query(model: Any, id_col: Any, prop_cols: list[Any], *where: Any) -> Select:
    """SELECT trả về (FeatureCollection dạng text JSON, số feature) — toàn bộ serialize trong PostgreSQL.

    Dùng `ST_AsGeoJSON(geom)` + `json_build_object` + `json_agg` nên Python chỉ nhận 1 chuỗi JSON,
    không phải giải mã WKB hay lặp từng feature → độ trễ thấp (< 50 ms với dữ liệu mock/thật).
    """
    props: list[Any] = []
    for col in prop_cols:
        props.extend([literal_column(f"'{col.key}'"), col])

    feature = func.json_build_object(
        literal_column("'type'"), literal_column("'Feature'"),
        literal_column("'id'"), id_col,
        literal_column("'geometry'"), cast(func.ST_AsGeoJSON(model.geom, GEOJSON_MAX_DECIMALS), JSON),
        literal_column("'properties'"), func.json_build_object(*props),
    )
    features = func.coalesce(func.json_agg(aggregate_order_by(feature, id_col)), literal_column("'[]'::json"))
    collection = func.json_build_object(
        literal_column("'type'"), literal_column("'FeatureCollection'"),
        literal_column("'features'"), features,
    )
    return select(cast(collection, Text).label("geojson"), func.count().label("n")).select_from(model).where(*where)
