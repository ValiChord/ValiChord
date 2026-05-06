#!/usr/bin/env python3
"""
Build a ValiChord attestation bundle from lm-evaluation-harness output.

Usage (real eval output from run_eval.sh):
    python build_bundle.py --output-path ./eval_output

Usage (fixture mode — no GPU required, uses built-in simulated data):
    python build_bundle.py --fixture

The produced bundle.json stores both the bundle and the per-sample data
(same format as the examples in the parent directory) so that
challenge_response_demo.py can load it without the raw eval log.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path

import jcs

from valichord_attestation import build_bundle, hash_bundle, merkle_proof
from valichord_attestation.canonical import bundle_to_dict

HERE = Path(__file__).parent


# ---------------------------------------------------------------------------
# Parsing real lm-eval output
# ---------------------------------------------------------------------------

def _find_file(root: Path, pattern: str) -> Path:
    matches = sorted(root.rglob(pattern))
    if not matches:
        sys.exit(f"No file matching '{pattern}' found under {root}")
    return matches[-1]  # latest if timestamps in name


def parse_lm_eval_output(output_path: Path) -> tuple[dict, list[dict]]:
    """Return (results_dict, samples_list) from an lm-eval output directory.

    lm-eval v0.4.x writes:
      {output_path}/**/results_*.json          — aggregated metrics
      {output_path}/**/samples_gsm8k*.jsonl    — per-sample outputs (--log_samples)
    """
    results_file = _find_file(output_path, "results_*.json")
    samples_file = _find_file(output_path, "samples_gsm8k*.jsonl")

    results = json.loads(results_file.read_text())

    samples: list[dict] = []
    for line in samples_file.read_text().splitlines():
        line = line.strip()
        if line:
            samples.append(json.loads(line))

    return results, samples


def extract_metrics(results: dict) -> list[dict]:
    """Extract metrics from lm-eval results_*.json into build_bundle() format.

    lm-eval stores paired metrics with a `_stderr` suffix.  We emit one entry
    per base metric and attach the stderr if present.

    Example input:
        {"gsm8k": {"exact_match,flexible-extract": 0.35,
                   "exact_match,flexible-extract_stderr": 0.048, "alias": "gsm8k"}}
    """
    gsm8k = results.get("results", {}).get("gsm8k", {})
    out: list[dict] = []
    for key, value in gsm8k.items():
        if key in ("alias",) or key.endswith("_stderr"):
            continue
        stderr = gsm8k.get(f"{key}_stderr")
        entry: dict = {"key": key, "value": float(value)}
        if stderr is not None:
            entry["stderr"] = float(stderr)
        out.append(entry)
    return out


def extract_bundle_samples(lm_eval_samples: list[dict]) -> list[dict]:
    """Reduce lm-eval per-sample dicts to the minimal bundle-sample schema.

    Keeps: doc_id, target (gold answer), filtered_response (model answer),
    exact_match (bool).  Strips the raw multi-token response and 5-shot prompt
    — those are too large and not needed for Merkle commitments.
    """
    out = []
    for s in sorted(lm_eval_samples, key=lambda x: x["doc_id"]):
        filtered = s.get("filtered_resps", [""])[0]
        out.append({
            "doc_id": s["doc_id"],
            "target": s["target"],
            "filtered_response": filtered,
            "exact_match": s.get("exact_match", 0.0) == 1.0,
        })
    return out


def extract_run_metadata(results: dict) -> dict:
    """Pull harness_version, repo_commit, and command from results_*.json."""
    config = results.get("config", {})
    model_args = config.get("model_args", "")
    model = config.get("model", "hf")
    limit = config.get("limit", 100)

    git_hash = results.get("git_hash") or config.get("git_hash")
    harness_version = f"lm-evaluation-harness=={git_hash}" if git_hash else "lm-evaluation-harness==0.4.4"

    command = (
        f"lm_eval --model {model} --model_args {model_args!r} "
        f"--tasks gsm8k --num_fewshot 5 --limit {limit} --batch_size 1 --log_samples"
    )
    return {"harness_version": harness_version, "command": command}


# ---------------------------------------------------------------------------
# Fixture — deterministic simulated data (no GPU required)
# ---------------------------------------------------------------------------

def _make_fixture() -> tuple[dict, list[dict]]:
    """Return (results_dict, bundle_samples) matching the real lm-eval schema.

    Generated with random.Random(42) for full determinism.  Accuracy ~35%,
    consistent with Mistral-7B-Instruct-v0.3 on GSM8K (5-shot, greedy).

    WARNING: this is simulated data for demonstration purposes.
    Run run_eval.sh on a GPU to produce a real bundle.
    """
    rng = random.Random(42)
    n = 100

    # Realistic GSM8K answer distribution: mostly small integers, some larger.
    def _target() -> int:
        r = rng.random()
        if r < 0.40:
            return rng.randint(1, 50)
        elif r < 0.70:
            return rng.randint(51, 200)
        elif r < 0.90:
            return rng.randint(201, 1000)
        else:
            return rng.randint(1001, 5000)

    targets = [_target() for _ in range(n)]
    correct_indices = set(rng.sample(range(n), 35))  # 35% accuracy

    samples: list[dict] = []
    for i in range(n):
        t = targets[i]
        if i in correct_indices:
            response = str(t)
        else:
            # Plausible wrong answer: arithmetic perturbation
            ops = [(t * 2, "doubled"), (t + rng.randint(1, 15), "+err"),
                   (max(1, t - rng.randint(1, 10)), "-err"),
                   (t * rng.randint(3, 6), "scaled")]
            response = str(rng.choice(ops)[0])
        samples.append({
            "doc_id": i,
            "target": str(t),
            "filtered_response": response,
            "exact_match": i in correct_indices,
        })

    accuracy = 35 / n
    stderr = math.sqrt(accuracy * (1 - accuracy) / n)

    results = {
        "results": {
            "gsm8k": {
                "exact_match,flexible-extract": round(accuracy, 6),
                "exact_match,flexible-extract_stderr": round(stderr, 6),
                "alias": "gsm8k",
            }
        },
        "config": {
            "model": "hf",
            "model_args": (
                "pretrained=mistralai/Mistral-7B-Instruct-v0.3,"
                "revision=main,dtype=bfloat16"
            ),
            "limit": 100,
            "git_hash": "v0.5.0",  # lm-evaluation-harness version tag
        },
    }
    return results, samples


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--output-path", metavar="PATH",
        help="Path to lm-eval output directory produced by run_eval.sh",
    )
    group.add_argument(
        "--fixture", action="store_true",
        help="Use built-in simulated data (no GPU required)",
    )
    parser.add_argument(
        "--generated-at", metavar="ISO8601",
        help="Fix the bundle timestamp for reproducibility (default: current UTC time)",
    )
    args = parser.parse_args()

    if args.output_path:
        print(f"Parsing lm-eval output from: {args.output_path}")
        results, lm_samples = parse_lm_eval_output(Path(args.output_path))
        bundle_samples = extract_bundle_samples(lm_samples)
        raw_metrics = extract_metrics(results)
        meta = extract_run_metadata(results)
        model_id = "mistralai/Mistral-7B-Instruct-v0.3"
        fixture_warning = None
    else:
        if not args.fixture and sys.stdin.isatty():
            print("No --output-path given; running in fixture mode (simulated data).")
            print("Pass --output-path ./eval_output after running run_eval.sh on a GPU.\n")
        results, bundle_samples = _make_fixture()
        raw_metrics = extract_metrics(results)
        meta = extract_run_metadata(results)
        model_id = "mistralai/Mistral-7B-Instruct-v0.3"
        fixture_warning = (
            "SIMULATED DATA — not from a real GPU run. "
            "Run run_eval.sh on a GPU and re-run this script with --output-path "
            "to produce a bundle from a real evaluation."
        )

    print(f"  samples: {len(bundle_samples)}")
    print(f"  metrics: {[m['key'] for m in raw_metrics]}")

    bundle = build_bundle(
        model_id=model_id,
        task_id="gsm8k",
        raw_metrics=raw_metrics,
        samples=bundle_samples,
        samples_total=100,  # explicit: exercises the sample-omission defence
        harness_version=meta["harness_version"],
        command=meta["command"],
        repo_commit=results.get("config", {}).get("git_hash"),
        generated_at=args.generated_at or None,
    )

    bundle_hash = hash_bundle(bundle)
    print(f"  bundle hash: {bundle_hash}")
    print(f"  Merkle root: {bundle.outputs_merkle_root}")

    # Round-trip validation: re-canonicalise from the dict and confirm hash.
    bundle_dict = bundle_to_dict(bundle)
    recanon = jcs.canonicalize(bundle_dict)
    recanon_bytes = recanon if isinstance(recanon, bytes) else recanon.encode()
    rehash = hashlib.sha256(recanon_bytes).hexdigest()
    assert rehash == bundle_hash, f"Round-trip hash mismatch: {rehash} != {bundle_hash}"
    print("  Round-trip validated.")

    # Build sample_0 Merkle proof for the _source block.
    proof_0 = merkle_proof(bundle_samples, 0)

    source: dict = {
        "note": (
            "Real-data demo: Mistral-7B-Instruct-v0.3 on GSM8K (100-sample subset). "
            "Built with build_bundle.py; verified by challenge_response_demo.py."
        ),
        "bundle_sha256": bundle_hash,
        "sample_0_proof": proof_0,
    }
    if fixture_warning:
        source["warning"] = fixture_warning

    out = {
        "_source": source,
        "bundle": bundle_dict,
        "samples": bundle_samples,
    }

    out_path = HERE / "bundle.json"
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
