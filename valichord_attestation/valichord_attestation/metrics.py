"""Verifier-side metric recomputation (issue #13; threat model §10(c)).

A bundle commits separately to its reported ``metrics`` and to its per-sample
outputs (``outputs_merkle_root``). Nothing in the format binds one to the other,
so an honest Merkle root can sit next to a dishonest number.
``spec/conformance.md`` §4.2(5) says a verifier SHOULD recompute each reported
metric from the samples disclosed to it. This module is the tool for that step.

The verifier always supplies the derivation — which function turns samples into
the metric. The library never guesses it: the format does not record it, and a
guessed derivation that happened to agree would prove nothing.

Two situations, two functions
-----------------------------
* **The whole log is disclosed** — :func:`check_metric`. The samples are first
  re-committed and must reproduce ``outputs_merkle_root`` exactly; the metric is
  then recomputed and must equal the reported value at the format's 6-decimal
  precision. A pass is a proof, not an estimate.
* **Only challenged samples are disclosed** (the usual case) —
  :func:`bind_disclosed_samples` ties each disclosed sample to the leaf hash in a
  response that :func:`~valichord_attestation.response.verify_response` has
  already accepted, then :func:`check_mean_metric` asks whether the reported value
  is *plausible* given those samples. A subset can never reproduce an aggregate
  exactly, so this is a statistical test (Hoeffding's inequality) and its result
  is "consistent" or "inconsistent at confidence 1 − alpha" — never "verified".

What this does not check
------------------------
* That the derivation the verifier chose is the one the reporter used. A
  mismatch there reads as misreporting; agree the definition out of band.
* Metrics that are not a mean of per-sample values (pass@k with sampling,
  F1, BLEU…) from a subset. Those need the whole log, or a bound of their own.
* Anything about the samples themselves beyond their commitment: a verified
  inclusion proof says a sample was committed, not that it is correct
  (conformance §4.2(4)).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Mapping, Optional, Sequence

from .bundle import Bundle, Metric
from .canonical import pre_round
from .merkle import leaf_hash, merkle_root
from .response import ChallengeResponse

__all__ = [
    "MetricCheck",
    "MetricCheckError",
    "find_metric",
    "recompute_metric",
    "check_metric",
    "bind_disclosed_samples",
    "check_mean_metric",
]


class MetricCheckError(ValueError):
    """The check could not be performed as asked — not a finding about the bundle.

    Raised for a missing or ambiguous metric, disclosed samples that do not match
    their commitment, or inputs outside a test's assumptions. A *finding* (the
    metric does not match) is reported as ``MetricCheck.consistent = False``.
    """


@dataclass(frozen=True)
class MetricCheck:
    """The outcome of one metric check.

    Attributes:
        key, filter: Which reported metric was checked.
        reported: The value in the bundle.
        recomputed: The verifier's value from the disclosed samples.
        samples_used: How many samples the recomputation used.
        samples_completed: How many samples the bundle commits to.
        complete: True when every committed sample was used — the comparison is
            exact. False for a subset — the comparison is statistical.
        tolerance: Allowed ``|recomputed - reported|``. 0 for a complete check
            (both sides pre-rounded to 6 dp); the Hoeffding bound for a subset.
        alpha: For a subset, the probability that an HONEST report is flagged
            inconsistent. ``None`` for a complete check.
        consistent: The finding.
    """

    key: str
    filter: Optional[str]
    reported: float
    recomputed: float
    samples_used: int
    samples_completed: int
    complete: bool
    tolerance: float
    alpha: Optional[float]
    consistent: bool


def find_metric(bundle: Bundle, key: str, *, filter: Optional[str] = None) -> Metric:
    """Return the bundle's metric with this ``key`` and ``filter``.

    ``filter=None`` matches a metric with no filter. Raises
    :class:`MetricCheckError` if there is no match, or more than one.
    """
    matches = [m for m in bundle.metrics if m.key == key and m.filter == filter]
    if not matches:
        available = sorted({(m.key, m.filter) for m in bundle.metrics}, key=str)
        raise MetricCheckError(
            f"bundle reports no metric key={key!r} filter={filter!r}; it has {available}"
        )
    if len(matches) > 1:
        raise MetricCheckError(
            f"bundle reports {len(matches)} metrics with key={key!r} filter={filter!r}; "
            "cannot tell which one to check"
        )
    return matches[0]


def recompute_metric(
    samples: Sequence[dict], derivation: Callable[[Sequence[dict]], float]
) -> float:
    """Apply the verifier's ``derivation`` and round it the way bundles round.

    Pre-rounding to 6 dp is the format's own policy (``canonical.pre_round``):
    values that agree within 6 dp are the same value.
    """
    return pre_round(float(derivation(samples)), label="recomputed metric")


def check_metric(
    bundle: Bundle,
    key: str,
    samples: Sequence[dict],
    derivation: Callable[[Sequence[dict]], float],
    *,
    filter: Optional[str] = None,
) -> MetricCheck:
    """Exact check from the WHOLE disclosed log.

    Raises :class:`MetricCheckError` unless ``samples`` is exactly the committed
    log — the right number of samples, re-committing to the bundle's
    ``outputs_merkle_root`` under the bundle's own ``format_version``. Only then
    is the recomputation meaningful.
    """
    metric = find_metric(bundle, key, filter=filter)
    if len(samples) != bundle.samples_completed:
        raise MetricCheckError(
            f"an exact check needs all {bundle.samples_completed} committed samples, "
            f"got {len(samples)}; for a subset use bind_disclosed_samples + check_mean_metric"
        )
    if merkle_root(list(samples), format_version=bundle.format_version) != bundle.outputs_merkle_root:
        raise MetricCheckError(
            "the disclosed samples do not re-commit to the bundle's outputs_merkle_root — "
            "they are not the log this bundle attests"
        )
    recomputed = recompute_metric(samples, derivation)
    return MetricCheck(
        key=key,
        filter=filter,
        reported=metric.value,
        recomputed=recomputed,
        samples_used=len(samples),
        samples_completed=bundle.samples_completed,
        complete=True,
        tolerance=0.0,
        alpha=None,
        consistent=recomputed == pre_round(metric.value),
    )


def bind_disclosed_samples(
    response: ChallengeResponse,
    disclosed: Mapping[int, dict],
    bundle: Bundle,
) -> list[dict]:
    """Tie disclosed sample contents to a verified challenge response.

    A :class:`~valichord_attestation.response.ChallengeResponse` carries only leaf
    hashes and paths. The holder discloses the sample contents separately; this
    checks that each one hashes — under the bundle's ``format_version`` — to the
    leaf the response proved, and returns them in response order.

    **Call** :func:`~valichord_attestation.response.verify_response` **first.**
    This function trusts the response's leaf hashes; it is ``verify_response``
    that proves they chain to the bundle's root and are the indices the
    verifier's challenge selected.

    Raises :class:`MetricCheckError` if a challenged sample is missing from
    ``disclosed``, or does not match its leaf.
    """
    out: list[dict] = []
    for rs in response.samples:
        if rs.sample_index not in disclosed:
            raise MetricCheckError(
                f"challenged sample {rs.sample_index} was not disclosed; a check that "
                "skipped it would let the holder choose which samples are seen"
            )
        sample = disclosed[rs.sample_index]
        got = leaf_hash(sample, format_version=bundle.format_version).hex()
        if got != rs.sample_content_hash:
            raise MetricCheckError(
                f"disclosed sample {rs.sample_index} does not match the leaf hash its "
                "proof committed to"
            )
        out.append(sample)
    return out


def check_mean_metric(
    bundle: Bundle,
    key: str,
    values: Sequence[float],
    *,
    value_range: tuple[float, float] = (0.0, 1.0),
    alpha: float = 1e-3,
    filter: Optional[str] = None,
) -> MetricCheck:
    """Is a reported MEAN plausible, given per-sample values from challenged samples?

    ``values`` are the verifier's per-sample values for the samples returned by
    :func:`bind_disclosed_samples` — e.g. ``[1.0 if s["correct"] else 0.0 for s in
    samples]`` for accuracy. **Asserting that the metric is the mean of these
    values is the verifier's responsibility.**

    The samples must be the ones the verifier's own challenge selected (random,
    via its nonce). If the holder chose them, no bound applies.

    Hoeffding's inequality — which also holds for sampling without replacement
    (Hoeffding 1963, §6) — gives, for ``k`` values in ``[lo, hi]``::

        P(|sample mean − true mean| ≥ t) ≤ 2·exp(−2k·t² / (hi − lo)²)

    so ``t = (hi − lo)·sqrt(ln(2/alpha) / (2k))``. An honest report is flagged
    with probability at most ``alpha``. 1e-6 is added for the format's 6-dp
    rounding. When ``values`` covers every committed sample the check is exact
    instead (tolerance 0) — but it then trusts the caller that ``values`` really
    is the whole log; :func:`check_metric` proves it.

    The bound is deliberately conservative. It assumes nothing about the
    distribution, so it is wide: at k = 100 on a 0–1 metric with alpha = 1e-3 it
    is about ±0.195. It catches gross misreporting; a small shading of a number
    needs more samples or the whole log.
    """
    metric = find_metric(bundle, key, filter=filter)
    lo, hi = value_range
    if not (math.isfinite(lo) and math.isfinite(hi) and hi > lo):
        raise MetricCheckError(f"value_range must be finite with hi > lo, got {value_range}")
    if not (0.0 < alpha < 1.0):
        raise MetricCheckError(f"alpha must be in (0, 1), got {alpha}")
    k = len(values)
    if k == 0:
        raise MetricCheckError("no values to check")
    if k > bundle.samples_completed:
        raise MetricCheckError(
            f"{k} values for a bundle committing to {bundle.samples_completed} samples"
        )
    for v in values:
        if not (math.isfinite(v) and lo <= v <= hi):
            raise MetricCheckError(
                f"per-sample value {v!r} is outside value_range {value_range}; the bound "
                "does not apply"
            )

    recomputed = pre_round(sum(values) / k, label="recomputed mean")
    reported = pre_round(metric.value)
    complete = k == bundle.samples_completed
    if complete:
        tolerance, used_alpha = 0.0, None
        consistent = recomputed == reported
    else:
        tolerance = (hi - lo) * math.sqrt(math.log(2.0 / alpha) / (2.0 * k))
        used_alpha = alpha
        consistent = abs(recomputed - reported) <= tolerance + 1e-6
    return MetricCheck(
        key=key,
        filter=filter,
        reported=metric.value,
        recomputed=recomputed,
        samples_used=k,
        samples_completed=bundle.samples_completed,
        complete=complete,
        tolerance=tolerance,
        alpha=used_alpha,
        consistent=consistent,
    )
