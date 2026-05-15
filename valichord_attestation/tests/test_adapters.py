import pytest
from valichord_attestation.adapters.base import AdapterBase
from valichord_attestation.adapters.inspect_evals_stub import InspectEvalsAdapter
from valichord_attestation.bundle import Bundle


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

MINIMAL_BLOCK = {
    "commit": "abc123def456" * 3,  # 36-char SHA (arbitrary length OK)
    "results": [
        {
            "model": "gpt-4o",
            "metrics": [{"key": "accuracy", "value": 0.856}],
        }
    ],
}

FULL_BLOCK = {
    "commit": "abc123def456abc123def456abc123def456abc1",
    "command": "inspect eval arc_easy --model gpt-4o",
    "timestamp": "2026-05-01T12:00:00+00:00",
    "version": "1.0",
    "notes": ["Ran on A100", "Rate limited to 10 req/s"],
    "results": [
        {
            "model": "gpt-4o",
            "task": "arc_easy",
            "provider": "OpenAI",
            "time": "45.3s",
            "date": "2026-05-01",
            "metrics": [
                {"key": "accuracy", "value": 0.856},
                {"key": "stderr", "value": 0.032},
            ],
        },
        {
            "model": "claude-opus-4",
            "task": "arc_easy",
            "provider": "Anthropic",
            "metrics": [
                {"key": "accuracy", "value": 0.891},
                {"key": "stderr", "value": 0.028},
            ],
        },
    ],
}

SAMPLES = [
    {"sample_id": "1", "input": "What is 2+2?", "target": "4", "model_answer": "4", "correct": True},
    {"sample_id": "2", "input": "Capital of France?", "target": "Paris", "model_answer": "Paris", "correct": True},
]


# ---------------------------------------------------------------------------
# Structural
# ---------------------------------------------------------------------------

def test_is_subclass_of_base():
    assert issubclass(InspectEvalsAdapter, AdapterBase)


def test_to_bundle_returns_bundle():
    adapter = InspectEvalsAdapter()
    bundle = adapter.to_bundle(MINIMAL_BLOCK, SAMPLES)
    assert isinstance(bundle, Bundle)


# ---------------------------------------------------------------------------
# Field mapping — required fields
# ---------------------------------------------------------------------------

def test_model_id_mapped():
    adapter = InspectEvalsAdapter()
    bundle = adapter.to_bundle(MINIMAL_BLOCK, SAMPLES)
    assert bundle.model_id == "gpt-4o"


def test_repo_commit_mapped():
    adapter = InspectEvalsAdapter()
    bundle = adapter.to_bundle(MINIMAL_BLOCK, SAMPLES)
    assert bundle.repo_commit == MINIMAL_BLOCK["commit"]


def test_metrics_key_and_value_mapped():
    adapter = InspectEvalsAdapter()
    bundle = adapter.to_bundle(MINIMAL_BLOCK, SAMPLES)
    assert len(bundle.metrics) == 1
    assert bundle.metrics[0].key == "accuracy"
    assert abs(bundle.metrics[0].value - 0.856) < 1e-9


def test_merkle_root_populated():
    adapter = InspectEvalsAdapter()
    bundle = adapter.to_bundle(MINIMAL_BLOCK, SAMPLES)
    assert len(bundle.outputs_merkle_root) == 64  # SHA-256 hex


# ---------------------------------------------------------------------------
# task convention: None → "overall"
# ---------------------------------------------------------------------------

def test_task_none_becomes_overall():
    block = {
        "commit": "abc",
        "results": [
            {"model": "gpt-4o", "metrics": [{"key": "accuracy", "value": 0.9}]},
        ],
    }
    adapter = InspectEvalsAdapter()
    bundle = adapter.to_bundle(block, SAMPLES)
    assert bundle.task_id == "overall"


def test_task_string_preserved():
    adapter = InspectEvalsAdapter()
    bundle = adapter.to_bundle(FULL_BLOCK, SAMPLES, result_index=0)
    assert bundle.task_id == "arc_easy"


# ---------------------------------------------------------------------------
# Optional top-level provenance fields
# ---------------------------------------------------------------------------

def test_command_mapped():
    adapter = InspectEvalsAdapter()
    bundle = adapter.to_bundle(FULL_BLOCK, SAMPLES)
    assert bundle.command == FULL_BLOCK["command"]


def test_generated_at_from_timestamp():
    adapter = InspectEvalsAdapter()
    bundle = adapter.to_bundle(FULL_BLOCK, SAMPLES)
    assert bundle.generated_at == FULL_BLOCK["timestamp"]


def test_generated_at_defaults_when_absent():
    adapter = InspectEvalsAdapter()
    bundle = adapter.to_bundle(MINIMAL_BLOCK, SAMPLES)
    # Builder fills in current UTC time — just verify it's a non-empty string
    assert bundle.generated_at and len(bundle.generated_at) > 0


def test_no_command_when_absent():
    adapter = InspectEvalsAdapter()
    bundle = adapter.to_bundle(MINIMAL_BLOCK, SAMPLES)
    assert bundle.command is None


# ---------------------------------------------------------------------------
# Meta fields (version, notes, provider, time, date)
# ---------------------------------------------------------------------------

def test_meta_eval_version():
    adapter = InspectEvalsAdapter()
    meta = adapter.to_bundle(FULL_BLOCK, SAMPLES).meta
    assert meta is not None
    assert meta["eval_version"] == "1.0"


def test_meta_notes():
    adapter = InspectEvalsAdapter()
    meta = adapter.to_bundle(FULL_BLOCK, SAMPLES).meta
    assert meta is not None
    assert meta["notes"] == ["Ran on A100", "Rate limited to 10 req/s"]


def test_meta_provider():
    adapter = InspectEvalsAdapter()
    meta = adapter.to_bundle(FULL_BLOCK, SAMPLES).meta
    assert meta is not None
    assert meta["provider"] == "OpenAI"


def test_meta_run_time():
    adapter = InspectEvalsAdapter()
    meta = adapter.to_bundle(FULL_BLOCK, SAMPLES).meta
    assert meta is not None
    assert meta["run_time"] == "45.3s"


def test_meta_run_date():
    adapter = InspectEvalsAdapter()
    meta = adapter.to_bundle(FULL_BLOCK, SAMPLES).meta
    assert meta is not None
    assert meta["run_date"] == "2026-05-01"


def test_meta_none_when_all_optional_absent():
    adapter = InspectEvalsAdapter()
    bundle = adapter.to_bundle(MINIMAL_BLOCK, SAMPLES)
    assert bundle.meta is None


# ---------------------------------------------------------------------------
# Stderr convention — standalone metric entry, not Metric.stderr
# ---------------------------------------------------------------------------

def test_stderr_metric_as_standalone_entry():
    block = {
        "commit": "abc",
        "results": [
            {
                "model": "gpt-4o",
                "metrics": [
                    {"key": "accuracy", "value": 0.856},
                    {"key": "stderr", "value": 0.032},
                ],
            }
        ],
    }
    adapter = InspectEvalsAdapter()
    bundle = adapter.to_bundle(block, SAMPLES)
    assert len(bundle.metrics) == 2
    keys = [m.key for m in bundle.metrics]
    assert "accuracy" in keys
    assert "stderr" in keys
    # The "stderr" metric has no Metric.stderr field — it's a standalone Metric
    stderr_metric = next(m for m in bundle.metrics if m.key == "stderr")
    assert abs(stderr_metric.value - 0.032) < 1e-9
    assert stderr_metric.stderr is None  # not a paired stderr, just a named metric


# ---------------------------------------------------------------------------
# Multi-result + result_index
# ---------------------------------------------------------------------------

def test_result_index_zero_is_default():
    adapter = InspectEvalsAdapter()
    bundle0 = adapter.to_bundle(FULL_BLOCK, SAMPLES)
    bundle_explicit = adapter.to_bundle(FULL_BLOCK, SAMPLES, result_index=0)
    assert bundle0.model_id == bundle_explicit.model_id


def test_result_index_selects_second_result():
    adapter = InspectEvalsAdapter()
    bundle = adapter.to_bundle(FULL_BLOCK, SAMPLES, result_index=1)
    assert bundle.model_id == "claude-opus-4"
    meta = bundle.meta
    assert meta is not None
    assert meta["provider"] == "Anthropic"


def test_result_index_out_of_range():
    adapter = InspectEvalsAdapter()
    with pytest.raises(IndexError, match="out of range"):
        adapter.to_bundle(FULL_BLOCK, SAMPLES, result_index=99)


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_empty_results_raises_value_error():
    block = {"commit": "abc", "results": []}
    adapter = InspectEvalsAdapter()
    with pytest.raises(ValueError, match="non-empty 'results'"):
        adapter.to_bundle(block, SAMPLES)


def test_missing_results_key_raises_value_error():
    block = {"commit": "abc"}
    adapter = InspectEvalsAdapter()
    with pytest.raises(ValueError, match="non-empty 'results'"):
        adapter.to_bundle(block, SAMPLES)


def test_result_with_no_valid_metrics_raises_value_error():
    block = {
        "commit": "abc",
        "results": [{"model": "gpt-4o", "metrics": [{"key": "accuracy"}]}],  # missing value
    }
    adapter = InspectEvalsAdapter()
    with pytest.raises(ValueError, match="no valid metrics"):
        adapter.to_bundle(block, SAMPLES)


def test_result_with_empty_metrics_raises_value_error():
    block = {
        "commit": "abc",
        "results": [{"model": "gpt-4o", "metrics": []}],
    }
    adapter = InspectEvalsAdapter()
    with pytest.raises(ValueError, match="no valid metrics"):
        adapter.to_bundle(block, SAMPLES)
