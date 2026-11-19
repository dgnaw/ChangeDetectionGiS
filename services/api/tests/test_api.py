"""Tests kiểm tra các endpoint cơ bản của FastAPI."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_water_layer_2020() -> None:
    res = client.get("/api/v1/layers/water?year=2020")
    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) > 0


def test_population_buffer_filter() -> None:
    res = client.get("/api/v1/layers/population?year=2024&only_buffer=true")
    assert res.status_code == 200
    features = res.json()["features"]
    assert len(features) > 0
    assert all(f["properties"]["in_water_buffer_500m"] is True for f in features)


def test_timeseries() -> None:
    res = client.get("/api/v1/analytics/timeseries")
    assert res.status_code == 200
    assert res.json()["years"] == [2016, 2018, 2020, 2022, 2024]
