"""lm-evaluation-harness results → Valichord Bundle adapter.

Reads an lm-evaluation-harness ``results_*.json`` dict (v0.4+) and an optional
per-sample dict from ``samples_*.json`` (written by ``--log_samples``) and
converts them into a canonical Valichord Bundle.

Field mapping (lm-eval → Valichord Bundle):

    results["pretty_model_name"]      → Bundle.model_id  (see resolution chain below)
    task name(s)                      → Bundle.task_id   ("|"-joined when multi-task)
    results["results"][task][metric]  → Bundle.metrics   (normalised; _stderr excluded)
    results["git_hash"]               → Bundle.repo_commit
    results["date"]                   → Bundle.generated_at  (Unix ts → ISO 8601 UTC)
    samples[task]                     → Bundle.outputs_merkle_root  (per-sample dicts)

Model ID resolution (first non-empty value wins):
    1. results["pretty_model_name"]
    2. results["model_source"]
    3. "pretrained=…" value from results["config"]["model_args"]
    4. results["config"]["model"]

Task ID:
    Single task → the task name as-is.
    Multiple tasks → sorted task names joined with ``"|"``.
    Override with ``task_id_override=``.

Metric key normalisation:
    ``"acc,none"``       → ``"acc"``          (strip trailing ``,none``)
    ``"acc,get-answer"`` → ``"acc,get-answer"``  (non-trivial filter preserved)
    Keys containing ``_stderr`` (after normalisation) are excluded entirely.
    Multi-task runs prefix each key with the task name: ``"hellaswag/acc"``.

Per-sample dict format when samples are provided (``--log_samples``):
    {
        "task":          str   — task name
        "doc_id":        int   — lm-eval doc_id
        "target":        str   — expected answer
        "filtered_resps": list — model predictions post-filter
    }
    Plus any numeric per-sample metric fields from the lm-eval sample dict.

Fallback when no samples are provided:
    One summary leaf dict per task is synthesised from the task-level metric values.
    This lets the adapter run without ``--log_samples``, but the Merkle root then
    commits only to the summary metrics, not to individual predictions.  Document this
    in any attestation produced this way.

Producing the required files:
    lm_eval --model hf \\
            --model_args pretrained=<model> \\
            --tasks hellaswag,mmlu \\
            --output_path ./results \\
            --log_samples
    # writes results/results_*.json + results/samples_*.json
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..adapters.base import AdapterBase
from ..builder import build_bundle
from ..bundle import Bundle


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_metric_key(key: str) -> str:
    """Strip trailing ``,none`` filter suffix; keep other filter suffixes."""
    if key.endswith(",none"):
        return key[:-5]
    return key


def _is_stderr_key(key: str) -> bool:
    """True for lm-eval stderr/uncertainty keys (e.g. ``acc_stderr,none``)."""
    return "_stderr" in _normalize_metric_key(key)


def _resolve_model_id(results: dict) -> str:
    """Return the best available model identifier from an lm-eval results dict."""
    # 1. pretty_model_name — already cleaned up by lm-eval
    val = results.get("pretty_model_name") or ""
    if val:
        return str(val)

    # 2. model_source — typically "pretrained=…,dtype=…"
    val = results.get("model_source") or ""
    if val:
        return str(val)

    config = results.get("config") or {}

    # 3. parse "pretrained=<model>" from model_args
    model_args = str(config.get("model_args") or "")
    if model_args:
        m = re.search(r"(?:^|,)pretrained=([^,]+)", model_args)
        if m:
            return m.group(1).strip()

    # 4. config.model ("hf", "vllm", etc.) — last resort, always present
    model = str(config.get("model") or "")
    if model:
        return model

    raise ValueError(
        "Cannot determine model_id from results dict: no pretty_model_name, "
        "model_source, model_args, or config.model found."
    )


def _extract_metrics(
    results: dict,
    tasks: list[str],
    metric_keys: Optional[list[str]],
) -> list[dict]:
    """Extract finite numeric metrics from results["results"], normalised.

    For a single task the metric keys are used as-is.  For multiple tasks
    every key is prefixed with the task name (``"hellaswag/acc"``).

    ``_stderr`` keys are always excluded.  Non-finite values are silently dropped.
    """
    multi = len(tasks) > 1
    task_results: dict = results.get("results") or {}

    raw: list[dict] = []
    for task in tasks:
        task_metrics: dict = task_results.get(task) or {}
        for raw_key, val in task_metrics.items():
            if _is_stderr_key(raw_key):
                continue
            norm_key = _normalize_metric_key(raw_key)
            if metric_keys is not None and norm_key not in metric_keys:
                continue
            try:
                fval = float(val)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(fval):
                continue
            out_key = f"{task}/{norm_key}" if multi else norm_key
            raw.append({"key": out_key, "value": fval})

    if metric_keys is not None:
        missing = []
        for task in tasks:
            for mk in metric_keys:
                expected = f"{task}/{mk}" if multi else mk
                if not any(m["key"] == expected for m in raw):
                    missing.append(expected)
        if missing:
            raise ValueError(
                f"metric_keys not found in results: {missing}"
            )

    return raw


def _build_sample_list(
    tasks: list[str],
    samples: Optional[dict],
    task_results: dict,
) -> list[dict]:
    """Return a flat list of per-sample dicts for the Merkle root.

    When ``samples`` is provided (from ``samples_*.json``), each lm-eval sample
    dict is normalised to a small canonical dict.  When absent, one summary leaf
    per task is synthesised from the task-level results.
    """
    if samples is not None:
        out: list[dict] = []
        for task in tasks:
            task_samples = samples.get(task) or []
            for s in task_samples:
                leaf: dict = {
                    "task": task,
                    "doc_id": int(s.get("doc_id", 0)),
                    "target": str(s.get("target", "")),
                    "filtered_resps": s.get("filtered_resps") or [],
                }
                # include numeric per-sample metric fields (acc, acc_norm, …)
                for k, v in s.items():
                    if k in leaf:
                        continue
                    if isinstance(v, (int, float)) and math.isfinite(float(v)):
                        leaf[k] = v
                out.append(leaf)
        return out

    # Fallback: synthesise one summary leaf per task from task-level results.
    out = []
    for task in tasks:
        task_metrics: dict = task_results.get(task) or {}
        leaf = {"task": task}
        for raw_key, val in task_metrics.items():
            if _is_stderr_key(raw_key):
                continue
            norm_key = _normalize_metric_key(raw_key)
            try:
                fval = float(val)
            except (TypeError, ValueError):
                continue
            if math.isfinite(fval):
                leaf[norm_key] = fval
        out.append(leaf)
    return out


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class LmEvalAdapter(AdapterBase):
    """Adapter: lm-evaluation-harness results → Valichord attestation Bundle.

    Reads an lm-eval ``results_*.json`` dict (v0.4+) or path to such a file.
    Optionally accepts per-sample data from ``samples_*.json`` to build a
    per-prediction Merkle root.

    See module docstring for field mapping and per-sample dict format.
    """

    def to_bundle(
        self,
        results: "dict | str | Path",
        samples: "Optional[dict[str, list[dict]]]" = None,
        *,
        task_names: Optional[list[str]] = None,
        task_id_override: Optional[str] = None,
        metric_keys: Optional[list[str]] = None,
        samples_total: Optional[int] = None,
        meta_extras: Optional[dict] = None,
    ) -> Bundle:
        """Convert an lm-eval results dict to a Valichord attestation Bundle.

        Args:
            results: lm-eval results dict (from ``results_*.json``) or path to
                     that file.
            samples: per-sample dict from ``samples_*.json`` (task → list of
                     sample dicts).  When None, one summary leaf per task is
                     synthesised from the task-level metric values.
            task_names: subset of tasks to include.  Defaults to all tasks in
                        ``results["results"]``.
            task_id_override: explicit Bundle.task_id, overriding the
                              auto-derived single-task name or multi-task join.
            metric_keys: restrict metrics to these normalised key names
                         (post-``,none``-strip).  ValueError if any are missing.
            samples_total: declared total sample count for sample-omission
                           detection (threat model §10(d)).
            meta_extras: extra key/value pairs merged last into Bundle.meta.

        Returns:
            A Valichord Bundle ready for canonicalisation and hashing.

        Raises:
            ValueError:          if results is missing required keys, no tasks
                                 are present, or no finite numeric metrics remain.
            MalformedBundleError: propagated from build_bundle().
        """
        # ---- load from file or use dict directly ----------------------------
        if isinstance(results, (str, Path)):
            with open(results, encoding="utf-8") as f:
                results = json.load(f)

        if not isinstance(results, dict):
            raise ValueError(
                f"results must be a dict or path to a JSON file, got {type(results).__name__!r}"
            )

        task_results: dict = results.get("results") or {}
        if not task_results:
            raise ValueError(
                "results dict has no 'results' key or it is empty. "
                "Ensure lm-eval completed successfully and the file is intact."
            )

        # ---- select tasks ---------------------------------------------------
        available_tasks: list[str] = list(task_results.keys())
        if task_names is not None:
            missing = [t for t in task_names if t not in task_results]
            if missing:
                raise ValueError(
                    f"task_names not found in results: {missing}. "
                    f"Available: {available_tasks}"
                )
            tasks = task_names
        else:
            tasks = available_tasks

        if not tasks:
            raise ValueError("No tasks found in results dict.")

        # ---- model and task IDs ---------------------------------------------
        model_id = _resolve_model_id(results)
        task_id = task_id_override or (
            tasks[0] if len(tasks) == 1 else "|".join(sorted(tasks))
        )

        # ---- metrics --------------------------------------------------------
        raw_metrics = _extract_metrics(results, tasks, metric_keys)
        if not raw_metrics:
            raise ValueError(
                "No finite numeric metrics found after filtering. "
                "Check that lm-eval produced numeric scores and that metric_keys= "
                "matches the normalised (post-',none'-strip) key names."
            )

        # ---- samples → Merkle root ------------------------------------------
        sample_list = _build_sample_list(tasks, samples, task_results)
        if not sample_list:
            raise ValueError(
                "No samples available for Merkle root. "
                "Pass samples= from samples_*.json or ensure task_results is non-empty."
            )

        # ---- generated_at from Unix timestamp -------------------------------
        generated_at: Optional[str] = None
        date_val = results.get("date")
        if date_val is not None:
            try:
                generated_at = datetime.fromtimestamp(
                    float(date_val), tz=timezone.utc
                ).isoformat()
            except (TypeError, ValueError, OSError):
                pass

        # ---- repo_commit from git_hash --------------------------------------
        repo_commit: Optional[str] = results.get("git_hash") or None

        # ---- meta from run config -------------------------------------------
        config: dict = results.get("config") or {}
        meta: dict = {}

        num_fewshot = results.get("n-shot") or config.get("num_fewshot")
        if num_fewshot is not None:
            meta["num_fewshot"] = num_fewshot

        batch_size = config.get("batch_size")
        if batch_size is not None:
            meta["batch_size"] = str(batch_size)

        limit = config.get("limit")
        if limit is not None:
            meta["limit"] = limit

        harness_ver = results.get("lm_eval_version") or results.get("harness_version")

        if meta_extras:
            meta.update(meta_extras)

        return build_bundle(
            model_id=model_id,
            task_id=task_id,
            raw_metrics=raw_metrics,
            samples=sample_list,
            samples_total=samples_total,
            repo_commit=repo_commit,
            harness_version=(
                f"lm-evaluation-harness=={harness_ver}" if harness_ver
                else "lm-evaluation-harness"
            ),
            generated_at=generated_at,
            meta=meta or None,
        )
