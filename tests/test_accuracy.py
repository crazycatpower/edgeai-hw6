#!/usr/bin/env python3
# Copyright (c) 2026 黃義鈞, 李軒杰
# Tatung University — I4210 AI實務專題

import json
from pathlib import Path

import pytest

BASELINE_PATH = Path(__file__).parent.parent / "calibration" / "accuracy_baseline.json"


@pytest.mark.skipif(
    not BASELINE_PATH.exists(),
    reason="accuracy_baseline.json not found — skipping accuracy gate",
)
def test_int8_map_drop_within_threshold():
    with open(BASELINE_PATH) as f:
        baseline = json.load(f)
    fp16 = baseline["fp16_map50"]
    int8 = baseline["int8_map50"]
    drop = fp16 - int8
    assert drop <= 0.02, (
        f"INT8 mAP drop too large: {drop:.4f} > 0.02 (fp16={fp16:.4f}, int8={int8:.4f})"
    )


@pytest.mark.skipif(
    not BASELINE_PATH.exists(),
    reason="accuracy_baseline.json not found — skipping accuracy gate",
)
def test_baseline_has_required_fields():
    with open(BASELINE_PATH) as f:
        baseline = json.load(f)
    for field in ("fp16_map50", "int8_map50", "calibrated_at", "best_pt_md5"):
        assert field in baseline, f"Missing field: {field}"


@pytest.mark.skipif(
    not BASELINE_PATH.exists(),
    reason="accuracy_baseline.json not found — skipping accuracy gate",
)
def test_map50_values_in_valid_range():
    with open(BASELINE_PATH) as f:
        baseline = json.load(f)
    assert 0.0 <= baseline["fp16_map50"] <= 1.0
    assert 0.0 <= baseline["int8_map50"] <= 1.0
