"""Tests for verifier-side metric recomputation (issue #13).

Each check is exercised in both directions: an honest bundle must pass and a
misreporting one must fail. A test that only ever saw honest input would pass
against a check that always says "consistent".
"""

import copy
import math

import pytest

from valichord_attestation import (
    MetricCheckError,
    bind_disclosed_samples,
    build_bundle,
    build_response,
    check_mean_metric,
    check_metric,
    find_metric,
    hash_bundle,
    recompute_metric,
    verify_response,
)
from valichord_attestation.bundle import Metric
from valichord_attestation.challenge import Challenge

NONCE = bytes(range(16))
# 200 samples, exactly 75% correct (every 4th wrong).
SAMPLES = [{"index": i, "output": str(i * 7), "correct": i % 4 != 0} for i in range(200)]
TRUE_ACCURACY = 0.75


def accuracy(samples):
    return sum(1 for s in samples if s["correct"]) / len(samples)


def _bundle(reported=TRUE_ACCURACY, samples=SAMPLES):
    return build_bundle(
        model_id="test-model",
        task_id="test-task",
        raw_metrics=[{"key": "accuracy", "value": reported}],
        samples=samples,
        generated_at="2026-01-01T00:00:00+00:00",
    )


def _challenged(bundle, k):
    """A verified challenge response plus the holder's disclosed contents."""
    challenge = Challenge(bundle_hash=hash_bundle(bundle), verifier_nonce=NONCE, k=k)
    response = build_response(challenge, SAMPLES, format_version=bundle.format_version)
    assert verify_response(challenge, response, bundle), "fixture: response must verify"
    disclosed = {rs.sample_index: SAMPLES[rs.sample_index] for rs in response.samples}
    return response, disclosed


# ---------------------------------------------------------------------------
# find_metric / recompute_metric
# ---------------------------------------------------------------------------


def test_find_metric_returns_the_reported_metric():
    assert find_metric(_bundle(), "accuracy").value == TRUE_ACCURACY


def test_find_metric_missing_key_raises():
    with pytest.raises(MetricCheckError, match="no metric key='f1'"):
        find_metric(_bundle(), "f1")


def test_find_metric_respects_filter():
    b = _bundle()
    b.metrics = [
        Metric(key="accuracy", value=0.5, filter="strict-match"),
        Metric(key="accuracy", value=0.75, filter="flexible-extract"),
    ]
    assert find_metric(b, "accuracy", filter="flexible-extract").value == 0.75
    with pytest.raises(MetricCheckError):
        find_metric(b, "accuracy")  # no unfiltered metric


def test_find_metric_ambiguous_raises():
    b = _bundle()
    b.metrics = [Metric(key="accuracy", value=0.5), Metric(key="accuracy", value=0.75)]
    with pytest.raises(MetricCheckError, match="cannot tell which one"):
        find_metric(b, "accuracy")


def test_recompute_metric_rounds_to_six_places():
    assert recompute_metric([{"v": 1}], lambda s: 1 / 3) == 0.333333


# ---------------------------------------------------------------------------
# check_metric — the whole log, exact
# ---------------------------------------------------------------------------


def test_full_log_honest_report_is_consistent():
    r = check_metric(_bundle(), "accuracy", SAMPLES, accuracy)
    assert r.consistent and r.complete
    assert r.tolerance == 0.0 and r.alpha is None
    assert r.recomputed == TRUE_ACCURACY
    assert r.samples_used == r.samples_completed == 200


def test_full_log_misreported_metric_is_inconsistent():
    r = check_metric(_bundle(reported=0.80), "accuracy", SAMPLES, accuracy)
    assert not r.consistent
    assert r.reported == 0.80 and r.recomputed == TRUE_ACCURACY


def test_full_log_shading_by_one_millionth_is_caught():
    # The exact check really is exact at the format's precision.
    r = check_metric(_bundle(reported=0.750001), "accuracy", SAMPLES, accuracy)
    assert not r.consistent


def test_full_log_that_is_not_the_committed_log_is_refused():
    # The attack §10(c) names: honest-looking samples beside a number they did not
    # produce. Flipping one sample changes the metric AND the root; the root check
    # must refuse before any number is compared.
    altered = copy.deepcopy(SAMPLES)
    altered[0]["correct"] = True
    with pytest.raises(MetricCheckError, match="do not re-commit"):
        check_metric(_bundle(), "accuracy", altered, accuracy)


def test_full_log_check_refuses_a_subset():
    with pytest.raises(MetricCheckError, match="needs all 200"):
        check_metric(_bundle(), "accuracy", SAMPLES[:50], accuracy)


# ---------------------------------------------------------------------------
# bind_disclosed_samples
# ---------------------------------------------------------------------------


def test_bind_returns_disclosed_samples_in_response_order():
    b = _bundle()
    response, disclosed = _challenged(b, k=20)
    bound = bind_disclosed_samples(response, disclosed, b)
    assert bound == [SAMPLES[rs.sample_index] for rs in response.samples]


def test_bind_refuses_a_tampered_disclosure():
    b = _bundle()
    response, disclosed = _challenged(b, k=20)
    idx = response.samples[0].sample_index
    disclosed[idx] = {**disclosed[idx], "correct": not disclosed[idx]["correct"]}
    with pytest.raises(MetricCheckError, match="does not match the leaf hash"):
        bind_disclosed_samples(response, disclosed, b)


def test_bind_refuses_a_withheld_sample():
    b = _bundle()
    response, disclosed = _challenged(b, k=20)
    del disclosed[response.samples[0].sample_index]
    with pytest.raises(MetricCheckError, match="was not disclosed"):
        bind_disclosed_samples(response, disclosed, b)


# ---------------------------------------------------------------------------
# check_mean_metric — a challenged subset, statistical
# ---------------------------------------------------------------------------


def _subset_values(bundle, k):
    response, disclosed = _challenged(bundle, k)
    return [1.0 if s["correct"] else 0.0 for s in bind_disclosed_samples(response, disclosed, bundle)]


def test_subset_honest_report_is_consistent():
    b = _bundle()
    r = check_mean_metric(b, "accuracy", _subset_values(b, 50))
    assert r.consistent
    assert not r.complete and r.alpha == 1e-3 and r.samples_used == 50


def test_subset_gross_misreport_is_inconsistent():
    # Same samples, a reported 0.20 against a true 0.75: well outside the bound.
    b = _bundle(reported=0.20)
    r = check_mean_metric(b, "accuracy", _subset_values(b, 50))
    assert not r.consistent
    assert abs(r.recomputed - r.reported) > r.tolerance


def test_subset_tolerance_is_the_hoeffding_bound():
    b = _bundle()
    r = check_mean_metric(b, "accuracy", _subset_values(b, 100))
    assert r.tolerance == pytest.approx(math.sqrt(math.log(2 / 1e-3) / 200))
    assert r.tolerance == pytest.approx(0.195, abs=1e-3)  # the figure in the docstring


def test_subset_tolerance_shrinks_with_more_samples():
    b = _bundle()
    small = check_mean_metric(b, "accuracy", _subset_values(b, 25))
    large = check_mean_metric(b, "accuracy", _subset_values(b, 150))
    assert large.tolerance < small.tolerance


def test_subset_tolerance_scales_with_value_range():
    b = _bundle()
    vals = _subset_values(b, 50)
    unit = check_mean_metric(b, "accuracy", vals, value_range=(0.0, 1.0))
    wide = check_mean_metric(b, "accuracy", vals, value_range=(0.0, 2.0))
    assert wide.tolerance == pytest.approx(2 * unit.tolerance)


def test_every_value_disclosed_makes_the_mean_check_exact():
    b = _bundle()
    vals = [1.0 if s["correct"] else 0.0 for s in SAMPLES]
    r = check_mean_metric(b, "accuracy", vals)
    assert r.complete and r.tolerance == 0.0 and r.consistent
    r_bad = check_mean_metric(_bundle(reported=0.76), "accuracy", vals)
    assert not r_bad.consistent


@pytest.mark.parametrize(
    "values, kwargs, match",
    [
        ([], {}, "no values"),
        ([1.5], {}, "outside value_range"),
        ([float("nan")], {}, "outside value_range"),
        ([0.5], {"alpha": 0.0}, "alpha must be"),
        ([0.5], {"alpha": 1.0}, "alpha must be"),
        ([0.5], {"value_range": (1.0, 1.0)}, "hi > lo"),
        ([0.5] * 201, {}, "201 values for a bundle committing to 200"),
    ],
)
def test_mean_check_refuses_inputs_outside_its_assumptions(values, kwargs, match):
    with pytest.raises(MetricCheckError, match=match):
        check_mean_metric(_bundle(), "accuracy", values, **kwargs)
