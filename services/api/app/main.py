"""Khởi tạo FastAPI, CORS và gắn routers (Người B)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import analytics, layers

app = FastAPI(
    title="GIS Change Detection API — PA3 Hà Nội",
    description="REST API cung cấp dữ liệu mặt nước Sentinel-2 (MNDWI) và dân cư GHSL khu vực Sông Hồng – Hồ Tây – Đông Anh.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(layers.router)
app.include_router(analytics.router)


@app.get("/api/v1/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "gis-change-detection-api"}
