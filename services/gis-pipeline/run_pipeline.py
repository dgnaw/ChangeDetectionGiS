"""Unified CLI entrypoint for Người A's GIS & Remote Sensing ETL pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.config import DEFAULT_AOI_PATH, DEFAULT_OUT_DIR, DEFAULT_RAW_DIR, YEARS


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for running water, population, or full pipeline steps."""
    parser = argparse.ArgumentParser(
        description="Run Sentinel-2 surface water & GHSL population GIS pipeline."
    )
    parser.add_argument(
        "--step",
        choices=["water", "pop", "all"],
        default="all",
        help="Pipeline stage to execute: water, pop, or all.",
    )
    parser.add_argument(
        "--aoi",
        type=Path,
        default=DEFAULT_AOI_PATH,
        help="Path to AOI GeoJSON (EPSG:4326).",
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=list(YEARS),
        help="List of dry-season years to process.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help="Directory to cache clipped raw rasters.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Directory to write processed GeoJSON and timeseries JSON files.",
    )
    return parser.parse_args()


def main() -> None:
    """Execute the requested pipeline stages."""
    args = parse_args()
    print(f"[gis-pipeline] Step: {args.step}")
    print(f"[gis-pipeline] AOI: {args.aoi}")
    print(f"[gis-pipeline] Years: {args.years}")
    print(f"[gis-pipeline] Raw dir: {args.raw_dir}")
    print(f"[gis-pipeline] Output dir: {args.out}")
    print(
        "[gis-pipeline] Scaffold ready. Implement src/water/ (Weeks 2-4) and src/population/ (Week 5)."
    )


if __name__ == "__main__":
    main()
