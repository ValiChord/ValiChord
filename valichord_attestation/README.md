# valichord_attestation

A lightweight verification layer for AI evaluation claims.

The protocol provides a **verifiable commitment over an entire evaluation trace** — its summary metrics, its per-sample outputs, and the harness configuration that produced them — together with a **probabilistic challenge-response protocol** that lets a verifier confirm faithfulness of reported results without transferring the full log.

The system enables:
- **Selective disclosure** — the holder of the log can prove individual samples on demand without revealing the rest
- **Bounded-confidence fraud detection** — the verifier picks random samples; the probability of catching a misreport grows with the number of samples requested
- **Deterministic cross-implementation comparison** — RFC 8785 (JCS) canonical encoding means two implementations in different languages produce byte-identical bundles for the same input

v1 ships the format spec, the Merkle commitment, and selective disclosure. v1.1 (already shipped) adds the probabilistic challenge-response. Future work extends this with hardware-attested execution and zero-knowledge faithfulness proofs.

The format is harness-agnostic. Adapters for specific harnesses (Inspect AI, lm-evaluation-harness, etc.) are thin converters written separately.

Architectural context: this format was designed in response to Scott Simmons's review of [UKGovernmentBEIS/inspect_evals#1610](https://github.com/UKGovernmentBEIS/inspect_evals/pull/1610). The core feedback was that the canonical spec belongs in Valichord, not in each eval harness, and that the valuable attestation is not "I have the log file" but "this reported result is faithful to the run."

---

## Verifiable statement vs attested claim

A bundle in isolation is a **verifiable statement**: any reader can confirm the bundle's internal consistency (the Merkle root commits to the per-sample outputs; the canonical encoding is deterministic; the challenge-response succeeds against a holder of the log). But anyone could have produced the bundle — there is no built-in identity layer in the format itself.

When a bundle is committed to a signed, append-only log — for example, Valichord's Holochain DNAs (`validator_workspace`, `attestation`, `governance`) — it becomes an **attested claim**: the commit is signed by the validator's Ed25519 keypair, recorded in a tamper-proof source chain, and witnessed by independent peers. At this point the bundle carries cryptographic non-repudiation: the validator cannot later deny they made the claim.

The two layers are deliberately separable. The format is harness-agnostic and substrate-agnostic — useful in contexts beyond Valichord's protocol, and compatible with any signed-log infrastructure. Within Valichord's protocol, the signed-log layer adds the identity and witnessing properties that the format alone deliberately doesn't carry.

---

## Concrete example

A lab publishes a benchmark result for a frontier model — say, *"87.2% on SWE-bench Verified"* — and constructs a bundle with the canonical metric, the harness configuration, and a Merkle commitment over the per-sample outputs. The lab does not need to share the underlying 4 GB of log files publicly.

A third-party verifier (a journalist, a regulator, a competing lab) reads the bundle and wants to confirm the score is faithful. They generate a fresh challenge — *"reveal samples 17, 142, 391, 894, 1,205, ..."* — and the lab responds with those 50 samples plus their Merkle paths. The verifier checks each path against the bundle's commitment, and recomputes the headline metric from the disclosed samples to confirm it matches what the lab reported.

If the lab fabricated even 5% of their results, the verifier's 50-sample challenge catches the fabrication with probability ≈92%. The verifier has confirmed faithfulness without ever downloading the full log; the lab has demonstrated their result without exposing per-sample data their privacy or competitive position requires they not publish wholesale.

That tradeoff — *probabilistic faithfulness verification with selective disclosure* — is what the protocol is for.

---

## Installation

From the `valichord_attestation/` directory:

```bash
pip install -e .
```

For development (includes pytest, coverage, and type-checking tools):

```bash
pip install -e ".[dev]"
```

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
    samples_total=1319,           # optional: assert intended run size (detects silent omission)
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

`build_bundle` raises `MalformedBundleError` if any `value` key is missing — absent metrics are never silently defaulted to `0.0`. Pass `samples_total` to explicitly declare the intended run size; if an adapter silently drops samples, `bundle.samples_total > bundle.samples_completed` will be directly visible. Raises `ValueError` if `samples_total < len(samples)`.

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
# Verify synthetic examples (no GPU required)
python examples/verify_examples.py
python examples/challenge_response_demo.py

# Real-data demo: verify the committed Mistral-7B-Instruct-v0.3 + GSM8K-100 bundle (no GPU required for verification)
python examples/mistral_7b_gsm8k_demo/challenge_response_demo.py
```

The synthetic examples contain GSM8K-shaped and agentdojo-shaped bundles with pre-computed inclusion proofs. `verify_examples.py` recomputes bundle hashes and Merkle roots from scratch.

The real-data demo (`mistral_7b_gsm8k_demo/`) exercises the full v1.1 protocol — `samples_total=100` declared explicitly, k=20 challenge-response, tamper detection — against a committed `bundle.json`. The bundle ships with simulated fixture data so the demo runs without a GPU. Run `run_eval.sh` on a GPU and re-run `build_bundle.py --output-path ./eval_output` to replace it with real eval output. See [`examples/mistral_7b_gsm8k_demo/README.md`](examples/mistral_7b_gsm8k_demo/README.md) for full instructions.

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

142 tests, 100% line coverage.

---

## License

Apache 2.0 — see [`LICENSE`](../LICENSE) at the repository root.
