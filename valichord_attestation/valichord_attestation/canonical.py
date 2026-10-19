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
    if bundle.prml_lock_hash is not None:
        d["prml_lock_hash"] = bundle.prml_lock_hash
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


def content_preimage(bundle: Bundle) -> bytes:
    """Return the exact bytes that :func:`content_hash` digests.

    The RFC 8785 canonical encoding of the bundle with ``meta`` removed.

    Extracted so the preimage has one definition. ``content_hash`` hashes it,
    and ``protocol.submission_bytes`` hands the same bytes to the DNA's
    ``compute_data_hash`` \u2014 which makes
    ``sha256(content_preimage(b)) == content_hash(b)`` structural rather than a
    coincidence two call sites happen to preserve.

    .. note::
       This exists because the format has been bitten by exactly that. Shipping
       v2 turned up a *second inlined copy* of the Merkle pair hashing inside
       ``verify_response``; had it not been found by reading, v2 would have
       shipped with challenge-response still computing v1 paths. A third inlined
       copy of the canonical encoding is the same mistake with a different
       victim.
    """
    d = bundle_to_dict(bundle)
    d.pop("meta", None)
    raw = jcs.canonicalize(d)
    return raw if isinstance(raw, bytes) else raw.encode("utf-8")


#: Fields that describe *a run* rather than *the claim*. ``claim_hash`` excludes
#: them; ``content_hash`` excludes only ``meta``. ``prml_lock_hash`` is
#: deliberately NOT here: a pre-registered claim and a post-hoc one are
#: different claims.
CLAIM_EXCLUDED_FIELDS = ("meta", "generated_at", "repo_commit", "harness_version", "command")


def claim_preimage(bundle: Bundle) -> bytes:
    """Return the exact bytes that :func:`claim_hash` digests.

    The RFC 8785 canonical encoding of the bundle with ``meta`` **and** the
    top-level run-provenance fields (``generated_at``, ``repo_commit``,
    ``harness_version``, ``command``) removed.

    WHY THIS EXISTS (2026-10-19). ``content_hash`` removes ``meta`` only, but
    ``generated_at`` is a required top-level field and ``build_bundle`` defaults
    it to the current time. So two runs of the same evaluation, on two machines
    or on two days, have different ``content_hash`` values — and the protocol
    bridge, which needs one identifier per *claim*, cannot use it. This is the
    preimage the bridge uses instead (``protocol.submission_bytes``).

    It inherits the ``meta`` trap: anything that could change a result must not
    be placed in ``meta`` or in these provenance fields, or two different
    claims will share a ``claim_hash``.
    """
    d = bundle_to_dict(bundle)
    for key in CLAIM_EXCLUDED_FIELDS:
        d.pop(key, None)
    raw = jcs.canonicalize(d)
    return raw if isinstance(raw, bytes) else raw.encode("utf-8")


def claim_hash(bundle: Bundle) -> str:
    """Return the SHA-256 hex digest of :func:`claim_preimage`.

    Answers "is this the same claim?": the same model, task, metrics, sample
    counts, outputs Merkle root, format version (and pre-registration lock, if
    any), regardless of when, where or how the run was performed.
    """
    return hashlib.sha256(claim_preimage(bundle)).hexdigest()


def content_hash(bundle: Bundle) -> str:
    """Return the SHA-256 hex digest of the canonical encoding with meta excluded.

    Captures scientific equivalence: two bundles with identical model_id, task_id,
    metrics, outputs_merkle_root, samples counts, and format_version produce the same
    content_hash regardless of their meta-block contents.

    ⚠️ It does NOT ignore run provenance outside ``meta``: the top-level
    ``generated_at`` (always present), ``repo_commit``, ``harness_version`` and
    ``command`` are all inside it. To compare reruns that may differ in commit,
    timestamp or command, use :func:`claim_hash` instead. (This docstring said
    otherwise until 2026-10-19.)

    v1.1 bundles (no meta block) have content_hash == bundle_hash, because meta
    is absent from both encodings.
    """
    return hashlib.sha256(content_preimage(bundle)).hexdigest()
