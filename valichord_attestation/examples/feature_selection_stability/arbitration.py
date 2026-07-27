"""Which rule, if any, picks the RIGHT member of a correlated block?

The demonstration reports that a block is recovered reliably while which of its
members gets selected scatters. That is the finite-sample shadow of a classical
result (R. J. Tibshirani, *The Lasso Problem and Uniqueness*, EJS 7, 2013): with
identical columns the lasso FIT is unique while the COEFFICIENTS are not. The
same reading underpins polite-shrink's `RELATED_regularisation.md`, which reaches
it from the distributed-storage side: coverage is determined, the holder set is
not.

That raises a question worth settling by experiment rather than by argument:
**is there a rule that recovers the true member anyway?**

Because the data is synthetic we know the answer. `blk{b}_f0` carries the signal;
its three partners correlate at 0.95 and carry nothing. So every rule can be
scored against ground truth, and "closer to the answer" is a number rather than
an opinion. Chance is 25% (four members per block).

Three rules are compared:

  NAIVE   — the member the most validators selected.
  MASS    — the member carrying the largest mean |coefficient|. This is the
            direct test of the uniqueness reading: if the block's total weight is
            determined while its split is not, mass should be steadier than
            selection.
  POLITE  — the polite-shrink rule. Process validators in order; the first to
            claim any member of a block fixes that block's representative, and
            later validators defer instead of re-claiming. That is the
            Gauss-Seidel sweep manufactured without a coordinator, exactly as in
            `polite_shrink.py`'s `_execute_intent`.

POLITE is additionally run under many random validator orderings. If it is
finding the answer, permuting the order should barely matter. If it is
manufacturing one, the answer will move with the ordering — which would
demonstrate the underdetermination directly instead of citing a theorem for it.

A caveat that is itself a finding: POLITE can only be tested here as a POST-HOC
aggregation over already-revealed supports. A validator who defers to another's
announced choice has stopped being an independent witness, and independence is
the entire evidentiary value of the round. Polite-shrink needs
coordination-by-announcement; ValiChord's value is the absence of it. Same shape,
opposite objectives.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.linear_model import Lasso

import lambda_rule
from generate import SPEC, feature_names
from party import bootstrap
from sweep import VALIDATOR_POOL, party_seed, spec_for

# Betas for the ATTACKED block (blk2). blk0 and blk1 keep their fixed strengths
# of 3.0 and 2.0 throughout, so they supply strong-block evidence at every step.
ARBITRATION_BETAS = (1.0, 0.4, 0.2, 0.12, 0.0)

N_ORDERINGS = 20
CHANCE = 1.0 / SPEC.block_size


def coefficients_at(X: np.ndarray, y: np.ndarray, alpha: float) -> np.ndarray:
    """Coefficients at a given alpha.

    Deliberately NOT added to lambda_rule.py. That module is hashed into the
    pre-registration; extracting coefficients is an analysis step taken after the
    fact, not part of the agreed procedure, and adding it there would invalidate
    every protocol hash for no methodological reason. The estimator constants are
    imported rather than restated so the two cannot drift.
    """
    model = Lasso(
        alpha=alpha,
        max_iter=lambda_rule.MAX_ITER,
        fit_intercept=True,
        selection="cyclic",
    )
    model.fit(X, y)
    return model.coef_


def block_members(block_index: int) -> list[int]:
    start = block_index * SPEC.block_size
    return list(range(start, start + SPEC.block_size))


def true_member(block_index: int) -> int:
    """Ground truth: the signal always sits at the block's first index."""
    return block_index * SPEC.block_size


def run_replication(dataset_seed: int, target_beta: float, pool: int = VALIDATOR_POOL) -> dict:
    """Fit a pool of validators, keeping supports AND coefficients."""
    spec = spec_for(dataset_seed, target_beta)
    X, y = np.array([]), np.array([])
    from generate import generate

    X, y = generate(spec)

    validators = []
    for v in range(1, pool + 1):
        Xv, yv = bootstrap(X, y, party_seed(dataset_seed, v))
        idx, alpha = lambda_rule.fit_support(Xv, yv)
        coefs = coefficients_at(Xv, yv, alpha)
        validators.append({"support_idx": idx, "coefs": coefs})

    return {"dataset_seed": dataset_seed, "target_beta": target_beta, "validators": validators}


def rule_naive(validators: list[dict], members: list[int]) -> int | None:
    """Most-selected member. Ties broken by lowest index — recorded, not hidden."""
    counts = Counter()
    for v in validators:
        for m in members:
            if m in v["support_idx"]:
                counts[m] += 1
    if not counts:
        return None
    best = max(counts.values())
    return min(m for m, c in counts.items() if c == best)


def rule_mass(validators: list[dict], members: list[int]) -> int | None:
    """Member with the largest mean |coefficient| across validators."""
    totals = {m: 0.0 for m in members}
    seen = False
    for v in validators:
        for m in members:
            totals[m] += abs(v["coefs"][m])
            if m in v["support_idx"]:
                seen = True
    if not seen:
        return None
    return max(totals, key=lambda m: (totals[m], -m))


def rule_polite(validators: list[dict], members: list[int], order: list[int]) -> int | None:
    """First claimant wins; later validators defer.

    The polite-shrink move: honour the announcements already made, then act. The
    first validator in `order` holding any member of the block fixes the
    representative — its own strongest held member — and everyone after defers.
    """
    for i in order:
        held = [m for m in members if m in validators[i]["support_idx"]]
        if held:
            return max(held, key=lambda m: (abs(validators[i]["coefs"][m]), -m))
    return None


def score_replication(rep: dict, k: int, rng: np.random.Generator) -> list[dict]:
    """Score all three rules on every block of one replication."""
    validators = rep["validators"][:k]
    rows = []

    for b in range(SPEC.n_blocks):
        members = block_members(b)
        truth = true_member(b)

        # blk2 at beta = 0 has NO true member, so accuracy is undefined there.
        # Excluded rather than scored against a fiction.
        beta = rep["target_beta"] if b == SPEC.n_blocks - 1 else SPEC.signal_coefficients[b]
        if beta == 0.0:
            continue

        naive = rule_naive(validators, members)
        mass = rule_mass(validators, members)
        if naive is None and mass is None:
            continue  # block not recovered by anyone; nothing to arbitrate

        orderings = [list(rng.permutation(k)) for _ in range(N_ORDERINGS)]
        polite_picks = [rule_polite(validators, members, o) for o in orderings]
        polite_picks = [p for p in polite_picks if p is not None]

        rows.append(
            {
                "block": b,
                "beta": beta,
                "naive_correct": naive == truth,
                "mass_correct": mass == truth,
                "polite_mean_correct": (
                    sum(p == truth for p in polite_picks) / len(polite_picks)
                    if polite_picks
                    else None
                ),
                "polite_distinct_answers": len(set(polite_picks)),
                "polite_order_dependent": len(set(polite_picks)) > 1,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replications", type=int, default=100)
    parser.add_argument("--base-seed", type=int, default=880000)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "artifacts")
    args = parser.parse_args()

    rng = np.random.default_rng(12345)
    seeds = [args.base_seed + i for i in range(args.replications)]
    total = len(seeds) * len(ARBITRATION_BETAS)

    rows: list[dict] = []
    done = 0
    for beta in ARBITRATION_BETAS:
        for seed in seeds:
            rep = run_replication(seed, beta)
            rows.extend(score_replication(rep, args.k, rng))
            done += 1
            if done % 25 == 0 or done == total:
                print(f"  {done}/{total} replications", flush=True)

    def summarise(subset: list[dict]) -> dict:
        if not subset:
            return {}
        polite = [r["polite_mean_correct"] for r in subset if r["polite_mean_correct"] is not None]
        return {
            "n": len(subset),
            "naive": sum(r["naive_correct"] for r in subset) / len(subset),
            "mass": sum(r["mass_correct"] for r in subset) / len(subset),
            "polite": sum(polite) / len(polite) if polite else None,
            "polite_order_dependent": sum(r["polite_order_dependent"] for r in subset) / len(subset),
            "polite_mean_distinct_answers": sum(r["polite_distinct_answers"] for r in subset) / len(subset),
        }

    strong = [r for r in rows if r["beta"] >= 2.0]
    by_beta = {
        beta: summarise([r for r in rows if r["block"] == SPEC.n_blocks - 1 and r["beta"] == beta])
        for beta in ARBITRATION_BETAS
        if beta > 0
    }

    result = {
        "k": args.k,
        "n_orderings": N_ORDERINGS,
        "chance": CHANCE,
        "strong_blocks": summarise(strong),
        "attacked_block_by_beta": by_beta,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "arbitration_results.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, default=float) + "\n"
    )

    print(f"\nWhich rule picks the TRUE member of a correlated block?")
    print(f"k={args.k} validators, {N_ORDERINGS} orderings per block, chance = {CHANCE:.0%}\n")

    s = result["strong_blocks"]
    print(f"STRONG BLOCKS (beta 3.0 and 2.0), n={s['n']}")
    print(f"  naive (most-selected):      {s['naive']:.0%}")
    print(f"  mass  (largest |coef|):     {s['mass']:.0%}")
    print(f"  polite (first claimant):    {s['polite']:.0%}")
    print(f"  polite answer changed with ordering: {s['polite_order_dependent']:.0%} of blocks")
    print(f"  polite distinct answers per block:   {s['polite_mean_distinct_answers']:.2f}")

    print(f"\nATTACKED BLOCK, by its signal strength")
    print(f"  {'beta':<7}{'n':>5}{'naive':>9}{'mass':>9}{'polite':>9}{'order-dep':>12}")
    for beta, st in sorted(by_beta.items(), reverse=True):
        if not st:
            continue
        pol = "n/a" if st["polite"] is None else f"{st['polite']:.0%}"
        print(
            f"  {beta:<7.2f}{st['n']:>5}{st['naive']:>8.0%}{st['mass']:>9.0%}"
            f"{pol:>9}{st['polite_order_dependent']:>11.0%}"
        )

    print("\n  'order-dep' = share of blocks where permuting the validator order")
    print("  changed which member the polite rule returned.")


if __name__ == "__main__":
    main()
