from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .bundle import Bundle, Metric, MalformedBundleError
from .canonical import pre_round
from .merkle import merkle_root


def build_bundle(
    *,
    model_id: str,
    task_id: str,
    raw_metrics: list[dict],
    samples: list[dict],
    repo_commit: Optional[str] = None,
    harness_version: Optional[str] = None,
    command: Optional[str] = None,
    generated_at: Optional[str] = None,
) -> Bundle:
    """Construct a Bundle from raw harness outputs.

    Args:
        model_id: model identifier (required, non-empty).
        task_id: task/eval identifier (required, non-empty).
        raw_metrics: list of dicts with keys:
            "key"    — str, metric name (required)
            "value"  — float, pre-rounded to 6 dp (required; MalformedBundleError if absent)
            "stderr" — float, optional; pre-rounded to 6 dp if present
            Missing keys always raise MalformedBundleError — never silently defaulted.
        samples: list of per-sample output dicts used to compute outputs_merkle_root.
            Must be non-empty.
        repo_commit: git commit hash of the eval repository (optional).
        harness_version: eval harness version string (optional).
        command: command used to run the eval (optional).
        generated_at: ISO 8601 timestamp; defaults to current UTC time if absent.

    Returns:
        A fully-constructed Bundle ready for canonicalisation and hashing.

    Raises:
        MalformedBundleError: if any required field is absent, empty, or contains
            a non-finite numeric value.
    """
    if not raw_metrics:
        raise MalformedBundleError("raw_metrics must not be empty")
    if not samples:
        raise MalformedBundleError("samples must not be empty — required for outputs_merkle_root")

    metrics: list[Metric] = []
    for entry in raw_metrics:
        if "key" not in entry:
            raise MalformedBundleError("each metric entry must have a 'key' field")
        key = entry["key"]
        if "value" not in entry:
            raise MalformedBundleError(
                f"metric '{key}' is missing a 'value' field — "
                "absent metrics must not be silently defaulted"
            )
        value = pre_round(float(entry["value"]), label=f"metric '{key}' value")
        stderr: Optional[float] = None
        if "stderr" in entry and entry["stderr"] is not None:
            stderr = pre_round(float(entry["stderr"]), label=f"metric '{key}' stderr")
        metrics.append(Metric(key=key, value=value, stderr=stderr))

    root = merkle_root(samples)
    ts = generated_at or datetime.now(timezone.utc).isoformat()

    return Bundle(
        format_version="v1",
        generated_at=ts,
        model_id=model_id,
        task_id=task_id,
        metrics=metrics,
        samples_total=len(samples),
        samples_completed=len(samples),
        outputs_merkle_root=root,
        repo_commit=repo_commit,
        harness_version=harness_version,
        command=command,
    )
