"""Tuần 5: Tạo vùng đệm Buffer 500m quanh mặt nước hiện hữu (EPSG:32648) & đếm dân số bằng rasterio.mask."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask as rasterio_mask
from shapely.geometry import mapping

from src.config import BUFFER_RADIUS_METERS, CRS_METRIC, CRS_STORAGE
from src.water.fetch_stac import load_aoi


def load_active_water_32648(water_geojson: Path) -> gpd.GeoDataFrame:
    """Đọc đa giác mặt nước hiện hữu (chỉ lấy stable + gain, loại bỏ loss) và chiếu sang EPSG:32648."""
    gdf = gpd.read_file(water_geojson)
    if gdf.empty:
        return gpd.GeoDataFrame({"geometry": []}, crs=CRS_METRIC)
    if "change_type" in gdf.columns:
        gdf = gdf[gdf["change_type"].isin(["stable", "gain"])].copy()
    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_STORAGE)
    return gdf.to_crs(CRS_METRIC)


def compute_pop_in_water_buffer(
    water_geojson: Path,
    pop_raster_path: Path,
    aoi_path: Path | None = None,
    buffer_m: float = BUFFER_RADIUS_METERS,
    out_buffer_geojson: Path | None = None,
) -> dict[str, float | int]:
    """Tính tổng dân số toàn AOI và dân số nằm trong hành lang Buffer 500m quanh mặt nước hiện hữu."""
    active_water = load_active_water_32648(water_geojson)
    with rasterio.open(pop_raster_path) as src:
        pop_arr = src.read(1)
        valid_all = np.isfinite(pop_arr) & (pop_arr >= 0.0)
        total_pop = int(round(float(pop_arr[valid_all].sum())))

        if active_water.empty:
            return {
                "total_pop": total_pop,
                "pop_in_buffer_500m": 0,
                "pop_buffer_ratio_pct": 0.0,
                "buffer_area_km2": 0.0,
            }

        water_union = active_water.geometry.union_all()
        buffer_geom = water_union.buffer(buffer_m)
        if aoi_path is not None and aoi_path.exists():
            _, aoi_32648 = load_aoi(aoi_path)
            buffer_geom = buffer_geom.intersection(aoi_32648.geometry.union_all())

        if out_buffer_geojson is not None:
            out_buffer_geojson.parent.mkdir(parents=True, exist_ok=True)
            buf_gdf = gpd.GeoDataFrame({"buffer_m": [buffer_m]}, geometry=[buffer_geom], crs=CRS_METRIC).to_crs(
                CRS_STORAGE
            )
            buf_gdf.to_file(out_buffer_geojson, driver="GeoJSON")

        masked, _ = rasterio_mask(
            src,
            [mapping(buffer_geom)],
            crop=False,
            filled=True,
            nodata=-1.0,
        )
        valid_buf = np.isfinite(masked[0]) & (masked[0] >= 0.0)
        pop_in_buf = int(round(float(masked[0][valid_buf].sum())))

    ratio_pct = round(pop_in_buf / total_pop * 100.0, 2) if total_pop > 0 else 0.0
    return {
        "total_pop": total_pop,
        "pop_in_buffer_500m": pop_in_buf,
        "pop_buffer_ratio_pct": ratio_pct,
        "buffer_area_km2": round(float(buffer_geom.area) / 1_000_000.0, 3),
    }


def run_spatial_overlay_all_years(
    raw_dir: Path,
    out_dir: Path,
    aoi_path: Path,
    years: list[int],
    buffer_m: float = BUFFER_RADIUS_METERS,
) -> dict[str, Any]:
    """Chạy chồng lớp Buffer 500m cho cả 5 năm và lưu pop_overlay_metrics.json."""
    ghsl_dir = raw_dir / "ghsl"
    by_year: dict[str, Any] = {}

    for yr in years:
        water_geojson = out_dir / f"water_{yr}.geojson"
        pop_tif = ghsl_dir / f"pop_100m_{yr}.tif"
        buf_geojson = ghsl_dir / f"water_buffer_500m_{yr}.geojson"

        if not water_geojson.exists():
            raise FileNotFoundError(f"Thiếu {water_geojson}. Hãy chạy --step vectorize trước.")
        if not pop_tif.exists():
            raise FileNotFoundError(f"Thiếu {pop_tif}. Hãy chạy bước nội suy GHSL trước.")

        res = compute_pop_in_water_buffer(
            water_geojson=water_geojson,
            pop_raster_path=pop_tif,
            aoi_path=aoi_path,
            buffer_m=buffer_m,
            out_buffer_geojson=buf_geojson,
        )
        res["year"] = yr
        by_year[str(yr)] = res
        print(
            f"[spatial_overlay] {yr} | total_pop={res['total_pop']:,} | "
            f"pop_in_buffer_500m={res['pop_in_buffer_500m']:,} ({res['pop_buffer_ratio_pct']:.2f}%) | "
            f"buffer_area={res['buffer_area_km2']:.2f} km²"
        )

    doc = {
        "buffer_radius_m": buffer_m,
        "crs_metric": CRS_METRIC,
        "years": by_year,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "pop_overlay_metrics.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return doc
