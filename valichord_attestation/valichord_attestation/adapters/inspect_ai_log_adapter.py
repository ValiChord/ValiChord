"""inspect_ai EvalLog → Valichord Bundle adapter.

Reads inspect_ai evaluation log files (.eval / .json) or accepts a pre-loaded
EvalLog-duck-type object and converts the run data into a canonical Valichord Bundle.

Field mapping (EvalLog → Valichord Bundle):

    EvalSpec.model             → Bundle.model_id
    EvalSpec.task              → Bundle.task_id  (override with task_id_override=)
    EvalSpec.created           → Bundle.generated_at  (ISO 8601 datetime)
    EvalSpec.revision.commit   → Bundle.repo_commit   (auto-extracted when available)
    EvalResults.scores         → Bundle.metrics       (all scorers; scorer-name prefix on collision)
    EvalLog.samples            → Bundle.outputs_merkle_root  (per-sample dicts)
    EvalSpec.packages          → Bundle.meta["harness_version"]  (inspect_ai version string)
    EvalSpec.task_version      → Bundle.meta["task_version"]     (when non-default)
    EvalStats.completed_at     → Bundle.meta["completed_at"]     (when non-empty)

Per-sample dict format (feeds merkle_root()):
    {
        "id":     str   — sample ID (always string for determinism)
        "epoch":  int   — epoch number (multi-epoch evals)
        "output": str | null  — ModelOutput.completion; null for errored samples
        "scores": {scorer_name: {"value": str, "answer": str | null}, ...}
    }

Score selection:
    By default all scorers' metrics are collected.  On key collision across
    scorers, the key is prefixed with the scorer name ("scorer_name/metric").
    Use score_name= to restrict metrics to a single named scorer.

inspect_ai dependency:
    Loading from a file path requires inspect_ai to be installed.
    Passing a pre-loaded duck-type object works without inspect_ai (useful for
    testing).  Install: pip install inspect-ai
"""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from ..adapters.base import AdapterBase
from ..builder import build_bundle
from ..bundle import Bundle

try:
    from inspect_ai.log import read_eval_log as _read_eval_log
    from inspect_ai.log import read_eval_log_samples as _read_eval_log_samples

    _INSPECT_AI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _INSPECT_AI_AVAILABLE = False
    _read_eval_log = None  # type: ignore[assignment]
    _read_eval_log_samples = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sample_to_dict(sample: object) -> dict:
    """Convert an EvalSample (or duck-type) to a JSON-serialisable bundle dict.

    Always produces the same four keys — id, epoch, output, scores — so the
    dict shape is uniform across all samples (consistent JCS encoding).
    """
    output_text: Optional[str] = None
    out = getattr(sample, "output", None)
    if out is not None:
        completion = getattr(out, "completion", None)
        if completion is not None:
            output_text = str(completion)

    raw_scores = getattr(sample, "scores", None) or {}
    scores = {
        name: {
            "value": str(score.value) if score.value is not None else None,
            "answer": getattr(score, "answer", None),
        }
        for name, score in raw_scores.items()
    }

    return {
        "id": str(getattr(sample, "id", "")),
        "epoch": int(getattr(sample, "epoch", 1)),
        "output": output_text,
        "scores": scores,
    }


def _extract_metrics(eval_log: object, score_name: Optional[str] = None) -> list[dict]:
    """Extract numeric metrics from EvalLog.results.scores into build_bundle() format.

    Selects from all EvalScore objects unless score_name is given.  On key
    collision within the selected set, the metric key is prefixed with the
    scorer name to produce a unique key (e.g. "accuracy_scorer/accuracy").
    Non-numeric metric values are silently skipped.
    """
    results = getattr(eval_log, "results", None)
    all_scores: list = list(getattr(results, "scores", None) or [])

    selected = [
        s for s in all_scores
        if score_name is None or getattr(s, "name", None) == score_name
    ]

    # Count metric key occurrences within the selected set to detect collisions.
    key_counts: Counter = Counter(
        k
        for s in selected
        for k in (getattr(s, "metrics", None) or {})
    )

    raw_metrics: list[dict] = []
    for eval_score in selected:
        scorer_name: str = getattr(eval_score, "name", "score") or "score"
        for mname, emetic in (getattr(eval_score, "metrics", None) or {}).items():
            try:
                val = float(emetic.value)
            except (TypeError, ValueError, AttributeError):
                continue
            if not math.isfinite(val):
                continue
            key = mname if key_counts[mname] == 1 else f"{scorer_name}/{mname}"
            raw_metrics.append({"key": key, "value": val})

    return raw_metrics


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class InspectAILogAdapter(AdapterBase):
    """Adapter: inspect_ai EvalLog → Valichord attestation Bundle.

    Reads inspect_ai evaluation log files (.eval / .json format) or accepts
    a pre-loaded EvalLog-compatible object.  Produces a Bundle that commits
    to the model, task, metrics, and per-sample outputs of the evaluation run.

    See module docstring for field mapping and per-sample dict format.
    """

    def to_bundle(
        self,
        log: "str | Path | object",
        *,
        task_id_override: Optional[str] = None,
        repo_commit: Optional[str] = None,
        score_name: Optional[str] = None,
        samples_total: Optional[int] = None,
        meta_extras: Optional[dict] = None,
    ) -> Bundle:
        """Convert an inspect_ai log to a Valichord attestation Bundle.

        Args:
            log: Path to a .eval or .json log file (str or Path), or a
                 pre-loaded EvalLog-duck-type with .eval, .results, .samples,
                 and optionally .stats attributes.
            task_id_override: Override Bundle.task_id when EvalSpec.task is a
                              module path rather than a short task name.
            repo_commit: Git commit SHA of the eval code repository.  When
                         absent, auto-extracted from EvalSpec.revision.commit
                         if the log records it.
            score_name: Restrict metrics to a single named EvalScore.  By
                        default all scorers are combined; colliding metric keys
                        are prefixed with the scorer name.
            samples_total: Declared total sample count (threat-model §10(d)
                           guard for sample-omission detection).  Defaults to
                           len(log.samples).
            meta_extras: Extra key/value pairs merged last into Bundle.meta.
                         Useful for provenance from eval.yaml (arxiv, group,
                         human_baseline) when calling alongside InspectEvalsAdapter.

        Returns:
            A Valichord Bundle ready for canonicalisation and hashing.

        Raises:
            ImportError:      if log is a file path and inspect_ai is not installed.
            ValueError:       if EvalLog.status is not "success", if model_id is
                              empty, if no numeric metrics are found, or if the
                              sample list is empty.
            MalformedBundleError: propagated from build_bundle() on bad values.
        """
        # ---- load from file or use duck-type --------------------------------
        eval_log: Any
        if isinstance(log, (str, Path)):
            if not _INSPECT_AI_AVAILABLE:
                raise ImportError(
                    "inspect_ai is required for loading .eval files.\n"
                    "Install: pip install inspect-ai\n"
                    "Or pass a pre-loaded EvalLog object."
                )
            eval_log = _read_eval_log(str(log))  # type: ignore[misc]
            sample_list = list(_read_eval_log_samples(str(log)))  # type: ignore[misc]
        else:
            eval_log = log
            sample_list = list(getattr(eval_log, "samples", None) or [])

        # ---- status guard ---------------------------------------------------
        status = getattr(eval_log, "status", "success")
        if status != "success":
            raise ValueError(
                f"EvalLog.status is {status!r} — only 'success' is supported for "
                "attestation.  Verify the run completed without errors."
            )

        # ---- model and task -------------------------------------------------
        eval_spec = eval_log.eval
        model_id: str = str(getattr(eval_spec, "model", "") or "")
        if not model_id:
            raise ValueError(
                "EvalSpec.model is empty — cannot build Bundle.model_id"
            )

        raw_task: str = str(getattr(eval_spec, "task", "") or "")
        task_id: str = task_id_override or raw_task or "overall"

        # ---- timestamp ------------------------------------------------------
        created = getattr(eval_spec, "created", None)
        generated_at: Optional[str] = (
            created.isoformat() if hasattr(created, "isoformat") else str(created)
        ) if created is not None else None

        # ---- repo commit (auto-extract from revision if not provided) -------
        if repo_commit is None:
            revision = getattr(eval_spec, "revision", None)
            if revision is not None:
                repo_commit = getattr(revision, "commit", None) or None

        # ---- metrics --------------------------------------------------------
        raw_metrics = _extract_metrics(eval_log, score_name=score_name)
        if not raw_metrics:
            detail = f" (score_name={score_name!r})" if score_name else ""
            raise ValueError(
                f"No numeric metrics found in EvalLog.results.scores{detail}. "
                "Verify the evaluation completed and produced results."
            )

        # ---- samples → Merkle root ------------------------------------------
        sample_dicts = [_sample_to_dict(s) for s in sample_list]
        if not sample_dicts:
            raise ValueError(
                "EvalLog.samples is empty — cannot compute outputs_merkle_root."
            )

        # ---- meta -----------------------------------------------------------
        meta: dict = {}

        packages = getattr(eval_spec, "packages", None) or {}
        ia_ver = packages.get("inspect_ai") or packages.get("inspect-ai")
        if ia_ver:
            meta["harness_version"] = f"inspect_ai=={ia_ver}"

        task_version = getattr(eval_spec, "task_version", None)
        if task_version is not None and task_version != 0:
            meta["task_version"] = str(task_version)

        stats = getattr(eval_log, "stats", None)
        if stats is not None:
            completed_at = getattr(stats, "completed_at", None)
            if completed_at:
                meta["completed_at"] = str(completed_at)

        if meta_extras:
            meta.update(meta_extras)

        return build_bundle(
            model_id=model_id,
            task_id=task_id,
            raw_metrics=raw_metrics,
            samples=sample_dicts,
            samples_total=samples_total,
            repo_commit=repo_commit,
            generated_at=generated_at,
            meta=meta or None,
        )
