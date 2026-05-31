import math
import pytest
from report_to_verdict import derive_committed_claim, match_value

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
