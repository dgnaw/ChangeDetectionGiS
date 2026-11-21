"""Tests kiểm tra 5 endpoint FastAPI + seed idempotent (cần PostGIS đang chạy)."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import VALID_YEARS
from app.db import engine
from app.main import app

client = TestClient(app)

WATER_KEYS = {"water_id", "year", "area_km2", "perimeter_km", "mean_mndwi", "otsu_threshold", "change_type"}
POP_KEYS = {"grid_id", "year", "pop_count", "density_per_km2", "in_water_buffer_500m", "dist_to_water_m"}


def test_health() -> None:
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["records"]["water_polygons"] > 0


def test_aoi() -> None:
    res = client.get("/api/v1/aoi")
    assert res.status_code == 200
    assert res.json()["features"][0]["properties"]["aoi_id"] == "PA3_HANOI"


@pytest.mark.parametrize("year", VALID_YEARS)
def test_water_layer(year: int) -> None:
    res = client.get(f"/api/v1/layers/water?year={year}")
    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) > 0
    for f in body["features"]:
        assert f["geometry"]["type"] in {"Polygon", "MultiPolygon"}
        assert set(f["properties"]) == WATER_KEYS
        assert f["properties"]["year"] == year


def test_population_all_vs_buffer() -> None:
    all_feats = client.get("/api/v1/layers/population?year=2024&only_buffer=false").json()["features"]
    res = client.get("/api/v1/layers/population?year=2024&only_buffer=true")
    assert res.status_code == 200
    features = res.json()["features"]
    assert 0 < len(features) <= len(all_feats)
    assert all(f["properties"]["in_water_buffer_500m"] is True for f in features)
    assert all(set(f["properties"]) == POP_KEYS for f in all_feats)


def test_timeseries() -> None:
    res = client.get("/api/v1/analytics/timeseries")
    assert res.status_code == 200
    body = res.json()
    assert body["years"] == [2016, 2018, 2020, 2022, 2024]
    assert body["crs_storage"] == "EPSG:4326"
    assert body["series"][3]["jrc_iou_score"] is None


@pytest.mark.parametrize("path", ["/api/v1/layers/water", "/api/v1/layers/population"])
def test_invalid_year_400(path: str) -> None:
    assert client.get(f"{path}?year=1999").status_code == 400


@pytest.mark.parametrize("path", ["/api/v1/layers/water", "/api/v1/layers/population"])
def test_unavailable_year_404(path: str) -> None:
    assert client.get(f"{path}?year=2019").status_code == 404


def test_cors_localhost_5173() -> None:
    res = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_seed_is_idempotent(seed_module) -> None:
    first = seed_module.seed()
    second = seed_module.seed()
    assert first == second
    with engine.connect() as conn:
        dup = conn.execute(
            text("SELECT count(*) FROM (SELECT year, water_id FROM water_polygons GROUP BY 1, 2 HAVING count(*) > 1) d")
        ).scalar_one()
    assert dup == 0


def test_gist_indexes_exist() -> None:
    with engine.connect() as conn:
        names = set(
            conn.execute(text("SELECT indexname FROM pg_indexes WHERE indexdef ILIKE '%USING gist%'")).scalars()
        )
    assert {"idx_water_polygons_geom", "idx_population_grids_geom"} <= names


def test_layer_latency_under_50ms() -> None:
    client.get("/api/v1/layers/water?year=2020")  # warm-up connection pool
    start = time.perf_counter()
    for _ in range(10):
        client.get("/api/v1/layers/population?year=2020")
    avg_ms = (time.perf_counter() - start) * 100
    assert avg_ms < 50, f"Trung bình {avg_ms:.1f} ms"
