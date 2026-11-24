"""Tuần 5: Gộp lưới dân số 100m lên 250m bảo toàn tổng dân số (lọc ô < 5 người) và xuất GeoJSON EPSG:4326."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import rasterio
import shapely
from jsonschema import validate
from rasterio.transform import Affine
from shapely.geometry import Point, box, mapping

from src.config import (
    BUFFER_RADIUS_METERS,
    CRS_METRIC,
    CRS_STORAGE,
    MIN_POP_PER_CELL,
    POP_GRID_AGG_METERS,
    REPO_ROOT,
)
from src.population.spatial_overlay import load_active_water_32648

POP_SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "pop_layer.schema.json"


def aggregate_100m_to_250m(pop_100m: np.ndarray, transform_100m: Affine) -> tuple[np.ndarray, Affine]:
    """Gộp mảng dân số 100m lên lưới 250m bằng chia khối 50m (5x5) bảo toàn 100% tổng dân số."""
    clean = np.where(np.isfinite(pop_100m) & (pop_100m > 0.0), pop_100m, 0.0).astype(np.float64)
    h, w = clean.shape

    pad_h = (5 - (h % 5)) % 5
    pad_w = (5 - (w % 5)) % 5
    if pad_h > 0 or pad_w > 0:
        clean = np.pad(clean, ((0, pad_h), (0, pad_w)), mode="constant", constant_values=0.0)

    # Mỗi ô 100m x 100m chia đều thành 2x2 ô 50m x 50m, sau đó cộng gộp khối 5x5 ô 50m = đúng 250m x 250m
    sub_50m = np.repeat(np.repeat(clean * 0.25, 2, axis=0), 2, axis=1)
    h_250 = sub_50m.shape[0] // 5
    w_250 = sub_50m.shape[1] // 5
    agg_250m = sub_50m.reshape(h_250, 5, w_250, 5).sum(axis=(1, 3)).astype(np.float32)

    transform_250m = Affine(
        float(POP_GRID_AGG_METERS),
        0.0,
        transform_100m.c,
        0.0,
        -float(POP_GRID_AGG_METERS),
        transform_100m.f,
    )
    return agg_250m, transform_250m


def _round_poly_coords(coords: Any, precision: int = 6) -> Any:
    if isinstance(coords[0], (int, float)):
        return [round(float(coords[0]), precision), round(float(coords[1]), precision)]
    return [_round_poly_coords(c, precision=precision) for c in coords]


def export_population_grid_geojson(
    raster_path: Path,
    year: int,
    out_geojson: Path,
    water_geojson: Path | None = None,
    min_pop: float = MIN_POP_PER_CELL,
    buffer_m: float = BUFFER_RADIUS_METERS,
    schema_path: Path = POP_SCHEMA_PATH,
) -> dict[str, Any]:
    """Chuyển lưới dân số 250m sang GeoJSON khớp contracts/schemas/pop_layer.schema.json."""
    with rasterio.open(raster_path) as src:
        pop_100m = src.read(1)
        transform_100m = src.transform

    agg_250m, transform_250m = aggregate_100m_to_250m(pop_100m, transform_100m)
    rows, cols = np.where(agg_250m >= min_pop)

    water_union = None
    if water_geojson is not None and water_geojson.exists():
        active_water = load_active_water_32648(water_geojson)
        if not active_water.empty:
            water_union = active_water.geometry.union_all()

    cell_size = float(POP_GRID_AGG_METERS)
    cell_area_km2 = (cell_size * cell_size) / 1_000_000.0  # 0.0625 km²
    origin_x = transform_250m.c
    origin_y = transform_250m.f

    polys_32648 = []
    centroids_32648 = []
    pop_vals: list[float] = []
    grid_ids: list[str] = []

    for r, c in zip(rows.tolist(), cols.tolist()):
        minx = origin_x + c * cell_size
        maxy = origin_y - r * cell_size
        maxx = minx + cell_size
        miny = maxy - cell_size
        polys_32648.append(box(minx, miny, maxx, maxy))
        centroids_32648.append(Point(minx + cell_size * 0.5, miny + cell_size * 0.5))
        pop_vals.append(float(agg_250m[r, c]))
        grid_ids.append(f"g_{year}_{r:03d}_{c:03d}")

    features: list[dict[str, Any]] = []
    if polys_32648:
        if water_union is not None:
            dists = shapely.distance(np.array(centroids_32648, dtype=object), water_union).astype(np.float64)
        else:
            dists = np.zeros(len(polys_32648), dtype=np.float64)

        gdf_4326 = gpd.GeoDataFrame({"geometry": polys_32648}, crs=CRS_METRIC).to_crs(CRS_STORAGE)

        for idx, geom_4326 in enumerate(gdf_4326.geometry):
            p_val = round(pop_vals[idx], 1)
            dens_val = round(pop_vals[idx] / cell_area_km2, 1)
            d_val = round(float(dists[idx]), 1)
            if math.isnan(d_val) or d_val < 0.0:
                d_val = 0.0
            geom_dict = mapping(geom_4326)
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": _round_poly_coords(geom_dict["coordinates"], precision=6),
                    },
                    "properties": {
                        "grid_id": grid_ids[idx],
                        "year": int(year),
                        "pop_count": p_val,
                        "density_per_km2": dens_val,
                        "in_water_buffer_500m": bool(d_val <= buffer_m),
                        "dist_to_water_m": d_val,
                    },
                }
            )

    fc = {"type": "FeatureCollection", "features": features}
    if schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validate(instance=fc, schema=schema)

    out_geojson.parent.mkdir(parents=True, exist_ok=True)
    out_geojson.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    return {
        "year": int(year),
        "cell_count": len(features),
        "buffer_cell_count": sum(1 for f in features if f["properties"]["in_water_buffer_500m"]),
        "file_size_kb": round(out_geojson.stat().st_size / 1024.0, 1),
    }


def run_export_pop_grids_all_years(
    raw_dir: Path,
    out_dir: Path,
    years: list[int],
) -> list[dict[str, Any]]:
    """Xuất toàn bộ pop_{year}.geojson (lưới 250m) cho cả 5 năm."""
    ghsl_dir = raw_dir / "ghsl"
    summaries: list[dict[str, Any]] = []
    for yr in years:
        pop_tif = ghsl_dir / f"pop_100m_{yr}.tif"
        water_geojson = out_dir / f"water_{yr}.geojson"
        out_geojson = out_dir / f"pop_{yr}.geojson"
        res = export_population_grid_geojson(
            raster_path=pop_tif,
            year=yr,
            out_geojson=out_geojson,
            water_geojson=water_geojson,
        )
        summaries.append(res)
        print(
            f"[grid_to_geojson] {yr} | cells={res['cell_count']} "
            f"(in_buffer_500m={res['buffer_cell_count']}) | {res['file_size_kb']} KB"
        )
    return summaries
