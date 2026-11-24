"""Tuần 4: Đối chứng độ khớp (IoU, F1, OA, Precision, Recall) giữa mặt nước Sentinel-2 MNDWI và JRC Global Surface Water."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import planetary_computer as pc
import pystac_client
import rasterio
from rasterio.warp import Resampling, reproject

from src.config import CRS_METRIC, MIN_WATER_AREA_KM2, WATER_MASK_NODATA
from src.water.fetch_stac import STAC_API_URL
from src.water.vectorize import clean_binary_water_mask

JRC_COLLECTION = "jrc-gsw"


def compute_iou(pred_mask: np.ndarray, ref_mask: np.ndarray) -> float:
    """Tính chỉ số Intersection over Union (IoU) giữa 2 mảng nhị phân."""
    pred = pred_mask.astype(bool)
    ref = ref_mask.astype(bool)
    union = np.logical_or(pred, ref).sum()
    if union == 0:
        return 0.0
    intersection = np.logical_and(pred, ref).sum()
    return float(intersection / union)


def compute_validation_metrics(
    pred_mask: np.ndarray,
    ref_mask: np.ndarray,
    valid_mask: np.ndarray | None = None,
    pixel_area_km2: float = 0.0001,
) -> dict[str, float | int]:
    """Tính đầy đủ bộ chỉ số đối chứng học thuật: IoU, F1 (Dice), OA, Precision, Recall và diện tích."""
    pred = pred_mask.astype(bool)
    ref = ref_mask.astype(bool)
    if valid_mask is not None:
        v = valid_mask.astype(bool)
        pred = pred[v]
        ref = ref[v]
    else:
        pred = pred.ravel()
        ref = ref.ravel()

    total = int(pred.size)
    if total == 0:
        return {
            "iou": 0.0,
            "f1_score": 0.0,
            "overall_accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "pred_area_km2": 0.0,
            "ref_area_km2": 0.0,
            "tp_pixels": 0,
            "fp_pixels": 0,
            "fn_pixels": 0,
            "tn_pixels": 0,
        }

    tp = int(np.logical_and(pred, ref).sum())
    fp = int(np.logical_and(pred, ~ref).sum())
    fn = int(np.logical_and(~pred, ref).sum())
    tn = int(np.logical_and(~pred, ~ref).sum())

    union = tp + fp + fn
    iou = float(tp / union) if union > 0 else 0.0
    precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    f1 = float(2 * tp / (2 * tp + fp + fn)) if (2 * tp + fp + fn) > 0 else 0.0
    oa = float((tp + tn) / total)

    return {
        "iou": round(iou, 4),
        "f1_score": round(f1, 4),
        "overall_accuracy": round(oa, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "pred_area_km2": round(float((tp + fp) * pixel_area_km2), 3),
        "ref_area_km2": round(float((tp + fn) * pixel_area_km2), 3),
        "tp_pixels": tp,
        "fp_pixels": fp,
        "fn_pixels": fn,
        "tn_pixels": tn,
    }


def fetch_and_align_jrc_rasters(
    aoi_path: Path,
    ref_mask_path: Path,
    raw_dir: Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Tải và chiếu lớp seasonality (2020) & occurrence (1984-2020) của JRC-GSW khớp lưới 10m EPSG:32648."""
    jrc_dir = raw_dir / "jrc"
    jrc_dir.mkdir(parents=True, exist_ok=True)
    seas_tif = jrc_dir / "jrc_seasonality_2020_32648.tif"
    occ_tif = jrc_dir / "jrc_occurrence_32648.tif"
    meta_json = jrc_dir / "jrc_metadata.json"

    if not overwrite and seas_tif.exists() and occ_tif.exists() and meta_json.exists():
        meta = json.loads(meta_json.read_text(encoding="utf-8"))
        return {"seasonality": seas_tif, "occurrence": occ_tif, "item_id": meta["item_id"]}

    aoi_gdf = gpd.read_file(aoi_path)
    catalog = pystac_client.Client.open(STAC_API_URL, modifier=pc.sign_inplace)
    items = list(catalog.search(collections=[JRC_COLLECTION], bbox=list(aoi_gdf.total_bounds)).items())
    if not items:
        raise RuntimeError("Không tìm thấy dữ liệu jrc-gsw phủ AOI trên Planetary Computer.")

    item = items[0]
    with rasterio.open(ref_mask_path) as ref_src:
        dst_crs = ref_src.crs
        dst_transform = ref_src.transform
        dst_shape = ref_src.shape
        out_profile = ref_src.profile.copy()

    out_profile.update(
        {
            "driver": "GTiff",
            "dtype": "uint8",
            "count": 1,
            "nodata": 255,
            "compress": "deflate",
            "tiled": True,
        }
    )

    gdal_env = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF",
    }

    for asset_key, out_path in (("seasonality", seas_tif), ("occurrence", occ_tif)):
        href = item.assets[asset_key].href
        aligned = np.full(dst_shape, 255, dtype=np.uint8)
        with rasterio.Env(**gdal_env):
            with rasterio.open(href) as jrc_src:
                reproject(
                    source=rasterio.band(jrc_src, 1),
                    destination=aligned,
                    src_transform=jrc_src.transform,
                    src_crs=jrc_src.crs,
                    dst_transform=dst_transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.nearest,
                )
        with rasterio.open(out_path, "w", **out_profile) as dst:
            dst.write(aligned, 1)

    meta = {
        "collection": JRC_COLLECTION,
        "item_id": item.id,
        "crs": dst_crs.to_string() if dst_crs else CRS_METRIC,
        "shape": list(dst_shape),
        "note": "JRC Global Surface Water v1.3 (30m Landsat resampled to 10m EPSG:32648 grid, reference up to 2020).",
    }
    meta_json.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"seasonality": seas_tif, "occurrence": occ_tif, "item_id": item.id}


def run_jrc_validation(
    raw_dir: Path,
    out_dir: Path,
    aoi_path: Path,
    years: list[int],
    overwrite: bool = False,
) -> dict[str, Any]:
    """Đối chứng mặt nạ nước Sentinel-2 đã khử nhiễu với JRC Global Surface Water và xuất JSON tổng hợp."""
    ref_year = 2020 if 2020 in years else years[0]
    ref_mask_path = raw_dir / "sentinel2" / str(ref_year) / "composite" / f"water_mask_{ref_year}.tif"
    if not ref_mask_path.exists():
        raise FileNotFoundError(f"Thiếu {ref_mask_path} để làm lưới chuẩn đối chứng JRC.")

    jrc_info = fetch_and_align_jrc_rasters(
        aoi_path=aoi_path,
        ref_mask_path=ref_mask_path,
        raw_dir=raw_dir,
        overwrite=overwrite,
    )

    with rasterio.open(jrc_info["seasonality"]) as s_src:
        jrc_seas = s_src.read(1)
        pixel_area_m2 = abs(float(s_src.res[0] * s_src.res[1]))
        pixel_area_km2 = pixel_area_m2 / 1_000_000.0
    with rasterio.open(jrc_info["occurrence"]) as o_src:
        jrc_occ = o_src.read(1)

    min_pixels = max(1, int(round((MIN_WATER_AREA_KM2 * 1_000_000.0) / pixel_area_m2)))
    # JRC seasonality: 1..12 tháng có nước trong năm 2020 (255 là NoData ngoài AOI)
    jrc_water_2020 = (jrc_seas >= 1) & (jrc_seas <= 12)
    # JRC occurrence >= 25%: mặt nước thường xuyên lịch sử 1984-2020
    jrc_occ_25 = (jrc_occ >= 25) & (jrc_occ <= 100)

    by_year: dict[str, Any] = {}
    for yr in years:
        mask_tif = raw_dir / "sentinel2" / str(yr) / "composite" / f"water_mask_{yr}.tif"
        if not mask_tif.exists():
            continue
        with rasterio.open(mask_tif) as m_src:
            s2_raw = m_src.read(1)

        valid_mask = (s2_raw != WATER_MASK_NODATA) & (jrc_seas != 255)
        s2_clean = clean_binary_water_mask(s2_raw == 1, min_pixels=min_pixels)

        seas_metrics = compute_validation_metrics(
            pred_mask=s2_clean,
            ref_mask=jrc_water_2020,
            valid_mask=valid_mask,
            pixel_area_km2=pixel_area_km2,
        )
        occ_metrics = compute_validation_metrics(
            pred_mask=s2_clean,
            ref_mask=jrc_occ_25,
            valid_mask=valid_mask,
            pixel_area_km2=pixel_area_km2,
        )

        # JRC v1.3 kết thúc ở năm 2020 -> gán jrc_iou_score chính thức cho các năm <= 2020, null cho 2022 & 2024
        official_iou: float | None = float(seas_metrics["iou"]) if yr <= 2020 else None

        by_year[str(yr)] = {
            "year": yr,
            "jrc_iou_score": official_iou,
            "vs_jrc_seasonality_2020": seas_metrics,
            "vs_jrc_occurrence_25pct": occ_metrics,
        }
        print(
            f"[validate_jrc] {yr} | IoU(seasonality)={seas_metrics['iou']:.4f} | "
            f"F1={seas_metrics['f1_score']:.4f} | OA={seas_metrics['overall_accuracy'] * 100:.2f}% | "
            f"S2={seas_metrics['pred_area_km2']:.2f} km² vs JRC={seas_metrics['ref_area_km2']:.2f} km² | "
            f"timeseries_iou={official_iou}"
        )

    summary = {
        "jrc_stac_item": jrc_info["item_id"],
        "jrc_native_resolution_m": 30,
        "s2_native_resolution_m": 10,
        "crs_metric": CRS_METRIC,
        "methodology_note": (
            "JRC Global Surface Water v1.3 (1984-2020, 30m Landsat) seasonality>=1 month used as official "
            "reference for years <= 2020; years > 2020 report null in timeseries_summary.json per contract."
        ),
        "years": by_year,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "jrc_validation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary
