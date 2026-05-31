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


def _coerce_number(raw) -> Optional[float]:
    try:
        return float(str(raw).replace("%", "").strip())
    except (ValueError, TypeError):
        return None


def report_to_verdict(report: Optional[dict], required_keys: list[str]) -> dict:
    """Map a (blind) report.json to a committed ValiChord verdict.

    Outcome is EXECUTION-SUCCESS only -- the validator cannot compare against the
    researcher's sealed value at commit time, so this never encodes a match.
    The researcher-relative match is computed at reveal by build_numeric_panel.

      valid numeric report, all keys present -> Reproduced
      no report / unparseable                -> FailedToReproduce
      parsed but a required key missing/non-numeric -> UnableToAssess
    """
    if not report:
        return {
            "outcome": "FailedToReproduce",
            "confidence": "High",
            "reasoning": "Agent produced no valid report.json -- the capsule did not reproduce.",
            "metrics": [],
        }
    metrics = []
    ok = True
    for k in required_keys:
        raw = report.get(k, None)
        num = _coerce_number(raw)
        if k not in report or num is None:
            ok = False
        metrics.append({
            "metric_name": k,
            # produced_value is the validator's OWN reproduced value; expected
            # is blank because the researcher's claim is sealed at commit time.
            "produced_value": ("" if raw is None else (repr(num) if num is not None else str(raw))),
            "expected_value": "",
            "within_tolerance": False,
        })
    if not ok:
        return {
            "outcome": "UnableToAssess",
            "confidence": "Medium",
            "reasoning": "report.json was produced but a required answer was missing or non-numeric.",
            "metrics": metrics,
        }
    return {
        "outcome": "Reproduced",
        "confidence": "High",
        "reasoning": "Agent independently executed the capsule from scratch and produced a valid numeric result.",
        "metrics": metrics,
    }


def build_numeric_panel(validator_reports: list, committed_claim: dict) -> list:
    """Reveal-time match. validator_reports: list of (label, report_dict|None).
    Returns per-validator rows comparing each value against the committed
    interval -- the verifiable, recomputable headline of the demo."""
    panel = []
    for label, report in validator_reports:
        rows = []
        for q, spec in committed_claim.items():
            raw = None if not report else report.get(q, None)
            num = _coerce_number(raw)
            rows.append({
                "question": q,
                "value": num,
                "lower": spec["lower"],
                "upper": spec["upper"],
                "match": False if num is None else match_value(num, spec["lower"], spec["upper"]),
            })
        panel.append({"validator": label, "rows": rows})
    return panel
