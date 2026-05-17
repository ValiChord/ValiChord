"""Tests for InspectAILogAdapter."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from valichord_attestation.adapters.base import AdapterBase
from valichord_attestation.adapters.inspect_ai_log_adapter import (
    InspectAILogAdapter,
    _extract_metrics,
    _sample_to_dict,
)
from valichord_attestation.bundle import Bundle


# ---------------------------------------------------------------------------
# Mock object helpers
# ---------------------------------------------------------------------------

def _eval_score(name: str, metrics: dict[str, float]) -> Any:
    """Build a mock EvalScore with the given metric name→value mapping."""
    return SimpleNamespace(
        name=name,
        metrics={k: SimpleNamespace(value=v) for k, v in metrics.items()},
    )


def _mock_sample(
    id: Any = 1,
    epoch: int = 1,
    output: str | None = "The answer is 42.",
    scores: dict[str, tuple[str, str | None]] | None = None,
) -> Any:
    """Build a mock EvalSample.

    scores: {scorer_name: (value_str, answer_str | None)}
    """
    raw_scores: dict = {}
    if scores:
        for name, (val, ans) in scores.items():
            raw_scores[name] = SimpleNamespace(value=val, answer=ans)
    out = SimpleNamespace(completion=output) if output is not None else None
    return SimpleNamespace(
        id=id,
        epoch=epoch,
        output=out,
        scores=raw_scores,
        error=None,
    )


def _mock_log(
    model: str = "gpt-4o-mini",
    task: str = "simple_qa",
    task_version: int | str = 0,
    created: datetime | None = None,
    revision_commit: str | None = None,
    scores: list[Any] | None = None,
    samples: list[Any] | None = None,
    packages: dict[str, str] | None = None,
    status: str = "success",
    completed_at: str = "2026-05-01T12:05:00+00:00",
    total_time: float | None = None,
) -> Any:
    """Build a minimal mock EvalLog duck-type."""
    if created is None:
        created = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
    if scores is None:
        scores = [_eval_score("accuracy", {"accuracy": 0.75, "stderr": 0.043})]
    if samples is None:
        samples = [
            _mock_sample(1, output="Paris"),
            _mock_sample(2, output="42"),
            _mock_sample(3, output="Blue"),
        ]
    if packages is None:
        packages = {"inspect_ai": "0.3.217"}

    revision = (
        SimpleNamespace(commit=revision_commit, dirty=False)
        if revision_commit is not None
        else None
    )

    return SimpleNamespace(
        status=status,
        eval=SimpleNamespace(
            model=model,
            task=task,
            task_version=task_version,
            created=created,
            packages=packages,
            revision=revision,
            metadata={},
        ),
        results=SimpleNamespace(scores=scores),
        samples=samples,
        stats=SimpleNamespace(
            completed_at=completed_at,
            total_time=total_time,
        ),
    )


ADAPTER = InspectAILogAdapter()


# ---------------------------------------------------------------------------
# Structural
# ---------------------------------------------------------------------------

def test_is_subclass_of_base():
    assert issubclass(InspectAILogAdapter, AdapterBase)


def test_to_bundle_returns_bundle():
    bundle = ADAPTER.to_bundle(_mock_log())
    assert isinstance(bundle, Bundle)


# ---------------------------------------------------------------------------
# model_id and task_id
# ---------------------------------------------------------------------------

def test_model_id_mapped():
    bundle = ADAPTER.to_bundle(_mock_log(model="openai/gpt-4o"))
    assert bundle.model_id == "openai/gpt-4o"


def test_task_id_mapped_from_eval_spec():
    bundle = ADAPTER.to_bundle(_mock_log(task="gpqa_diamond"))
    assert bundle.task_id == "gpqa_diamond"


def test_task_id_override_takes_precedence():
    bundle = ADAPTER.to_bundle(
        _mock_log(task="examples/gpqa/gpqa.py::gpqa_diamond"),
        task_id_override="gpqa_diamond",
    )
    assert bundle.task_id == "gpqa_diamond"


def test_task_id_defaults_to_overall_when_empty():
    log = _mock_log(task="")
    bundle = ADAPTER.to_bundle(log)
    assert bundle.task_id == "overall"


# ---------------------------------------------------------------------------
# generated_at
# ---------------------------------------------------------------------------

def test_generated_at_from_created_datetime():
    dt = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
    bundle = ADAPTER.to_bundle(_mock_log(created=dt))
    assert bundle.generated_at == dt.isoformat()


def test_generated_at_none_when_created_absent():
    log = _mock_log()
    log.eval.created = None
    bundle = ADAPTER.to_bundle(log)
    # build_bundle fills in current UTC time — just verify it's a non-empty string
    assert bundle.generated_at and len(bundle.generated_at) > 0


# ---------------------------------------------------------------------------
# repo_commit auto-extraction from revision
# ---------------------------------------------------------------------------

def test_repo_commit_auto_extracted_from_revision():
    sha = "abc123def456" * 3
    bundle = ADAPTER.to_bundle(_mock_log(revision_commit=sha))
    assert bundle.repo_commit == sha


def test_repo_commit_explicit_overrides_revision():
    explicit = "explicit_sha_001"
    bundle = ADAPTER.to_bundle(
        _mock_log(revision_commit="revision_sha"),
        repo_commit=explicit,
    )
    assert bundle.repo_commit == explicit


def test_repo_commit_none_when_no_revision():
    bundle = ADAPTER.to_bundle(_mock_log(revision_commit=None))
    assert bundle.repo_commit is None


# ---------------------------------------------------------------------------
# metrics extraction
# ---------------------------------------------------------------------------

def test_metrics_accuracy_and_stderr_extracted():
    bundle = ADAPTER.to_bundle(_mock_log(
        scores=[_eval_score("accuracy", {"accuracy": 0.75, "stderr": 0.043})]
    ))
    keys = [m.key for m in bundle.metrics]
    assert "accuracy" in keys
    assert "stderr" in keys


def test_metric_value_correct():
    bundle = ADAPTER.to_bundle(_mock_log(
        scores=[_eval_score("accuracy", {"accuracy": 0.75})]
    ))
    acc = next(m for m in bundle.metrics if m.key == "accuracy")
    assert abs(acc.value - 0.75) < 1e-9


def test_single_scorer_no_name_prefix():
    bundle = ADAPTER.to_bundle(_mock_log(
        scores=[_eval_score("accuracy", {"accuracy": 0.75})]
    ))
    assert bundle.metrics[0].key == "accuracy"


def test_colliding_metric_names_prefixed_with_scorer_name():
    scores = [
        _eval_score("scorer_a", {"accuracy": 0.80}),
        _eval_score("scorer_b", {"accuracy": 0.85}),
    ]
    bundle = ADAPTER.to_bundle(_mock_log(scores=scores))
    keys = {m.key for m in bundle.metrics}
    assert "scorer_a/accuracy" in keys
    assert "scorer_b/accuracy" in keys
    assert "accuracy" not in keys


def test_non_colliding_keys_not_prefixed():
    scores = [
        _eval_score("scorer_a", {"accuracy": 0.80}),
        _eval_score("scorer_b", {"f1": 0.77}),
    ]
    bundle = ADAPTER.to_bundle(_mock_log(scores=scores))
    keys = {m.key for m in bundle.metrics}
    assert "accuracy" in keys
    assert "f1" in keys


def test_non_numeric_metric_skipped():
    score = SimpleNamespace(
        name="custom",
        metrics={
            "accuracy": SimpleNamespace(value=0.9),
            "label": SimpleNamespace(value="pass"),  # non-numeric
        },
    )
    bundle = ADAPTER.to_bundle(_mock_log(scores=[score]))
    keys = [m.key for m in bundle.metrics]
    assert "accuracy" in keys
    assert "label" not in keys


def test_score_name_filter_restricts_to_named_scorer():
    scores = [
        _eval_score("model_graded", {"accuracy": 0.80}),
        _eval_score("exact_match", {"accuracy": 0.72}),
    ]
    bundle = ADAPTER.to_bundle(_mock_log(scores=scores), score_name="model_graded")
    assert len(bundle.metrics) == 1
    assert abs(bundle.metrics[0].value - 0.80) < 1e-9


def test_score_name_filter_no_match_raises():
    with pytest.raises(ValueError, match="No numeric metrics found"):
        ADAPTER.to_bundle(_mock_log(), score_name="nonexistent_scorer")


# ---------------------------------------------------------------------------
# Merkle root and sample counts
# ---------------------------------------------------------------------------

def test_merkle_root_64_hex_chars():
    bundle = ADAPTER.to_bundle(_mock_log())
    assert len(bundle.outputs_merkle_root) == 64
    assert all(c in "0123456789abcdef" for c in bundle.outputs_merkle_root)


def test_samples_completed_equals_sample_count():
    samples = [_mock_sample(i) for i in range(5)]
    bundle = ADAPTER.to_bundle(_mock_log(samples=samples))
    assert bundle.samples_completed == 5
    assert bundle.samples_total == 5


def test_samples_total_override():
    samples = [_mock_sample(i) for i in range(10)]
    bundle = ADAPTER.to_bundle(_mock_log(samples=samples), samples_total=100)
    assert bundle.samples_completed == 10
    assert bundle.samples_total == 100


# ---------------------------------------------------------------------------
# meta
# ---------------------------------------------------------------------------

def test_harness_version_in_meta():
    bundle = ADAPTER.to_bundle(_mock_log(packages={"inspect_ai": "0.3.217"}))
    assert bundle.meta is not None
    assert bundle.meta["harness_version"] == "inspect_ai==0.3.217"


def test_harness_version_absent_when_no_packages():
    bundle = ADAPTER.to_bundle(_mock_log(packages={}))
    assert bundle.meta is None or "harness_version" not in (bundle.meta or {})


def test_task_version_in_meta_when_non_default():
    bundle = ADAPTER.to_bundle(_mock_log(task_version="1-A", packages={}))
    assert bundle.meta is not None
    assert bundle.meta["task_version"] == "1-A"


def test_task_version_absent_when_default_zero():
    bundle = ADAPTER.to_bundle(_mock_log(task_version=0, packages={}))
    assert bundle.meta is None or "task_version" not in (bundle.meta or {})


def test_completed_at_in_meta_when_non_empty():
    bundle = ADAPTER.to_bundle(_mock_log(
        completed_at="2026-05-01T12:05:00+00:00",
        packages={},
    ))
    assert bundle.meta is not None
    assert "completed_at" in bundle.meta


def test_meta_extras_merged():
    extras = {"paper_arxiv": "https://arxiv.org/abs/2311.12022", "group": "Knowledge"}
    bundle = ADAPTER.to_bundle(_mock_log(packages={}), meta_extras=extras)
    assert bundle.meta is not None
    assert bundle.meta["paper_arxiv"] == "https://arxiv.org/abs/2311.12022"
    assert bundle.meta["group"] == "Knowledge"


def test_meta_none_when_no_provenance():
    log = _mock_log(packages={}, completed_at="", task_version=0)
    bundle = ADAPTER.to_bundle(log)
    assert bundle.meta is None


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_status_error_raises_value_error():
    with pytest.raises(ValueError, match="status is 'error'"):
        ADAPTER.to_bundle(_mock_log(status="error"))


def test_status_cancelled_raises_value_error():
    with pytest.raises(ValueError, match="status is 'cancelled'"):
        ADAPTER.to_bundle(_mock_log(status="cancelled"))


def test_empty_samples_raises_value_error():
    with pytest.raises(ValueError, match="empty"):
        ADAPTER.to_bundle(_mock_log(samples=[]))


def test_all_non_numeric_metrics_raises_value_error():
    score = SimpleNamespace(
        name="custom",
        metrics={"label": SimpleNamespace(value="pass")},
    )
    with pytest.raises(ValueError, match="No numeric metrics"):
        ADAPTER.to_bundle(_mock_log(scores=[score]))


def test_empty_model_raises_value_error():
    with pytest.raises(ValueError, match="model.*empty"):
        ADAPTER.to_bundle(_mock_log(model=""))


def test_no_scores_raises_value_error():
    with pytest.raises(ValueError, match="No numeric metrics"):
        ADAPTER.to_bundle(_mock_log(scores=[]))


# ---------------------------------------------------------------------------
# Errored sample handling
# ---------------------------------------------------------------------------

def test_errored_sample_output_is_none():
    errored = SimpleNamespace(
        id=99, epoch=1,
        output=None,
        scores={},
        error=SimpleNamespace(message="timeout"),
    )
    d = _sample_to_dict(errored)
    assert d["output"] is None


def test_sample_dict_always_has_four_keys():
    sample = _mock_sample(1)
    d = _sample_to_dict(sample)
    assert set(d.keys()) == {"id", "epoch", "output", "scores"}


def test_sample_id_always_string():
    d = _sample_to_dict(_mock_sample(id=42))
    assert isinstance(d["id"], str)
    assert d["id"] == "42"


def test_sample_scores_include_answer():
    sample = _mock_sample(
        scores={"accuracy": ("C", "Paris")}
    )
    d = _sample_to_dict(sample)
    assert d["scores"]["accuracy"]["answer"] == "Paris"
    assert d["scores"]["accuracy"]["value"] == "C"


# ---------------------------------------------------------------------------
# ImportError path when inspect_ai unavailable (monkeypatched)
# ---------------------------------------------------------------------------

def test_path_loading_raises_import_error_when_unavailable(monkeypatch):
    import valichord_attestation.adapters.inspect_ai_log_adapter as mod
    monkeypatch.setattr(mod, "_INSPECT_AI_AVAILABLE", False)
    with pytest.raises(ImportError, match="inspect_ai is required"):
        InspectAILogAdapter().to_bundle("/fake/run.eval")


def test_path_loading_calls_read_functions(monkeypatch, tmp_path):
    """File-path branch: _read_eval_log and _read_eval_log_samples are called."""
    import valichord_attestation.adapters.inspect_ai_log_adapter as mod

    fake_log = _mock_log()
    fake_samples = [_mock_sample(i) for i in range(3)]

    monkeypatch.setattr(mod, "_read_eval_log", lambda _: fake_log)
    monkeypatch.setattr(mod, "_read_eval_log_samples", lambda _: iter(fake_samples))

    fake_path = tmp_path / "run.eval"
    fake_path.touch()

    bundle = InspectAILogAdapter().to_bundle(str(fake_path))
    assert isinstance(bundle, Bundle)
    assert bundle.model_id == fake_log.eval.model
    assert bundle.samples_completed == 3


# ---------------------------------------------------------------------------
# _extract_metrics unit tests
# ---------------------------------------------------------------------------

def test_extract_metrics_empty_results_returns_empty():
    log = SimpleNamespace(results=SimpleNamespace(scores=[]))
    assert _extract_metrics(log) == []


def test_extract_metrics_no_results_attr_returns_empty():
    log = SimpleNamespace()
    assert _extract_metrics(log) == []


def test_extract_metrics_non_finite_values_skipped():
    import math
    score = SimpleNamespace(
        name="s",
        metrics={
            "acc": SimpleNamespace(value=0.5),
            "inf": SimpleNamespace(value=math.inf),
            "nan": SimpleNamespace(value=float("nan")),
        },
    )
    log = SimpleNamespace(results=SimpleNamespace(scores=[score]))
    result = _extract_metrics(log)
    keys = [m["key"] for m in result]
    assert "acc" in keys
    assert "inf" not in keys
    assert "nan" not in keys
