"""Balanced resampling across validators — coordinate the sample, never the answer.

The one place the "you go that way, I'll go this way" instinct legitimately
applies. Validators must not coordinate on what they CONCLUDE — that replaces
the measurement with an artefact of the coordination, whether they converge
(deferral, see arbitration.py) or diverge. But nothing stops them coordinating on
WHICH SLICE OF THE DATA they each look at, because assigning resamples requires
knowing nobody's answer and leaks nothing about anyone's verdict.

The balanced bootstrap (Davison, Hinkley & Schechtman, 1986) constructs a set of
k resamples so that each original observation appears exactly k times across the
set, rather than letting k independent draws over- and under-sample rows by
chance. Same estimator, same expectation, lower Monte Carlo variance.

Properties that matter here:
  * deterministic — validator i takes stratum i of a construction fixed in
    advance, so the assignment is reproducible;
  * verifiable — anyone can check a validator used the resample it was assigned;
  * blinding intact — no validator learns anything about another's result.

WHAT IS MEASURED. For one dataset, many independent COHORTS of k validators are
run under each scheme, and the spread of the resulting block-coverage estimate is
compared. Lower spread at equal k means a sharper estimate for the same validator
cost. The mean is reported alongside, because a scheme that shifted the mean
would be introducing bias rather than removing noise, and that would disqualify
it however tight the estimate looked.

An independent cohort of k=7 is included as a yardstick: if balanced-5 reaches
the precision of independent-7, the saving is two validators per round — which is
the cost reduction adaptive recruitment failed to deliver.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import lambda_rule
from generate import block_of, feature_names, generate
from sweep import spec_for

ATTACKED_BLOCK = "blk2"
BETAS = (1.0, 0.2, 0.12)
COHORT_K = 5
YARDSTICK_K = 7


def independent_indices(n: int, k: int, rng: np.random.Generator) -> np.ndarray:
    """k ordinary bootstrap resamples, drawn independently. Shape (k, n)."""
    return rng.integers(0, n, size=(k, n))


def balanced_indices(n: int, k: int, rng: np.random.Generator) -> np.ndarray:
    """k resamples in which every observation appears exactly k times in total.

    Construction is the standard one: concatenate k copies of the index vector,
    permute the lot, and cut it into k blocks of length n. The rows are no longer
    independent of each other — that is the entire point, and it is why the
    scheme has to be assigned rather than chosen by each validator alone.
    """
    pool = np.tile(np.arange(n), k)
    rng.shuffle(pool)
    return pool.reshape(k, n)


def cohort_coverage(
    X: np.ndarray, y: np.ndarray, names: list[str], idx: np.ndarray, block: str
) -> float:
    """Fraction of the cohort selecting at least one member of `block`."""
    hits = 0
    for row in idx:
        support_idx, _alpha = lambda_rule.fit_support(X[row], y[row])
        support = [names[i] for i in support_idx]
        if any(block_of(n) == block for n in support):
            hits += 1
    return hits / idx.shape[0]


def run_dataset(
    dataset_seed: int, target_beta: float, cohorts: int, rng: np.random.Generator
) -> dict:
    """Many cohorts on ONE dataset, under each scheme."""
    spec = spec_for(dataset_seed, target_beta)
    X, y = generate(spec)
    names = feature_names(spec)
    n = X.shape[0]

    out: dict[str, list[float]] = {"independent": [], "balanced": [], "independent_7": []}
    for _ in range(cohorts):
        out["independent"].append(
            cohort_coverage(X, y, names, independent_indices(n, COHORT_K, rng), ATTACKED_BLOCK)
        )
        out["balanced"].append(
            cohort_coverage(X, y, names, balanced_indices(n, COHORT_K, rng), ATTACKED_BLOCK)
        )
        out["independent_7"].append(
            cohort_coverage(X, y, names, independent_indices(n, YARDSTICK_K, rng), ATTACKED_BLOCK)
        )
    return {"dataset_seed": dataset_seed, "target_beta": target_beta, "coverage": out}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datasets", type=int, default=10)
    parser.add_argument("--cohorts", type=int, default=20)
    parser.add_argument("--base-seed", type=int, default=440000)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "artifacts")
    args = parser.parse_args()

    rng = np.random.default_rng(4242)
    results = []
    total = args.datasets * len(BETAS)
    done = 0

    for beta in BETAS:
        for d in range(args.datasets):
            results.append(run_dataset(args.base_seed + d, beta, args.cohorts, rng))
            done += 1
            print(f"  {done}/{total} datasets", flush=True)

    summary = {}
    for beta in BETAS:
        subset = [r for r in results if r["target_beta"] == beta]
        row = {}
        for scheme in ("independent", "balanced", "independent_7"):
            # Within-dataset spread, then averaged over datasets: this isolates
            # the resampling noise from genuine dataset-to-dataset differences,
            # which is the quantity the scheme is supposed to shrink.
            sds = [float(np.std(r["coverage"][scheme], ddof=1)) for r in subset]
            means = [float(np.mean(r["coverage"][scheme])) for r in subset]
            row[scheme] = {
                "mean_coverage": float(np.mean(means)),
                "mean_within_dataset_sd": float(np.mean(sds)),
                # Per-dataset values retained so the bias question can be settled
                # by a PAIRED test without refitting. The aggregate means above
                # cannot distinguish a real shift from between-dataset noise.
                "per_dataset_mean": means,
                "per_dataset_sd": sds,
            }
        ind = row["independent"]["mean_within_dataset_sd"]
        bal = row["balanced"]["mean_within_dataset_sd"]
        row["sd_reduction"] = (ind - bal) / ind if ind > 0 else None
        summary[str(beta)] = row

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "balanced_results.json").write_text(
        json.dumps(
            {
                "datasets": args.datasets,
                "cohorts_per_dataset": args.cohorts,
                "cohort_k": COHORT_K,
                "yardstick_k": YARDSTICK_K,
                "attacked_block": ATTACKED_BLOCK,
                "summary": summary,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    print(f"\nBalanced vs independent resampling across validators")
    print(f"{args.datasets} datasets x {args.cohorts} cohorts, k={COHORT_K} "
          f"(yardstick: independent k={YARDSTICK_K})\n")
    print(f"  {'beta':<7}{'scheme':<16}{'mean cov':>10}{'within-ds SD':>14}")
    for beta in BETAS:
        row = summary[str(beta)]
        for scheme in ("independent", "balanced", "independent_7"):
            s = row[scheme]
            label = beta if scheme == "independent" else ""
            print(
                f"  {str(label):<7}{scheme:<16}{s['mean_coverage']:>10.3f}"
                f"{s['mean_within_dataset_sd']:>14.4f}"
            )
        red = row["sd_reduction"]
        # None when the independent SD is exactly zero — every cohort agreed, so
        # there is no resampling noise left for balancing to remove. That is the
        # ceiling case, not a failure.
        shown = "n/a (no noise)" if red is None else f"{red:.1%}"
        print(f"  {'':<7}{'-> SD change':<16}{'':>10}{shown:>14}\n")

    print("  Mean coverage is the bias check: the schemes must agree, or balancing")
    print("  is shifting the estimate rather than sharpening it.")
    print("  'within-ds SD' is the spread of the estimate across cohorts on the SAME")
    print("  dataset — the resampling noise the scheme is meant to shrink.")


if __name__ == "__main__":
    main()
