"""
Probabilistic Challenge-Response Demo
======================================
Walks through the full protocol:
  1. Build a bundle from synthetic per-sample outputs.
  2. Verifier generates a challenge (k=20, random nonce).
  3. Log holder builds the response from their samples.
  4. Verifier verifies the response against the bundle.
  5. Demonstrate failure: tamper one sample, show verification fails.
"""

import os
import copy
from valichord_attestation import (
    build_bundle,
    hash_bundle,
    Challenge,
    build_response,
    verify_response,
    ResponseSample,
)

# ---------------------------------------------------------------------------
# Step 1 — build a bundle from synthetic per-sample outputs
# ---------------------------------------------------------------------------

N = 500
samples = [
    {"index": i, "prompt": f"question_{i}", "output": str(i * 13 % 97), "correct": i % 5 != 0}
    for i in range(N)
]

bundle = build_bundle(
    model_id="demo-model-v1",
    task_id="demo-eval/synthetic",
    raw_metrics=[{"key": "accuracy", "value": round(sum(s["correct"] for s in samples) / N, 6)}],
    samples=samples,
    repo_commit="deadbeef",
    command="demo eval --model demo-model-v1",
)

bundle_hash = hash_bundle(bundle)
print(f"[holder] bundle built: {N} samples, hash={bundle_hash[:16]}...")
print(f"[holder] Merkle root: {bundle.outputs_merkle_root[:16]}...")
print()

# ---------------------------------------------------------------------------
# Step 2 — verifier generates a challenge (k=20, fresh random nonce)
# ---------------------------------------------------------------------------

k = 20
nonce = os.urandom(32)
challenge = Challenge(bundle_hash=bundle_hash, verifier_nonce=nonce, k=k)

print(f"[verifier] generated challenge: {k} samples requested")
print(f"[verifier] nonce (first 8 bytes): {nonce[:8].hex()}...")
print()

# ---------------------------------------------------------------------------
# Step 3 — log holder builds the response
# ---------------------------------------------------------------------------

from valichord_attestation.challenge import generate_indices
indices = generate_indices(challenge, len(samples))
print(f"[holder] challenged indices (first 10): {indices[:10]}...")

response = build_response(challenge, samples)
print(f"[holder] response built: {len(response.samples)} samples revealed (hashes only)")
print()

# ---------------------------------------------------------------------------
# Step 4 — verifier verifies the response
# ---------------------------------------------------------------------------

ok = verify_response(challenge, response, bundle)
print(f"[verifier] verifying {k} Merkle paths against bundle root...")
assert ok, "verification failed unexpectedly"
print(f"[verifier] ✓ all paths verify, faithfulness confirmed (probabilistic, k={k})")
print()

# ---------------------------------------------------------------------------
# Step 5 — demonstrate failure: tamper one sample hash
# ---------------------------------------------------------------------------

tampered_response = copy.deepcopy(response)
s = tampered_response.samples[0]
tampered_response.samples[0] = ResponseSample(
    sample_index=s.sample_index,
    sample_content_hash="0" * 64,   # wrong hash
    merkle_path=s.merkle_path,
)

fail = verify_response(challenge, tampered_response, bundle)
assert not fail, "tampered response should have failed"
print(f"[verifier] ✗ tampered response correctly rejected (sample {s.sample_index} hash mismatch)")
print()
print("Demo complete.")
print()
print("Note: probabilistic guarantee — if a fraction f of the log is fabricated,")
print(f"the probability of catching it with k={k} challenges is 1-(1-f)^{k}.")
print(f"  f=5%  → {1 - 0.95**k:.0%} catch probability")
print(f"  f=10% → {1 - 0.90**k:.0%} catch probability")
