"""Tuần 2: Truy vấn Planetary Computer STAC API & cắt ảnh Sentinel-2 L2A trên lưới gốc EPSG:32648."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import planetary_computer as pc
import pystac_client
import rasterio
from rasterio.mask import mask as rasterio_mask
from shapely.geometry import mapping, shape

from src.config import (
    CRS_METRIC,
    CRS_STORAGE,
    DRY_SEASON_WINDOW,
    INVALID_SCL_CLASSES,
    MAX_CLOUD_COVER_PCT,
)

logger = logging.getLogger(__name__)

STAC_API_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
SENTINEL2_COLLECTION = "sentinel-2-l2a"
REQUIRED_BANDS: tuple[str, ...] = ("SCL", "B03", "B11")
MIN_AOI_COVERAGE_RATIO = 0.95
SECONDARY_DRY_WINDOW: tuple[str, str] = ("10-01", "12-31")
TARGET_COMBINED_CLEAR_PCT = 98.0
MAX_SCENE_AOI_CLOUD_PCT = 40.0


def load_aoi(aoi_path: Path) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Đọc AOI ở EPSG:4326 và chiếu sẵn sang EPSG:32648 để cắt ảnh trực tiếp trên lưới mét gốc."""
    aoi_4326 = gpd.read_file(aoi_path)
    if aoi_4326.crs is None:
        aoi_4326 = aoi_4326.set_crs(CRS_STORAGE)
    elif aoi_4326.crs.to_string() != CRS_STORAGE:
        aoi_4326 = aoi_4326.to_crs(CRS_STORAGE)

    aoi_32648 = aoi_4326.to_crs(CRS_METRIC)
    return aoi_4326, aoi_32648


def build_datetime_range(year: int, season_window: tuple[str, str] = DRY_SEASON_WINDOW) -> str:
    """Tạo chuỗi khoảng thời gian STAC ISO-8601 cho mùa khô của một năm."""
    start_md, end_md = season_window
    return f"{year}-{start_md}/{year}-{end_md}"


def _item_crs_is_metric(item: Any) -> bool:
    """Kiểm tra STAC item có hệ tọa độ gốc EPSG:32648 (hỗ trợ cả proj:code v2 và proj:epsg v1)."""
    proj_code = item.properties.get("proj:code")
    proj_epsg = item.properties.get("proj:epsg")
    return proj_code == CRS_METRIC or proj_epsg == 32648


def _item_acq_date(item: Any) -> str:
    """Trích xuất ngày chụp YYYY-MM-DD của STAC item để chống trùng cảnh tái xử lý cùng ngày."""
    if getattr(item, "datetime", None):
        return item.datetime.date().isoformat()
    raw_dt = str(item.properties.get("datetime", ""))
    return raw_dt[:10] if raw_dt else item.id


def filter_and_rank_items(
    items: list[Any],
    aoi_4326_geom: Any,
    max_scenes: int = 3,
    min_coverage: float = MIN_AOI_COVERAGE_RATIO,
) -> list[Any]:
    """Lọc cảnh phủ đủ AOI (>= 95%), khử trùng cùng ngày chụp, ưu tiên EPSG:32648 và ít mây nhất."""
    aoi_area = aoi_4326_geom.area
    by_date: dict[str, tuple[int, float, str, Any]] = {}

    for item in items:
        if item.geometry is None:
            continue
        item_geom = shape(item.geometry)
        coverage = item_geom.intersection(aoi_4326_geom).area / aoi_area if aoi_area > 0 else 0.0
        if coverage < min_coverage:
            continue

        crs_rank = 0 if _item_crs_is_metric(item) else 1
        cloud_pct = float(item.properties.get("eo:cloud_cover", 100.0))
        acq_date = _item_acq_date(item)

        # Nếu cùng ngày chụp có nhiều bản tái xử lý (reprocessed), giữ bản có item.id mới hơn
        existing = by_date.get(acq_date)
        if existing is None or (crs_rank, cloud_pct) < (existing[0], existing[1]) or (
            (crs_rank, cloud_pct) == (existing[0], existing[1]) and item.id > existing[2]
        ):
            by_date[acq_date] = (crs_rank, cloud_pct, item.id, item)

    ranked = sorted(by_date.values(), key=lambda row: (row[0], row[1]))
    return [item for _, _, _, item in ranked[:max_scenes]]


def compute_scl_stats_from_array(scl_array: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Tính mặt nạ pixel quang mây (bool), % mây/bóng mây trong AOI và % pixel hợp lệ từ mảng SCL."""
    inside_aoi = scl_array > 0
    total_aoi_pixels = int(inside_aoi.sum())
    if total_aoi_pixels == 0:
        return np.zeros_like(scl_array, dtype=bool), 100.0, 0.0

    bad_mask = np.isin(scl_array, INVALID_SCL_CLASSES) & inside_aoi
    clear_mask = inside_aoi & ~bad_mask
    cloud_pct = float(bad_mask.sum() / total_aoi_pixels * 100.0)
    valid_pct = float(clear_mask.sum() / total_aoi_pixels * 100.0)
    return clear_mask, round(cloud_pct, 2), round(valid_pct, 2)


def compute_combined_clear_coverage(clear_masks: list[np.ndarray], inside_aoi: np.ndarray | None = None) -> float:
    """Tính tỷ lệ % diện tích AOI có ít nhất 1 cảnh quang mây khi gộp nhiều cảnh."""
    if not clear_masks:
        return 0.0
    combined = np.zeros_like(clear_masks[0], dtype=bool)
    for mask in clear_masks:
        combined |= mask

    if inside_aoi is not None:
        total = int(inside_aoi.sum())
        valid = int((combined & inside_aoi).sum())
    else:
        total = int(combined.size)
        valid = int(combined.sum())

    if total == 0:
        return 0.0
    return round(float(valid / total * 100.0), 2)


def search_candidate_pool(
    aoi_4326_geom: Any,
    year: int,
    max_cloud_pct: float = MAX_CLOUD_COVER_PCT,
    season_window: tuple[str, str] = DRY_SEASON_WINDOW,
    pool_size: int = 8,
) -> list[tuple[Any, str]]:
    """Thu thập danh sách ứng viên ưu tiên mùa khô chính (T1–T4) trước, sau đó mới bổ sung đầu mùa khô (T10–T12)."""
    catalog = pystac_client.Client.open(STAC_API_URL, modifier=pc.sign_inplace)
    aoi_geojson_geom = mapping(aoi_4326_geom)

    stages: list[tuple[tuple[str, str], float, str]] = [
        (season_window, max_cloud_pct, "primary_dry_strict"),
        (season_window, 25.0, "primary_dry_relaxed_25"),
        (season_window, 35.0, "primary_dry_relaxed_35"),
        (SECONDARY_DRY_WINDOW, 25.0, "secondary_dry_oct_dec"),
        (SECONDARY_DRY_WINDOW, 35.0, "secondary_dry_oct_dec_35"),
    ]

    seen_dates: set[str] = set()
    ordered_pool: list[tuple[Any, str]] = []

    for win, cloud_limit, stage_label in stages:
        dt_range = build_datetime_range(year, win)
        search = catalog.search(
            collections=[SENTINEL2_COLLECTION],
            intersects=aoi_geojson_geom,
            datetime=dt_range,
            query={"eo:cloud_cover": {"lt": cloud_limit}},
        )
        ranked = filter_and_rank_items(list(search.items()), aoi_4326_geom, max_scenes=pool_size)
        for item in ranked:
            acq_date = _item_acq_date(item)
            if acq_date in seen_dates:
                continue
            seen_dates.add(acq_date)
            ordered_pool.append((item, stage_label))
            if len(ordered_pool) >= pool_size:
                return ordered_pool

    if not ordered_pool:
        raise RuntimeError(
            f"Không tìm thấy cảnh Sentinel-2 L2A nào phủ AOI trong năm {year} trên Planetary Computer."
        )
    return ordered_pool


def clip_asset_to_aoi(
    asset_href: str,
    aoi_32648: gpd.GeoDataFrame,
    out_tif: Path,
    overwrite: bool = False,
) -> Path:
    """Đọc cắt cửa sổ (Windowed COG Read) đúng vùng AOI trên lưới gốc EPSG:32648 và lưu GeoTIFF nén."""
    if out_tif.exists() and not overwrite:
        return out_tif

    out_tif.parent.mkdir(parents=True, exist_ok=True)
    gdal_env = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF",
    }

    with rasterio.Env(**gdal_env):
        with rasterio.open(asset_href) as src:
            if src.crs and src.crs.to_string() == CRS_METRIC:
                clip_gdf = aoi_32648
            else:
                clip_gdf = aoi_32648.to_crs(src.crs)

            geoms = [mapping(geom) for geom in clip_gdf.geometry]
            out_image, out_transform = rasterio_mask(
                src,
                geoms,
                crop=True,
                filled=True,
                nodata=0,
            )

            out_meta = src.meta.copy()
            out_meta.update(
                {
                    "driver": "GTiff",
                    "height": out_image.shape[1],
                    "width": out_image.shape[2],
                    "transform": out_transform,
                    "nodata": 0,
                    "compress": "deflate",
                    "tiled": True,
                }
            )

            with rasterio.open(out_tif, "w", **out_meta) as dst:
                dst.write(out_image)

    return out_tif


def fetch_sentinel2_for_year(
    aoi_path: Path,
    year: int,
    out_dir: Path,
    max_cloud_pct: float = MAX_CLOUD_COVER_PCT,
    season_window: tuple[str, str] = DRY_SEASON_WINDOW,
    max_scenes: int = 3,
    min_scenes: int = 2,
    target_clear_pct: float = TARGET_COMBINED_CLEAR_PCT,
    overwrite: bool = False,
) -> Path:
    """Tìm cảnh Sentinel-2 L2A mùa khô, chấm điểm độ sạch SCL trong AOI và tải đủ cảnh đạt >= 98% sạch mây."""
    aoi_4326, aoi_32648 = load_aoi(aoi_path)
    aoi_union_4326 = aoi_4326.geometry.union_all()

    candidate_pool = search_candidate_pool(
        aoi_4326_geom=aoi_union_4326,
        year=year,
        max_cloud_pct=max_cloud_pct,
        season_window=season_window,
        pool_size=max(max_scenes * 2, 6),
    )

    year_dir = out_dir / "sentinel2" / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)

    manifest_scenes: list[dict[str, Any]] = []
    clear_masks: list[np.ndarray] = []
    inside_aoi_ref: np.ndarray | None = None
    combined_clear_pct = 0.0

    for item, stage_label in candidate_pool:
        # Dừng sớm nếu đã đạt tối thiểu min_scenes và độ phủ sạch gộp >= target_clear_pct
        if len(manifest_scenes) >= min_scenes and combined_clear_pct >= target_clear_pct:
            break
        if len(manifest_scenes) >= max_scenes and combined_clear_pct >= target_clear_pct:
            break
        if len(manifest_scenes) >= max(max_scenes, 4):
            break

        scene_dir = year_dir / item.id
        scene_dir.mkdir(parents=True, exist_ok=True)

        # Bước 3a: Cắt nhanh SCL.tif (~75 KB) trước để chấm độ mây thực tế trong AOI
        if "SCL" not in item.assets:
            raise KeyError(f"Scene {item.id} thiếu asset 'SCL'.")
        scl_tif = scene_dir / "SCL.tif"
        clip_asset_to_aoi(item.assets["SCL"].href, aoi_32648, scl_tif, overwrite=overwrite)

        with rasterio.open(scl_tif) as scl_src:
            scl_arr = scl_src.read(1)
            clear_mask, aoi_cloud_pct, aoi_valid_pct = compute_scl_stats_from_array(scl_arr)

        if aoi_cloud_pct > MAX_SCENE_AOI_CLOUD_PCT:
            logger.info(
                "[fetch_stac] Bỏ qua %s (%s): mây thực tế trong AOI = %.2f%% (> %.1f%%).",
                item.id,
                _item_acq_date(item),
                aoi_cloud_pct,
                MAX_SCENE_AOI_CLOUD_PCT,
            )
            scl_tif.unlink(missing_ok=True)
            try:
                scene_dir.rmdir()
            except OSError:
                pass
            continue

        if inside_aoi_ref is None:
            inside_aoi_ref = scl_arr > 0

        # Bước 3b: Cảnh đạt chuẩn mây trong AOI -> mới cắt B03.tif (10m) và B11.tif (20m)
        band_paths: dict[str, str] = {"SCL": scl_tif.name}
        for band in ("B03", "B11"):
            if band not in item.assets:
                raise KeyError(f"Scene {item.id} thiếu asset '{band}'.")
            href = item.assets[band].href
            out_tif = scene_dir / f"{band}.tif"
            clip_asset_to_aoi(href, aoi_32648, out_tif, overwrite=overwrite)
            band_paths[band] = out_tif.name

        clear_masks.append(clear_mask)
        combined_clear_pct = compute_combined_clear_coverage(clear_masks, inside_aoi=inside_aoi_ref)

        crs_str = item.properties.get("proj:code")
        if not crs_str and item.properties.get("proj:epsg"):
            crs_str = f"EPSG:{item.properties['proj:epsg']}"
        if not crs_str:
            with rasterio.open(scene_dir / "B03.tif") as src_b03:
                crs_str = src_b03.crs.to_string() if src_b03.crs else CRS_METRIC

        scene_meta = {
            "scene_id": item.id,
            "year": year,
            "datetime": item.datetime.isoformat() if item.datetime else item.properties.get("datetime"),
            "selection_stage": stage_label,
            "tile_cloud_cover_pct": round(float(item.properties.get("eo:cloud_cover", 0.0)), 2),
            "aoi_cloud_cover_pct": aoi_cloud_pct,
            "aoi_valid_pixel_pct": aoi_valid_pct,
            "crs": crs_str,
            "mgrs_tile": item.properties.get("s2:mgrs_tile"),
            "processing_baseline": item.properties.get("s2:processing_baseline"),
            "bands": band_paths,
        }
        (scene_dir / "metadata.json").write_text(
            json.dumps(scene_meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        manifest_scenes.append(scene_meta)
        print(
            f"[fetch_stac] {year} | {item.id} | date={str(scene_meta['datetime'])[:10]} | "
            f"tile_cloud={scene_meta['tile_cloud_cover_pct']:.2f}% | "
            f"aoi_cloud={aoi_cloud_pct:.2f}% | combined_clear={combined_clear_pct:.2f}% | "
            f"{stage_label}"
        )

    mean_aoi_cloud = round(
        sum(s["aoi_cloud_cover_pct"] for s in manifest_scenes) / len(manifest_scenes), 2
    )
    manifest = {
        "year": year,
        "aoi_path": str(aoi_path),
        "crs_metric": CRS_METRIC,
        "scene_count": len(manifest_scenes),
        "combined_clear_coverage_pct": combined_clear_pct,
        "mean_aoi_cloud_cover_pct": mean_aoi_cloud,
        "scenes": manifest_scenes,
    }
    (year_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return year_dir
