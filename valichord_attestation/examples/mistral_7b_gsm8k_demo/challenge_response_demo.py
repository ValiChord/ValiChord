#!/usr/bin/env python3
"""
Challenge-Response Demo — Mistral-7B GSM8K bundle
===================================================
Loads the committed bundle.json and walks through the full v1.1 protocol:

  1. Load the bundle and its per-sample outputs.
  2. Verifier generates a challenge: k=20, fixed nonce for reproducibility.
  3. Log holder builds the response (hashes + Merkle paths, no raw content).
  4. Verifier checks all 20 paths against the bundle Merkle root.
  5. Demonstrate failure: tamper one sample hash, observe rejection.

Fixed nonce: bytes(range(32)) — 0x00 through 0x1f.
This is documented and fixed so the demo is reproducible across runs.
In production the verifier must use a fresh random nonce each time.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from valichord_attestation import (
    Challenge,
    ResponseSample,
    build_response,
    hash_bundle,
    verify_response,
)
from valichord_attestation.bundle import Bundle, Metric
from valichord_attestation.challenge import generate_indices

HERE = Path(__file__).parent


def _load_bundle_json() -> tuple[Bundle, list[dict], str]:
    """Load bundle.json; return (Bundle, samples, stored_hash)."""
    doc = json.loads((HERE / "bundle.json").read_text())
    bd = doc["bundle"]
    metrics = [
        Metric(key=m["key"], value=m["value"], stderr=m.get("stderr"))
        for m in bd["metrics"]
    ]
    s = bd["samples"]
    bundle = Bundle(
        format_version=bd["format_version"],
        generated_at=bd["generated_at"],
        model_id=bd["model_id"],
        task_id=bd["task_id"],
        metrics=metrics,
        samples_total=s["total"],
        samples_completed=s["completed"],
        outputs_merkle_root=bd["outputs_merkle_root"],
        repo_commit=bd.get("repo_commit"),
        harness_version=bd.get("harness_version"),
        command=bd.get("command"),
    )
    return bundle, doc["samples"], doc["_source"]["bundle_sha256"]


# ---------------------------------------------------------------------------
# Step 1 — load bundle
# ---------------------------------------------------------------------------

bundle, samples, stored_hash = _load_bundle_json()

live_hash = hash_bundle(bundle)
assert live_hash == stored_hash, (
    f"bundle.json hash mismatch!\n  stored:   {stored_hash}\n  computed: {live_hash}"
)
print(f"[1] Bundle loaded and hash verified")
print(f"    model:       {bundle.model_id}")
print(f"    task:        {bundle.task_id}")
print(f"    samples:     {bundle.samples_completed}/{bundle.samples_total}")
accuracy = next(m.value for m in bundle.metrics if "flexible" in m.key)
print(f"    accuracy:    {accuracy:.1%}  ({int(accuracy * bundle.samples_completed)}/{bundle.samples_completed})")
print(f"    hash:        {live_hash[:24]}...")
print(f"    Merkle root: {bundle.outputs_merkle_root[:24]}...")
print()

# ---------------------------------------------------------------------------
# Step 2 — verifier generates challenge (k=20, fixed nonce)
# ---------------------------------------------------------------------------

K = 20
FIXED_NONCE = bytes(range(32))  # 0x00..0x1f — fixed for demo reproducibility

challenge = Challenge(bundle_hash=live_hash, verifier_nonce=FIXED_NONCE, k=K)
indices = generate_indices(challenge, bundle.samples_total)

print(f"[2] Challenge issued by verifier")
print(f"    k={K}, nonce=bytes(range(32))  [fixed demo nonce — use os.urandom(32) in production]")
print(f"    challenged indices (first 10): {indices[:10]}")
print()

# ---------------------------------------------------------------------------
# Step 3 — log holder builds response
# ---------------------------------------------------------------------------

response = build_response(challenge, samples)
print(f"[3] Response built by log holder")
print(f"    {len(response.samples)} samples revealed (hashes + Merkle paths only, no raw content)")
print()

# ---------------------------------------------------------------------------
# Step 4 — verifier checks response
# ---------------------------------------------------------------------------

ok = verify_response(challenge, response, bundle)
assert ok, "Verification failed unexpectedly"
print(f"[4] Verification: PASS")
print(f"    All {K} Merkle paths reconstruct to the bundle root.")
print(f"    Probabilistic guarantee: if fraction f of the log is fabricated,")
print(f"    catch probability with k={K} is 1-(1-f)^{K}")
print(f"      f=5%  → {1 - 0.95**K:.0%} catch probability")
print(f"      f=10% → {1 - 0.90**K:.0%} catch probability")
print(f"      f=20% → {1 - 0.80**K:.0%} catch probability")
print()

# ---------------------------------------------------------------------------
# Step 5 — demonstrate failure: tamper one sample hash
# ---------------------------------------------------------------------------

tampered = copy.deepcopy(response)
original_idx = tampered.samples[0].sample_index
tampered.samples[0] = ResponseSample(
    sample_index=original_idx,
    sample_content_hash="0" * 64,   # wrong hash — all-zeros
    merkle_path=tampered.samples[0].merkle_path,
)

fail = verify_response(challenge, tampered, bundle)
assert not fail, "Tampered response should have been rejected"
print(f"[5] Tamper detection: PASS")
print(f"    Sample {original_idx} hash replaced with all-zeros → response correctly rejected.")
print()

print("=" * 60)
print("Demo complete. Protocol summary:")
print(f"  Bundle:    {bundle.model_id}")
print(f"  Task:      {bundle.task_id}  (samples_total={bundle.samples_total} declared)")
print(f"  Challenge: k={K}, verifier-chosen nonce")
print(f"  Result:    faithfulness verified probabilistically, tamper detected")
print("=" * 60)
