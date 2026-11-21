"""Nạp GeoJSON/JSON vào PostGIS (Người B).

- Tuần 2–6: nguồn `contracts/mock/` (mặc định).
- Tuần 7:   `python scripts/seed.py --source ../../data/processed` (chạy trong services/api/)
            hoặc trong Docker: `docker compose exec api python scripts/seed.py --source /data/processed`.

Idempotent — chạy lại bao nhiêu lần cũng không trùng bản ghi:
  * Mỗi năm có trong nguồn được nạp trong 1 transaction:
    xóa các bản ghi cũ của năm đó không còn trong file → `INSERT ... ON CONFLICT (year, id) DO UPDATE`.
  * Năm không có trong nguồn được giữ nguyên (trừ khi dùng `--reset`).
  * Hình học: `ST_GeomFromGeoJSON` → `ST_Force2D` → SRID 4326; hình không hợp lệ được sửa bằng
    `ST_MakeValid` + `ST_CollectionExtract(..., 3)` (giữ Polygon/MultiPolygon).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from sqlalchemy import delete, func, select, text, true, update  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402
from sqlalchemy.engine import Connection  # noqa: E402

from app.config import MOCK_DIR, VALID_YEARS  # noqa: E402
from app.db import Base, engine, init_db  # noqa: E402
from app.models import PopulationGrid, TimeseriesMetric, WaterPolygon  # noqa: E402

CHUNK_SIZE = 500

WATER_PROPS = {
    "water_id": str,
    "year": int,
    "area_km2": float,
    "perimeter_km": float,
    "mean_mndwi": float,
    "otsu_threshold": float,
    "change_type": str,
}
POP_PROPS = {
    "grid_id": str,
    "year": int,
    "pop_count": float,
    "density_per_km2": float,
    "in_water_buffer_500m": bool,
    "dist_to_water_m": float,
}
TS_SERIES_FIELDS = (
    "year",
    "water_area_km2",
    "water_ratio_pct",
    "water_gain_km2",
    "water_loss_km2",
    "otsu_threshold",
    "cloud_cover_pct",
    "total_pop",
    "pop_in_buffer_500m",
    "pop_buffer_ratio_pct",
    "jrc_iou_score",
)
POLYGONAL = {"Polygon", "MultiPolygon"}
CHANGE_TYPES = {"stable", "gain", "loss"}


class SeedError(RuntimeError):
    pass


# ───────────────────────────── Đọc & kiểm tra file nguồn ─────────────────────────────


def resolve_source(source: Path | None) -> Path:
    """Tìm thư mục nguồn: theo CWD, rồi theo services/api/, rồi theo services/api/scripts/."""
    if source is None:
        return MOCK_DIR
    candidates = [source] if source.is_absolute() else [Path.cwd() / source, API_ROOT / source, API_ROOT / "scripts" / source]
    for c in candidates:
        if c.is_dir():
            return c.resolve()
    tried = ", ".join(str(c) for c in candidates)
    raise SeedError(f"Không tìm thấy thư mục nguồn '{source}'. Đã thử: {tried}")


def discover(source: Path, prefix: str) -> dict[int, Path]:
    pattern = re.compile(rf"^{prefix}_(\d{{4}})\.geojson$")
    found: dict[int, Path] = {}
    for p in sorted(source.iterdir()):
        m = pattern.match(p.name)
        if not m:
            continue
        year = int(m.group(1))
        if year not in VALID_YEARS:
            print(f"[seed] ⚠ Bỏ qua {p.name}: năm {year} không thuộc {list(VALID_YEARS)}")
            continue
        found[year] = p
    return found


def _coerce(value: Any, typ: type, field: str, ctx: str) -> Any:
    if value is None:
        raise SeedError(f"{ctx}: thiếu giá trị '{field}'")
    if typ is bool:
        if not isinstance(value, bool):
            raise SeedError(f"{ctx}: '{field}' phải là boolean, nhận {value!r}")
        return value
    if typ is int:
        if isinstance(value, bool) or not float(value).is_integer():
            raise SeedError(f"{ctx}: '{field}' phải là số nguyên, nhận {value!r}")
        return int(value)
    if typ is float:
        if isinstance(value, bool):
            raise SeedError(f"{ctx}: '{field}' phải là số, nhận {value!r}")
        return float(value)
    return str(value)


def load_features(
    path: Path, year: int, props_spec: dict[str, type], id_field: str, geom_types: set[str]
) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("type") != "FeatureCollection" or not isinstance(data.get("features"), list):
        raise SeedError(f"{path.name}: không phải GeoJSON FeatureCollection hợp lệ")

    rows: dict[str, dict[str, Any]] = {}
    for i, feat in enumerate(data["features"]):
        ctx = f"{path.name}#feature[{i}]"
        geom = feat.get("geometry") or {}
        if geom.get("type") not in geom_types:
            raise SeedError(f"{ctx}: geometry.type={geom.get('type')!r}, yêu cầu {sorted(geom_types)}")
        props = feat.get("properties") or {}
        row = {k: _coerce(props.get(k), t, k, ctx) for k, t in props_spec.items()}
        if row["year"] != year:
            raise SeedError(f"{ctx}: properties.year={row['year']} không khớp tên file (năm {year})")
        if "change_type" in row and row["change_type"] not in CHANGE_TYPES:
            raise SeedError(f"{ctx}: change_type={row['change_type']!r} không thuộc {sorted(CHANGE_TYPES)}")
        row["geojson"] = json.dumps(geom, separators=(",", ":"))
        key = row[id_field]
        if key in rows:
            print(f"[seed] ⚠ {path.name}: {id_field}={key} bị lặp trong file — giữ bản ghi cuối")
        rows[key] = row
    return list(rows.values())


def load_timeseries(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("aoi_name", "aoi_area_km2", "series"):
        if key not in data:
            raise SeedError(f"{path.name}: thiếu trường '{key}'")
    rows: dict[int, dict[str, Any]] = {}
    for i, item in enumerate(data["series"]):
        missing = [f for f in TS_SERIES_FIELDS if f not in item]
        if missing:
            raise SeedError(f"{path.name}#series[{i}]: thiếu trường {missing}")
        row = {f: item[f] for f in TS_SERIES_FIELDS}
        row["aoi_name"] = str(data["aoi_name"])
        row["aoi_area_km2"] = float(data["aoi_area_km2"])
        rows[int(row["year"])] = row
    return [rows[y] for y in sorted(rows)]


# ───────────────────────────── Ghi vào PostGIS ─────────────────────────────


def _chunks(items: list[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _geom_expr(geojson: str):
    return func.ST_Force2D(func.ST_SetSRID(func.ST_GeomFromGeoJSON(geojson), 4326))


def upsert_layer(conn: Connection, model: Any, id_field: str, year: int, rows: list[dict[str, Any]]) -> None:
    table = model.__table__
    id_col = table.c[id_field]
    ids = [r[id_field] for r in rows]

    # 1) Xóa bản ghi cũ của năm này không còn trong nguồn (vd: chuyển mock → dữ liệu thật)
    conn.execute(delete(table).where(table.c.year == year, id_col.notin_(ids) if ids else true()))

    # 2) Upsert theo khóa tự nhiên (year, id)
    data_cols = [c for c in rows[0] if c != "geojson"] if rows else []
    for chunk in _chunks(rows, CHUNK_SIZE):
        values = [{**{c: r[c] for c in data_cols}, "geom": _geom_expr(r["geojson"])} for r in chunk]
        stmt = pg_insert(table).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[table.c.year, id_col],
            set_={c: stmt.excluded[c] for c in [*data_cols, "geom"] if c not in ("year", id_field)},
        )
        conn.execute(stmt)

    # 3) Sửa hình học không hợp lệ, giữ lại phần đa giác (Polygon/MultiPolygon)
    conn.execute(
        update(table)
        .where(table.c.year == year, func.ST_IsValid(table.c.geom).is_(False))
        .values(geom=func.ST_Multi(func.ST_CollectionExtract(func.ST_MakeValid(table.c.geom), 3)))
    )


def upsert_timeseries(conn: Connection, rows: list[dict[str, Any]]) -> None:
    table = TimeseriesMetric.__table__
    years = [r["year"] for r in rows]
    conn.execute(delete(table).where(table.c.year.notin_(years)))
    stmt = pg_insert(table).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[table.c.year],
        set_={c: stmt.excluded[c] for c in rows[0] if c != "year"},
    )
    conn.execute(stmt)


def table_counts() -> dict[str, int]:
    with engine.connect() as conn:
        return {
            m.__tablename__: conn.execute(select(func.count()).select_from(m)).scalar_one()
            for m in (WaterPolygon, PopulationGrid, TimeseriesMetric)
        }


def reset_tables() -> None:
    tables = [m.__table__ for m in (WaterPolygon, PopulationGrid, TimeseriesMetric)]
    Base.metadata.drop_all(bind=engine, tables=tables)
    print("[seed] Đã DROP 3 bảng (--reset).")


def seed(source: Path | None = None, *, reset: bool = False, if_empty: bool = False) -> dict[str, int]:
    src = resolve_source(source)
    print(f"[seed] Nguồn dữ liệu: {src}")

    if reset:
        reset_tables()
    init_db()

    if if_empty:
        counts = table_counts()
        if all(counts.values()):
            print(f"[seed] --if-empty: DB đã có dữ liệu {counts} → bỏ qua.")
            return counts

    water_files = discover(src, "water")
    pop_files = discover(src, "pop")
    ts_file = src / "timeseries_summary.json"
    if not water_files and not pop_files and not ts_file.is_file():
        raise SeedError(f"Không có water_YYYY.geojson / pop_YYYY.geojson / timeseries_summary.json trong {src}")

    # Đọc & kiểm tra toàn bộ trước khi ghi → lỗi dữ liệu không làm DB dở dang
    water = {y: load_features(p, y, WATER_PROPS, "water_id", POLYGONAL) for y, p in water_files.items()}
    pop = {y: load_features(p, y, POP_PROPS, "grid_id", POLYGONAL) for y, p in pop_files.items()}
    ts = load_timeseries(ts_file) if ts_file.is_file() else []

    with engine.begin() as conn:  # 1 transaction cho toàn bộ lần nạp
        for year, rows in sorted(water.items()):
            upsert_layer(conn, WaterPolygon, "water_id", year, rows)
            print(f"[seed]   water_polygons   {year}: {len(rows):>6} đa giác")
        for year, rows in sorted(pop.items()):
            upsert_layer(conn, PopulationGrid, "grid_id", year, rows)
            print(f"[seed]   population_grids {year}: {len(rows):>6} ô lưới")
        if ts:
            upsert_timeseries(conn, ts)
            print(f"[seed]   timeseries_metrics : {len(ts):>6} năm")

    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        for m in (WaterPolygon, PopulationGrid, TimeseriesMetric):
            conn.execute(text(f"ANALYZE {m.__tablename__}"))

    counts = table_counts()
    print(f"[seed] ✅ Hoàn tất. Số bản ghi hiện có: {counts}")
    return counts


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed PostGIS tables from GeoJSON/JSON directory.")
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help=f"Thư mục chứa water_YYYY.geojson, pop_YYYY.geojson, timeseries_summary.json (mặc định: {MOCK_DIR}).",
    )
    parser.add_argument("--reset", action="store_true", help="DROP & tạo lại 3 bảng trước khi nạp (khi đổi schema).")
    parser.add_argument("--if-empty", action="store_true", help="Chỉ nạp khi DB chưa có dữ liệu (dùng cho Docker).")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        seed(args.source, reset=args.reset, if_empty=args.if_empty)
    except SeedError as exc:
        print(f"[seed] ❌ {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
