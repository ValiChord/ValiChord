import json
import math
import pytest
import jcs
from valichord_attestation.bundle import Bundle, Metric, MalformedBundleError
from valichord_attestation.canonical import (
    bundle_to_dict, canonicalise, content_hash, hash_bundle, pre_round,
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


# --- Metric.filter in canonical encoding ---

def test_metric_filter_absent_when_none():
    m = Metric(key="accuracy", value=0.85)
    from valichord_attestation.canonical import _metric_to_dict
    d = _metric_to_dict(m)
    assert "filter" not in d


def test_metric_filter_included_when_set():
    m = Metric(key="exact_match", value=0.73, filter="strict-match")
    from valichord_attestation.canonical import _metric_to_dict
    d = _metric_to_dict(m)
    assert d["filter"] == "strict-match"


def test_metric_filter_in_canonical_bytes():
    b = _simple_bundle(metrics=[Metric(key="exact_match", value=0.73, filter="strict-match")])
    raw = canonicalise(b).decode("utf-8")
    assert '"filter":"strict-match"' in raw or "filter" in raw
    parsed = json.loads(raw)
    assert parsed["metrics"][0]["filter"] == "strict-match"


def test_multi_filter_metrics_produce_distinct_dicts():
    # Same key, different filter → different canonical representations → different hashes
    b1 = _simple_bundle(metrics=[Metric(key="exact_match", value=0.73, filter="strict-match")])
    b2 = _simple_bundle(metrics=[Metric(key="exact_match", value=0.73, filter="flexible-extract")])
    assert canonicalise(b1) != canonicalise(b2)
    assert hash_bundle(b1) != hash_bundle(b2)


def test_multi_filter_metrics_in_one_bundle():
    # lm-evaluation-harness style: two entries for the same task, different filters
    metrics = [
        Metric(key="exact_match", value=0.73, filter="strict-match"),
        Metric(key="exact_match", value=0.81, filter="flexible-extract"),
    ]
    b = _simple_bundle(metrics=metrics)
    data = json.loads(canonicalise(b).decode("utf-8"))
    assert data["metrics"][0]["filter"] == "strict-match"
    assert data["metrics"][1]["filter"] == "flexible-extract"


def test_filter_none_and_set_differ():
    b_no_filter = _simple_bundle(metrics=[Metric(key="accuracy", value=0.85)])
    b_with_filter = _simple_bundle(metrics=[Metric(key="accuracy", value=0.85, filter="none")])
    assert canonicalise(b_no_filter) != canonicalise(b_with_filter)


# --- Bundle.meta in canonical encoding ---

def test_meta_absent_when_none():
    d = bundle_to_dict(_simple_bundle())
    assert "meta" not in d


def test_meta_included_when_set():
    meta = {"repo_commit": "abc123", "harness_version": "0.5.0"}
    b = _simple_bundle(meta=meta)
    d = bundle_to_dict(b)
    assert d["meta"] == meta


def test_meta_in_canonical_bytes():
    b = _simple_bundle(meta={"repo_commit": "deadbeef"})
    data = json.loads(canonicalise(b).decode("utf-8"))
    assert data["meta"]["repo_commit"] == "deadbeef"


def test_meta_changes_bundle_hash():
    b_no_meta = _simple_bundle()
    b_with_meta = _simple_bundle(meta={"repo_commit": "abc123"})
    assert hash_bundle(b_no_meta) != hash_bundle(b_with_meta)


# --- content_hash ---

def test_content_hash_is_64_hex():
    h = content_hash(_simple_bundle())
    assert isinstance(h, str)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_content_hash_deterministic():
    b = _simple_bundle()
    assert content_hash(b) == content_hash(b)


def test_content_hash_equals_bundle_hash_no_meta():
    # v1.1 bundle (no meta) → content_hash == bundle_hash
    b = _simple_bundle()
    assert b.meta is None
    assert content_hash(b) == hash_bundle(b)


def test_content_hash_equals_bundle_hash_explicit_none_meta():
    b = _simple_bundle(meta=None)
    assert content_hash(b) == hash_bundle(b)


def test_content_hash_invariant_to_meta():
    # Same content, different meta → same content_hash
    b1 = _simple_bundle(meta={"repo_commit": "aaa"})
    b2 = _simple_bundle(meta={"repo_commit": "bbb"})
    assert content_hash(b1) == content_hash(b2)


def test_bundle_hash_differs_for_different_meta():
    # Different meta → different bundle_hash (meta IS in canonical encoding)
    b1 = _simple_bundle(meta={"repo_commit": "aaa"})
    b2 = _simple_bundle(meta={"repo_commit": "bbb"})
    assert hash_bundle(b1) != hash_bundle(b2)


def test_content_hash_differs_from_bundle_hash_when_meta_present():
    b = _simple_bundle(meta={"repo_commit": "abc"})
    assert content_hash(b) != hash_bundle(b)


def test_content_hash_sensitive_to_model():
    b1 = _simple_bundle(model_id="model-a")
    b2 = _simple_bundle(model_id="model-b")
    assert content_hash(b1) != content_hash(b2)


def test_content_hash_sensitive_to_metric():
    b1 = _simple_bundle(metrics=[Metric(key="accuracy", value=0.847)])
    b2 = _simple_bundle(metrics=[Metric(key="accuracy", value=0.848)])
    assert content_hash(b1) != content_hash(b2)


def test_content_hash_includes_filter():
    # filter is part of content → content_hash differs
    b1 = _simple_bundle(metrics=[Metric(key="exact_match", value=0.73, filter="strict-match")])
    b2 = _simple_bundle(metrics=[Metric(key="exact_match", value=0.73, filter="flexible-extract")])
    assert content_hash(b1) != content_hash(b2)


def test_content_hash_meta_empty_dict_vs_no_meta():
    # meta={} (present, empty) is still included in bundle_hash but excluded from content_hash
    b_none = _simple_bundle()
    b_empty = _simple_bundle(meta={})
    # content_hash: meta excluded in both cases → same
    assert content_hash(b_none) == content_hash(b_empty)
    # bundle_hash: empty dict IS in canonical encoding → differs
    assert hash_bundle(b_none) != hash_bundle(b_empty)


def test_content_hash_identical_content_and_meta():
    # Exact same bundle → same content_hash and same bundle_hash
    ts = "2026-05-09T00:00:00+00:00"
    meta = {"repo_commit": "abc123"}
    b1 = _simple_bundle(generated_at=ts, meta=meta)
    b2 = _simple_bundle(generated_at=ts, meta=meta)
    assert content_hash(b1) == content_hash(b2)
    assert hash_bundle(b1) == hash_bundle(b2)
