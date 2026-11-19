"""Tuần 5: Tổng hợp số liệu 5 mốc năm ra file timeseries_summary.json."""

from __future__ import annotations

from pathlib import Path


def build_timeseries_summary(processed_dir: Path, out_json: Path) -> Path:
    """Xuất timeseries_summary.json khớp contracts/schemas/timeseries.schema.json."""
    raise NotImplementedError("TODO (Tuần 5): Aggregate water & population metrics into timeseries_summary.json.")
