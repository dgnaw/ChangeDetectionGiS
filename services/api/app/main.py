"""Khởi tạo FastAPI, CORS và gắn routers (Người B)."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.db import init_db
from app.routers import analytics, health, layers

logger = logging.getLogger("gis_api")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        init_db()  # CREATE EXTENSION postgis + 3 bảng + GIST index (idempotent)
    except SQLAlchemyError as exc:  # DB chưa sẵn sàng: API vẫn chạy, /health báo 503
        logger.warning("Không khởi tạo được PostGIS lúc startup: %s", exc)
    yield


app = FastAPI(
    title="GIS Change Detection API — PA3 Hà Nội",
    description="REST API cung cấp dữ liệu mặt nước Sentinel-2 (MNDWI) và dân cư GHSL khu vực Sông Hồng – Hồ Tây – Đông Anh.",
    version="0.2.0",
    lifespan=lifespan,
)

DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
)
_cors_env = os.getenv("CORS_ORIGINS", "")
ALLOW_ORIGINS = [o.strip() for o in _cors_env.split(",") if o.strip()] or list(DEFAULT_CORS_ORIGINS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time-Ms"],
)
# Nén payload GeoJSON lớn (dữ liệu thật Tuần 7); payload nhỏ < 1 KB giữ nguyên.
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = f"{(time.perf_counter() - start) * 1000:.1f}"
    return response


@app.exception_handler(OperationalError)
async def db_unavailable_handler(_: Request, exc: OperationalError) -> JSONResponse:
    logger.error("PostGIS không khả dụng: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "Cơ sở dữ liệu PostGIS không khả dụng."})


app.include_router(health.router)
app.include_router(analytics.router)
app.include_router(layers.router)
