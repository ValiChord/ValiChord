"""Pure adapter between CORE-Bench report.json and ValiChord verdicts.

No Holochain, no network, no Inspect — just arithmetic and dict-shaping, so it
is fully unit-testable. Two sides:

  * researcher side  — derive the committed claim (value + 95% prediction
    interval, or an explicit tolerance for deterministic capsules) from N runs.
  * validator side   — map a (blind) report.json to a committed verdict, and
    (after reveal) compute the numeric match against the researcher's claim.

The prediction-interval formula matches inspect_evals
core_bench.utils.calculate_prediction_intervals exactly (verified in tests):
    margin = t.ppf(0.975, n-1) * stdev(values, ddof=1) * sqrt(1 + 1/n)
"""
import math
import statistics
from typing import Optional

from scipy.stats import t as _t


def derive_committed_claim(runs: list[dict], rel_tolerance: float = 0.001) -> dict:
    """runs: list of {question: numeric}. Returns {question: spec} where spec is
    {value, lower, upper, basis}. For >=2 runs with non-zero spread the bounds
    are the 95% prediction interval; otherwise an explicit +/- rel_tolerance
    band (so the researcher always commits a concrete, on-chain interval)."""
    if not runs:
        raise ValueError("derive_committed_claim requires at least one run")
    questions = list(runs[0].keys())
    claim = {}
    for q in questions:
        values = [float(r[q]) for r in runs]
        mean = statistics.mean(values)
        n = len(values)
        margin = 0.0
        basis = "explicit_tolerance"
        if n >= 2:
            std = statistics.stdev(values)  # sample std, ddof=1
            if std > 0.0:
                t_value = _t.ppf(0.975, n - 1)
                margin = t_value * std * math.sqrt(1 + 1 / n)
                basis = "prediction_interval"
        if margin == 0.0:
            margin = abs(mean) * rel_tolerance
            basis = "explicit_tolerance"
        claim[q] = {
            "value": mean,
            "lower": mean - margin,
            "upper": mean + margin,
            "basis": basis,
        }
    return claim


def match_value(value, lower: float, upper: float) -> bool:
    """True iff value is inside [lower, upper]. Non-numeric -> False."""
    try:
        v = float(str(value).replace("%", "").strip())
    except (ValueError, TypeError):
        return False
    return lower <= v <= upper
