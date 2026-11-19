"""Unified unit tests for Người A's GIS pipeline (MNDWI, PB 04.00 offset, IoU, population, schemas)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from jsonschema import validate

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from src.population.clip_population import interpolate_population_grid
from src.water.mndwi_otsu import compute_mndwi
from src.water.preprocess import apply_pb0400_offset
from src.water.validate_jrc import compute_iou

ROOT = PIPELINE_ROOT.parents[1]


def test_compute_mndwi_basic() -> None:
    b03 = np.array([[0.3, 0.2]], dtype=np.float32)
    b11 = np.array([[0.1, 0.6]], dtype=np.float32)
    mndwi = compute_mndwi(b03, b11)
    assert np.isclose(mndwi[0, 0], 0.5)
    assert np.isclose(mndwi[0, 1], -0.5)


def test_apply_pb0400_offset() -> None:
    raw_dn = np.array([[800, 1500, 3200]], dtype=np.float32)
    pre_2022 = apply_pb0400_offset(raw_dn, 2020)
    post_2022 = apply_pb0400_offset(raw_dn, "2022-02-10")
    assert np.allclose(pre_2022, np.array([[800.0, 1500.0, 3200.0]], dtype=np.float32))
    assert np.allclose(post_2022, np.array([[0.0, 500.0, 2200.0]], dtype=np.float32))


def test_compute_iou() -> None:
    pred = np.array([[1, 1], [0, 0]])
    ref = np.array([[1, 0], [0, 0]])
    assert np.isclose(compute_iou(pred, ref), 0.5)


def test_interpolate_population_grid() -> None:
    g2015 = np.array([[100.0, 200.0]], dtype=np.float32)
    g2020 = np.array([[150.0, 300.0]], dtype=np.float32)
    g2018 = interpolate_population_grid(g2015, g2020, 2015, 2020, 2018)
    assert np.allclose(g2018, np.array([[130.0, 260.0]], dtype=np.float32))


def test_mock_contracts_match_schemas() -> None:
    water_schema = json.loads((ROOT / "contracts/schemas/water_layer.schema.json").read_text(encoding="utf-8"))
    water_mock = json.loads((ROOT / "contracts/mock/water_2020.geojson").read_text(encoding="utf-8"))
    validate(instance=water_mock, schema=water_schema)

    pop_schema = json.loads((ROOT / "contracts/schemas/pop_layer.schema.json").read_text(encoding="utf-8"))
    pop_mock = json.loads((ROOT / "contracts/mock/pop_2020.geojson").read_text(encoding="utf-8"))
    validate(instance=pop_mock, schema=pop_schema)

    ts_schema = json.loads((ROOT / "contracts/schemas/timeseries.schema.json").read_text(encoding="utf-8"))
    ts_mock = json.loads((ROOT / "contracts/mock/timeseries_summary.json").read_text(encoding="utf-8"))
    validate(instance=ts_mock, schema=ts_schema)
