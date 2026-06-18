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


# --- Bundle.prml_lock_hash in canonical encoding ---

_LOCK = "c30dba8e0f566d1beebf4f8d468e6e07c821f0c72562dfb64ddf6596796f7797"


def test_prml_lock_hash_absent_when_none():
    d = bundle_to_dict(_simple_bundle())
    assert "prml_lock_hash" not in d


def test_prml_lock_hash_present_when_set():
    d = bundle_to_dict(_simple_bundle(prml_lock_hash=_LOCK))
    assert d["prml_lock_hash"] == _LOCK


def test_prml_lock_hash_in_canonical_bytes():
    b = _simple_bundle(prml_lock_hash=_LOCK)
    data = json.loads(canonicalise(b).decode("utf-8"))
    assert data["prml_lock_hash"] == _LOCK


def test_prml_lock_hash_changes_bundle_hash():
    b_without = _simple_bundle()
    b_with = _simple_bundle(prml_lock_hash=_LOCK)
    assert hash_bundle(b_without) != hash_bundle(b_with)


def test_prml_lock_hash_changes_content_hash():
    # prml_lock_hash is NOT excluded from content_hash (unlike meta).
    # A pre-registered bundle and a post-hoc bundle are scientifically distinct.
    b_without = _simple_bundle()
    b_with = _simple_bundle(prml_lock_hash=_LOCK)
    assert content_hash(b_without) != content_hash(b_with)


def test_prml_lock_hash_not_excluded_by_content_hash():
    # Explicit check: meta is excluded; prml_lock_hash is not.
    b = _simple_bundle(prml_lock_hash=_LOCK, meta={"repo_commit": "abc"})
    b_no_meta = _simple_bundle(prml_lock_hash=_LOCK)
    # content_hash strips meta — these two bundles differ only in meta, so same content_hash
    assert content_hash(b) == content_hash(b_no_meta)
    # but a bundle without prml_lock_hash differs in content_hash
    b_no_lock = _simple_bundle(meta={"repo_commit": "abc"})
    assert content_hash(b) != content_hash(b_no_lock)


def test_two_different_locks_produce_different_hashes():
    lock_a = "a" * 64
    lock_b = "b" * 64
    b_a = _simple_bundle(prml_lock_hash=lock_a)
    b_b = _simple_bundle(prml_lock_hash=lock_b)
    assert hash_bundle(b_a) != hash_bundle(b_b)
    assert content_hash(b_a) != content_hash(b_b)


# --- Canonicalization edge cases (Falsify cross-language analysis) ---
# Reference: studio-11-co/falsify spec/analysis/canonicalization-portability-v0.1.md
# valichord_attestation uses JCS (RFC 8785), not YAML, so YAML-specific findings
# (quoting heuristics, seed integer width) do not apply. The relevant findings are:
# Finding 2 (integer-valued float type loss) and Finding 4 (small-magnitude floats).
# These tests document JCS behaviour so cross-language verifiers have a reference.

def test_integer_valued_metric_encodes_stably():
    # Finding 2 (Falsify): integer-valued floats can lose decimal type across JSON
    # parsers. JCS/RFC 8785 serializes 1.0 as 1 (no decimal) — integer form.
    # Document this so a verifier in JS/Go/Rust expects "value":1, not "value":1.0.
    b = _simple_bundle(metrics=[Metric(key="accuracy", value=1.0)])
    raw = canonicalise(b).decode("utf-8")
    parsed = json.loads(raw)
    assert parsed["metrics"][0]["value"] == 1
    # Hash is deterministic
    assert hash_bundle(b) == hash_bundle(b)


def test_integer_and_float_one_hash_identically():
    # Because JCS serializes both int 1 and float 1.0 as the token 1,
    # Metric(value=1) and Metric(value=1.0) produce the same canonical bytes.
    b_int = _simple_bundle(metrics=[Metric(key="accuracy", value=1)])
    b_float = _simple_bundle(metrics=[Metric(key="accuracy", value=1.0)])
    assert canonicalise(b_int) == canonicalise(b_float)
    assert hash_bundle(b_int) == hash_bundle(b_float)


def test_small_magnitude_metric_encodes_stably():
    # Finding 4 (Falsify): small-magnitude floats near the scientific-notation
    # threshold can render differently across language stdlibs. RFC 8785 §3.2.2.3
    # specifies IEEE 754 double serialization. Test that valichord_attestation
    # produces consistent bytes and that the value round-trips correctly.
    b = _simple_bundle(metrics=[Metric(key="loss", value=0.000001)])
    h1 = hash_bundle(b)
    h2 = hash_bundle(b)
    assert h1 == h2
    parsed = json.loads(canonicalise(b).decode("utf-8"))
    assert abs(parsed["metrics"][0]["value"] - 1e-6) < 1e-15


def test_pre_round_produces_cross_language_safe_value():
    # pre_round clips to 6 dp before JCS encoding, so any IEEE 754 noise beyond
    # 6 dp cannot affect the hash. A verifier applying the same pre_round gets
    # an identical canonical representation and therefore an identical hash.
    v_raw = 0.8471239      # 7 significant digits of noise
    v_rounded = pre_round(v_raw)   # → 0.847124
    b_via_preround = _simple_bundle(metrics=[Metric(key="accuracy", value=v_rounded)])
    b_direct = _simple_bundle(metrics=[Metric(key="accuracy", value=0.847124)])
    assert canonicalise(b_via_preround) == canonicalise(b_direct)
    assert hash_bundle(b_via_preround) == hash_bundle(b_direct)


def test_six_dp_boundary_values_hash_differently():
    # Values that differ at the 6th decimal place produce distinct hashes —
    # pre_round does not over-clip.
    b1 = _simple_bundle(metrics=[Metric(key="accuracy", value=0.847124)])
    b2 = _simple_bundle(metrics=[Metric(key="accuracy", value=0.847125)])
    assert hash_bundle(b1) != hash_bundle(b2)
