"""Fixtures: seed contracts/mock/ vào PostGIS trước khi chạy test (bỏ qua nếu DB không chạy)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.db import engine

SEED_PATH = Path(__file__).resolve().parents[1] / "scripts" / "seed.py"


def _load_seed_module():
    spec = importlib.util.spec_from_file_location("seed_script", SEED_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def seed_module():
    return _load_seed_module()


@pytest.fixture(scope="session", autouse=True)
def seeded_db(seed_module):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as exc:
        pytest.skip(f"PostGIS không chạy ({exc.orig}). Chạy `docker compose up -d db` trước.")
    return seed_module.seed()
