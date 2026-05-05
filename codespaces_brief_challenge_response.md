# Codespaces Brief — Probabilistic Challenge-Response Extension

**Trigger:** v1 of `valichord_attestation` shipped selective-disclosure faithfulness verification (Merkle commitments). The next step toward the "excellent" property Scott Simmons described — *"verify the report is faithful to the run without needing to have the real eval log in my hands"* — is a probabilistic challenge-response protocol on top of the existing Merkle structure. This brief specifies that work.

**Status:** Additive extension. Does not change the v1 bundle format. No breaking changes.

**Target completion:** Single focused Codespaces session.

---

## Context

The v1 spec is honest that it delivers *selective disclosure* — a log holder can prove individual samples on request, but the verifier must trust the holder to reveal what's relevant. That's a partial answer to faithfulness verification.

The probabilistic challenge-response protocol takes the Merkle structure and adds a verifier-controlled randomness layer: the verifier picks which samples to inspect, the holder must reveal those specific samples (not ones of their choosing), and the verifier gains high-confidence evidence of faithfulness while seeing only a tiny fraction of the log.

The mathematics:
- If a fraction `f` of the log is fabricated and the verifier requests `k` random samples, the probability of catching the fabrication is `1 - (1-f)^k`.
- For `f = 0.05` (5% cheating) and `k = 60`, catch probability ≈ 95%.
- For `f = 0.01` (1% cheating) and `k = 100`, catch probability ≈ 63%; `k = 300` gives 95%.

The verifier picks `k` based on their tolerance for the cheating fraction they want to catch. The spec should describe this trade-off so users can pick `k` deliberately.

---

## Design requirements

### R1 — Verifier-controlled randomness

The challenge must be a function of (a) the bundle being verified and (b) verifier-supplied entropy. Specifically:

- Indices are derived deterministically from a seed
- Seed is `HMAC-SHA256(verifier_nonce, bundle_hash)` or equivalent PRF construction
- This binds the challenge to a specific bundle (can't reuse across bundles) and prevents the log holder from predicting which samples will be challenged before bundle creation
- Verifier nonce is a verifier-chosen byte string of at least 16 bytes

The spec must describe the PRF construction precisely so any implementation produces identical indices given the same seed.

### R2 — Reproducible challenge derivation

Anyone holding `(bundle_hash, verifier_nonce, k)` must be able to derive the same indices. The protocol is:

1. Compute seed = `HMAC-SHA256(verifier_nonce_bytes, bundle_hash_bytes)`
2. Use seed to instantiate a documented deterministic PRNG (recommend HMAC-DRBG or a SHA-256-based counter-mode construction; specify in spec)
3. Generate `k` distinct indices in `[0, total_samples)` via rejection sampling

The PRNG choice must be language-agnostic (i.e., not Python's `random.Random` which is implementation-specific). Document the exact construction.

### R3 — Compact response format

A `ChallengeResponse` contains, for each challenged index:
- `sample_index`: integer
- `sample_content_hash`: hash of the canonicalised sample (matching the leaf format in the v1 Merkle tree)
- `merkle_path`: list of sibling hashes from leaf to root

The verifier reconstructs the path against the bundle's `outputs_merkle_root`. If all paths verify, the response is valid.

Response should NOT include the raw sample content — only the hash. This minimises disclosure: the verifier learns *that the holder has a sample whose hash matches what the bundle commits to*, not the sample's content. (If the verifier wants the content too, they can request it separately; the protocol shouldn't force disclosure beyond what's needed for verification.)

Note: this is a deliberate change from the simplest implementation, which would reveal sample content. By separating "prove faithfulness" from "share content," we move further toward the "without log access" property.

### R4 — Hash-collision safety (carrying R6 from v1)

Same rule as v1: missing fields raise errors, never silently default. A challenge or response missing required fields must error rather than produce a hash of `0` or empty values.

### R5 — No bundle changes

The v1 bundle format is unchanged. All challenge-response data lives in separate `Challenge` and `ChallengeResponse` objects. This is purely additive.

### R6 — Honest framing in the spec

The spec section must be explicit that probabilistic challenge-response is *probabilistic* — it does not guarantee 100% catch of cheating, only catch with bounded probability for a given `k`. A verifier must understand the relationship between `k`, expected cheating fraction, and confidence level. Include a small table of `k` values and their catch rates for reference cheating fractions.

---

## Concrete deliverables

### 1. Spec section — append to `valichord_attestation/spec/attestation_format_v1.md`

A new section "Probabilistic Challenge-Response" covering:
- Goal and trust model (verifier controls randomness; holder cannot predict)
- `Challenge` and `ChallengeResponse` JSON schemas
- Seed derivation (`HMAC-SHA256(nonce, bundle_hash)`)
- Index derivation algorithm (specific, language-agnostic PRNG)
- Response verification algorithm
- Mathematical sensitivity table (`k` vs catch rate for `f = 0.01, 0.05, 0.1`)
- Honest framing: probabilistic, not deterministic; confidence depends on `k`

The bundle's `format_version` stays at `v1`. Challenge and response objects carry their own optional `format_version: "v1"` if needed.

### 2. Reference implementation — `valichord_attestation/challenge.py`

- `Challenge` dataclass: `{bundle_hash: str, verifier_nonce: bytes, k: int}`
- `generate_indices(challenge) -> list[int]` — deterministic index derivation
- `derive_seed(challenge) -> bytes` — exposed for testing
- Validation: raises on `k <= 0`, `k > total_samples`, `len(verifier_nonce) < 16`

### 3. Reference implementation — `valichord_attestation/response.py`

- `ChallengeResponse` dataclass: `{challenge_hash: str, samples: list[ResponseSample]}`
- `ResponseSample`: `{sample_index: int, sample_content_hash: str, merkle_path: list[str]}`
- `build_response(challenge, log_samples) -> ChallengeResponse` — constructs response from a log holder's samples
- `verify_response(challenge, response, bundle) -> bool` — verifies all paths against bundle's Merkle root
- Validation: raises on missing fields, wrong path lengths, mismatched challenge

### 4. Tests — `valichord_attestation/tests/test_challenge.py` and `test_response.py`

Coverage:
- Deterministic indices: same `(bundle_hash, nonce, k)` produces same index list across runs
- Cross-platform determinism: if possible, test against fixed expected indices
- `k` validation (negative, zero, exceeds total_samples)
- Nonce length validation (<16 bytes raises)
- Round-trip: generate challenge → build response → verify response → success
- Tampered sample: response with wrong sample hash fails verification
- Tampered path: response with wrong Merkle path fails verification
- Mismatched challenge: response built for challenge A, verified against challenge B, fails
- Negative cases: missing fields raise (R4 hash-collision safety)
- Coverage maintained at 100%

### 5. Example — `valichord_attestation/examples/challenge_response_demo.py`

Walks a reader through:
1. Build a bundle from synthetic per-sample outputs
2. Verifier generates a challenge with `k=20`, random nonce
3. Log holder builds the response from their samples
4. Verifier verifies the response against the bundle
5. Demonstrate failure mode: tamper one sample, show verification fails

Output should be readable when run, e.g.:
```
[verifier] generated challenge: 20 samples requested
[holder] revealing: indices [3, 17, 42, ..., 491]
[verifier] verifying 20 paths against bundle root...
[verifier] ✓ all paths verify, faithfulness confirmed (probabilistic, k=20)
```

### 6. README update — `valichord_attestation/README.md`

Add a brief subsection "Probabilistic Challenge-Response" pointing at the spec and the demo. One paragraph; this isn't a marketing surface.

---

## Out of scope — do not implement in this work

- **Trusted Execution Environment (TEE) integration.** TEE-backed attestation is a separate v2 design; do not bundle it with this work.
- **Zero-knowledge proofs over eval execution.** Research-stage; explicitly future.
- **Signed responses.** A response signed by the log holder's private key would add non-repudiation but isn't strictly necessary for faithfulness verification. Defer to a later iteration if useful.
- **Adaptive challenges.** Challenges that target specific suspected regions of the log (rather than uniform random) are a future direction. v1.1 stays uniform.
- **On-chain integration with Holochain DNAs.** Separate piece of work; the on-chain commit-reveal flow stays untouched in this PR.
- **Changes to the v1 bundle format.** Bundles do not change. Any field additions to bundles are explicitly out of scope.

---

## Acceptance criteria

- [ ] Spec doc includes the Probabilistic Challenge-Response section with PRF construction, schemas, verification algorithm, and a sensitivity table
- [ ] `challenge.py` and `response.py` modules implemented and exported from `__init__.py`
- [ ] Tests pass with coverage at 100% (matching v1)
- [ ] `challenge_response_demo.py` runs end-to-end and demonstrates both success and tampered-sample failure
- [ ] README updated with a brief pointer
- [ ] No changes to the v1 bundle format
- [ ] No new heavy dependencies beyond the existing `jcs` library
- [ ] R4 (no silent defaults) verified by negative-case tests on Challenge and Response constructors

---

## If anything is ambiguous

Raise the question before guessing. Specific things worth checking with the founder:

- **PRF/PRNG construction.** HMAC-DRBG (NIST SP 800-90A) is the most rigorous choice. A simpler SHA-256 counter-mode construction (`SHA256(seed || counter)` mod `total_samples`) is easier to specify and re-implement in other languages. Recommend the simpler counter-mode unless there's a reason to prefer HMAC-DRBG.
- **Whether responses should include sample content as well as hash.** Brief specifies hash-only (stronger privacy). If there's a use case where verifier needs content too, that's a separate "audit response" mode and should be a deliberate design choice, not a default.
- **Whether to accept a challenge by hash (compact) or by full structure.** Recommend full structure (`bundle_hash`, `verifier_nonce`, `k`) so the protocol is self-contained, but a hash-only "compact challenge" is possible if size matters.
- **Sensitivity table values.** What cheating fractions to tabulate (`f = 0.01, 0.05, 0.1` is suggested; could include `f = 0.001` for very stringent verifiers).

These are real design choices. Surface them rather than picking silently.

---

## Strategic note

This work moves Valichord materially closer to Scott's "excellent" goal without waiting for TEE infrastructure or ZK proofs. Combined with the protocol-level federation (multiple validators independently producing matching Merkle roots), the realistic faithfulness story for Valichord becomes:

> *"Multiple independent validators reproduce the eval; their bundles converge on identical Merkle roots; any verifier can probabilistically challenge any individual bundle to confirm its log holder really has the samples that produced the root. To fabricate a result, an attacker would need to (a) produce a Merkle root matching what 6+ honest validators independently produced, AND (b) produce log samples consistent with that root for any randomly-chosen index a verifier might challenge. Both conditions together are vanishingly hard."*

That's a story worth telling — and one that's grounded in shipped code rather than future cryptography.
