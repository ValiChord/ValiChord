"""Tests for the pure logic in pep_master_round.py.

These cover the §3 outcome_rule (medical-device-critical), the researcher
reference-metric builder, and the per-builder verdict builder. They do NOT
touch Holochain — the commit-reveal round is exercised by the live docker
demo, not unit tests.
"""
import json
from pathlib import Path

import pytest

from pep_master_round import (
    derive_outcome,
    build_researcher_metrics,
    build_validator_verdict,
    build_round_inputs,
)

DEMO_DIR = Path(__file__).parent


# ── §3 outcome_rule ───────────────────────────────────────────────────────────
# Reproduced          if every setpoint within ±5%
# PartiallyReproduced if every setpoint within ±10% but some outside ±5%
# FailedToReproduce   otherwise

def test_outcome_within_tolerance_is_reproduced():
    assert derive_outcome(3.1, tolerance_pct=5.0) == "Reproduced"
    assert derive_outcome(4.4, tolerance_pct=5.0) == "Reproduced"
    assert derive_outcome(2.7, tolerance_pct=5.0) == "Reproduced"


def test_outcome_tolerance_boundary_is_inclusive():
    # exactly at ±5% counts as within tolerance
    assert derive_outcome(5.0, tolerance_pct=5.0) == "Reproduced"


def test_outcome_between_tolerance_and_double_is_partial():
    assert derive_outcome(5.0001, tolerance_pct=5.0) == "PartiallyReproduced"
    assert derive_outcome(7.0, tolerance_pct=5.0) == "PartiallyReproduced"
    assert derive_outcome(10.0, tolerance_pct=5.0) == "PartiallyReproduced"  # inclusive ±10%


def test_outcome_beyond_double_tolerance_is_failed():
    assert derive_outcome(10.0001, tolerance_pct=5.0) == "FailedToReproduce"
    assert derive_outcome(12.0, tolerance_pct=5.0) == "FailedToReproduce"


def test_outcome_rule_scales_with_tolerance():
    # swapping the tolerance moves both bands (partial = 2x tolerance)
    assert derive_outcome(2.5, tolerance_pct=3.0) == "Reproduced"
    assert derive_outcome(4.0, tolerance_pct=3.0) == "PartiallyReproduced"
    assert derive_outcome(7.0, tolerance_pct=3.0) == "FailedToReproduce"


# ── Researcher reference metrics ──────────────────────────────────────────────

def test_researcher_metrics_one_per_setpoint():
    metrics = build_researcher_metrics([5, 10, 15, 20])
    assert [m["metric_name"] for m in metrics] == [
        "expiratory_pressure_cmH2O@5",
        "expiratory_pressure_cmH2O@10",
        "expiratory_pressure_cmH2O@15",
        "expiratory_pressure_cmH2O@20",
    ]


def test_researcher_metric_is_the_reference_gauge_reading():
    # The researcher's "result" is the reference/spec value: expected == produced,
    # within_tolerance true (the gauge reproduces itself by definition).
    metrics = build_researcher_metrics([10])
    m = metrics[0]
    assert m["expected_value"] == "10.0"
    assert m["produced_value"] == "10.0"
    assert m["within_tolerance"] is True


# ── Per-builder verdict ───────────────────────────────────────────────────────

def test_verdict_reproduced_for_in_spec_builder():
    builder = {"name": "Builder A", "location": "Montreal lab", "max_deviation_pct": 3.1}
    v = build_validator_verdict(builder, setpoints=[5, 10, 15, 20], tolerance_pct=5.0)
    assert v["outcome"] == "Reproduced"
    assert v["confidence"] == "High"


def test_verdict_reasoning_carries_deviation_and_setpoints():
    builder = {"name": "Builder A", "location": "Montreal lab", "max_deviation_pct": 3.1}
    v = build_validator_verdict(builder, setpoints=[5, 10, 15, 20], tolerance_pct=5.0)
    assert "3.1%" in v["reasoning"]
    assert "5/10/15/20" in v["reasoning"]


def test_verdict_failed_builder_gets_low_confidence():
    builder = {"name": "Builder X", "location": "nowhere", "max_deviation_pct": 14.0}
    v = build_validator_verdict(builder, setpoints=[5, 10, 15, 20], tolerance_pct=5.0)
    assert v["outcome"] == "FailedToReproduce"
    assert v["confidence"] == "Low"


def test_verdict_honours_explicit_confidence():
    builder = {"name": "B", "location": "x", "max_deviation_pct": 4.4, "confidence": "Medium"}
    v = build_validator_verdict(builder, setpoints=[5, 10], tolerance_pct=5.0)
    assert v["confidence"] == "Medium"


# ── Whole-bundle wiring ───────────────────────────────────────────────────────

def test_build_round_inputs_from_bundle():
    bundle = {
        "test_protocol": {
            "reference_input": {"setpoints_cmH2O": [5, 10, 15, 20]},
            "tolerance": {"value": 5.0},
        },
        "readings": [
            {"name": "Builder A", "location": "Montreal lab", "max_deviation_pct": 3.1},
            {"name": "Builder B", "location": "Lyon hospital", "max_deviation_pct": 4.4},
            {"name": "Builder C", "location": "Seoul makerspace", "max_deviation_pct": 2.7},
        ],
    }
    metrics, verdicts, discipline = build_round_inputs(bundle)

    assert len(metrics) == 4
    assert len(verdicts) == 3
    assert all(v["outcome"] == "Reproduced" for v in verdicts)
    # discipline must NOT be ComputationalBiology — this is a hardware device
    assert discipline["type"] == "Other"
    assert "ardware" in discipline["content"]


def test_committed_bundle_file_yields_three_reproduced():
    # The shipped bundle's stand-in numbers must all reproduce (Version A).
    bundle = json.loads((DEMO_DIR / "pep_master_bundle.json").read_text())
    _metrics, verdicts, _disc = build_round_inputs(bundle)
    assert len(verdicts) == 3
    assert all(v["outcome"] == "Reproduced" for v in verdicts)
