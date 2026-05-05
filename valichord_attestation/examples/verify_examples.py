#!/usr/bin/env python3
"""Verify that the bundled example JSON files are self-consistent.

Loads each example, recomputes the bundle hash and Merkle root from
the embedded samples, and checks both against the stored values.
Also verifies the embedded sample proof for each example.

Exit 0 if all checks pass; non-zero on any failure.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import jcs

from valichord_attestation import hash_bundle, merkle_root, verify_faithfulness
from valichord_attestation.bundle import Bundle, Metric


def _load(name: str) -> dict:
    path = Path(__file__).parent / name
    with open(path) as f:
        return json.load(f)


def _dict_to_bundle(d: dict) -> Bundle:
    metrics = [
        Metric(
            key=m["key"],
            value=m["value"],
            stderr=m.get("stderr"),
        )
        for m in d["metrics"]
    ]
    samples_block = d.get("samples", {})
    return Bundle(
        format_version=d["format_version"],
        generated_at=d["generated_at"],
        model_id=d["model_id"],
        task_id=d["task_id"],
        metrics=metrics,
        samples_total=samples_block.get("total", 0),
        samples_completed=samples_block.get("completed", 0),
        outputs_merkle_root=d["outputs_merkle_root"],
        repo_commit=d.get("repo_commit"),
        harness_version=d.get("harness_version"),
        command=d.get("command"),
    )


def verify_example(filename: str) -> bool:
    doc = _load(filename)
    bundle_dict = doc["bundle"]
    samples = doc["samples"]
    source = doc["_source"]

    bundle = _dict_to_bundle(bundle_dict)
    ok = True

    # 1. Recompute bundle hash and compare to stored value
    computed_hash = hash_bundle(bundle)
    stored_hash = source["bundle_sha256"]
    if computed_hash != stored_hash:
        print(f"FAIL [{filename}] bundle hash mismatch")
        print(f"  stored:   {stored_hash}")
        print(f"  computed: {computed_hash}")
        ok = False
    else:
        print(f"OK   [{filename}] bundle hash matches")

    # 2. Recompute Merkle root from samples and compare to bundle field
    computed_root = merkle_root(samples)
    stored_root = bundle_dict["outputs_merkle_root"]
    if computed_root != stored_root:
        print(f"FAIL [{filename}] Merkle root mismatch")
        print(f"  stored:   {stored_root}")
        print(f"  computed: {computed_root}")
        ok = False
    else:
        print(f"OK   [{filename}] Merkle root matches")

    # 3. Verify the embedded sample proof
    proof_key = next(k for k in source if k.endswith("_proof"))
    sample_idx = int(proof_key.split("_")[1])
    proof = source[proof_key]
    if not verify_faithfulness(stored_root, sample_idx, samples[sample_idx], proof):
        print(f"FAIL [{filename}] sample {sample_idx} proof does not verify")
        ok = False
    else:
        print(f"OK   [{filename}] sample {sample_idx} proof verifies")

    # 4. Re-canonicalise and confirm JCS round-trip
    re_encoded = jcs.canonicalize(bundle_dict)
    re_hash = hashlib.sha256(
        re_encoded if isinstance(re_encoded, bytes) else re_encoded.encode()
    ).hexdigest()
    if re_hash != stored_hash:
        print(f"FAIL [{filename}] JCS round-trip hash mismatch")
        ok = False
    else:
        print(f"OK   [{filename}] JCS round-trip consistent")

    return ok


def main() -> None:
    examples = ["simple_eval.json", "complex_eval.json"]
    results = [verify_example(name) for name in examples]
    if all(results):
        print("\nAll examples verified.")
    else:
        print("\nOne or more examples FAILED verification.")
        sys.exit(1)


if __name__ == "__main__":
    main()
