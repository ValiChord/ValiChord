from __future__ import annotations

import hashlib
import math

import jcs

from .bundle import Bundle, Metric, MalformedBundleError


def pre_round(value: float, *, label: str = "value") -> float:
    """Round a metric float to 6 decimal places, rejecting non-finite values.

    Call this before constructing Metric objects. Pre-rounding is a policy
    gate — values that agree within 6 dp hash identically; values that differ
    beyond 6 dp still produce distinct hashes.

    Raises MalformedBundleError for NaN or Infinity.
    """
    if not math.isfinite(value):
        raise MalformedBundleError(
            f"{label}: NaN and Infinity are not permitted in bundle metrics"
        )
    return round(value, 6)


def _metric_to_dict(m: Metric) -> dict:
    d: dict = {"key": m.key, "value": m.value}
    if m.filter is not None:
        d["filter"] = m.filter
    if m.stderr is not None:
        d["stderr"] = m.stderr
    return d


def bundle_to_dict(bundle: Bundle) -> dict:
    """Convert a Bundle to a plain dict ready for JCS canonicalisation.

    Optional fields that are None are omitted — never serialised as null.
    """
    d: dict = {
        "format_version": bundle.format_version,
        "generated_at": bundle.generated_at,
        "metrics": [_metric_to_dict(m) for m in bundle.metrics],
        "model_id": bundle.model_id,
        "outputs_merkle_root": bundle.outputs_merkle_root,
        "samples": {
            "completed": bundle.samples_completed,
            "total": bundle.samples_total,
        },
        "task_id": bundle.task_id,
    }
    if bundle.command is not None:
        d["command"] = bundle.command
    if bundle.harness_version is not None:
        d["harness_version"] = bundle.harness_version
    if bundle.meta is not None:
        d["meta"] = bundle.meta
    if bundle.repo_commit is not None:
        d["repo_commit"] = bundle.repo_commit
    return d


def canonicalise(bundle: Bundle) -> bytes:
    """Return the RFC 8785 (JCS) canonical encoding of a bundle as UTF-8 bytes."""
    result = jcs.canonicalize(bundle_to_dict(bundle))
    return result if isinstance(result, bytes) else result.encode("utf-8")


def hash_bundle(bundle: Bundle) -> str:
    """Return the SHA-256 hex digest of the canonical encoding (full bundle).

    Captures byte identity: any field change, including meta-block contents,
    produces a different hash. Use this for archival, deduplication, and
    challenge-response (the challenge binds to a specific bundle_hash).
    """
    return hashlib.sha256(canonicalise(bundle)).hexdigest()


def content_hash(bundle: Bundle) -> str:
    """Return the SHA-256 hex digest of the canonical encoding with meta excluded.

    Captures scientific equivalence: two bundles with identical model_id, task_id,
    metrics, outputs_merkle_root, samples counts, and format_version produce the same
    content_hash regardless of their meta-block contents. Use this when comparing
    reruns that may differ only in provenance (commit, timestamp, command).

    v1.1 bundles (no meta block) have content_hash == bundle_hash, because meta
    is absent from both encodings.
    """
    d = bundle_to_dict(bundle)
    d.pop("meta", None)
    raw = jcs.canonicalize(d)
    encoded = raw if isinstance(raw, bytes) else raw.encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
