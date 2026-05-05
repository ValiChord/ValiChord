import json
import math
import pytest
import jcs
from valichord_attestation.bundle import Bundle, Metric, MalformedBundleError
from valichord_attestation.canonical import (
    bundle_to_dict, canonicalise, hash_bundle, pre_round,
)


def _simple_bundle(**overrides):
    defaults = dict(
        format_version="v1",
        generated_at="2026-05-05T12:00:00+00:00",
        model_id="gpt-4o",
        task_id="gsm8k",
        metrics=[Metric(key="accuracy", value=0.847)],
        samples_total=100,
        samples_completed=100,
        outputs_merkle_root="a" * 64,
    )
    defaults.update(overrides)
    return Bundle(**defaults)


# --- pre_round ---

def test_pre_round_rounds_to_six_places():
    assert pre_round(0.8471239) == pytest.approx(0.847124, abs=1e-9)


def test_pre_round_exact_value_unchanged():
    assert pre_round(0.847) == 0.847


def test_pre_round_nan_raises():
    with pytest.raises(MalformedBundleError):
        pre_round(math.nan)


def test_pre_round_inf_raises():
    with pytest.raises(MalformedBundleError):
        pre_round(math.inf)


def test_pre_round_neg_inf_raises():
    with pytest.raises(MalformedBundleError):
        pre_round(-math.inf)


def test_pre_round_label_in_error():
    with pytest.raises(MalformedBundleError, match="my_field"):
        pre_round(math.nan, label="my_field")


# --- bundle_to_dict ---

def test_none_optional_fields_omitted():
    d = bundle_to_dict(_simple_bundle())
    assert "repo_commit" not in d
    assert "harness_version" not in d
    assert "command" not in d


def test_set_optional_fields_included():
    d = bundle_to_dict(_simple_bundle(repo_commit="abc", harness_version="1.0", command="run"))
    assert d["repo_commit"] == "abc"
    assert d["harness_version"] == "1.0"
    assert d["command"] == "run"


def test_metric_stderr_omitted_when_none():
    d = bundle_to_dict(_simple_bundle(metrics=[Metric(key="accuracy", value=0.85)]))
    assert "stderr" not in d["metrics"][0]


def test_metric_stderr_present_when_set():
    d = bundle_to_dict(_simple_bundle(metrics=[Metric(key="accuracy", value=0.85, stderr=0.01)]))
    assert d["metrics"][0]["stderr"] == 0.01


def test_samples_nested_dict():
    d = bundle_to_dict(_simple_bundle(samples_total=200, samples_completed=195))
    assert d["samples"] == {"total": 200, "completed": 195}


def test_all_required_keys_present():
    d = bundle_to_dict(_simple_bundle())
    for key in ("format_version", "generated_at", "metrics", "model_id",
                "outputs_merkle_root", "samples", "task_id"):
        assert key in d


# --- canonicalise ---

def test_canonicalise_returns_bytes():
    assert isinstance(canonicalise(_simple_bundle()), bytes)


def test_canonicalise_deterministic():
    b = _simple_bundle()
    assert canonicalise(b) == canonicalise(b)


def test_canonicalise_different_model_differs():
    assert canonicalise(_simple_bundle(model_id="a")) != canonicalise(_simple_bundle(model_id="b"))


def test_canonicalise_different_task_differs():
    assert canonicalise(_simple_bundle(task_id="a")) != canonicalise(_simple_bundle(task_id="b"))


def test_canonicalise_different_metric_value_differs():
    b1 = _simple_bundle(metrics=[Metric(key="accuracy", value=0.847)])
    b2 = _simple_bundle(metrics=[Metric(key="accuracy", value=0.848)])
    assert canonicalise(b1) != canonicalise(b2)


def test_canonicalise_round_trip():
    b = _simple_bundle(repo_commit="abc123", harness_version="0.3.19")
    canonical_bytes = canonicalise(b)
    reconstructed = json.loads(canonical_bytes.decode("utf-8"))
    assert jcs.canonicalize(reconstructed) == canonical_bytes


def test_canonicalise_valid_utf8_json():
    b = _simple_bundle()
    decoded = canonicalise(b).decode("utf-8")
    parsed = json.loads(decoded)
    assert parsed["model_id"] == "gpt-4o"


def test_canonicalise_multi_metric_bundle():
    metrics = [
        Metric(key="accuracy", value=0.847),
        Metric(key="pass_at_1", value=0.731, stderr=0.012),
    ]
    b = _simple_bundle(metrics=metrics)
    data = json.loads(canonicalise(b).decode("utf-8"))
    assert len(data["metrics"]) == 2


# --- hash_bundle ---

def test_hash_bundle_is_64_char_hex():
    h = hash_bundle(_simple_bundle())
    assert isinstance(h, str)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_hash_bundle_deterministic():
    b = _simple_bundle()
    assert hash_bundle(b) == hash_bundle(b)


def test_hash_bundle_sensitive_to_model():
    assert hash_bundle(_simple_bundle(model_id="a")) != hash_bundle(_simple_bundle(model_id="b"))


def test_hash_bundle_sensitive_to_metric():
    b1 = _simple_bundle(metrics=[Metric(key="accuracy", value=0.847)])
    b2 = _simple_bundle(metrics=[Metric(key="accuracy", value=0.848)])
    assert hash_bundle(b1) != hash_bundle(b2)


def test_hash_bundle_agentdojo_shaped():
    """Multi-dimensional metrics (agentdojo style) hash consistently."""
    metrics = [
        Metric(key="benign_utility", value=0.71),
        Metric(key="targeted_asr", value=0.04),
        Metric(key="untargeted_asr", value=0.02),
    ]
    b = _simple_bundle(metrics=metrics)
    h1 = hash_bundle(b)
    h2 = hash_bundle(b)
    assert h1 == h2


def test_hash_bundle_pass_at_k_shaped():
    """pass@k metrics hash consistently."""
    metrics = [
        Metric(key="pass_at_1", value=0.612),
        Metric(key="pass_at_10", value=0.847),
    ]
    b = _simple_bundle(task_id="swe-bench-verified", metrics=metrics)
    assert len(hash_bundle(b)) == 64
