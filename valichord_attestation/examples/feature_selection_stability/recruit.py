"""Wave-based validator recruitment — V0 / V3 / V5 on who joins, not who stores.

The demonstration runs a fixed cohort: every validator does identical work
regardless of whether the evidence was settled after three of them or still
contested after eleven. In polite-shrink's terms that is the blunt fallback —
the small-network clamp that forces every survivor to a FULL arc. Safe, and
maximally expensive.

Validator time is the scarce resource in the real protocol, so the question is
whether the same evidentiary standard can be reached for fewer validator-rounds
by recruiting adaptively: run a wave, see which blocks are still ambiguous,
commission more only for those.

That turns recruitment into polite-shrink's actual problem — autonomous actors
deciding whether to act, on stale views, to meet a coverage target without a
coordinator — and the three encodings can be compared directly:

  V0 naive   Candidates count only COMPLETED work. Everyone currently mid-round
             is invisible, so every candidate sees the same thin evidence and
             joins at once. The thundering herd.
  V3 polite  Candidates announce intent on a separate channel and defer to
             lower-id intenders before deciding. Costs an extra message hop.
  V5 claim   The claim IS the announcement, carried on the channel that already
             exists. A validator registers as a participant immediately and
             produces its attestation later, so readers count in-flight work
             without a new message type.

V5 is not a hypothetical for ValiChord: `StudyClaim` (with `RequestToClaim`,
`release_claim`, `reclaim_abandoned_claim`) is exactly this encoding — claim
first, visible immediately, attest later.

WHAT IS MEASURED AND WHAT IS ASSUMED. The V0-vs-polite gap is a real effect of
the model: counting only completed work hides everyone mid-round, and the herd
follows. The V5-vs-V3 gap is NOT a discovery — it is assumed, by giving V3 one
extra hop of staleness for its separate intent message. That is polite-shrink's
own claim about why the AgentInfo encoding is preferable, faithfully modelled,
but a model of a claim is not evidence for it. Reported separately for that
reason.

THE STOPPING RULE IS PRE-REGISTERED, AND HAS TO BE. Recruiting until the
evidence looks acceptable is optional stopping — the same sin as lambda-shopping,
in a different costume, in an artefact built to expose it. So `is_resolved` keys
only on whether a block's coverage is unambiguous, never on which side it falls,
and this file is hashed into the record alongside `lambda_rule.py`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

import lambda_rule
from aggregate import BLOCK_CONSENSUS_THRESHOLD
from generate import SPEC, block_of, feature_names, generate
from party import bootstrap
from sweep import party_seed, spec_for

POOL = 15
INITIAL_COHORT = 3

# A block is RESOLVED when a Wilson interval on its coverage EXCLUDES the
# consensus threshold — in either direction. Direction-blind by construction:
# "clearly selected" and "clearly not selected" both stop recruitment, and the
# rule cannot tell which side it is on until it stops. A rule that stopped only
# on confirmation would be optional stopping.
#
# An earlier version used a fixed margin from the threshold and was degenerate:
# with three validators the only attainable coverages are 0, 1/3, 2/3 and 1, so
# almost everything sat "clear of" 0.8 and no recruitment ever happened. The
# fault was measuring DISTANCE from the threshold while ignoring how unreliable
# a three-sample estimate is. Wilson prices in the sample size, which is the
# whole point: three unanimous validators and eleven unanimous validators are
# not the same evidence.
#
# z = 1.0 (a one-standard-error band) rather than 1.96, deliberately echoing the
# 1-SE rule already pre-registered in lambda_rule.py. At this setting a clearly
# absent block resolves on the opening cohort of three, a unanimous block
# resolves at about five, and genuinely marginal blocks keep recruiting — which
# is the behaviour worth measuring.
WILSON_Z = 1.0

# Staleness, in candidate-decisions. V3 carries one extra hop for its separate
# intent message; V5 rides the existing channel. See the module docstring —
# this gap is modelled, not measured.
LAGS = (0, 1, 2, 4)
V3_EXTRA_HOP = 1

RECRUITMENT_POLICIES = ("V0", "V3", "V5")
FIXED_BASELINES = (3, 5, 7, 11)
BETAS = (1.0, 0.4, 0.2, 0.12, 0.0)


def impl_hash() -> str:
    """SHA-256 of this file — the stopping rule pinned as code, not prose."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def block_coverage(supports: list[list[str]]) -> dict[str, float]:
    """Fraction of the given validators selecting at least one member of each block."""
    blocks = sorted({b for b in (block_of(n) for n in feature_names()) if b})
    if not supports:
        return {b: 0.0 for b in blocks}
    counts = {b: 0 for b in blocks}
    for s in supports:
        hit = {block_of(n) for n in s}
        for b in blocks:
            if b in hit:
                counts[b] += 1
    return {b: counts[b] / len(supports) for b in blocks}


def wilson_interval(successes: int, n: int, z: float = WILSON_Z) -> tuple[float, float]:
    """Wilson score interval for a proportion. Well-behaved at small n and at 0/1."""
    if n == 0:
        return 0.0, 1.0
    p = successes / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z / denom) * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, centre - half), min(1.0, centre + half)


def is_resolved(supports: list[list[str]]) -> bool:
    """Every block's coverage interval excludes the threshold, either side."""
    if not supports:
        return False
    n = len(supports)
    for cov in block_coverage(supports).values():
        lo, hi = wilson_interval(round(cov * n), n)
        if lo <= BLOCK_CONSENSUS_THRESHOLD <= hi:
            return False
    return True


def run_pool(dataset_seed: int, target_beta: float, pool: int = POOL) -> dict:
    """Fit the whole candidate pool once; recruitment policies read prefixes of it."""
    spec = spec_for(dataset_seed, target_beta)
    X, y = generate(spec)
    names = feature_names(spec)

    supports = []
    for v in range(1, pool + 1):
        Xv, yv = bootstrap(X, y, party_seed(dataset_seed, v))
        idx, _alpha = lambda_rule.fit_support(Xv, yv)
        supports.append(sorted(names[i] for i in idx))
    return {"dataset_seed": dataset_seed, "target_beta": target_beta, "supports": supports}


def recruit(supports: list[list[str]], policy: str, lag: int) -> int:
    """Simulate adaptive recruitment; return how many validators were consumed.

    One pass over the remaining candidates is one wave. Within a wave each
    candidate decides from a view that is stale by `effective_lag` decisions —
    which is what allows several to join for the same thin block.
    """
    joined = list(range(min(INITIAL_COHORT, len(supports))))

    while True:
        current = [supports[i] for i in joined]
        if is_resolved(current) or len(joined) >= len(supports):
            return len(joined)

        candidates = [i for i in range(len(supports)) if i not in joined]
        wave_joiners: list[int] = []

        for position, cand in enumerate(candidates):
            if policy == "V0":
                # Only completed work is visible; nobody mid-round counts.
                visible = list(joined)
            else:
                effective_lag = lag + (V3_EXTRA_HOP if policy == "V3" else 0)
                cutoff = position - effective_lag
                visible = list(joined) + [
                    j for p, j in enumerate(wave_joiners[:cutoff]) if p < cutoff
                ]

            if not is_resolved([supports[i] for i in visible]):
                wave_joiners.append(cand)

        if not wave_joiners:
            return len(joined)
        joined.extend(wave_joiners)


def verdict_correct(supports: list[list[str]], target_beta: float) -> bool:
    """Did the cohort reach the right conclusion about the attacked block?

    Ground truth is known: at beta > 0 the block genuinely carries signal, so
    coverage at or above the threshold is correct; at beta = 0 it does not, so
    below is correct.
    """
    attacked = f"blk{SPEC.n_blocks - 1}"
    cov = block_coverage(supports).get(attacked, 0.0)
    above = cov >= BLOCK_CONSENSUS_THRESHOLD
    return above if target_beta > 0 else not above


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replications", type=int, default=60)
    parser.add_argument("--base-seed", type=int, default=660000)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "artifacts")
    args = parser.parse_args()

    seeds = [args.base_seed + i for i in range(args.replications)]
    total = len(seeds) * len(BETAS)

    pools = []
    done = 0
    for beta in BETAS:
        for seed in seeds:
            pools.append(run_pool(seed, beta))
            done += 1
            if done % 20 == 0 or done == total:
                print(f"  {done}/{total} pools fitted", flush=True)

    rows = []
    for p in pools:
        supports, beta = p["supports"], p["target_beta"]

        for k in FIXED_BASELINES:
            cohort = supports[:k]
            rows.append(
                {
                    "policy": f"fixed-{k}",
                    "lag": None,
                    "beta": beta,
                    "used": k,
                    "correct": verdict_correct(cohort, beta),
                    "resolved": is_resolved(cohort),
                }
            )

        for policy in RECRUITMENT_POLICIES:
            for lag in LAGS:
                used = recruit(supports, policy, lag)
                cohort = supports[:used]
                rows.append(
                    {
                        "policy": policy,
                        "lag": lag,
                        "beta": beta,
                        "used": used,
                        "correct": verdict_correct(cohort, beta),
                        "resolved": is_resolved(cohort),
                    }
                )

    def agg(subset: list[dict]) -> dict:
        n = len(subset)
        return {
            "n": n,
            "mean_used": sum(r["used"] for r in subset) / n,
            "accuracy": sum(r["correct"] for r in subset) / n,
            "resolved": sum(r["resolved"] for r in subset) / n,
        }

    result = {
        "stopping_rule_impl_hash": impl_hash(),
        "wilson_z": WILSON_Z,
        "consensus_threshold": BLOCK_CONSENSUS_THRESHOLD,
        "initial_cohort": INITIAL_COHORT,
        "pool": POOL,
        "fixed": {f"fixed-{k}": agg([r for r in rows if r["policy"] == f"fixed-{k}"]) for k in FIXED_BASELINES},
        "adaptive": {
            policy: {
                str(lag): agg([r for r in rows if r["policy"] == policy and r["lag"] == lag])
                for lag in LAGS
            }
            for policy in RECRUITMENT_POLICIES
        },
        "by_beta": {
            str(beta): {
                "fixed-5": agg([r for r in rows if r["policy"] == "fixed-5" and r["beta"] == beta]),
                "fixed-11": agg([r for r in rows if r["policy"] == "fixed-11" and r["beta"] == beta]),
                **{
                    p: agg([r for r in rows if r["policy"] == p and r["lag"] == 1 and r["beta"] == beta])
                    for p in RECRUITMENT_POLICIES
                },
            }
            for beta in BETAS
        },
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "recruit_results.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, default=float) + "\n"
    )

    print(f"\nAdaptive recruitment vs fixed cohorts")
    print(f"pool={POOL}, initial cohort={INITIAL_COHORT}, Wilson z={WILSON_Z}")
    print(f"stopping rule hash: {impl_hash()[:12]}…\n")

    print(f"  {'policy':<12}{'validators':>11}{'accuracy':>10}{'resolved':>10}")
    for k in FIXED_BASELINES:
        a = result["fixed"][f"fixed-{k}"]
        print(f"  {'fixed-' + str(k):<12}{a['mean_used']:>11.2f}{a['accuracy']:>9.0%}{a['resolved']:>10.0%}")

    print()
    for policy in RECRUITMENT_POLICIES:
        for lag in LAGS:
            a = result["adaptive"][policy][str(lag)]
            print(
                f"  {policy + ' lag=' + str(lag):<12}{a['mean_used']:>11.2f}"
                f"{a['accuracy']:>9.0%}{a['resolved']:>10.0%}"
            )

    print(f"\n  BY SIGNAL STRENGTH (adaptive policies at lag=1)")
    print(f"  {'beta':<7}{'fixed-5':>18}{'fixed-11':>18}{'V0':>18}{'V3':>18}{'V5':>18}")
    print(f"  {'':<7}" + "".join(f"{'used / acc':>18}" for _ in range(5)))
    for beta in BETAS:
        row = f"  {beta:<7.2f}"
        for key in ("fixed-5", "fixed-11", "V0", "V3", "V5"):
            a = result["by_beta"][str(beta)][key]
            row += f"{a['mean_used']:>11.1f} /{a['accuracy']:>5.0%}"
        print(row)

    print("\n  'validators' is the mean consumed — the cost. 'accuracy' is against")
    print("  known ground truth for the attacked block. 'resolved' is how often")
    print("  recruitment terminated on the stopping rule rather than the pool cap.")
    print("\n  V0-vs-polite is a measured effect. V5-vs-V3 is ASSUMED: V3 is given")
    print("  one extra hop of staleness for its separate intent message, which is")
    print("  polite-shrink's own claim modelled, not evidence for it.")


if __name__ == "__main__":
    main()
