"""Fixtures: seed contracts/mock/ vào PostGIS trước khi chạy test tích hợp (bỏ qua nếu DB không chạy)."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.db import engine

SEED_PATH = Path(__file__).resolve().parents[1] / "scripts" / "seed.py"


def _load_seed_module():
    spec = importlib.util.spec_from_file_location("seed_script", SEED_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def seed_module():
    return _load_seed_module()


@pytest.fixture(scope="session")
def seeded_db(seed_module):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            has_table = conn.execute(text("SELECT to_regclass('public.water_polygons')")).scalar() is not None
            if has_table and os.getenv("ALLOW_TEST_RESEED") != "true":
                total = conn.execute(text("SELECT count(*) FROM water_polygons")).scalar_one()
                has_mock = conn.execute(
                    text("SELECT EXISTS (SELECT 1 FROM water_polygons WHERE water_id = 'w_2020_hotay')")
                ).scalar_one()
                if total > 0 and not has_mock:
                    pytest.skip(
                        "DB đang chứa dữ liệu thật (không thấy w_2020_hotay) — bỏ qua auto-seed mock "
                        "để tránh ghi đè. Đặt ALLOW_TEST_RESEED=true nếu muốn chạy test trên mock."
                    )
    except OperationalError as exc:
        pytest.skip(f"PostGIS không chạy ({exc.orig}). Chạy `docker compose up -d db` trước.")
    return seed_module.seed()
