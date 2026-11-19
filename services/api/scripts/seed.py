"""Tuần 2: Script nạp GeoJSON từ contracts/mock/ (T2-6) hoặc data/processed/ (T7) vào PostGIS (Người B)."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed PostGIS tables from GeoJSON/JSON directory.")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("../../contracts/mock"),
        help="Source directory containing water_YYYY.geojson, pop_YYYY.geojson, timeseries_summary.json.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(f"[seed] Source directory: {args.source.resolve()}")
    print("[seed] Scaffold ready. Implement SQLAlchemy + GeoAlchemy2 bulk insert into PostGIS in Week 2.")


if __name__ == "__main__":
    main()
