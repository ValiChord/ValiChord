"""Tests for LmEvalAdapter — no lm-evaluation-harness package required."""

import json
import math
import tempfile
from pathlib import Path

import pytest

from valichord_attestation.adapters.base import AdapterBase
from valichord_attestation.adapters.lm_eval_adapter import (
    LmEvalAdapter,
    _is_stderr_key,
    _normalize_metric_key,
    _resolve_model_id,
)
from valichord_attestation.bundle import Bundle


# ---------------------------------------------------------------------------
# Minimal fake lm-eval results dicts
# ---------------------------------------------------------------------------

def _results(
    *,
    tasks=None,
    pretty_model_name="mistralai/Mistral-7B-v0.3",
    model_source=None,
    model_args=None,
    model="hf",
    git_hash="abc123def456",
    date=1_700_000_000.0,
    num_fewshot=5,
    batch_size="auto:8",
    limit=None,
    lm_eval_version=None,
) -> dict:
    """Build a minimal lm-eval results_*.json dict."""
    if tasks is None:
        tasks = {"hellaswag": {"acc,none": 0.852, "acc_norm,none": 0.865, "acc_stderr,none": 0.003}}
    config: dict = {"model": model, "num_fewshot": num_fewshot, "batch_size": batch_size}
    if model_args is not None:
        config["model_args"] = model_args
    if limit is not None:
        config["limit"] = limit
    r: dict = {"results": tasks, "config": config}
    if pretty_model_name is not None:
        r["pretty_model_name"] = pretty_model_name
    if model_source is not None:
        r["model_source"] = model_source
    if git_hash is not None:
        r["git_hash"] = git_hash
    if date is not None:
        r["date"] = date
    if lm_eval_version is not None:
        r["lm_eval_version"] = lm_eval_version
    return r


SAMPLES = {
    "hellaswag": [
        {"doc_id": 0, "target": "3", "filtered_resps": ["3"], "acc": 1.0, "acc_norm": 1.0},
        {"doc_id": 1, "target": "1", "filtered_resps": ["1"], "acc": 1.0, "acc_norm": 0.0},
    ]
}


# ---------------------------------------------------------------------------
# Key-normalisation helpers
# ---------------------------------------------------------------------------

def test_normalize_strips_none_suffix():
    assert _normalize_metric_key("acc,none") == "acc"

def test_normalize_keeps_non_none_suffix():
    assert _normalize_metric_key("acc,get-answer") == "acc,get-answer"

def test_normalize_no_suffix():
    assert _normalize_metric_key("perplexity") == "perplexity"

def test_is_stderr_true():
    assert _is_stderr_key("acc_stderr,none") is True

def test_is_stderr_norm_variant():
    assert _is_stderr_key("acc_norm_stderr,none") is True

def test_is_stderr_false_for_acc():
    assert _is_stderr_key("acc,none") is False

def test_is_stderr_false_for_perplexity():
    assert _is_stderr_key("word_perplexity,none") is False


# ---------------------------------------------------------------------------
# Model ID resolution
# ---------------------------------------------------------------------------

def test_resolve_model_id_pretty_model_name():
    assert _resolve_model_id({"pretty_model_name": "meta-llama/Llama-3.1-8B"}) == "meta-llama/Llama-3.1-8B"

def test_resolve_model_id_model_source_fallback():
    r = {"model_source": "pretrained=mistralai/Mistral-7B"}
    assert _resolve_model_id(r) == "pretrained=mistralai/Mistral-7B"

def test_resolve_model_id_model_args_fallback():
    r = {"config": {"model_args": "pretrained=mistralai/Mistral-7B-v0.3,dtype=bfloat16"}}
    assert _resolve_model_id(r) == "mistralai/Mistral-7B-v0.3"

def test_resolve_model_id_config_model_last_resort():
    r = {"config": {"model": "vllm"}}
    assert _resolve_model_id(r) == "vllm"

def test_resolve_model_id_raises_when_nothing():
    with pytest.raises(ValueError, match="Cannot determine model_id"):
        _resolve_model_id({})


# ---------------------------------------------------------------------------
# Structural
# ---------------------------------------------------------------------------

def test_is_subclass_of_base():
    assert issubclass(LmEvalAdapter, AdapterBase)

def test_to_bundle_returns_bundle():
    bundle = LmEvalAdapter().to_bundle(_results(), SAMPLES)
    assert isinstance(bundle, Bundle)


# ---------------------------------------------------------------------------
# model_id, task_id
# ---------------------------------------------------------------------------

def test_model_id_from_pretty_model_name():
    bundle = LmEvalAdapter().to_bundle(_results(), SAMPLES)
    assert bundle.model_id == "mistralai/Mistral-7B-v0.3"

def test_model_id_fallback_chain():
    r = _results(pretty_model_name=None, model_source="pretrained=my-model")
    bundle = LmEvalAdapter().to_bundle(r, SAMPLES)
    assert bundle.model_id == "pretrained=my-model"

def test_task_id_single_task():
    bundle = LmEvalAdapter().to_bundle(_results(), SAMPLES)
    assert bundle.task_id == "hellaswag"

def test_task_id_multi_task_sorted():
    tasks = {
        "mmlu": {"acc,none": 0.71, "acc_stderr,none": 0.01},
        "hellaswag": {"acc,none": 0.85, "acc_stderr,none": 0.003},
    }
    r = _results(tasks=tasks)
    samples = {
        "mmlu": [{"doc_id": 0, "target": "A", "filtered_resps": ["A"]}],
        "hellaswag": [{"doc_id": 0, "target": "3", "filtered_resps": ["3"]}],
    }
    bundle = LmEvalAdapter().to_bundle(r, samples)
    assert bundle.task_id == "hellaswag|mmlu"

def test_task_id_override():
    bundle = LmEvalAdapter().to_bundle(_results(), SAMPLES, task_id_override="my-task")
    assert bundle.task_id == "my-task"

def test_task_names_subset():
    tasks = {
        "mmlu": {"acc,none": 0.71, "acc_stderr,none": 0.01},
        "hellaswag": {"acc,none": 0.85, "acc_stderr,none": 0.003},
    }
    r = _results(tasks=tasks)
    samples = {"hellaswag": SAMPLES["hellaswag"]}
    bundle = LmEvalAdapter().to_bundle(r, samples, task_names=["hellaswag"])
    assert bundle.task_id == "hellaswag"
    metric_keys = [m.key for m in bundle.metrics]
    assert all("hellaswag" not in k or "/" not in k for k in metric_keys)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def test_metric_keys_stripped_of_none():
    bundle = LmEvalAdapter().to_bundle(_results(), SAMPLES)
    keys = [m.key for m in bundle.metrics]
    assert "acc" in keys
    assert "acc_norm" in keys
    assert not any(",none" in k for k in keys)

def test_stderr_keys_excluded():
    bundle = LmEvalAdapter().to_bundle(_results(), SAMPLES)
    keys = [m.key for m in bundle.metrics]
    assert not any("stderr" in k for k in keys)

def test_metric_values_correct():
    bundle = LmEvalAdapter().to_bundle(_results(), SAMPLES)
    acc_metric = next(m for m in bundle.metrics if m.key == "acc")
    assert math.isclose(acc_metric.value, 0.852, rel_tol=1e-5)

def test_multi_task_metric_prefix():
    tasks = {
        "mmlu": {"acc,none": 0.71, "acc_stderr,none": 0.01},
        "hellaswag": {"acc,none": 0.85, "acc_stderr,none": 0.003},
    }
    r = _results(tasks=tasks)
    samples = {
        "mmlu": [{"doc_id": 0, "target": "A", "filtered_resps": ["A"]}],
        "hellaswag": [{"doc_id": 0, "target": "3", "filtered_resps": ["3"]}],
    }
    bundle = LmEvalAdapter().to_bundle(r, samples)
    keys = [m.key for m in bundle.metrics]
    assert "hellaswag/acc" in keys
    assert "mmlu/acc" in keys

def test_metric_keys_filter():
    bundle = LmEvalAdapter().to_bundle(_results(), SAMPLES, metric_keys=["acc"])
    keys = [m.key for m in bundle.metrics]
    assert keys == ["acc"]

def test_metric_keys_filter_raises_on_missing():
    with pytest.raises(ValueError, match="metric_keys not found"):
        LmEvalAdapter().to_bundle(_results(), SAMPLES, metric_keys=["nonexistent"])

def test_non_none_filter_suffix_preserved():
    tasks = {"hellaswag": {"acc,get-answer": 0.80, "acc_norm,none": 0.85}}
    r = _results(tasks=tasks)
    bundle = LmEvalAdapter().to_bundle(r, SAMPLES)
    keys = [m.key for m in bundle.metrics]
    assert "acc,get-answer" in keys
    assert "acc_norm" in keys


# ---------------------------------------------------------------------------
# repo_commit, generated_at
# ---------------------------------------------------------------------------

def test_repo_commit_from_git_hash():
    bundle = LmEvalAdapter().to_bundle(_results(), SAMPLES)
    assert bundle.repo_commit == "abc123def456"

def test_repo_commit_absent_when_no_git_hash():
    r = _results(git_hash=None)
    bundle = LmEvalAdapter().to_bundle(r, SAMPLES)
    assert bundle.repo_commit is None

def test_generated_at_from_unix_timestamp():
    # date=1_700_000_000 → 2023-11-14T22:13:20+00:00
    bundle = LmEvalAdapter().to_bundle(_results(date=1_700_000_000.0), SAMPLES)
    assert bundle.generated_at is not None
    assert "2023-11-14" in bundle.generated_at

def test_generated_at_auto_generated_when_no_date():
    # build_bundle always produces a timestamp; when lm-eval date is absent
    # it auto-generates one rather than leaving the field empty.
    r = _results(date=None)
    bundle = LmEvalAdapter().to_bundle(r, SAMPLES)
    assert bundle.generated_at  # non-empty string


# ---------------------------------------------------------------------------
# Meta fields
# ---------------------------------------------------------------------------

def test_meta_num_fewshot():
    bundle = LmEvalAdapter().to_bundle(_results(num_fewshot=5), SAMPLES)
    assert bundle.meta is not None
    assert bundle.meta["num_fewshot"] == 5

def test_meta_batch_size():
    bundle = LmEvalAdapter().to_bundle(_results(batch_size="auto:8"), SAMPLES)
    assert bundle.meta is not None
    assert bundle.meta["batch_size"] == "auto:8"

def test_meta_limit_included_when_set():
    bundle = LmEvalAdapter().to_bundle(_results(limit=100), SAMPLES)
    assert bundle.meta is not None
    assert bundle.meta["limit"] == 100

def test_meta_limit_absent_when_none():
    bundle = LmEvalAdapter().to_bundle(_results(limit=None), SAMPLES)
    if bundle.meta:
        assert "limit" not in bundle.meta

def test_meta_extras_merged():
    bundle = LmEvalAdapter().to_bundle(_results(), SAMPLES, meta_extras={"custom": "value"})
    assert bundle.meta is not None
    assert bundle.meta["custom"] == "value"

def test_harness_version_in_bundle():
    bundle = LmEvalAdapter().to_bundle(_results(lm_eval_version="0.4.12"), SAMPLES)
    assert bundle.harness_version == "lm-evaluation-harness==0.4.12"

def test_harness_version_without_version_number():
    bundle = LmEvalAdapter().to_bundle(_results(), SAMPLES)
    assert bundle.harness_version == "lm-evaluation-harness"


# ---------------------------------------------------------------------------
# Samples and Merkle root
# ---------------------------------------------------------------------------

def test_samples_produce_non_empty_merkle_root():
    bundle = LmEvalAdapter().to_bundle(_results(), SAMPLES)
    assert bundle.outputs_merkle_root is not None
    assert len(bundle.outputs_merkle_root) == 64  # hex SHA-256

def test_samples_total_declared():
    bundle = LmEvalAdapter().to_bundle(_results(), SAMPLES, samples_total=10)
    assert bundle.samples_total == 10
    assert bundle.samples_completed == 2  # len(SAMPLES["hellaswag"])

def test_samples_fallback_synthesises_leaf_per_task():
    # no samples dict → one summary leaf per task → non-empty Merkle root
    bundle = LmEvalAdapter().to_bundle(_results())
    assert bundle.outputs_merkle_root is not None

def test_samples_fallback_multi_task():
    tasks = {
        "mmlu": {"acc,none": 0.71},
        "hellaswag": {"acc,none": 0.85},
    }
    r = _results(tasks=tasks)
    bundle = LmEvalAdapter().to_bundle(r)  # no samples
    assert bundle.outputs_merkle_root is not None

def test_samples_numeric_fields_included():
    # Adapter includes numeric per-sample fields (acc, acc_norm, …)
    # as extra leaf keys — verify via round-trip determinism
    bundle1 = LmEvalAdapter().to_bundle(_results(), SAMPLES)
    bundle2 = LmEvalAdapter().to_bundle(_results(), SAMPLES)
    assert bundle1.outputs_merkle_root == bundle2.outputs_merkle_root


# ---------------------------------------------------------------------------
# File path loading
# ---------------------------------------------------------------------------

def test_load_from_path_str():
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(_results(), f)
        path = f.name
    bundle = LmEvalAdapter().to_bundle(path, SAMPLES)
    assert isinstance(bundle, Bundle)

def test_load_from_path_object():
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(_results(), f)
        path = Path(f.name)
    bundle = LmEvalAdapter().to_bundle(path, SAMPLES)
    assert isinstance(bundle, Bundle)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_raises_on_missing_results_key():
    with pytest.raises(ValueError, match="no 'results' key"):
        LmEvalAdapter().to_bundle({"config": {}}, SAMPLES)

def test_raises_on_empty_results():
    with pytest.raises(ValueError, match="no 'results' key"):
        LmEvalAdapter().to_bundle({"results": {}}, SAMPLES)

def test_raises_on_non_dict_input():
    with pytest.raises(ValueError, match="must be a dict"):
        LmEvalAdapter().to_bundle([1, 2, 3], SAMPLES)  # type: ignore[arg-type]

def test_raises_on_missing_task_name():
    with pytest.raises(ValueError, match="task_names not found"):
        LmEvalAdapter().to_bundle(_results(), SAMPLES, task_names=["unknown_task"])

def test_raises_when_all_metrics_non_numeric():
    tasks = {"hellaswag": {"acc,none": "n/a", "acc_stderr,none": "n/a"}}
    r = _results(tasks=tasks)
    with pytest.raises(ValueError, match="No finite numeric metrics"):
        LmEvalAdapter().to_bundle(r, SAMPLES)

def test_raises_when_only_stderr_metrics():
    tasks = {"hellaswag": {"acc_stderr,none": 0.003}}
    r = _results(tasks=tasks)
    with pytest.raises(ValueError, match="No finite numeric metrics"):
        LmEvalAdapter().to_bundle(r, SAMPLES)
