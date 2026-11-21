"""Kết nối PostgreSQL + PostGIS qua SQLAlchemy."""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://gis_user:gis_password@localhost:5432/gis_change_detection",
)

# SQLAlchemy >= 2.1 mặc định map `postgresql://` sang driver psycopg (v3);
# requirements.txt dùng psycopg2-binary nên chỉ định driver tường minh.
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL.removeprefix("postgresql://")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Bật extension PostGIS và tạo 3 bảng + index (idempotent, an toàn khi gọi nhiều lần)."""
    from app import models  # noqa: F401  (đăng ký model vào Base.metadata)

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
