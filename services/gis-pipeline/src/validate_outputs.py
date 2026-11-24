"""Tuần 6: Kiểm định chéo toàn diện dữ liệu thật (Schema, PostGIS Unique ID, Hình học, Tọa độ) & đóng gói bàn giao .zip."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from jsonschema import validate
from shapely.geometry import MultiPolygon, Polygon, shape

from src.config import REPO_ROOT, YEARS

DEFAULT_SCHEMAS_DIR = REPO_ROOT / "contracts" / "schemas"
PA3_LON_BOUNDS = (105.75, 105.96)
PA3_LAT_BOUNDS = (20.98, 21.18)
MAX_WATER_GEOJSON_KB = 500.0
MAX_POP_GEOJSON_KB = 1536.0


def audit_processed_outputs(
    processed_dir: Path,
    years: list[int] | None = None,
    schemas_dir: Path = DEFAULT_SCHEMAS_DIR,
) -> dict[str, Any]:
    """Kiểm định 4 lớp rào chắn cho toàn bộ 11 file hợp đồng trong data/processed/."""
    target_years = list(years) if years is not None else list(YEARS)

    water_schema = json.loads((schemas_dir / "water_layer.schema.json").read_text(encoding="utf-8"))
    pop_schema = json.loads((schemas_dir / "pop_layer.schema.json").read_text(encoding="utf-8"))
    ts_schema = json.loads((schemas_dir / "timeseries.schema.json").read_text(encoding="utf-8"))

    ts_path = processed_dir / "timeseries_summary.json"
    if not ts_path.exists():
        raise FileNotFoundError(f"Thiếu file hợp đồng {ts_path}.")

    ts_doc = json.loads(ts_path.read_text(encoding="utf-8"))
    validate(instance=ts_doc, schema=ts_schema)
    ts_by_year = {int(row["year"]): row for row in ts_doc["series"]}

    seen_water_ids: set[str] = set()
    seen_grid_ids: set[str] = set()
    total_water_features = 0
    total_pop_features = 0

    for yr in target_years:
        if yr not in ts_by_year:
            raise ValueError(f"timeseries_summary.json thiếu năm {yr}.")
        ts_row = ts_by_year[yr]

        # 1. Kiểm định water_{yr}.geojson
        w_path = processed_dir / f"water_{yr}.geojson"
        if not w_path.exists():
            raise FileNotFoundError(f"Thiếu file hợp đồng {w_path}.")
        w_kb = w_path.stat().st_size / 1024.0
        if w_kb > MAX_WATER_GEOJSON_KB:
            raise ValueError(f"{w_path.name} vượt ngưỡng dung lượng WebGIS ({w_kb:.1f} KB > {MAX_WATER_GEOJSON_KB} KB).")

        w_fc = json.loads(w_path.read_text(encoding="utf-8"))
        validate(instance=w_fc, schema=water_schema)

        active_sum = 0.0
        gain_sum = 0.0
        loss_sum = 0.0

        for feat in w_fc["features"]:
            props = feat["properties"]
            wid = props["water_id"]
            if wid in seen_water_ids:
                raise ValueError(f"Phát hiện trùng lặp water_id='{wid}' (sẽ lỗi unique constraint trong PostGIS).")
            seen_water_ids.add(wid)

            geom = shape(feat["geometry"])
            if geom.is_empty or not geom.is_valid:
                raise ValueError(f"Hình học không hợp lệ tại water_id='{wid}'.")
            if not isinstance(geom, (Polygon, MultiPolygon)):
                raise ValueError(f"Kiểu hình học không hợp lệ tại water_id='{wid}': {geom.geom_type}.")

            minx, miny, maxx, maxy = geom.bounds
            if not (PA3_LON_BOUNDS[0] <= minx <= maxx <= PA3_LON_BOUNDS[1]) or not (
                PA3_LAT_BOUNDS[0] <= miny <= maxy <= PA3_LAT_BOUNDS[1]
            ):
                raise ValueError(f"Tọa độ water_id='{wid}' nằm ngoài phạm vi EPSG:4326 PA3 Hà Nội: {geom.bounds}.")

            ctype = props["change_type"]
            area = float(props["area_km2"])
            if ctype in ("stable", "gain"):
                active_sum += area
            if ctype == "gain":
                gain_sum += area
            elif ctype == "loss":
                loss_sum += area

        total_water_features += len(w_fc["features"])

        # Kiểm tra khớp số liệu chéo giữa GeoJSON và timeseries_summary.json
        if abs(active_sum - float(ts_row["water_area_km2"])) > 0.02:
            raise ValueError(
                f"Lệch diện tích nước năm {yr}: GeoJSON={active_sum:.3f} vs timeseries={ts_row['water_area_km2']}."
            )
        if abs(gain_sum - float(ts_row["water_gain_km2"])) > 0.02:
            raise ValueError(f"Lệch water_gain_km2 năm {yr}.")
        if abs(loss_sum - float(ts_row["water_loss_km2"])) > 0.02:
            raise ValueError(f"Lệch water_loss_km2 năm {yr}.")

        if yr <= 2020 and ts_row["jrc_iou_score"] is None:
            raise ValueError(f"Năm {yr} bắt buộc có jrc_iou_score hợp lệ.")
        if yr > 2020 and ts_row["jrc_iou_score"] is not None:
            raise ValueError(f"Năm {yr} bắt buộc để jrc_iou_score = null theo hợp đồng JRC v1.3.")

        # 2. Kiểm định pop_{yr}.geojson
        p_path = processed_dir / f"pop_{yr}.geojson"
        if not p_path.exists():
            raise FileNotFoundError(f"Thiếu file hợp đồng {p_path}.")
        p_kb = p_path.stat().st_size / 1024.0
        if p_kb > MAX_POP_GEOJSON_KB:
            raise ValueError(f"{p_path.name} vượt ngưỡng dung lượng WebGIS ({p_kb:.1f} KB > {MAX_POP_GEOJSON_KB} KB).")

        p_fc = json.loads(p_path.read_text(encoding="utf-8"))
        validate(instance=p_fc, schema=pop_schema)

        for feat in p_fc["features"]:
            props = feat["properties"]
            gid = props["grid_id"]
            if gid in seen_grid_ids:
                raise ValueError(f"Phát hiện trùng lặp grid_id='{gid}' (sẽ lỗi unique constraint trong PostGIS).")
            seen_grid_ids.add(gid)

            geom = shape(feat["geometry"])
            if geom.is_empty or not geom.is_valid or not isinstance(geom, Polygon):
                raise ValueError(f"Ô lưới không hợp lệ tại grid_id='{gid}'.")
            minx, miny, maxx, maxy = geom.bounds
            if not (PA3_LON_BOUNDS[0] <= minx <= maxx <= PA3_LON_BOUNDS[1]) or not (
                PA3_LAT_BOUNDS[0] <= miny <= maxy <= PA3_LAT_BOUNDS[1]
            ):
                raise ValueError(f"Tọa độ grid_id='{gid}' nằm ngoài phạm vi EPSG:4326 PA3 Hà Nội: {geom.bounds}.")

        total_pop_features += len(p_fc["features"])

    report = {
        "status": "PASSED",
        "years_verified": target_years,
        "contract_files_verified": len(target_years) * 2 + 1,
        "unique_water_polygons": total_water_features,
        "unique_population_cells": total_pop_features,
    }
    print(
        f"[verify] AUDIT PASSED | files={report['contract_files_verified']} | "
        f"water_polys={total_water_features} | pop_cells={total_pop_features} | 0 schema/PostGIS errors."
    )
    return report


def package_handover_bundles(
    raw_dir: Path,
    processed_dir: Path,
    aoi_path: Path,
    years: list[int] | None = None,
) -> dict[str, Path]:
    """Đóng gói 2 file .zip bàn giao cho Người B (seed PostGIS) và Người C & D (QGIS & Báo cáo Chương 5)."""
    target_years = list(years) if years is not None else list(YEARS)
    data_root = processed_dir.parent

    # 1. Gói cho Người B: giải nén thẳng vào data/processed/ để chạy seed.py
    bundle_b = data_root / "handover_for_B_processed.zip"
    with zipfile.ZipFile(bundle_b, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for fpath in sorted(processed_dir.glob("*")):
            if fpath.is_file() and fpath.suffix in (".geojson", ".json"):
                zf.write(fpath, arcname=fpath.name)

    # 2. Gói cho Người C & Người D: bản đồ QGIS + bảng số liệu Chương 5
    bundle_cd = data_root / "handover_for_C_D_qgis_report.zip"
    latest_yr = max(target_years)
    ref_yr = 2020 if 2020 in target_years else target_years[0]

    cd_candidates: list[tuple[Path, str]] = [(aoi_path, "aoi.geojson")]
    for yr in target_years:
        cd_candidates.append((processed_dir / f"water_{yr}.geojson", f"layers/water_{yr}.geojson"))
    cd_candidates.extend(
        [
            (processed_dir / f"pop_{latest_yr}.geojson", f"layers/pop_{latest_yr}.geojson"),
            (
                raw_dir / "ghsl" / f"water_buffer_500m_{latest_yr}.geojson",
                f"layers/water_buffer_500m_{latest_yr}.geojson",
            ),
            (
                raw_dir / "jrc" / "jrc_seasonality_2020_32648.tif",
                "rasters/jrc_seasonality_2020_32648.tif",
            ),
            (
                raw_dir / "sentinel2" / str(ref_yr) / "composite" / f"mndwi_{ref_yr}.tif",
                f"rasters/mndwi_{ref_yr}.tif",
            ),
            (processed_dir / "timeseries_summary.json", "metrics/timeseries_summary.json"),
            (processed_dir / "water_change_metrics.json", "metrics/water_change_metrics.json"),
            (processed_dir / "jrc_validation_summary.json", "metrics/jrc_validation_summary.json"),
            (processed_dir / "pop_overlay_metrics.json", "metrics/pop_overlay_metrics.json"),
        ]
    )

    with zipfile.ZipFile(bundle_cd, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for src_file, arc_name in cd_candidates:
            if src_file.exists():
                zf.write(src_file, arcname=arc_name)

    b_kb = bundle_b.stat().st_size / 1024.0
    cd_mb = bundle_cd.stat().st_size / (1024.0 * 1024.0)
    print(f"[verify] Packaged B bundle -> {bundle_b} ({b_kb:.1f} KB)")
    print(f"[verify] Packaged C & D bundle -> {bundle_cd} ({cd_mb:.2f} MB)")
    return {"bundle_b": bundle_b, "bundle_cd": bundle_cd}
