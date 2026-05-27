import math
import pytest
from valichord_attestation.adapters.base import AdapterBase
from valichord_attestation.adapters.wandb_adapter import WandbRunAdapter
from valichord_attestation.bundle import Bundle


# ---------------------------------------------------------------------------
# Minimal fake wandb Run — no wandb package required
# ---------------------------------------------------------------------------

class _FakeRun:
    """Minimal stand-in for wandb.apis.public.Run for unit testing."""

    def __init__(
        self,
        *,
        config=None,
        summary=None,
        metadata=None,
        created_at="2026-05-27T12:00:00+00:00",
        entity="my-org",
        project="evals",
        id="run123",
        name="sunny-meadow-42",
        url="https://wandb.ai/my-org/evals/runs/run123",
        tags=None,
        notes=None,
    ):
        self.config = config or {"model": "gpt-4o", "task": "mmlu"}
        self.summary = summary if summary is not None else {
            "accuracy": 0.856,
            "loss": 0.234,
            "_runtime": 3600,
            "_step": 100,
            "_timestamp": 1748390400.0,
        }
        self.metadata = metadata if metadata is not None else {
            "git": {"commit": "abc123def456abc123def456abc123def456abc1"},
            "program": "eval.py",
            "args": ["--model", "gpt-4o", "--task", "mmlu"],
        }
        self.created_at = created_at
        self.entity = entity
        self.project = project
        self.id = id
        self.name = name
        self.url = url
        self.tags = tags or []
        self.notes = notes


SAMPLES = [
    {"sample_id": "1", "input": "What is 2+2?", "target": "4", "model_answer": "4"},
    {"sample_id": "2", "input": "Capital of France?", "target": "Paris", "model_answer": "Paris"},
]


# ---------------------------------------------------------------------------
# Structural
# ---------------------------------------------------------------------------

def test_is_subclass_of_base():
    assert issubclass(WandbRunAdapter, AdapterBase)


def test_to_bundle_returns_bundle():
    bundle = WandbRunAdapter().to_bundle(_FakeRun(), SAMPLES)
    assert isinstance(bundle, Bundle)


# ---------------------------------------------------------------------------
# model_id resolution
# ---------------------------------------------------------------------------

def test_model_id_from_config():
    run = _FakeRun(config={"model": "gpt-4o", "task": "mmlu"})
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.model_id == "gpt-4o"


def test_model_id_fallback_model_name():
    run = _FakeRun(config={"model_name": "claude-opus-4", "task": "mmlu"})
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.model_id == "claude-opus-4"


def test_model_id_fallback_model_id_key():
    run = _FakeRun(config={"model_id": "gemini-2.0", "task": "mmlu"})
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.model_id == "gemini-2.0"


def test_model_id_fallback_to_run_name():
    run = _FakeRun(config={"task": "mmlu"}, name="sunny-meadow-42")
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.model_id == "sunny-meadow-42"


def test_model_id_custom_key():
    run = _FakeRun(config={"llm": "mistral-7b", "task": "arc"})
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES, model_id_key="llm")
    assert bundle.model_id == "mistral-7b"


def test_model_id_unresolvable_raises():
    run = _FakeRun(config={"task": "mmlu"}, name="")
    with pytest.raises(ValueError, match="model_id"):
        WandbRunAdapter().to_bundle(run, SAMPLES)


# ---------------------------------------------------------------------------
# task_id resolution
# ---------------------------------------------------------------------------

def test_task_id_from_config():
    run = _FakeRun(config={"model": "gpt-4o", "task": "mmlu"})
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.task_id == "mmlu"


def test_task_id_fallback_dataset():
    run = _FakeRun(config={"model": "gpt-4o", "dataset": "arc_easy"})
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.task_id == "arc_easy"


def test_task_id_fallback_benchmark():
    run = _FakeRun(config={"model": "gpt-4o", "benchmark": "hellaswag"})
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.task_id == "hellaswag"


def test_task_id_fallback_task_name():
    run = _FakeRun(config={"model": "gpt-4o", "task_name": "winogrande"})
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.task_id == "winogrande"


def test_task_id_fallback_overall():
    run = _FakeRun(config={"model": "gpt-4o"})
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.task_id == "overall"


def test_task_id_custom_key():
    run = _FakeRun(config={"model": "gpt-4o", "eval_suite": "gpqa_diamond"})
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES, task_id_key="eval_suite")
    assert bundle.task_id == "gpqa_diamond"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def test_metrics_extracted_from_summary():
    run = _FakeRun(summary={"accuracy": 0.856, "loss": 0.234})
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    keys = {m.key for m in bundle.metrics}
    assert "accuracy" in keys
    assert "loss" in keys


def test_wandb_internal_fields_excluded():
    run = _FakeRun(summary={
        "accuracy": 0.856,
        "_runtime": 3600,
        "_step": 100,
        "_timestamp": 1748390400.0,
    })
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    keys = {m.key for m in bundle.metrics}
    assert "_runtime" not in keys
    assert "_step" not in keys
    assert "_timestamp" not in keys
    assert "accuracy" in keys


def test_non_numeric_summary_fields_excluded():
    run = _FakeRun(summary={
        "accuracy": 0.856,
        "model_type": "transformer",   # string — should be excluded
        "converged": True,             # bool is subclass of int — included
    })
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    keys = {m.key for m in bundle.metrics}
    assert "model_type" not in keys
    assert "accuracy" in keys


def test_metric_keys_selects_subset():
    run = _FakeRun(summary={"accuracy": 0.856, "loss": 0.234, "f1": 0.791})
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES, metric_keys=["accuracy", "f1"])
    keys = [m.key for m in bundle.metrics]
    assert keys == ["accuracy", "f1"]
    assert "loss" not in keys


def test_metric_keys_missing_raises():
    run = _FakeRun(summary={"accuracy": 0.856})
    with pytest.raises(ValueError, match="not found in run.summary"):
        WandbRunAdapter().to_bundle(run, SAMPLES, metric_keys=["accuracy", "nonexistent"])


def test_metric_keys_non_numeric_raises():
    run = _FakeRun(summary={"accuracy": 0.856, "label": "good"})
    with pytest.raises(ValueError, match="not numeric"):
        WandbRunAdapter().to_bundle(run, SAMPLES, metric_keys=["accuracy", "label"])


def test_no_numeric_metrics_raises():
    run = _FakeRun(summary={"_runtime": 3600, "label": "good"})
    with pytest.raises(ValueError, match="no usable numeric metrics"):
        WandbRunAdapter().to_bundle(run, SAMPLES)


def test_nan_metrics_filtered_and_noted_in_meta():
    run = _FakeRun(summary={
        "accuracy": 0.856,
        "bad_metric": float("nan"),
        "inf_metric": float("inf"),
    })
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    keys = {m.key for m in bundle.metrics}
    assert "bad_metric" not in keys
    assert "inf_metric" not in keys
    assert "accuracy" in keys
    assert bundle.meta is not None
    dropped = bundle.meta.get("filtered_non_finite_metrics", [])
    assert "bad_metric" in dropped
    assert "inf_metric" in dropped


def test_nan_only_metrics_raises():
    run = _FakeRun(summary={"only_nan": float("nan")})
    with pytest.raises(ValueError, match="no usable numeric metrics"):
        WandbRunAdapter().to_bundle(run, SAMPLES)


def test_metric_values_correct():
    run = _FakeRun(summary={"accuracy": 0.856789})
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    acc = next(m for m in bundle.metrics if m.key == "accuracy")
    assert abs(acc.value - 0.856789) < 1e-5


# ---------------------------------------------------------------------------
# Provenance fields
# ---------------------------------------------------------------------------

def test_repo_commit_from_git_metadata():
    run = _FakeRun(metadata={
        "git": {"commit": "abc123def456abc123def456abc123def456abc1"},
        "program": "eval.py",
    })
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.repo_commit == "abc123def456abc123def456abc123def456abc1"


def test_repo_commit_none_when_no_git():
    run = _FakeRun(metadata={"program": "eval.py"})
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.repo_commit is None


def test_repo_commit_none_when_no_metadata():
    run = _FakeRun(metadata={})
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.repo_commit is None


def test_generated_at_from_created_at():
    run = _FakeRun(created_at="2026-05-27T12:00:00+00:00")
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.generated_at == "2026-05-27T12:00:00+00:00"


def test_generated_at_defaults_when_absent():
    run = _FakeRun(created_at=None)
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.generated_at and len(bundle.generated_at) > 0


def test_command_with_args():
    run = _FakeRun(metadata={
        "program": "eval.py",
        "args": ["--model", "gpt-4o", "--task", "mmlu"],
    })
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.command == "eval.py --model gpt-4o --task mmlu"


def test_command_without_args():
    run = _FakeRun(metadata={"program": "eval.py", "args": []})
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.command == "eval.py"


def test_command_none_when_no_program():
    run = _FakeRun(metadata={})
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.command is None


# ---------------------------------------------------------------------------
# Merkle root / samples
# ---------------------------------------------------------------------------

def test_merkle_root_populated():
    bundle = WandbRunAdapter().to_bundle(_FakeRun(), SAMPLES)
    assert len(bundle.outputs_merkle_root) == 64  # SHA-256 hex


def test_samples_completed_matches_input():
    bundle = WandbRunAdapter().to_bundle(_FakeRun(), SAMPLES)
    assert bundle.samples_completed == len(SAMPLES)


# ---------------------------------------------------------------------------
# Meta / wandb provenance
# ---------------------------------------------------------------------------

def test_meta_includes_wandb_entity():
    bundle = WandbRunAdapter().to_bundle(_FakeRun(entity="my-org"), SAMPLES)
    assert bundle.meta is not None
    assert bundle.meta["wandb_entity"] == "my-org"


def test_meta_includes_wandb_project():
    bundle = WandbRunAdapter().to_bundle(_FakeRun(project="evals"), SAMPLES)
    assert bundle.meta is not None
    assert bundle.meta["wandb_project"] == "evals"


def test_meta_includes_wandb_run_id():
    bundle = WandbRunAdapter().to_bundle(_FakeRun(id="run123"), SAMPLES)
    assert bundle.meta is not None
    assert bundle.meta["wandb_run_id"] == "run123"


def test_meta_includes_wandb_run_name():
    bundle = WandbRunAdapter().to_bundle(_FakeRun(name="sunny-meadow-42"), SAMPLES)
    assert bundle.meta is not None
    assert bundle.meta["wandb_run_name"] == "sunny-meadow-42"


def test_meta_includes_wandb_run_url():
    run = _FakeRun(url="https://wandb.ai/my-org/evals/runs/run123")
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.meta is not None
    assert bundle.meta["wandb_run_url"] == "https://wandb.ai/my-org/evals/runs/run123"


def test_meta_includes_tags_when_present():
    run = _FakeRun(tags=["benchmark", "v2"])
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.meta is not None
    assert bundle.meta["tags"] == ["benchmark", "v2"]


def test_meta_excludes_tags_when_empty():
    run = _FakeRun(tags=[])
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.meta is None or "tags" not in (bundle.meta or {})


def test_meta_includes_notes_when_present():
    run = _FakeRun(notes="Run with new prompt template")
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.meta is not None
    assert bundle.meta["notes"] == "Run with new prompt template"


def test_meta_excludes_notes_when_absent():
    run = _FakeRun(notes=None)
    bundle = WandbRunAdapter().to_bundle(run, SAMPLES)
    assert bundle.meta is None or "notes" not in (bundle.meta or {})
