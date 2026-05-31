"""Orchestrates the CORE-Bench commit-reveal demo: researcher claim -> three
mixed-model validators -> commit-reveal via the existing demo node HTTP APIs ->
HarmonyRecord -> recomputable numeric panel.

Reuses demo_runner's node HTTP helpers and agreement.py so the displayed
outcome matches the on-chain HarmonyRecord by construction."""
import argparse
import hashlib
import os
import time
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from agreement import derive_agreement_level, derive_majority_outcome
from core_bench_validator import run_validator_eval, run_researcher_claim
from report_to_verdict import report_to_verdict, build_numeric_panel
# Reuse the battle-tested node HTTP helpers + URL config from demo_runner.
from demo_runner import _node_post, _node_get, RESEARCHER_URL, VALIDATOR_URLS
from inspect_evals.core_bench.dataset import CAPSULE_CHECKSUMS

# provider env var expected per model-string prefix
_PROVIDER_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
}


def claim_to_metrics(claim: dict) -> list:
    """Encode the committed claim as a MetricResult list for /lock-result.
    The interval is sealed in expected_value (string) so it is committed
    on-chain and any third party can read the bounds the match was judged
    against."""
    metrics = []
    for q, spec in claim.items():
        metrics.append({
            "metric_name": q,
            "produced_value": repr(spec["value"]),
            "expected_value": f"[{spec['lower']!r}, {spec['upper']!r}] ({spec['basis']})",
            "within_tolerance": True,
        })
    return metrics


def compute_capsule_data_hash(capsule_id: str, salt: bytes) -> str:
    """data_hash = SHA-256(capsule_tarball_checksum_bytes || salt). Binds the
    claim to the exact verified capsule; salt makes each run a fresh identity."""
    checksum_hex = CAPSULE_CHECKSUMS[capsule_id]
    return hashlib.sha256(bytes.fromhex(checksum_hex) + salt).hexdigest()


def validate_model_keys(models: list) -> None:
    """Fail fast if any required provider key is missing, naming the offender."""
    missing = []
    for model in models:
        provider = model.split("/", 1)[0]
        env = _PROVIDER_KEY_ENV.get(provider)
        if env is None:
            raise RuntimeError(f"Unknown model provider in '{model}' (expected one of {list(_PROVIDER_KEY_ENV)})")
        if not os.environ.get(env):
            missing.append(f"{env} (needed for validator model '{model}')")
    if missing:
        raise RuntimeError("Missing required provider API keys:\n  - " + "\n  - ".join(missing))


_MAX_VALIDATOR_ATTEMPTS = 2


def _sleep(seconds):  # indirection so tests can stub out real waiting
    time.sleep(seconds)


def _run_one_validator(capsule_id, required_keys, model):
    """Run a validator eval (one retry with a fresh sandbox) -> (report, verdict)."""
    last_err = None
    for _ in range(_MAX_VALIDATOR_ATTEMPTS):
        try:
            report = run_validator_eval(capsule_id, model)
            verdict = report_to_verdict(report, required_keys)
            return report, verdict
        except Exception as exc:  # noqa: BLE001 - surfaced below with model context
            last_err = exc
    raise RuntimeError(f"Validator model '{model}' failed after {_MAX_VALIDATOR_ATTEMPTS} attempts: {last_err}")


def run_core_bench_protocol(capsule_id, researcher_model, validator_models,
                            discipline=None, n_researcher_runs=3, rel_tolerance=0.001):
    """Drive the full CORE-Bench commit-reveal round. Returns a result dict with
    harmony_record_hash, outcome, agreement_level, numeric_panel, record_url."""
    if len(validator_models) != 3:
        raise ValueError("This demo uses exactly three validators.")
    validate_model_keys([researcher_model] + validator_models)
    disc = discipline or {"type": "Other", "content": "Computational Reproducibility"}

    # 1. Researcher establishes + seals the claim.
    claim = run_researcher_claim(capsule_id, researcher_model,
                                 n_runs=n_researcher_runs, rel_tolerance=rel_tolerance)
    required_keys = list(claim.keys())
    metrics = claim_to_metrics(claim)
    data_hash = compute_capsule_data_hash(capsule_id, salt=uuid.uuid4().bytes)

    lock = _node_post(f"{RESEARCHER_URL}/lock-result", {"data_hash_hex": data_hash, "metrics": metrics})
    ext = lock["external_hash_b64"]
    _node_post(f"{RESEARCHER_URL}/submit-request",
               {"external_hash_b64": ext, "discipline": disc, "num_validators_required": 3})
    _sleep(20)  # DHT propagation

    # 2. Three mixed-model validators reproduce in parallel, blind.
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_run_one_validator, capsule_id, required_keys, m): (i, m)
                   for i, m in enumerate(validator_models)}
        results = {}
        errors = []
        for fut in as_completed(futures):
            i, m = futures[fut]
            try:
                results[i] = fut.result()
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
    if errors:
        raise RuntimeError("Validator reproduction failed; round aborted:\n  - " + "\n  - ".join(errors))
    validator_reports = [(f"V{i+1}-{validator_models[i].split('/')[-1]}", results[i][0]) for i in range(3)]
    verdicts = [results[i][1] for i in range(3)]

    # 3. Commit each verdict blind.
    for i, (vurl, verdict) in enumerate(zip(VALIDATOR_URLS, verdicts)):
        _node_post(f"{vurl}/commit", {
            "external_hash_b64": ext, "verdict": verdict,
            "metrics": verdict["metrics"], "discipline": disc,
        })
        if i < 2:
            _sleep(30)

    # 4. Wait for reveal phase.
    phase_url = f"{RESEARCHER_URL}/phase?hash={urllib.parse.quote(ext)}"
    for _ in range(120):
        if _node_get(phase_url).get("phase") == "RevealOpen":
            break
        _sleep(2)
    else:
        raise RuntimeError("Reveal phase did not open after 240s")

    # 5. Simultaneous reveal (researcher + validators).
    reveal = _node_post(f"{RESEARCHER_URL}/reveal", {"external_hash_b64": ext, "metrics": metrics})
    for i, vurl in enumerate(VALIDATOR_URLS):
        _node_post(f"{vurl}/reveal", {"external_hash_b64": ext})
        if i < 2:
            _sleep(15)

    # 6. Finalise.
    harmony = _node_post(f"{VALIDATOR_URLS[0]}/create-harmony-record", {"external_hash_b64": ext})
    harmony_hash = harmony.get("harmony_record_hash")
    if not harmony_hash:
        raise RuntimeError(f"HarmonyRecord not written after gossip retries (ext={ext[:20]}...)")

    # 7. Display + the verifiable numeric headline.
    outcomes = [v["outcome"] for v in verdicts]
    return {
        "harmony_record_hash": harmony_hash,
        "external_hash_b64": ext,
        "outcome": derive_majority_outcome(outcomes),
        "agreement_level": derive_agreement_level(outcomes),
        "researcher_reveal_hash": reveal.get("researcher_reveal_hash"),
        "record_url": f"{RESEARCHER_URL}/record?hash={urllib.parse.quote(ext)}",
        "committed_claim": claim,
        "numeric_panel": build_numeric_panel(validator_reports, claim),
        "validator_verdicts": [
            {"validator": i + 1, "model": validator_models[i], **{k: verdicts[i][k] for k in ("outcome", "confidence", "reasoning")}}
            for i in range(3)
        ],
    }


_DEFAULT_MODELS = ["anthropic/claude-opus-4-8", "openai/gpt-4o", "google/gemini-1.5-pro"]


def format_result(result: dict) -> str:
    lines = []
    a = lines.append
    a("=" * 60)
    a("  ValiChord x CORE-Bench - Computational Reproducibility")
    a("=" * 60)
    a(f"  Outcome:          {result['outcome']}")
    a(f"  Agreement level:  {result['agreement_level']}  (independent execution agreement)")
    a(f"  HarmonyRecord:    {result['harmony_record_hash']}")
    a("")
    a("  Validators (mixed models, blind, isolated sandboxes):")
    for v in result["validator_verdicts"]:
        a(f"    V{v['validator']} [{v['model']}]: {v['outcome']} ({v['confidence']}) - {v['reasoning']}")
    a("")
    a("  Numeric convergence vs researcher's committed interval (recomputable):")
    for v in result["numeric_panel"]:
        for row in v["rows"]:
            verdict = "MATCH" if row["match"] else "OUTSIDE"
            a(f"    {v['validator']}: {row['value']} in [{row['lower']!r}, {row['upper']!r}] -> {verdict}")
    a("")
    a(f"  Verify independently:")
    a(f"    curl \"{result['record_url']}\"")
    a("=" * 60)
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="ValiChord x CORE-Bench CLI demo")
    parser.add_argument("--capsule", required=True, help="capsule_id, e.g. capsule-5507257")
    parser.add_argument("--researcher-model", default=_DEFAULT_MODELS[0])
    parser.add_argument("--validator-models", nargs=3, default=_DEFAULT_MODELS,
                        help="three model strings, e.g. anthropic/claude-opus-4-8 openai/gpt-4o google/gemini-1.5-pro")
    parser.add_argument("--researcher-runs", type=int, default=3)
    parser.add_argument("--tolerance", type=float, default=0.001, help="relative tolerance for deterministic capsules")
    args = parser.parse_args(argv)

    result = run_core_bench_protocol(
        capsule_id=args.capsule,
        researcher_model=args.researcher_model,
        validator_models=args.validator_models,
        n_researcher_runs=args.researcher_runs,
        rel_tolerance=args.tolerance,
    )
    print(format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
