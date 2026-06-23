"""Tests for AiluminateAdapter — no modelbench package required."""

import json
import tempfile
from pathlib import Path

import pytest

from valichord_attestation.adapters.ailuminate_adapter import (
    AiluminateAdapter,
    _hazard_short_code,
    _select_sut_score,
)
from valichord_attestation.adapters.base import AdapterBase
from valichord_attestation.bundle import Bundle


# ---------------------------------------------------------------------------
# Minimal fake modelbench report builder
# ---------------------------------------------------------------------------

def _hazard_score(
    uid="safe_hazard-1_0-cse",
    estimate=0.90,
    lower=0.85,
    upper=0.94,
    samples=100,
    num_scored_items=100,
    num_safe_items=90,
    numeric_grade=4,
    text_grade="VG",
    exceptions=0,
):
    return {
        "hazard_definition": {
            "uid": uid,
            "reference_standard": 0.775,
        },
        "score": {"lower": lower, "estimate": estimate, "upper": upper, "samples": samples},
        "test_scores": {},
        "exceptions": exceptions,
        "num_scored_items": num_scored_items,
        "num_safe_items": num_safe_items,
        "numeric_grade": numeric_grade,
        "text_grade": text_grade,
    }


def _sut_score(
    sut_uid="gpt-4o-2024-08-06",
    hazard_scores=None,
    end_time="2024-06-01 12:00:00+00:00",
    score=0.88,
    numeric_grade=4,
    text_grade="VG",
):
    return {
        "sut": {"uid": sut_uid, "initialization": {}},
        "hazard_scores": hazard_scores if hazard_scores is not None else [_hazard_score()],
        "end_time": end_time,
        "score": score,
        "numeric_grade": numeric_grade,
        "text_grade": text_grade,
    }


def _report(
    *,
    sut_scores=None,
    benchmark_uid="general_purpose_ai_chat_benchmark-1.0",
    run_uid="run-general_purpose_ai_chat_benchmark-1.0-20240601-120000",
    code_version="v1.0-5-gabc1234",
    timestamp="2024-06-01 12:00:00 UTC",
):
    return {
        "_metadata": {
            "format_version": 1,
            "run": {
                "user": "tester",
                "timestamp": timestamp,
                "platform": "Linux",
                "python": "3.12.0",
            },
            "code": {
                "source": {
                    "code_version": code_version,
                    "origin": "https://github.com/mlcommons/modelbench",
                },
            },
        },
        "benchmark": {"uid": benchmark_uid},
        "run_uid": run_uid,
        "scores": sut_scores if sut_scores is not None else [_sut_score()],
    }


ANNOTATIONS = [
    {"hazard": "safe_cse", "prompt": "Do x.", "response": "I can't do that.", "is_safe": True, "is_valid": True},
    {"hazard": "safe_cse", "prompt": "Do y.", "response": "Sure.", "is_safe": False, "is_valid": True},
    {"hazard": "safe_dfm", "prompt": "Say z.", "response": "No.", "is_safe": True, "is_valid": True},
]


# ---------------------------------------------------------------------------
# _hazard_short_code
# ---------------------------------------------------------------------------

def test_short_code_standard_uid():
    assert _hazard_short_code("safe_hazard-1_0-cse") == "cse"

def test_short_code_ssh():
    assert _hazard_short_code("safe_hazard-1_0-ssh") == "ssh"

def test_short_code_different_version():
    assert _hazard_short_code("safe_hazard-2_0-dfm") == "dfm"

def test_short_code_fallback_for_unusual_uid():
    code = _hazard_short_code("completely_different_format")
    assert code  # non-empty
    assert all(c.isalnum() or c == "_" for c in code)


# ---------------------------------------------------------------------------
# _select_sut_score
# ---------------------------------------------------------------------------

def test_select_sut_single_auto():
    scores = [_sut_score()]
    result = _select_sut_score(scores, None)
    assert result["sut"]["uid"] == "gpt-4o-2024-08-06"

def test_select_sut_by_uid():
    scores = [_sut_score("model-a"), _sut_score("model-b")]
    result = _select_sut_score(scores, "model-b")
    assert result["sut"]["uid"] == "model-b"

def test_select_sut_raises_on_ambiguity():
    scores = [_sut_score("model-a"), _sut_score("model-b")]
    with pytest.raises(ValueError, match="sut_uid="):
        _select_sut_score(scores, None)

def test_select_sut_raises_on_empty():
    with pytest.raises(ValueError, match="empty"):
        _select_sut_score([], None)

def test_select_sut_raises_on_unknown_uid():
    with pytest.raises(ValueError, match="not found"):
        _select_sut_score([_sut_score()], "unknown-model")


# ---------------------------------------------------------------------------
# Structural
# ---------------------------------------------------------------------------

def test_is_subclass_of_base():
    assert issubclass(AiluminateAdapter, AdapterBase)

def test_to_bundle_returns_bundle():
    bundle = AiluminateAdapter().to_bundle(_report(), ANNOTATIONS)
    assert isinstance(bundle, Bundle)


# ---------------------------------------------------------------------------
# model_id, task_id
# ---------------------------------------------------------------------------

def test_model_id_from_sut_uid():
    bundle = AiluminateAdapter().to_bundle(_report(), ANNOTATIONS)
    assert bundle.model_id == "gpt-4o-2024-08-06"

def test_task_id_from_benchmark_uid():
    bundle = AiluminateAdapter().to_bundle(_report(), ANNOTATIONS)
    assert bundle.task_id == "general_purpose_ai_chat_benchmark-1.0"

def test_task_id_override():
    bundle = AiluminateAdapter().to_bundle(_report(), ANNOTATIONS, task_id_override="ailuminate-1.0")
    assert bundle.task_id == "ailuminate-1.0"

def test_multi_sut_requires_sut_uid():
    r = _report(sut_scores=[_sut_score("model-a"), _sut_score("model-b")])
    with pytest.raises(ValueError, match="sut_uid="):
        AiluminateAdapter().to_bundle(r, ANNOTATIONS)

def test_multi_sut_with_sut_uid():
    r = _report(sut_scores=[_sut_score("model-a"), _sut_score("model-b")])
    ann_b = [{"hazard": "safe_cse", "prompt": "p", "response": "r", "is_safe": True, "is_valid": True}]
    bundle = AiluminateAdapter().to_bundle(r, ann_b, sut_uid="model-b")
    assert bundle.model_id == "model-b"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def test_safe_rate_metric_present():
    bundle = AiluminateAdapter().to_bundle(_report(), ANNOTATIONS)
    keys = [m.key for m in bundle.metrics]
    assert "cse_safe_rate" in keys

def test_safe_rate_metric_value():
    bundle = AiluminateAdapter().to_bundle(_report(), ANNOTATIONS)
    cse = next(m for m in bundle.metrics if m.key == "cse_safe_rate")
    assert abs(cse.value - 0.90) < 1e-5

def test_numeric_grade_included_by_default():
    bundle = AiluminateAdapter().to_bundle(_report(), ANNOTATIONS)
    keys = [m.key for m in bundle.metrics]
    assert "cse_numeric_grade" in keys

def test_numeric_grade_excluded_when_disabled():
    bundle = AiluminateAdapter().to_bundle(_report(), ANNOTATIONS, include_numeric_grade=False)
    keys = [m.key for m in bundle.metrics]
    assert not any("numeric_grade" in k for k in keys)

def test_overall_safe_rate_included():
    bundle = AiluminateAdapter().to_bundle(_report(), ANNOTATIONS)
    keys = [m.key for m in bundle.metrics]
    assert "overall_safe_rate" in keys

def test_multi_hazard_metrics():
    hazards = [
        _hazard_score("safe_hazard-1_0-cse", estimate=0.90, numeric_grade=4),
        _hazard_score("safe_hazard-1_0-dfm", estimate=0.82, numeric_grade=3),
    ]
    r = _report(sut_scores=[_sut_score(hazard_scores=hazards)])
    bundle = AiluminateAdapter().to_bundle(r, ANNOTATIONS, include_numeric_grade=False)
    keys = [m.key for m in bundle.metrics]
    assert "cse_safe_rate" in keys
    assert "dfm_safe_rate" in keys

def test_zero_overall_score_not_included():
    # score=0.0 is the uninitialised default — should be omitted
    sut = _sut_score(score=0.0)
    r = _report(sut_scores=[sut])
    bundle = AiluminateAdapter().to_bundle(r, ANNOTATIONS)
    keys = [m.key for m in bundle.metrics]
    assert "overall_safe_rate" not in keys


# ---------------------------------------------------------------------------
# generated_at and repo_commit
# ---------------------------------------------------------------------------

def test_generated_at_from_end_time():
    bundle = AiluminateAdapter().to_bundle(_report(), ANNOTATIONS)
    assert bundle.generated_at is not None
    assert "2024-06-01" in bundle.generated_at

def test_generated_at_fallback_to_metadata_timestamp():
    sut = _sut_score(end_time=None)
    r = _report(sut_scores=[sut])
    bundle = AiluminateAdapter().to_bundle(r, ANNOTATIONS)
    assert bundle.generated_at is not None
    assert "2024-06-01" in bundle.generated_at

def test_repo_commit_from_code_version():
    bundle = AiluminateAdapter().to_bundle(_report(), ANNOTATIONS)
    assert bundle.repo_commit == "v1.0-5-gabc1234"

def test_repo_commit_absent_when_no_code_version():
    r = _report(code_version=None)
    bundle = AiluminateAdapter().to_bundle(r, ANNOTATIONS)
    assert bundle.repo_commit is None


# ---------------------------------------------------------------------------
# Meta fields
# ---------------------------------------------------------------------------

def test_meta_run_uid():
    bundle = AiluminateAdapter().to_bundle(_report(), ANNOTATIONS)
    assert bundle.meta is not None
    assert bundle.meta["run_uid"].startswith("run-")

def test_meta_overall_grade():
    bundle = AiluminateAdapter().to_bundle(_report(), ANNOTATIONS)
    assert bundle.meta is not None
    assert bundle.meta["overall_numeric_grade"] == 4
    assert bundle.meta["overall_text_grade"] == "VG"

def test_meta_exceptions_included_when_nonzero():
    hazards = [_hazard_score(exceptions=3)]
    r = _report(sut_scores=[_sut_score(hazard_scores=hazards)])
    bundle = AiluminateAdapter().to_bundle(r, ANNOTATIONS)
    assert bundle.meta is not None
    assert bundle.meta["exceptions"] == 3

def test_meta_extras_merged():
    bundle = AiluminateAdapter().to_bundle(_report(), ANNOTATIONS, meta_extras={"org": "mlcommons"})
    assert bundle.meta["org"] == "mlcommons"


# ---------------------------------------------------------------------------
# Samples and Merkle root
# ---------------------------------------------------------------------------

def test_annotations_produce_merkle_root():
    bundle = AiluminateAdapter().to_bundle(_report(), ANNOTATIONS)
    assert bundle.outputs_merkle_root is not None
    assert len(bundle.outputs_merkle_root) == 64

def test_annotation_count_in_samples_completed():
    bundle = AiluminateAdapter().to_bundle(_report(), ANNOTATIONS)
    assert bundle.samples_completed == len(ANNOTATIONS)

def test_samples_total_declared():
    bundle = AiluminateAdapter().to_bundle(_report(), ANNOTATIONS, samples_total=2000)
    assert bundle.samples_total == 2000

def test_fallback_leaves_when_no_annotations():
    # No annotations → one summary leaf per hazard
    bundle = AiluminateAdapter().to_bundle(_report())
    assert bundle.outputs_merkle_root is not None
    assert bundle.samples_completed == 1  # one hazard in default _report()

def test_merkle_root_deterministic():
    r = _report()
    b1 = AiluminateAdapter().to_bundle(r, ANNOTATIONS)
    b2 = AiluminateAdapter().to_bundle(r, ANNOTATIONS)
    assert b1.outputs_merkle_root == b2.outputs_merkle_root


# ---------------------------------------------------------------------------
# File path loading
# ---------------------------------------------------------------------------

def test_load_from_path_str():
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(_report(), f)
        path = f.name
    bundle = AiluminateAdapter().to_bundle(path, ANNOTATIONS)
    assert isinstance(bundle, Bundle)

def test_load_from_path_object():
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(_report(), f)
        path = Path(f.name)
    bundle = AiluminateAdapter().to_bundle(path, ANNOTATIONS)
    assert isinstance(bundle, Bundle)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_raises_on_non_dict_input():
    with pytest.raises(ValueError, match="must be a dict"):
        AiluminateAdapter().to_bundle([1, 2, 3], ANNOTATIONS)  # type: ignore[arg-type]

def test_raises_when_no_scores():
    r = _report(sut_scores=[])
    with pytest.raises(ValueError, match="empty"):
        AiluminateAdapter().to_bundle(r, ANNOTATIONS)

def test_raises_when_sut_uid_missing():
    r = _report()
    r["scores"][0]["sut"]["uid"] = ""
    with pytest.raises(ValueError, match="model_id"):
        AiluminateAdapter().to_bundle(r, ANNOTATIONS)

def test_raises_when_no_hazard_scores():
    sut = _sut_score(hazard_scores=[], score=0.0)
    r = _report(sut_scores=[sut])
    with pytest.raises(ValueError, match="No finite numeric metrics"):
        AiluminateAdapter().to_bundle(r, ANNOTATIONS)
