"""Tuần 5: Tải tự động GHSL GHS-POP R2023A (2015, 2020, 2025), chiếu bảo toàn dân số sang EPSG:32648 (100m) & nội suy tuyến tính 2016..2024."""

from __future__ import annotations

import math
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pyproj
import rasterio
import requests
from rasterio.features import geometry_mask
from rasterio.mask import mask as rasterio_mask
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from shapely.geometry import mapping

from src.config import CRS_METRIC
from src.water.fetch_stac import load_aoi

GHSL_EPOCHS = (2015, 2020, 2025)
GHSL_NODATA = -1.0


def interpolate_population_grid(
    grid_start: np.ndarray,
    grid_end: np.ndarray,
    year_start: int,
    year_end: int,
    target_year: int,
) -> np.ndarray:
    """Nội suy tuyến tính theo từng pixel giữa 2 mốc năm GHSL liền kề."""
    if year_end == year_start:
        return grid_start.astype(np.float32)
    weight = (target_year - year_start) / (year_end - year_start)
    return ((1.0 - weight) * grid_start + weight * grid_end).astype(np.float32)


def compute_ghsl_tile_id(lon: float, lat: float) -> str:
    """Tính mã ô lưới 1000x1000 km của GHSL (ESRI:54009 World Mollweide) từ tọa độ WGS84."""
    transformer = pyproj.Transformer.from_crs("EPSG:4326", "ESRI:54009", always_xy=True)
    x, y = transformer.transform(lon, lat)
    col = int((x - (-18041000.0)) // 1_000_000.0) + 1
    row = int((9000000.0 - y) // 1_000_000.0) + 1
    return f"R{row}_C{col}"


def build_ghsl_tile_url(epoch: int, tile_id: str) -> str:
    """Tạo URL tải trực tiếp GHSL GHS-POP R2023A 100m từ máy chủ mở của EC JRC."""
    return (
        f"https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/"
        f"GHS_POP_GLOBE_R2023A/GHS_POP_E{epoch}_GLOBE_R2023A_54009_100/V1-0/"
        f"tiles/GHS_POP_E{epoch}_GLOBE_R2023A_54009_100_V1_0_{tile_id}.zip"
    )


def _build_aligned_100m_grid(aoi_32648: gpd.GeoDataFrame) -> tuple[rasterio.Affine, int, int]:
    """Tạo lưới 100m chuẩn trên EPSG:32648 căn chẵn bội số 500m để khớp cả lưới 100m lẫn 250m."""
    minx, miny, maxx, maxy = aoi_32648.total_bounds
    snap = 500.0
    west = math.floor(minx / snap) * snap
    south = math.floor(miny / snap) * snap
    east = math.ceil(maxx / snap) * snap
    north = math.ceil(maxy / snap) * snap

    width = int(round((east - west) / 100.0))
    height = int(round((north - south) / 100.0))
    transform = from_origin(west, north, 100.0, 100.0)
    return transform, height, width


def download_and_clip_ghsl_epoch(
    epoch: int,
    aoi_path: Path,
    ghsl_dir: Path,
    overwrite: bool = False,
) -> Path:
    """Tải mốc GHSL (2015/2020/2025), cắt theo AOI và chiếu bảo toàn tổng dân số sang EPSG:32648 (100m)."""
    ghsl_dir.mkdir(parents=True, exist_ok=True)
    out_tif = ghsl_dir / f"pop_100m_epoch_{epoch}.tif"
    if out_tif.exists() and not overwrite:
        return out_tif

    aoi_4326, aoi_32648 = load_aoi(aoi_path)
    centroid = aoi_4326.geometry.union_all().centroid
    tile_id = compute_ghsl_tile_id(float(centroid.x), float(centroid.y))
    url = build_ghsl_tile_url(epoch=epoch, tile_id=tile_id)

    zip_path = ghsl_dir / f"ghs_pop_{epoch}_{tile_id}.zip"
    if not zip_path.exists() or overwrite:
        print(f"[clip_population] Downloading GHSL {epoch} ({tile_id}) from EC JRC...")
        with requests.get(url, stream=True, timeout=180) as resp:
            resp.raise_for_status()
            with open(zip_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        fh.write(chunk)

    tmp_tif = ghsl_dir / f"_tmp_raw_{epoch}.tif"
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            tif_members = [n for n in zf.namelist() if n.lower().endswith(".tif")]
            if not tif_members:
                raise RuntimeError(f"Archive {zip_path} không chứa file .tif nào.")
            with zf.open(tif_members[0]) as src_zf, open(tmp_tif, "wb") as dst_tmp:
                while True:
                    buf = src_zf.read(1024 * 512)
                    if not buf:
                        break
                    dst_tmp.write(buf)

        with rasterio.open(tmp_tif) as src:
            aoi_54009 = aoi_4326.to_crs(src.crs)
            geoms_54009 = [mapping(g) for g in aoi_54009.geometry]
            # Mở rộng nhẹ khung cắt ở 54009 (buffer 300m) cho bước reproject, đồng thời tính tổng chuẩn trong AOI gốc
            exact_crop, _ = rasterio_mask(src, geoms_54009, crop=True, filled=True, nodata=-200.0)
            valid_exact = np.isfinite(exact_crop[0]) & (exact_crop[0] >= 0.0)
            total_native = float(exact_crop[0][valid_exact].sum())

            buffered_54009 = [mapping(g.buffer(300.0)) for g in aoi_54009.geometry]
            pad_crop, pad_transform = rasterio_mask(src, buffered_54009, crop=True, filled=True, nodata=-200.0)
            clean_src = np.where(np.isfinite(pad_crop[0]) & (pad_crop[0] >= 0.0), pad_crop[0], 0.0).astype(np.float32)
            src_crs = src.crs

        dst_transform, dst_h, dst_w = _build_aligned_100m_grid(aoi_32648)
        reproj = np.zeros((dst_h, dst_w), dtype=np.float32)
        reproject(
            source=clean_src,
            destination=reproj,
            src_transform=pad_transform,
            src_crs=src_crs,
            dst_transform=dst_transform,
            dst_crs=CRS_METRIC,
            resampling=Resampling.bilinear,
        )

        outside_aoi = geometry_mask(
            [mapping(g) for g in aoi_32648.geometry],
            out_shape=(dst_h, dst_w),
            transform=dst_transform,
            invert=False,
        )
        inside_aoi = ~outside_aoi
        reproj = np.maximum(reproj, 0.0)
        total_reproj = float(reproj[inside_aoi].sum())
        if total_reproj > 0 and total_native > 0:
            reproj[inside_aoi] *= float(total_native / total_reproj)
        reproj[outside_aoi] = GHSL_NODATA

        profile = {
            "driver": "GTiff",
            "dtype": "float32",
            "width": dst_w,
            "height": dst_h,
            "count": 1,
            "crs": CRS_METRIC,
            "transform": dst_transform,
            "nodata": GHSL_NODATA,
            "compress": "deflate",
        }
        with rasterio.open(out_tif, "w", **profile) as dst:
            dst.write(reproj, 1)

        print(
            f"[clip_population] Epoch {epoch} | native_pop={round(total_native):,} | "
            f"aligned_32648_pop={round(float(reproj[inside_aoi].sum())):,} | shape=({dst_h}, {dst_w})"
        )
    finally:
        tmp_tif.unlink(missing_ok=True)
        if out_tif.exists():
            zip_path.unlink(missing_ok=True)

    return out_tif


def run_population_interpolation(
    aoi_path: Path,
    raw_dir: Path,
    years: list[int],
    overwrite: bool = False,
) -> dict[int, Path]:
    """Tải 3 mốc gốc GHSL (2015, 2020, 2025) và nội suy tuyến tính ra pop_100m_{year}.tif cho từng năm."""
    ghsl_dir = raw_dir / "ghsl"
    epoch_rasters: dict[int, np.ndarray] = {}
    ref_profile: dict | None = None

    for ep in GHSL_EPOCHS:
        ep_tif = download_and_clip_ghsl_epoch(ep, aoi_path=aoi_path, ghsl_dir=ghsl_dir, overwrite=overwrite)
        with rasterio.open(ep_tif) as src:
            epoch_rasters[ep] = src.read(1)
            if ref_profile is None:
                ref_profile = src.profile.copy()

    assert ref_profile is not None
    valid_mask = epoch_rasters[2020] >= 0.0
    outputs: dict[int, Path] = {}

    for yr in years:
        out_tif = ghsl_dir / f"pop_100m_{yr}.tif"
        if yr <= 2020:
            y0, y1 = 2015, 2020
        else:
            y0, y1 = 2020, 2025

        interp = interpolate_population_grid(epoch_rasters[y0], epoch_rasters[y1], y0, y1, yr)
        interp = np.where(valid_mask, np.maximum(interp, 0.0), GHSL_NODATA).astype(np.float32)

        with rasterio.open(out_tif, "w", **ref_profile) as dst:
            dst.write(interp, 1)

        total_yr = int(round(float(interp[valid_mask].sum())))
        print(f"[clip_population] Interpolated {yr} ({y0}->{y1}) | total_pop={total_yr:,} -> {out_tif.name}")
        outputs[yr] = out_tif

    return outputs
