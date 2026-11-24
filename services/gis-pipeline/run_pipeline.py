"""Unified CLI entrypoint for Người A's GIS & Remote Sensing ETL pipeline."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src.config import (
    DEFAULT_AOI_PATH,
    DEFAULT_OUT_DIR,
    DEFAULT_RAW_DIR,
    MAX_CLOUD_COVER_PCT,
    YEARS,
)
from src.population.build_timeseries import build_timeseries_summary
from src.population.clip_population import run_population_interpolation
from src.population.grid_to_geojson import run_export_pop_grids_all_years
from src.population.spatial_overlay import run_spatial_overlay_all_years
from src.water.fetch_stac import fetch_sentinel2_for_year
from src.water.mndwi_otsu import run_mndwi_otsu_for_year
from src.water.preprocess import build_year_composite
from src.water.validate_jrc import run_jrc_validation
from src.water.vectorize import run_vectorize_all_years


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for running fetch, preprocess, vectorize, validate-jrc, water, pop, or all steps."""
    parser = argparse.ArgumentParser(
        description="Run Sentinel-2 surface water & GHSL population GIS pipeline."
    )
    parser.add_argument(
        "--step",
        choices=["fetch", "preprocess", "vectorize", "validate-jrc", "water", "pop", "all"],
        default="all",
        help=(
            "Pipeline stage: fetch (Tuần 2), preprocess (Tuần 3), "
            "vectorize (Tuần 4 GeoJSON), validate-jrc (Tuần 4 JRC), water (full Tuần 2-4), pop, or all."
        ),
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
        "--max-cloud",
        type=float,
        default=MAX_CLOUD_COVER_PCT,
        help="Maximum eo:cloud_cover percentage for STAC search (default: 10.0).",
    )
    parser.add_argument(
        "--max-scenes",
        type=int,
        default=3,
        help="Maximum number of least-cloudy scenes to download per year (default: 3).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-download and overwrite existing clipped GeoTIFFs.",
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
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    print(f"[gis-pipeline] Step: {args.step} | Years: {args.years}")
    print(f"[gis-pipeline] AOI: {args.aoi}")

    if args.step in ("fetch", "water", "all"):
        for year in args.years:
            year_dir = fetch_sentinel2_for_year(
                aoi_path=args.aoi,
                year=year,
                out_dir=args.raw_dir,
                max_cloud_pct=args.max_cloud,
                max_scenes=args.max_scenes,
                overwrite=args.overwrite,
            )
            print(f"[gis-pipeline] Cached Sentinel-2 ({year}) -> {year_dir}")

    if args.step in ("preprocess", "water", "all"):
        for year in args.years:
            year_dir = args.raw_dir / "sentinel2" / str(year)
            build_year_composite(year_dir=year_dir, overwrite=args.overwrite)
            stats = run_mndwi_otsu_for_year(year_dir=year_dir)
            print(
                f"[mndwi_otsu] {year} | raw_otsu={stats['raw_otsu_threshold']:.4f} | "
                f"used_otsu={stats['otsu_threshold']:.4f} | "
                f"raw_water_area={stats['raw_water_area_km2']:.2f} km² | "
                f"mean_mndwi={stats['mean_water_mndwi']:.3f}"
            )

    if args.step in ("vectorize", "water", "all"):
        run_vectorize_all_years(
            raw_dir=args.raw_dir,
            out_dir=args.out,
            aoi_path=args.aoi,
            years=args.years,
        )

    if args.step in ("validate-jrc", "water", "all"):
        run_jrc_validation(
            raw_dir=args.raw_dir,
            out_dir=args.out,
            aoi_path=args.aoi,
            years=args.years,
            overwrite=args.overwrite,
        )

    if args.step in ("pop", "all"):
        run_population_interpolation(
            aoi_path=args.aoi,
            raw_dir=args.raw_dir,
            years=args.years,
            overwrite=args.overwrite,
        )
        run_spatial_overlay_all_years(
            raw_dir=args.raw_dir,
            out_dir=args.out,
            aoi_path=args.aoi,
            years=args.years,
        )
        run_export_pop_grids_all_years(
            raw_dir=args.raw_dir,
            out_dir=args.out,
            years=args.years,
        )
        build_timeseries_summary(
            processed_dir=args.out,
            out_json=args.out / "timeseries_summary.json",
            aoi_path=args.aoi,
        )


if __name__ == "__main__":
    main()
