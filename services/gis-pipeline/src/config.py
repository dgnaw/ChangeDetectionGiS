"""Centralized constants and CRS/processing rules for the GIS pipeline."""

from __future__ import annotations

from pathlib import Path

# Repository paths relative to services/gis-pipeline/
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
DEFAULT_AOI_PATH = REPO_ROOT / "contracts" / "aoi.geojson"
DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw"
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "processed"

# Coordinate Reference Systems
CRS_STORAGE = "EPSG:4326"
CRS_METRIC = "EPSG:32648"

# Temporal & STAC search parameters
YEARS = [2016, 2018, 2020, 2022, 2024]
DRY_SEASON_WINDOW = ("01-01", "04-30")
MAX_CLOUD_COVER_PCT = 10.0

# ESA Sentinel-2 L2A Processing Baseline 04.00 radiometric offset rule
# From 2022-01-25 onward, ESA adds +1000 DN to spectral bands; subtract 1000 to match 2016-2020.
S2_PB0400_CUTOFF_DATE = "2022-01-25"
S2_BOA_ADD_OFFSET = -1000

# SCL classes to mask: No Data (0), Saturated/Defective (1), Cloud Shadows (3),
# Cloud Medium Prob (8), Cloud High Prob (9), Thin Cirrus (10)
INVALID_SCL_CLASSES = (0, 1, 3, 8, 9, 10)

# MNDWI-Otsu bimodal window & physical clamp bounds
OTSU_WINDOW_MIN = -0.30
OTSU_WINDOW_MAX = 0.60
OTSU_CLAMP_MIN = 0.00
OTSU_CLAMP_MAX = 0.15
WATER_MASK_NODATA = 255

# Water vectorization & topology simplification rules
MIN_WATER_AREA_KM2 = 0.005
SIMPLIFY_TOLERANCE_DEG = 0.0001

# Population overlay & export rules
BUFFER_RADIUS_METERS = 500.0
POP_GRID_AGG_METERS = 250
MIN_POP_PER_CELL = 5.0
