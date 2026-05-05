# valichord_attestation

Canonical attestation format for AI evaluation runs.

A **bundle** is a lightweight JSON document that binds a reported evaluation result to the underlying run that produced it. Two things make it verifiable:

1. **Deterministic hash** — the bundle is RFC 8785 (JCS) encoded, so the same run always produces the same bytes and the same SHA-256 digest.
2. **Merkle root** — a SHA-256 Merkle tree over per-sample outputs lets the log holder prove any individual sample to a third party without disclosing the full log.

The format is harness-agnostic. Adapters for specific harnesses (Inspect AI, lm-evaluation-harness, etc.) are thin converters written separately.

Architectural context: this format was designed in response to Scott Simmons's review of [UKGovernmentBEIS/inspect_evals#1610](https://github.com/UKGovernmentBEIS/inspect_evals/pull/1610). The core feedback was that the canonical spec belongs in Valichord, not in each eval harness, and that the valuable attestation is not "I have the log file" but "this reported result is faithful to the run."

---

## Quickstart

```python
from valichord_attestation import build_bundle, hash_bundle, merkle_proof, verify_faithfulness

# 1. Build a bundle from raw harness output
bundle = build_bundle(
    model_id="gpt-4o-2024-08-06",
    task_id="gsm8k",
    raw_metrics=[{"key": "accuracy", "value": 0.847, "stderr": 0.025}],
    samples=[{"index": i, "output": "...", "correct": True} for i in range(1319)],
    repo_commit="abc123",
    harness_version="inspect_ai/0.3.19",
    command="inspect eval gsm8k --model openai/gpt-4o-2024-08-06",
)

# 2. Hash it — this is what you publish alongside the report
bundle_hash = hash_bundle(bundle)
print(bundle_hash)  # 64 hex chars

# 3. Prove a specific sample (for selective disclosure to a verifier)
proof = merkle_proof(samples, index=42)

# 4. Verify the proof (verifier side — receives bundle_hash, sample, proof)
ok = verify_faithfulness(bundle.outputs_merkle_root, 42, samples[42], proof)
```

Multi-metric evals work the same way — pass multiple entries in `raw_metrics`:

```python
raw_metrics = [
    {"key": "benign_utility",  "value": 0.75},
    {"key": "targeted_asr",   "value": 0.0625},
    {"key": "untargeted_asr", "value": 0.0},
]
```

`build_bundle` raises `MalformedBundleError` if any `value` key is missing — absent metrics are never silently defaulted to `0.0`.

---

## Writing a harness adapter

Subclass `AdapterBase` and implement `to_bundle`:

```python
from valichord_attestation.adapters.base import AdapterBase
from valichord_attestation import build_bundle, Bundle

class MyHarnessAdapter(AdapterBase):
    def to_bundle(self, report: dict, samples: list[dict]) -> Bundle:
        return build_bundle(
            model_id=report["model"],
            task_id=report["task"],
            raw_metrics=[{"key": m["key"], "value": m["value"]} for m in report["metrics"]],
            samples=samples,
            repo_commit=report.get("commit"),
            command=report.get("command"),
        )
```

The `InspectEvalsAdapter` stub in `valichord_attestation/adapters/inspect_evals_stub.py` shows the intended field mapping for Inspect AI once the upstream API stabilises.

---

## Probabilistic Challenge-Response

Selective disclosure (Section 5 of the spec) lets the log holder choose which samples to prove. The challenge-response protocol inverts control: the verifier picks which samples to inspect, and the holder must reveal those specific ones.

```python
from valichord_attestation import (
    build_bundle, hash_bundle, Challenge,
    build_response, verify_response,
)
import os

bundle = build_bundle(...)
challenge = Challenge(
    bundle_hash=hash_bundle(bundle),
    verifier_nonce=os.urandom(32),
    k=60,  # challenge 60 randomly-chosen samples
)
response = build_response(challenge, samples)  # holder's side
ok = verify_response(challenge, response, bundle)  # verifier's side
```

With `k=60` and a 5% fabrication rate, catch probability is ~95%. See [`spec/attestation_format_v1.md`](spec/attestation_format_v1.md) Section 6 for the full protocol (seed derivation, index algorithm, test vector) and the sensitivity table. Runnable walkthrough: [`examples/challenge_response_demo.py`](examples/challenge_response_demo.py).

---

## Running the examples

```bash
python examples/verify_examples.py
```

Each example JSON contains a synthetic bundle, the source samples, and a pre-computed inclusion proof. The script recomputes the bundle hash and Merkle root from scratch and confirms they match.

---

## Spec

Full format specification: [`spec/attestation_format_v1.md`](spec/attestation_format_v1.md)

Covers: bundle schema, canonical encoding rules, pre-rounding policy, Merkle tree construction, proof format and verifier algorithm, versioning policy, adapter interface, security considerations.

---

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/ --cov=valichord_attestation
```

138 tests, 100% line coverage.

---

## License

Apache 2.0 — see [`LICENSE`](../LICENSE) at the repository root.
