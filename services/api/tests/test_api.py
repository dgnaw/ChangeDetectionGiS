"""Unit/Contract tests (chạy offline) + Integration tests với PostGIS (`@pytest.mark.integration`)."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from geoalchemy2 import Geometry
from sqlalchemy import UniqueConstraint, text
from sqlalchemy.exc import OperationalError

from app.config import MOCK_DIR, VALID_YEARS
from app.db import engine, get_db
from app.main import app
from app.models import PopulationGrid, TimeseriesMetric, WaterPolygon

client = TestClient(app)

WATER_KEYS = {"water_id", "year", "area_km2", "perimeter_km", "mean_mndwi", "otsu_threshold", "change_type"}
POP_KEYS = {"grid_id", "year", "pop_count", "density_per_km2", "in_water_buffer_500m", "dist_to_water_m"}


# ───────────────────────────── Helpers cho test offline (mock DB) ─────────────────────────────


class _Result:
    def __init__(self, *, scalar: Any = None, mapping: dict[str, Any] | None = None, one: Any = None, scalars: list[Any] | None = None):
        self._scalar = scalar
        self._mapping = mapping
        self._one = one
        self._scalars = scalars or []

    def scalar(self) -> Any:
        return self._scalar

    def mappings(self) -> _Result:
        return self

    def one(self) -> Any:
        return self._mapping if self._mapping is not None else self._one

    def scalars(self) -> _Result:
        return self

    def all(self) -> list[Any]:
        return self._scalars


class _FakeSession:
    def __init__(self, handler):
        self._handler = handler

    def execute(self, stmt: Any) -> _Result:
        return self._handler(stmt)

    def rollback(self) -> None:
        pass


@contextmanager
def _override_db(fake_session: _FakeSession) -> Iterator[None]:
    def _dep():
        yield fake_session

    app.dependency_overrides[get_db] = _dep
    try:
        yield
    finally:
        app.dependency_overrides.clear()


# ───────────────────────────── Offline Unit & Contract Tests ─────────────────────────────


def test_aoi_offline() -> None:
    res = client.get("/api/v1/aoi")
    assert res.status_code == 200
    assert res.json()["features"][0]["properties"]["aoi_id"] == "PA3_HANOI"
    assert "x-process-time-ms" in {k.lower() for k in res.headers}


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://localhost:4173"])
def test_cors_allowed_origins(origin: str) -> None:
    res = client.get("/api/v1/aoi", headers={"Origin": origin})
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == origin


@pytest.mark.parametrize("path", ["/api/v1/layers/water", "/api/v1/layers/population"])
def test_invalid_year_400(path: str) -> None:
    with _override_db(_FakeSession(lambda _: _Result())):
        assert client.get(f"{path}?year=1999").status_code == 400


@pytest.mark.parametrize("path", ["/api/v1/layers/water", "/api/v1/layers/population"])
def test_unavailable_year_404(path: str) -> None:
    with _override_db(_FakeSession(lambda _: _Result())):
        assert client.get(f"{path}?year=2019").status_code == 404


def test_health_with_mocked_db() -> None:
    def ok_handler(stmt: Any) -> _Result:
        sql = str(stmt)
        if "postgis_lib_version" in sql:
            return _Result(scalar="3.4 USE_GEOS=1")
        return _Result(mapping={"water_polygons": 25, "population_grids": 120, "timeseries_metrics": 5})

    with _override_db(_FakeSession(ok_handler)):
        res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert body["postgis_version"] == "3.4 USE_GEOS=1"
    assert body["records"] == {"water_polygons": 25, "population_grids": 120, "timeseries_metrics": 5}

    def down_handler(_: Any) -> _Result:
        raise OperationalError("SELECT postgis_lib_version()", {}, Exception("db down"))

    with _override_db(_FakeSession(down_handler)):
        res_down = client.get("/api/v1/health")
    assert res_down.status_code == 503
    assert res_down.json()["status"] == "error"
    assert res_down.json()["database"] == "unreachable"


def test_water_layer_with_mocked_db() -> None:
    sample = (MOCK_DIR / "water_2020.geojson").read_text(encoding="utf-8")
    with _override_db(_FakeSession(lambda _: _Result(one=(sample, 2)))):
        res = client.get("/api/v1/layers/water?year=2020")
    assert res.status_code == 200
    assert res.json()["type"] == "FeatureCollection"

    with _override_db(_FakeSession(lambda _: _Result(one=('{"type":"FeatureCollection","features":[]}', 0)))):
        assert client.get("/api/v1/layers/water?year=2020").status_code == 404


def test_population_layer_with_mocked_db() -> None:
    sample = (MOCK_DIR / "pop_2024.geojson").read_text(encoding="utf-8")
    with _override_db(_FakeSession(lambda _: _Result(one=(sample, 3)))):
        res = client.get("/api/v1/layers/population?year=2024&only_buffer=true")
    assert res.status_code == 200
    assert res.json()["type"] == "FeatureCollection"

    # only_buffer=true trả về 0 ô trên năm đã seed -> vẫn trả 200 FeatureCollection rỗng
    calls = {"n": 0}

    def empty_buffer_handler(_: Any) -> _Result:
        calls["n"] += 1
        if calls["n"] == 1:
            return _Result(one=('{"type":"FeatureCollection","features":[]}', 0))
        return _Result(scalar=True)

    with _override_db(_FakeSession(empty_buffer_handler)):
        res_empty = client.get("/api/v1/layers/population?year=2024&only_buffer=true")
    assert res_empty.status_code == 200
    assert res_empty.json() == {"type": "FeatureCollection", "features": []}

    # Năm chưa seed -> 404
    calls["n"] = 0

    def unseeded_handler(_: Any) -> _Result:
        calls["n"] += 1
        if calls["n"] == 1:
            return _Result(one=('{"type":"FeatureCollection","features":[]}', 0))
        return _Result(scalar=False)

    with _override_db(_FakeSession(unseeded_handler)):
        assert client.get("/api/v1/layers/population?year=2024").status_code == 404


def test_timeseries_with_mocked_db() -> None:
    raw = json.loads((MOCK_DIR / "timeseries_summary.json").read_text(encoding="utf-8"))
    rows = [
        SimpleNamespace(aoi_name=raw["aoi_name"], aoi_area_km2=raw["aoi_area_km2"], **item)
        for item in raw["series"]
    ]
    with _override_db(_FakeSession(lambda _: _Result(scalars=rows))):
        res = client.get("/api/v1/analytics/timeseries")
    assert res.status_code == 200
    body = res.json()
    assert body["crs_storage"] == "EPSG:4326"
    assert body["crs_metric"] == "EPSG:32648"
    assert body["years"] == [2016, 2018, 2020, 2022, 2024]
    assert body["series"][3]["jrc_iou_score"] is None

    with _override_db(_FakeSession(lambda _: _Result(scalars=[]))):
        assert client.get("/api/v1/analytics/timeseries").status_code == 404


def test_models_spatial_contract() -> None:
    for model, id_col in ((WaterPolygon, "water_id"), (PopulationGrid, "grid_id")):
        geom_type = model.__table__.c.geom.type
        assert isinstance(geom_type, Geometry)
        assert geom_type.geometry_type == "GEOMETRY"
        assert geom_type.srid == 4326
        indexes = {idx.name: idx for idx in model.__table__.indexes}
        gist_idx = indexes[f"idx_{model.__tablename__}_geom"]
        assert gist_idx.dialect_options["postgresql"]["using"] == "gist"
        unique_cols = [
            tuple(c.name for c in cons.columns)
            for cons in model.__table__.constraints
            if isinstance(cons, UniqueConstraint)
        ]
        assert ("year", id_col) in unique_cols
    assert TimeseriesMetric.__table__.c.year.primary_key is True


def test_seed_loaders_against_contracts_mock(seed_module) -> None:
    resolved = seed_module.resolve_source(Path("../../contracts/mock"))
    assert resolved == MOCK_DIR.resolve()
    water_files = seed_module.discover(resolved, "water")
    pop_files = seed_module.discover(resolved, "pop")
    assert tuple(sorted(water_files)) == VALID_YEARS
    assert tuple(sorted(pop_files)) == VALID_YEARS

    for year, path in water_files.items():
        rows = seed_module.load_features(path, year, seed_module.WATER_PROPS, "water_id", seed_module.POLYGONAL)
        assert len(rows) > 0
        assert set(rows[0]) == {*WATER_KEYS, "geojson"}

    for year, path in pop_files.items():
        rows = seed_module.load_features(path, year, seed_module.POP_PROPS, "grid_id", seed_module.POLYGONAL)
        assert len(rows) > 0
        assert set(rows[0]) == {*POP_KEYS, "geojson"}

    ts_rows = seed_module.load_timeseries(resolved / "timeseries_summary.json")
    assert [r["year"] for r in ts_rows] == list(VALID_YEARS)


def test_seed_validators_reject_bad_data(tmp_path: Path, seed_module) -> None:
    SeedError = seed_module.SeedError
    base_geom = {"type": "Polygon", "coordinates": [[[105.8, 21.0], [105.81, 21.0], [105.81, 21.01], [105.8, 21.0]]]}
    base_props = {
        "water_id": "w_1",
        "year": 2020,
        "area_km2": 1.0,
        "perimeter_km": 4.0,
        "mean_mndwi": 0.3,
        "otsu_threshold": 0.1,
        "change_type": "stable",
    }

    bad_feature_cases = [
        ({"type": "GeometryCollection", "geometries": []}, base_props),
        (base_geom, {**base_props, "area_km2": -0.5}),
        (base_geom, {**base_props, "mean_mndwi": 1.5}),
        (base_geom, {**base_props, "change_type": "unknown"}),
        (base_geom, {**base_props, "year": 2022}),
        (base_geom, {**base_props, "water_id": "w" * 65}),
    ]
    for idx, (geom, props) in enumerate(bad_feature_cases):
        p = tmp_path / f"bad_water_{idx}.geojson"
        p.write_text(json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": geom, "properties": props}]}), encoding="utf-8")
        with pytest.raises(SeedError):
            seed_module.load_features(p, 2020, seed_module.WATER_PROPS, "water_id", seed_module.POLYGONAL)

    nan_file = tmp_path / "nan.geojson"
    nan_file.write_text(
        '{"type":"FeatureCollection","features":[{"type":"Feature",'
        '"geometry":{"type":"Polygon","coordinates":[[[105.8,21.0],[105.81,21.0],[105.81,21.01],[105.8,21.0]]]},'
        '"properties":{"water_id":"w_1","year":2020,"area_km2":NaN,"perimeter_km":4.0,"mean_mndwi":0.2,"otsu_threshold":0.1,"change_type":"stable"}}]}',
        encoding="utf-8",
    )
    with pytest.raises(SeedError):
        seed_module.load_features(nan_file, 2020, seed_module.WATER_PROPS, "water_id", seed_module.POLYGONAL)

    ts_bad = tmp_path / "ts_bad.json"
    ts_data = json.loads((MOCK_DIR / "timeseries_summary.json").read_text(encoding="utf-8"))
    ts_data["series"][0]["jrc_iou_score"] = 1.2
    ts_bad.write_text(json.dumps(ts_data), encoding="utf-8")
    with pytest.raises(SeedError):
        seed_module.load_timeseries(ts_bad)


# ───────────────────────────── Live PostGIS Integration Tests ─────────────────────────────


@pytest.mark.integration
def test_health(seeded_db) -> None:
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert body["records"]["water_polygons"] > 0


@pytest.mark.integration
@pytest.mark.parametrize("year", VALID_YEARS)
def test_water_layer(seeded_db, year: int) -> None:
    res = client.get(f"/api/v1/layers/water?year={year}")
    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) > 0
    for f in body["features"]:
        assert f["geometry"]["type"] in {"Polygon", "MultiPolygon"}
        assert set(f["properties"]) == WATER_KEYS
        assert f["properties"]["year"] == year


@pytest.mark.integration
def test_population_all_vs_buffer(seeded_db) -> None:
    all_feats = client.get("/api/v1/layers/population?year=2024&only_buffer=false").json()["features"]
    res = client.get("/api/v1/layers/population?year=2024&only_buffer=true")
    assert res.status_code == 200
    features = res.json()["features"]
    assert 0 < len(features) <= len(all_feats)
    assert all(f["properties"]["in_water_buffer_500m"] is True for f in features)
    assert all(set(f["properties"]) == POP_KEYS for f in all_feats)


@pytest.mark.integration
def test_timeseries(seeded_db) -> None:
    res = client.get("/api/v1/analytics/timeseries")
    assert res.status_code == 200
    body = res.json()
    assert body["years"] == [2016, 2018, 2020, 2022, 2024]
    assert body["crs_storage"] == "EPSG:4326"
    assert body["series"][3]["jrc_iou_score"] is None


@pytest.mark.integration
def test_seed_is_idempotent(seeded_db, seed_module) -> None:
    first = seed_module.seed()
    second = seed_module.seed()
    assert first == second
    with engine.connect() as conn:
        dup = conn.execute(
            text("SELECT count(*) FROM (SELECT year, water_id FROM water_polygons GROUP BY 1, 2 HAVING count(*) > 1) d")
        ).scalar_one()
    assert dup == 0


@pytest.mark.integration
def test_gist_indexes_exist(seeded_db) -> None:
    with engine.connect() as conn:
        names = set(
            conn.execute(text("SELECT indexname FROM pg_indexes WHERE indexdef ILIKE '%USING gist%'")).scalars()
        )
    assert {"idx_water_polygons_geom", "idx_population_grids_geom"} <= names


@pytest.mark.integration
def test_layer_latency_under_50ms(seeded_db) -> None:
    client.get("/api/v1/layers/water?year=2020")  # warm-up connection pool
    start = time.perf_counter()
    for _ in range(10):
        client.get("/api/v1/layers/population?year=2020")
    avg_ms = (time.perf_counter() - start) * 100
    assert avg_ms < 50, f"Trung bình {avg_ms:.1f} ms"
