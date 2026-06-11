#!/usr/bin/env python3
"""
PEP Master round driver — ValiChord hardware-verification demo (Version A)
=========================================================================
Produces ONE real HarmonyRecord for the Breathing Games / Sensorica 2024
"PEP Master" pressure device by feeding hardware-shaped measurement data
(stand-in builder readings) through the EXISTING decentralised commit-reveal
round. It does NOT reimplement the protocol — it builds the researcher metrics
and three validator verdicts from a measurement bundle and hands them to
`ai_validator.run_decentralised_protocol(data_hash, metrics, verdicts, discipline)`.

VERSION A is a PROTOCOL DEMONSTRATION with illustrative stand-in numbers — NOT
three real physical builds. To produce Version B, edit `readings` in
demo/pep_master_bundle.json (a single-file edit, no code change).

What survives on-chain (confirmed against demo/validator-node.mjs + researcher-node.mjs):
  - The researcher's shared reference metric vector  -> ResearcherReveal.metrics
  - Each validator's outcome + confidence            -> ValidationAttestation
  - For an all-`Reproduced` round, `Reproduced` is a UNIT variant with no content,
    so each builder's per-setpoint numbers / reasoning string do NOT survive in the
    record. Version A therefore demonstrates agreement at the OUTCOME LEVEL.
    Carrying each builder's full numeric vector per-validator needs a small node
    tweak (key_metrics is currently hardwired to the shared researcher vector) —
    that's a follow-up for the real build, noted but not faked here.

Usage
-----
    python3 demo/pep_master_round.py --bundle demo/pep_master_bundle.json
"""
import argparse
import hashlib
import json
import uuid
from pathlib import Path

DEMO_DIR = Path(__file__).parent

DISCIPLINE = {"type": "Other", "content": "Open-Hardware Engineering"}

DISCLAIMER = (
    "This proves reproducibility across builds, not medical correctness or "
    "regulatory approval — Version A uses illustrative stand-in readings, not "
    "real independent builds."
)


# ── Pure logic (unit-tested in test_pep_master_round.py) ──────────────────────

def derive_outcome(max_deviation_pct: float, tolerance_pct: float,
                   partial_multiple: float = 2.0) -> str:
    """Apply the §3 outcome_rule to a single builder's max deviation.

    Reproduced          if max deviation within +/- tolerance
    PartiallyReproduced if within +/- (tolerance * partial_multiple) but outside tolerance
    FailedToReproduce   otherwise

    partial_multiple defaults to 2.0 so a 5% tolerance gives the §3 5%/10% bands;
    swapping the tolerance moves both bands together.
    """
    if max_deviation_pct <= tolerance_pct:
        return "Reproduced"
    if max_deviation_pct <= tolerance_pct * partial_multiple:
        return "PartiallyReproduced"
    return "FailedToReproduce"


def _confidence_for(outcome: str) -> str:
    return {
        "Reproduced": "High",
        "PartiallyReproduced": "Medium",
    }.get(outcome, "Low")


def _setpoint_label(s) -> str:
    f = float(s)
    return str(int(f)) if f.is_integer() else f"{f:g}"


def build_researcher_metrics(setpoints) -> list:
    """The researcher's 'result' is the reference-gauge reading at each setpoint:
    expected == produced (the gauge reproduces its own spec), within_tolerance true.
    Returns MetricResult dicts as the node scripts expect (string-valued)."""
    metrics = []
    for s in setpoints:
        ref = f"{float(s):.1f}"
        metrics.append({
            "metric_name":      f"expiratory_pressure_cmH2O@{_setpoint_label(s)}",
            "produced_value":   ref,
            "expected_value":   ref,
            "within_tolerance": True,
        })
    return metrics


def build_validator_verdict(builder: dict, setpoints, tolerance_pct: float) -> dict:
    """Derive one builder's {outcome, confidence, reasoning} from their max
    deviation vs the pinned tolerance. `builder` may carry an explicit
    `confidence`; otherwise it is derived from the outcome."""
    max_dev = float(builder["max_deviation_pct"])
    outcome = derive_outcome(max_dev, tolerance_pct)
    confidence = builder.get("confidence") or _confidence_for(outcome)
    sp_str = "/".join(_setpoint_label(s) for s in setpoints)
    name = builder.get("name", "Builder")
    location = builder.get("location", "")
    where = f"{name} ({location})" if location else name
    reasoning = (
        f"{where}: max deviation {max_dev:g}% across setpoints {sp_str} "
        f"(tolerance +/-{tolerance_pct:g}%) -> {outcome}"
    )
    return {"outcome": outcome, "confidence": confidence, "reasoning": reasoning}


def build_round_inputs(bundle: dict):
    """From a measurement bundle, build (researcher metrics, validator verdicts,
    discipline) ready to hand to run_decentralised_protocol."""
    proto = bundle["test_protocol"]
    setpoints = proto["reference_input"]["setpoints_cmH2O"]
    tolerance_pct = float(proto["tolerance"]["value"])
    metrics = build_researcher_metrics(setpoints)
    verdicts = [
        build_validator_verdict(b, setpoints, tolerance_pct)
        for b in bundle["readings"]
    ]
    return metrics, verdicts, DISCIPLINE


def load_bundle(path) -> dict:
    return json.loads(Path(path).read_text())


# ── Orchestration ─────────────────────────────────────────────────────────────

def _data_hash_for(bundle_path: Path) -> str:
    """SHA-256 of the bundle bytes, salted with a per-run UUID — mirrors
    ai_validator.load_study so each run is a fresh, never-claimed deposit."""
    data_bytes = bundle_path.read_bytes()
    run_id = uuid.uuid4().bytes
    return hashlib.sha256(data_bytes + run_id).hexdigest()


def run(bundle_path: str) -> dict:
    # Imported lazily so unit tests of the pure logic don't pull in the
    # protocol/runtime stack.
    import ai_validator

    bundle_path = Path(bundle_path)
    bundle = load_bundle(bundle_path)
    metrics, verdicts, discipline = build_round_inputs(bundle)
    setpoints = bundle["test_protocol"]["reference_input"]["setpoints_cmH2O"]

    print("=" * 64)
    print("  ValiChord — PEP Master hardware-verification round (VERSION A)")
    print("=" * 64)
    lo, hi = bundle["test_protocol"].get("measurand_range_cmH2O", [min(setpoints), max(setpoints)])
    print(f"  Device:   {bundle['device']['name']}")
    print(f"  Spec:     expiratory pressure {lo}-{hi} cmH2O, "
          f"within +/-{bundle['test_protocol']['tolerance']['value']:g}% of reference gauge "
          f"(setpoints {'/'.join(_setpoint_label(s) for s in setpoints)})")
    print(f"  Builders: {len(bundle['readings'])} (illustrative stand-in readings)")
    print()
    print("  !! VERSION A — PROTOCOL DEMONSTRATION, NOT REAL BUILDS !!")
    print(f"  {DISCLAIMER}")
    print()

    data_hash = _data_hash_for(bundle_path)
    result = ai_validator.run_decentralised_protocol(
        data_hash, metrics, verdicts, discipline=discipline,
    )

    _display(result, bundle)
    _verify_public_fetch(ai_validator, result)
    return result


def _verify_public_fetch(ai_validator, result: dict):
    """Independently fetch the record back from the researcher node — a DIFFERENT
    conductor than the validator that authored it. This demonstrates the core
    ValiChord property: the HarmonyRecord is publicly readable from the DHT, with
    no central server vouching for it. Mirrors ai_validator.display_result's
    self-verification."""
    import urllib.parse
    external = result.get("external_hash_b64")
    if not external:
        return
    url = f"{ai_validator.RESEARCHER_URL}/record?hash={urllib.parse.quote(external)}"
    print()
    print("  Independently fetching the record back from the researcher node")
    print("  (a different conductor than the validator that authored it)…")
    print(f"  GET {url}")
    try:
        record = ai_validator._node_get(url, timeout=30)
    except SystemExit:
        print("  WARNING: record fetch failed — see node error above.")
        return
    print(f"  Record confirmed on the DHT. "
          f"Outcome: {record.get('outcome')}  "
          f"Agreement: {record.get('agreement_level')}  "
          f"Validators: {record.get('validator_count')}")
    print(f"  Discipline on record: {record.get('discipline')}")


def _display(result: dict, bundle: dict):
    print()
    print("=" * 64)
    print("  PERMANENT RECORD (HarmonyRecord on the public DHT)")
    print("=" * 64)
    n = result.get("validator_count", len(bundle["readings"]))
    print(f"  Outcome:         {result.get('outcome_type')} ({n}/{n} builders)")
    print(f"  AgreementLevel:  {result.get('agreement_level')}")
    print(f"  Discipline:      {DISCIPLINE['content']}")
    print(f"  HarmonyRecord:   {result.get('harmony_record_hash')}")
    if result.get("researcher_reveal_hash"):
        print(f"  Researcher ref:  {result['researcher_reveal_hash']}")
    print()
    # Per-builder deviations come from the bundle (display only — see note below).
    for reading in bundle["readings"]:
        proto = bundle["test_protocol"]
        v = build_validator_verdict(
            reading,
            proto["reference_input"]["setpoints_cmH2O"],
            float(proto["tolerance"]["value"]),
        )
        print(f"  {reading['name']} ({reading['location']}): "
              f"max deviation {float(reading['max_deviation_pct']):g}%  -> {v['outcome']}")
    print()
    print("  What survives on-chain (Version A): each builder's OUTCOME + confidence.")
    print("  The per-builder deviation numbers above are display-only — for an")
    print("  all-Reproduced round the attestation outcome is a unit variant with no")
    print("  content, and key_metrics carries the shared researcher reference vector.")
    print("  Version A demonstrates agreement at the OUTCOME LEVEL. Carrying each")
    print("  builder's full per-setpoint vector into the record is a small node tweak")
    print("  (follow-up for the real build).")
    print()
    print("-" * 64)
    print(f"  {DISCLAIMER}")
    print("-" * 64)


def main():
    parser = argparse.ArgumentParser(description="Run the PEP Master Version-A round.")
    parser.add_argument("--bundle", default=str(DEMO_DIR / "pep_master_bundle.json"),
                        help="Path to the measurement bundle JSON.")
    args = parser.parse_args()
    run(args.bundle)


if __name__ == "__main__":
    main()
