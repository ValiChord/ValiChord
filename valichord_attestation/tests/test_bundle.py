import math
import pytest
from valichord_attestation.bundle import Bundle, Metric, MalformedBundleError


def _make_bundle(**overrides):
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


def test_valid_bundle_constructs():
    b = _make_bundle()
    assert b.format_version == "v1"
    assert b.model_id == "gpt-4o"
    assert b.task_id == "gsm8k"


def test_empty_format_version_raises():
    with pytest.raises(MalformedBundleError, match="format_version"):
        _make_bundle(format_version="")


def test_empty_model_id_raises():
    with pytest.raises(MalformedBundleError, match="model_id"):
        _make_bundle(model_id="")


def test_empty_task_id_raises():
    with pytest.raises(MalformedBundleError, match="task_id"):
        _make_bundle(task_id="")


def test_empty_metrics_raises():
    with pytest.raises(MalformedBundleError, match="metrics"):
        _make_bundle(metrics=[])


def test_empty_merkle_root_raises():
    with pytest.raises(MalformedBundleError, match="outputs_merkle_root"):
        _make_bundle(outputs_merkle_root="")


def test_empty_generated_at_raises():
    with pytest.raises(MalformedBundleError, match="generated_at"):
        _make_bundle(generated_at="")


def test_negative_samples_total_raises():
    with pytest.raises(MalformedBundleError):
        _make_bundle(samples_total=-1)


def test_negative_samples_completed_raises():
    with pytest.raises(MalformedBundleError):
        _make_bundle(samples_completed=-1)


def test_nan_metric_value_raises():
    with pytest.raises(MalformedBundleError):
        Metric(key="accuracy", value=math.nan)


def test_inf_metric_value_raises():
    with pytest.raises(MalformedBundleError):
        Metric(key="accuracy", value=math.inf)


def test_neg_inf_metric_value_raises():
    with pytest.raises(MalformedBundleError):
        Metric(key="accuracy", value=-math.inf)


def test_nan_stderr_raises():
    with pytest.raises(MalformedBundleError):
        Metric(key="accuracy", value=0.85, stderr=math.nan)


def test_empty_metric_key_raises():
    with pytest.raises(MalformedBundleError):
        Metric(key="", value=0.85)


def test_optional_fields_default_none():
    b = _make_bundle()
    assert b.repo_commit is None
    assert b.harness_version is None
    assert b.command is None


def test_optional_fields_set():
    b = _make_bundle(repo_commit="abc123", harness_version="0.3.19", command="inspect eval gsm8k")
    assert b.repo_commit == "abc123"
    assert b.harness_version == "0.3.19"
    assert b.command == "inspect eval gsm8k"


def test_multiple_metrics():
    metrics = [
        Metric(key="accuracy", value=0.847),
        Metric(key="pass_at_1", value=0.731),
        Metric(key="f1", value=0.812, stderr=0.009),
    ]
    b = _make_bundle(metrics=metrics)
    assert len(b.metrics) == 3
    assert b.metrics[2].stderr == 0.009


# --- Metric.filter ---

def test_metric_filter_default_none():
    m = Metric(key="accuracy", value=0.847)
    assert m.filter is None


def test_metric_filter_set():
    m = Metric(key="accuracy", value=0.847, filter="strict-match")
    assert m.filter == "strict-match"


def test_metric_filter_flexible_extract():
    m = Metric(key="exact_match", value=0.731, filter="flexible-extract")
    assert m.filter == "flexible-extract"


def test_metric_filter_does_not_affect_validation():
    # filter value is unconstrained — any string is accepted
    m = Metric(key="f1", value=0.9, filter="none")
    assert m.filter == "none"


# --- Bundle.meta ---

def test_bundle_meta_default_none():
    b = _make_bundle()
    assert b.meta is None


def test_bundle_meta_set():
    meta = {"repo_commit": "abc123", "harness_version": "0.5.0"}
    b = _make_bundle(meta=meta)
    assert b.meta == meta


def test_bundle_meta_arbitrary_shape():
    meta = {"nested": {"k": 1}, "list_val": [1, 2, 3], "timestamp": "2026-05-09T00:00:00Z"}
    b = _make_bundle(meta=meta)
    assert b.meta["nested"] == {"k": 1}
    assert b.meta["list_val"] == [1, 2, 3]
