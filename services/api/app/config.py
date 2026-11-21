"""Cấu hình dùng chung cho API + seed (đường dẫn, mốc năm hợp lệ).

Hoạt động được cả khi chạy local (repo root) lẫn trong Docker
(docker-compose mount `./contracts -> /contracts`, `./data/processed -> /data/processed`).
"""

from __future__ import annotations

import os
from pathlib import Path

# services/api/
API_ROOT = Path(__file__).resolve().parents[1]


def _first_existing(*candidates: Path | None) -> Path:
    """Trả về thư mục đầu tiên tồn tại; nếu không có thì trả về ứng viên đầu tiên khác None."""
    valid = [c for c in candidates if c is not None]
    for c in valid:
        if c.is_dir():
            return c
    return valid[0]


def _env_path(name: str) -> Path | None:
    value = os.getenv(name)
    return Path(value) if value else None


def _repo_child(*parts: str) -> Path | None:
    # Local: services/api/ -> repo root nằm 2 cấp phía trên. Trong Docker (/app) không có cấp này.
    parents = API_ROOT.parents
    return parents[1].joinpath(*parts) if len(parents) >= 2 else None


CONTRACTS_DIR: Path = _first_existing(_env_path("CONTRACTS_DIR"), Path("/contracts"), _repo_child("contracts"))
MOCK_DIR: Path = CONTRACTS_DIR / "mock"
AOI_PATH: Path = CONTRACTS_DIR / "aoi.geojson"
PROCESSED_DIR: Path = _first_existing(
    _env_path("PROCESSED_DIR"), Path("/data/processed"), _repo_child("data", "processed")
)

# Mốc năm phân tích cố định (CLAUDE.md §1)
VALID_YEARS: tuple[int, ...] = (2016, 2018, 2020, 2022, 2024)
# Miền giá trị `year` hợp lệ theo contracts/schemas/*_layer.schema.json
SCHEMA_YEAR_MIN, SCHEMA_YEAR_MAX = 2015, 2030
