"""Tuần 5: Tổng hợp số liệu 5 mốc năm ra file timeseries_summary.json khớp chuẩn hợp đồng."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import validate

from src.config import CRS_METRIC, CRS_STORAGE, DEFAULT_AOI_PATH, REPO_ROOT

TIMESERIES_SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "timeseries.schema.json"


def build_timeseries_summary(
    processed_dir: Path,
    out_json: Path,
    aoi_path: Path = DEFAULT_AOI_PATH,
    schema_path: Path = TIMESERIES_SCHEMA_PATH,
) -> dict[str, Any]:
    """Ghép water_change_metrics + jrc_validation_summary + pop_overlay_metrics -> timeseries_summary.json."""
    aoi_doc = json.loads(aoi_path.read_text(encoding="utf-8"))
    aoi_props = aoi_doc["features"][0].get("properties", {})
    aoi_name = str(aoi_props.get("name", "Hành lang Sông Hồng – Hồ Tây – Đông Anh (Hà Nội)"))

    water_doc = json.loads((processed_dir / "water_change_metrics.json").read_text(encoding="utf-8"))
    jrc_doc = json.loads((processed_dir / "jrc_validation_summary.json").read_text(encoding="utf-8"))
    pop_doc = json.loads((processed_dir / "pop_overlay_metrics.json").read_text(encoding="utf-8"))

    aoi_area_km2 = round(float(water_doc["aoi_area_km2"]), 2)
    water_by_yr = {int(item["year"]): item for item in water_doc["years"]}
    jrc_by_yr = {int(k): v for k, v in jrc_doc["years"].items()}
    pop_by_yr = {int(k): v for k, v in pop_doc["years"].items()}

    years = sorted(water_by_yr.keys())
    series: list[dict[str, Any]] = []

    for yr in years:
        w = water_by_yr[yr]
        p = pop_by_yr[yr]
        j = jrc_by_yr.get(yr, {})
        raw_iou = j.get("jrc_iou_score")
        jrc_iou = round(float(raw_iou), 4) if raw_iou is not None else None

        series.append(
            {
                "year": yr,
                "water_area_km2": round(float(w["water_area_km2"]), 2),
                "water_ratio_pct": round(float(w["water_ratio_pct"]), 2),
                "water_gain_km2": round(float(w["water_gain_km2"]), 2),
                "water_loss_km2": round(float(w["water_loss_km2"]), 2),
                "otsu_threshold": round(float(w["otsu_threshold"]), 4),
                "cloud_cover_pct": round(float(w.get("cloud_cover_pct", 0.0)), 2),
                "total_pop": int(p["total_pop"]),
                "pop_in_buffer_500m": int(p["pop_in_buffer_500m"]),
                "pop_buffer_ratio_pct": round(float(p["pop_buffer_ratio_pct"]), 2),
                "jrc_iou_score": jrc_iou,
            }
        )

    summary_doc = {
        "aoi_name": aoi_name,
        "aoi_area_km2": aoi_area_km2,
        "crs_storage": CRS_STORAGE,
        "crs_metric": CRS_METRIC,
        "years": years,
        "series": series,
    }

    if schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validate(instance=summary_doc, schema=schema)

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[build_timeseries] Wrote {out_json} ({len(series)} years validated against schema).")
    return summary_doc
