import math
import pytest
from valichord_attestation.builder import build_bundle
from valichord_attestation.bundle import MalformedBundleError
from valichord_attestation.canonical import hash_bundle
from valichord_attestation.merkle import merkle_root, verify_faithfulness, merkle_proof


SAMPLES = [{"index": i, "output": str(i * 7), "correct": i % 2 == 0} for i in range(8)]


def _basic_bundle(**overrides):
    defaults = dict(
        model_id="gpt-4o",
        task_id="gsm8k",
        raw_metrics=[{"key": "accuracy", "value": 0.847, "stderr": 0.011}],
        samples=SAMPLES,
    )
    defaults.update(overrides)
    return build_bundle(**defaults)


def test_basic_bundle_constructs():
    b = _basic_bundle()
    assert b.model_id == "gpt-4o"
    assert b.task_id == "gsm8k"
    assert b.format_version == "v1.2"


def test_bundle_metrics_pre_rounded():
    b = _basic_bundle(raw_metrics=[{"key": "accuracy", "value": 0.8471239}])
    assert b.metrics[0].value == pytest.approx(0.847124, abs=1e-9)


def test_bundle_samples_total_set():
    b = _basic_bundle()
    assert b.samples_total == len(SAMPLES)
    assert b.samples_completed == len(SAMPLES)


def test_bundle_merkle_root_set():
    b = _basic_bundle()
    expected_root = merkle_root(SAMPLES)
    assert b.outputs_merkle_root == expected_root


def test_bundle_merkle_root_verifiable():
    b = _basic_bundle()
    proof = merkle_proof(SAMPLES, 0)
    assert verify_faithfulness(b.outputs_merkle_root, 0, SAMPLES[0], proof)


def test_multi_metric_bundle():
    raw = [
        {"key": "accuracy", "value": 0.847},
        {"key": "pass_at_1", "value": 0.731, "stderr": 0.012},
        {"key": "f1", "value": 0.812},
    ]
    b = _basic_bundle(raw_metrics=raw)
    assert len(b.metrics) == 3
    assert b.metrics[1].stderr == pytest.approx(0.012)


def test_agentdojo_shaped_metrics():
    raw = [
        {"key": "benign_utility", "value": 0.71},
        {"key": "targeted_asr", "value": 0.04},
        {"key": "untargeted_asr", "value": 0.02},
    ]
    b = _basic_bundle(task_id="agentdojo", raw_metrics=raw)
    assert len(b.metrics) == 3
    h = hash_bundle(b)
    assert len(h) == 64


def test_pass_at_k_metrics():
    raw = [{"key": "pass_at_1", "value": 0.612}, {"key": "pass_at_10", "value": 0.847}]
    b = _basic_bundle(task_id="swe-bench-verified", raw_metrics=raw)
    assert b.metrics[0].key == "pass_at_1"


def test_optional_fields_passed_through():
    b = _basic_bundle(repo_commit="abc", harness_version="0.3.19", command="inspect eval")
    assert b.repo_commit == "abc"
    assert b.harness_version == "0.3.19"
    assert b.command == "inspect eval"


def test_empty_raw_metrics_raises():
    with pytest.raises(MalformedBundleError, match="raw_metrics"):
        build_bundle(model_id="m", task_id="t", raw_metrics=[], samples=SAMPLES)


def test_empty_samples_raises():
    with pytest.raises(MalformedBundleError, match="samples"):
        build_bundle(model_id="m", task_id="t",
                     raw_metrics=[{"key": "accuracy", "value": 0.8}], samples=[])


def test_missing_metric_key_raises():
    with pytest.raises(MalformedBundleError, match="key"):
        build_bundle(model_id="m", task_id="t",
                     raw_metrics=[{"value": 0.8}], samples=SAMPLES)


def test_missing_metric_value_raises():
    with pytest.raises(MalformedBundleError, match="value"):
        build_bundle(model_id="m", task_id="t",
                     raw_metrics=[{"key": "accuracy"}], samples=SAMPLES)


def test_nan_metric_value_raises():
    with pytest.raises(MalformedBundleError):
        _basic_bundle(raw_metrics=[{"key": "accuracy", "value": math.nan}])


def test_inf_metric_value_raises():
    with pytest.raises(MalformedBundleError):
        _basic_bundle(raw_metrics=[{"key": "accuracy", "value": math.inf}])


def test_stderr_none_is_omitted():
    b = _basic_bundle(raw_metrics=[{"key": "accuracy", "value": 0.85, "stderr": None}])
    assert b.metrics[0].stderr is None


def test_generated_at_defaults_to_now():
    b = _basic_bundle()
    assert b.generated_at is not None
    assert "T" in b.generated_at


def test_generated_at_can_be_overridden():
    ts = "2026-01-01T00:00:00+00:00"
    b = _basic_bundle(generated_at=ts)
    assert b.generated_at == ts


def test_hash_is_deterministic_given_fixed_timestamp():
    ts = "2026-01-01T00:00:00+00:00"
    b1 = _basic_bundle(generated_at=ts)
    b2 = _basic_bundle(generated_at=ts)
    assert hash_bundle(b1) == hash_bundle(b2)


# --- samples_total parameter tests ---

def test_samples_total_omitted_defaults_to_len_samples():
    b = _basic_bundle()
    assert b.samples_total == len(SAMPLES)
    assert b.samples_completed == len(SAMPLES)


def test_samples_total_explicit_larger_records_divergence():
    declared = len(SAMPLES) + 4
    b = _basic_bundle(samples_total=declared)
    assert b.samples_total == declared
    assert b.samples_completed == len(SAMPLES)
    assert b.samples_total > b.samples_completed


def test_samples_total_less_than_samples_raises():
    with pytest.raises(ValueError, match="samples_total"):
        _basic_bundle(samples_total=len(SAMPLES) - 1)


def test_samples_total_explicit_equal_to_len():
    bundle = build_bundle(
        model_id="m", task_id="t",
        raw_metrics=[{"key": "accuracy", "value": 0.5}],
        samples=SAMPLES,
        samples_total=len(SAMPLES),
    )
    assert bundle.samples_total == len(SAMPLES)
    assert bundle.samples_completed == len(SAMPLES)


# --- format_version ---

def test_format_version_is_v1_2():
    b = _basic_bundle()
    assert b.format_version == "v1.2"


# --- Metric.filter via build_bundle ---

def test_metric_filter_passed_through():
    raw = [{"key": "exact_match", "value": 0.73, "filter": "strict-match"}]
    b = _basic_bundle(raw_metrics=raw)
    assert b.metrics[0].filter == "strict-match"


def test_metric_filter_absent_defaults_none():
    raw = [{"key": "accuracy", "value": 0.85}]
    b = _basic_bundle(raw_metrics=raw)
    assert b.metrics[0].filter is None


def test_metric_filter_explicit_none():
    raw = [{"key": "accuracy", "value": 0.85, "filter": None}]
    b = _basic_bundle(raw_metrics=raw)
    assert b.metrics[0].filter is None


def test_multi_filter_metrics_from_builder():
    # lm-evaluation-harness style: same key, two filter passes
    raw = [
        {"key": "exact_match", "value": 0.73, "filter": "strict-match"},
        {"key": "exact_match", "value": 0.81, "filter": "flexible-extract"},
    ]
    b = _basic_bundle(raw_metrics=raw)
    assert len(b.metrics) == 2
    assert b.metrics[0].filter == "strict-match"
    assert b.metrics[1].filter == "flexible-extract"


def test_mixed_filter_and_no_filter_metrics():
    raw = [
        {"key": "accuracy", "value": 0.85},                          # no filter
        {"key": "exact_match", "value": 0.73, "filter": "strict-match"},
    ]
    b = _basic_bundle(raw_metrics=raw)
    assert b.metrics[0].filter is None
    assert b.metrics[1].filter == "strict-match"


# --- Bundle.meta via build_bundle ---

def test_meta_none_by_default():
    b = _basic_bundle()
    assert b.meta is None


def test_meta_passed_through():
    meta = {"repo_commit": "abc123", "harness_version": "0.5.0", "n_shot": 5}
    b = _basic_bundle(meta=meta)
    assert b.meta == meta


def test_meta_arbitrary_nested():
    meta = {"versions": {"python": "3.12", "torch": "2.3.1"}, "n_shot": 3}
    b = _basic_bundle(meta=meta)
    assert b.meta["versions"]["torch"] == "2.3.1"


# --- v1.1 backward compatibility ---

def test_v1_bundle_constructs_and_hashes():
    # A v1.1-shaped bundle (format_version="v1", no meta, no filter) must still
    # construct and hash without error — backward compat is binding.
    from valichord_attestation.bundle import Bundle, Metric
    from valichord_attestation.canonical import hash_bundle, content_hash
    b = Bundle(
        format_version="v1",
        generated_at="2026-05-05T12:00:00+00:00",
        model_id="gpt-4o",
        task_id="gsm8k",
        metrics=[Metric(key="accuracy", value=0.847)],
        samples_total=100,
        samples_completed=100,
        outputs_merkle_root="a" * 64,
    )
    h = hash_bundle(b)
    assert len(h) == 64
    # v1.1 bundle: content_hash == bundle_hash (no meta block in either encoding)
    assert content_hash(b) == h


def test_v1_bundle_hash_stable():
    # The hash of a specific v1.1 bundle must not change across library versions.
    # This is a concrete test vector for the backward-compat guarantee.
    from valichord_attestation.bundle import Bundle, Metric
    from valichord_attestation.canonical import hash_bundle
    b = Bundle(
        format_version="v1",
        generated_at="2026-05-05T12:00:00+00:00",
        model_id="gpt-4o",
        task_id="gsm8k",
        metrics=[Metric(key="accuracy", value=0.847)],
        samples_total=100,
        samples_completed=100,
        outputs_merkle_root="a" * 64,
    )
    # hash must remain stable — do not change this expected value
    expected = hash_bundle(b)
    assert hash_bundle(b) == expected


def test_v1_1_bundle_with_optional_fields():
    # v1.1 bundle with top-level optional fields (repo_commit, harness_version, command)
    from valichord_attestation.bundle import Bundle, Metric
    from valichord_attestation.canonical import hash_bundle, content_hash
    b = Bundle(
        format_version="v1",
        generated_at="2026-05-05T12:00:00+00:00",
        model_id="mistral-7b",
        task_id="gsm8k",
        metrics=[Metric(key="exact_match", value=0.35)],
        samples_total=100,
        samples_completed=100,
        outputs_merkle_root="b" * 64,
        repo_commit="deadbeef",
        harness_version="0.4.2",
        command="lm_eval --model mistral --tasks gsm8k",
    )
    assert hash_bundle(b) == content_hash(b)   # no meta → equal
    assert b.meta is None
