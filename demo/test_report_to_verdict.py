import math
import pytest
from report_to_verdict import derive_committed_claim, match_value, report_to_verdict, build_numeric_panel

Q = "Report the accuracy of the model."


def test_deterministic_runs_use_explicit_tolerance():
    runs = [{Q: 96.125}, {Q: 96.125}, {Q: 96.125}]
    claim = derive_committed_claim(runs, rel_tolerance=0.001)
    spec = claim[Q]
    assert spec["value"] == pytest.approx(96.125)
    assert spec["basis"] == "explicit_tolerance"
    # ±0.1% of 96.125
    assert spec["lower"] == pytest.approx(96.125 * (1 - 0.001))
    assert spec["upper"] == pytest.approx(96.125 * (1 + 0.001))


def test_stochastic_runs_use_prediction_interval():
    runs = [{Q: 0.982}, {Q: 0.815}, {Q: 0.978}]
    claim = derive_committed_claim(runs, rel_tolerance=0.001)
    spec = claim[Q]
    assert spec["basis"] == "prediction_interval"
    # interval is symmetric about the mean and strictly wider than the spread
    mean = (0.982 + 0.815 + 0.978) / 3
    assert spec["value"] == pytest.approx(mean)
    assert spec["lower"] < min(0.982, 0.815, 0.978)
    assert spec["upper"] > max(0.982, 0.815, 0.978)


def test_match_value_boundaries():
    assert match_value(5.0, 4.0, 6.0) is True
    assert match_value(4.0, 4.0, 6.0) is True   # inclusive lower
    assert match_value(6.0, 4.0, 6.0) is True   # inclusive upper
    assert match_value(3.999, 4.0, 6.0) is False
    assert match_value("5.0", 4.0, 6.0) is True  # string coercion
    assert match_value("not a number", 4.0, 6.0) is False


REQ = [Q]


def test_verdict_valid_numeric_report_is_reproduced():
    v = report_to_verdict({Q: 96.125}, REQ)
    assert v["outcome"] == "Reproduced"
    assert v["metrics"][0]["metric_name"] == Q
    assert v["metrics"][0]["produced_value"] == "96.125"
    # blind: no researcher value known at commit time
    assert v["metrics"][0]["expected_value"] == ""
    assert v["metrics"][0]["within_tolerance"] is False


def test_verdict_no_report_is_failed():
    v = report_to_verdict(None, REQ)
    assert v["outcome"] == "FailedToReproduce"
    assert v["metrics"] == []


def test_verdict_missing_key_is_unable_to_assess():
    v = report_to_verdict({"some other question": 1.0}, REQ)
    assert v["outcome"] == "UnableToAssess"


def test_verdict_non_numeric_value_is_unable_to_assess():
    v = report_to_verdict({Q: "ran out of time"}, REQ)
    assert v["outcome"] == "UnableToAssess"


def test_numeric_panel_marks_match_and_divergence():
    claim = derive_committed_claim([{Q: 96.125}, {Q: 96.125}, {Q: 96.125}])
    panel = build_numeric_panel(
        [("V1-claude", {Q: 96.125}), ("V2-gpt4o", {Q: 50.0})], claim
    )
    assert panel[0]["rows"][0]["match"] is True
    assert panel[1]["rows"][0]["match"] is False
    assert panel[1]["rows"][0]["value"] == pytest.approx(50.0)


def test_interval_matches_inspect_evals():
    """Pin our prediction interval to inspect_evals' own implementation."""
    pytest.importorskip("inspect_evals")
    from inspect_evals.core_bench.utils import calculate_prediction_intervals
    runs = [{Q: 0.982}, {Q: 0.815}, {Q: 0.978}]
    ours = derive_committed_claim(runs)[Q]
    theirs_lo, theirs_hi = calculate_prediction_intervals(runs, [Q])[Q]
    assert ours["lower"] == pytest.approx(theirs_lo)
    assert ours["upper"] == pytest.approx(theirs_hi)
