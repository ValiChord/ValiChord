"""Sweep — turn the single round into a measurement.

The single-round demonstration (round.py / aggregate.py / lambda_shop.py) shows
a mechanism working ONCE, on one dataset, with one seed. That is an anecdote.
Every number in it could be luck of the draw.

This runs the whole thing many times, over independent datasets, and reports
distributions instead of instances. Three numbers come out of it that the single
round cannot produce:

  DETECTION RATE   — how often a lambda-shopped researcher is actually caught.
  FALSE-ALARM RATE — how often an HONEST researcher is flagged. This is the
                     number a model-risk reviewer asks for first, and the single
                     round has no answer to it whatsoever.
  OPERATING CURVE  — both of the above across the consensus threshold, so
                     "we chose 0.8" becomes "here is what any choice costs you".

It also varies the number of validators over 3 / 5 / 7 / 11 — deliberately
ValiChord's Bronze / Silver / Gold badge thresholds — so the question "what does
a Gold badge actually buy over a Bronze one?" has a measured answer in at least
one domain.

Efficiency note: validators are exchangeable (each draws an independent
resample), so for a given dataset the first k of a pool of 11 IS a valid sample
of k validators. Fitting the pool once and reading prefixes off it is
statistically sound and about four times cheaper than refitting per k.

Attribution discipline: a flagged HONEST round is not evidence the protocol is
broken. It usually means the honest researcher's own fit dropped a whole block —
the one-standard-error rule misbehaving under an unlucky resample, which is the
instability the single round already surfaced. Every false alarm is recorded
with the researcher's alpha and support size so the cause can be attributed
rather than assumed. See `attribute_false_alarms`.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from aggregate import flagged_blocks
from generate import SPEC, block_of, dataset_hash, feature_names, generate
from lambda_rule import fit_support
from lambda_shop import TARGET_BLOCK, shop_for_alpha
from party import bootstrap

VALIDATOR_COUNTS = (3, 5, 7, 11)
VALIDATOR_POOL = max(VALIDATOR_COUNTS)
THRESHOLDS = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0)

# Reported as the headline operating point, matching aggregate.py's default.
HEADLINE_THRESHOLD = 0.8

# Signal strength of the ATTACKED block, swept.
#
# This dimension exists because without it the sweep reports a ceiling and calls
# it a result. At the demonstration's own setting (1.0) every validator recovers
# the block, so removing it is always conspicuous and detection is 100% at every
# threshold and every validator count — true, but it measures the easy case and
# says nothing about where the method stops working.
#
# Weakening the attacked block is what produces a real trade-off: validators
# start missing it honestly, so the consensus that powers the detector erodes,
# and honest researchers start dropping it themselves, which is what generates
# false alarms. The interesting claim is not "we catch it" but "here is the
# signal strength below which we stop catching it".
# The grid spans ceiling -> transition -> floor. Probed empirically: a single
# validator recovers the attacked block ~100% of the time at beta >= 0.4, ~90% at
# 0.2, ~50% at 0.12, ~10% at 0.05, and ~13% at beta = 0 purely by chance.
#
# READ THE beta = 0 ROW DIFFERENTLY. There, the attacked block carries no signal
# at all, so a researcher who removes it is doing something entirely legitimate.
# A flag in that row is not a detection, it is a FALSE ACCUSATION, and low is
# good. The column heading cannot be right for both rows, so the report has to
# say which it means.
TARGET_BETAS = (1.0, 0.4, 0.2, 0.12, 0.08, 0.05, 0.0)


def party_seed(dataset_seed: int, index: int) -> int:
    """Distinct resample seed per party per replication.

    Index 0 is the researcher; 1..n are validators. Offsetting by the dataset
    seed keeps every replication's resamples independent of every other's.
    """
    return dataset_seed * 100 + index


def spec_for(dataset_seed: int, target_beta: float):
    """Dataset spec with a given seed and a given signal strength on the attacked block."""
    coefficients = list(SPEC.signal_coefficients)
    coefficients[-1] = target_beta  # blk2 is the attacked block
    return replace(SPEC, seed=dataset_seed, signal_coefficients=tuple(coefficients))


def run_replication(
    dataset_seed: int, target_beta: float, pool: int = VALIDATOR_POOL
) -> dict:
    """One complete replication: fresh dataset, honest round, and a shopped researcher."""
    spec = spec_for(dataset_seed, target_beta)
    X, y = generate(spec)
    names = feature_names(spec)

    Xr, yr = bootstrap(X, y, party_seed(dataset_seed, 0))
    honest_idx, honest_alpha = fit_support(Xr, yr)
    honest_support = sorted(names[i] for i in honest_idx)

    validators = []
    for v in range(1, pool + 1):
        Xv, yv = bootstrap(X, y, party_seed(dataset_seed, v))
        idx, alpha = fit_support(Xv, yv)
        validators.append(
            {"support": sorted(names[i] for i in idx), "alpha": alpha}
        )

    try:
        shopped_alpha, shopped_support = shop_for_alpha(Xr, yr, names, TARGET_BLOCK)
        shop_failed = False
    except RuntimeError:
        # The attacker could not remove the block within the search grid. Recorded
        # rather than dropped: a replication where the attack is IMPOSSIBLE is not
        # the same as one where it succeeded and went unnoticed, and silently
        # discarding these would inflate the detection rate.
        shopped_alpha, shopped_support, shop_failed = float("nan"), [], True

    return {
        "dataset_seed": dataset_seed,
        "target_beta": target_beta,
        "dataset_hash": dataset_hash(X, y),
        "honest": {"support": honest_support, "alpha": honest_alpha},
        "shopped": {
            "support": shopped_support,
            "alpha": shopped_alpha,
            "attack_infeasible": shop_failed,
        },
        "validators": validators,
    }


def evaluate(rep: dict, k: int, threshold: float) -> dict:
    """Apply the detector to one replication at k validators and one threshold."""
    supports = [v["support"] for v in rep["validators"][:k]]

    honest_flags = flagged_blocks(supports, rep["honest"]["support"], threshold)
    result = {"honest_flagged": bool(honest_flags)}

    if rep["shopped"]["attack_infeasible"]:
        result["shopped_flagged"] = None  # not counted either way
    else:
        shopped_flags = flagged_blocks(supports, rep["shopped"]["support"], threshold)
        result["shopped_flagged"] = bool(shopped_flags)

    return result


def effective_count_threshold(k: int, threshold: float) -> int:
    """The consensus threshold expressed in validators, not fraction.

    This matters more than it looks. A fixed FRACTION becomes a different bar at
    each validator count once you round: at 0.8, k=3 demands 3 of 3 (100%) while
    k=5 demands 4 of 5 (80%). Comparing detection across k without showing this
    invites the reader to conclude that more validators hurt, when what actually
    varies is how harsh the rounding was. Printed alongside every k for that
    reason.
    """
    return -(-int(round(threshold * k * 1000)) // 1000)  # ceil without float drift


def target_recovery_rate(reps: list[dict], k: int) -> float:
    """How often a validator recovers the attacked block at all.

    This is the explanatory variable behind the whole sweep: the detector is
    powered by validator consensus, so as this falls, detection must fall too.
    Reporting it alongside the rates stops the decline looking mysterious.
    """
    hits = total = 0
    for rep in reps:
        for v in rep["validators"][:k]:
            total += 1
            if any(block_of(n) == TARGET_BLOCK for n in v["support"]):
                hits += 1
    return hits / total if total else 0.0


def summarise(reps: list[dict]) -> dict:
    """Detection and false-alarm rates for every (beta, k, threshold) cell."""
    cells = []
    for beta in TARGET_BETAS:
        subset = [r for r in reps if r["target_beta"] == beta]
        if not subset:
            continue
        for k in VALIDATOR_COUNTS:
            recovery = target_recovery_rate(subset, k)
            for threshold in THRESHOLDS:
                evals = [evaluate(r, k, threshold) for r in subset]

                false_alarms = [e["honest_flagged"] for e in evals]
                detections = [
                    e["shopped_flagged"] for e in evals if e["shopped_flagged"] is not None
                ]

                cells.append(
                    {
                        "target_beta": beta,
                        "n_validators": k,
                        "threshold": threshold,
                        "n_replications": len(evals),
                        "target_block_recovery_rate": recovery,
                        "false_alarm_rate": sum(false_alarms) / len(false_alarms),
                        "detection_rate": (
                            sum(detections) / len(detections) if detections else None
                        ),
                        "n_attack_feasible": len(detections),
                    }
                )
    return {"cells": cells}


def attribute_false_alarms(reps: list[dict], k: int, threshold: float) -> dict:
    """Explain the honest rounds that got flagged, rather than assuming a cause.

    A false alarm means the honest researcher's published support contained no
    member of a block the validators agreed on. The candidate explanations are
    distinguishable from what we already record:

      * the researcher's alpha was high relative to the validators' — the 1-SE
        rule landing on an over-sparse fit for that resample, which is the rule
        misbehaving, not the protocol.
      * the researcher's alpha was ordinary and they simply lost a weak block on
        an unlucky resample — genuine sampling variation.

    Reporting the alpha ratio lets a reader tell which, instead of taking either
    on trust.
    """
    flagged = []
    for rep in reps:
        supports = [v["support"] for v in rep["validators"][:k]]
        hits = flagged_blocks(supports, rep["honest"]["support"], threshold)
        if not hits:
            continue
        val_alphas = [v["alpha"] for v in rep["validators"][:k]]
        median_alpha = float(np.median(val_alphas))
        flagged.append(
            {
                "dataset_seed": rep["dataset_seed"],
                "blocks": [h["block"] for h in hits],
                "researcher_alpha": rep["honest"]["alpha"],
                "median_validator_alpha": median_alpha,
                "alpha_ratio": rep["honest"]["alpha"] / median_alpha,
                "researcher_n_selected": len(rep["honest"]["support"]),
            }
        )

    over_sparse = [f for f in flagged if f["alpha_ratio"] > 1.5]
    return {
        "n_false_alarms": len(flagged),
        "n_attributable_to_over_sparse_researcher_fit": len(over_sparse),
        "detail": flagged,
    }


def block_split_profile(reps: list[dict], k: int) -> dict:
    """How often the true signal wins its block outright, across replications.

    The single round found all three true signals at 5/5, with the correlated
    partners a secondary effect. That was one draw. This says whether it holds.
    """
    names = feature_names()
    true_signals = {f"blk{b}": f"blk{b}_f0" for b in range(SPEC.n_blocks)}

    profile = {}
    for block, signal in true_signals.items():
        members = [n for n in names if block_of(n) == block]
        counts = {m: 0 for m in members}
        total = 0
        for rep in reps:
            for v in rep["validators"][:k]:
                total += 1
                for m in members:
                    if m in v["support"]:
                        counts[m] += 1
        profile[block] = {
            "true_signal": signal,
            "selection_rate": {m: counts[m] / total for m in members},
        }
    return profile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replications", type=int, default=200)
    parser.add_argument("--base-seed", type=int, default=770000)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "artifacts")
    args = parser.parse_args()

    seeds = [args.base_seed + i for i in range(args.replications)]
    total_runs = len(seeds) * len(TARGET_BETAS)

    reps = []
    done = 0
    for beta in TARGET_BETAS:
        for seed in seeds:
            reps.append(run_replication(seed, beta))
            done += 1
            if done % 25 == 0 or done == total_runs:
                print(f"  {done}/{total_runs} replications", flush=True)

    summary = summarise(reps)

    def cell(beta: float, k: int, threshold: float) -> dict:
        return next(
            c for c in summary["cells"]
            if c["target_beta"] == beta
            and c["n_validators"] == k
            and c["threshold"] == threshold
        )

    # Focus betas are chosen from the data, not fixed in advance. Picking the
    # minimum beta (as an earlier version did) lands on the row where the
    # attacked block carries no signal — everything is zero there and both the
    # curve and the attribution report nothing.
    #
    # The operating curve wants the transition: where detection is nearest 50%,
    # so the threshold trade-off is actually visible.
    live_betas = [b for b in TARGET_BETAS if b > 0]
    curve_beta = min(
        live_betas,
        key=lambda b: abs((cell(b, 5, HEADLINE_THRESHOLD)["detection_rate"] or 0) - 0.5),
    )
    # Attribution wants wherever false alarms are most common — there is nothing
    # to attribute where the rate is zero.
    attribution_beta = max(
        TARGET_BETAS, key=lambda b: cell(b, 5, HEADLINE_THRESHOLD)["false_alarm_rate"]
    )
    attribution_reps = [r for r in reps if r["target_beta"] == attribution_beta]
    attribution = attribute_false_alarms(attribution_reps, k=5, threshold=HEADLINE_THRESHOLD)

    strongest = max(TARGET_BETAS)
    splits = block_split_profile(
        [r for r in reps if r["target_beta"] == strongest], k=5
    )

    infeasible = sum(1 for r in reps if r["shopped"]["attack_infeasible"])

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "sweep_results.json").write_text(
        json.dumps(
            {
                "n_replications_per_cell": len(seeds),
                "target_betas": list(TARGET_BETAS),
                "validator_counts": list(VALIDATOR_COUNTS),
                "thresholds": list(THRESHOLDS),
                "headline_threshold": HEADLINE_THRESHOLD,
                "n_attack_infeasible": infeasible,
                "summary": summary,
                "false_alarm_attribution": {
                    "target_beta": attribution_beta,
                    "n_validators": 5,
                    **attribution,
                },
                "operating_curve_target_beta": curve_beta,
                "effective_count_thresholds": {
                    str(k): effective_count_threshold(k, HEADLINE_THRESHOLD)
                    for k in VALIDATOR_COUNTS
                },
                "block_split_profile": {"target_beta": strongest, "blocks": splits},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    # Raw rounds, so the reporting above can be reworked without a refit.
    (args.out / "sweep_replications.json").write_text(
        json.dumps(reps, indent=2, sort_keys=True) + "\n"
    )

    print(
        f"\n{len(seeds)} replications per cell x {len(TARGET_BETAS)} signal strengths "
        f"= {len(reps)} rounds, {VALIDATOR_POOL}-validator pool"
    )
    if infeasible:
        print(
            f"attack infeasible in {infeasible} round(s) — excluded from the detection "
            "rate, counted nowhere else"
        )

    print(f"\nDETECTION / FALSE ALARM at threshold {HEADLINE_THRESHOLD}")
    print("  Signal strength of the ATTACKED block down the side; validator count across.")
    print("  Each cell is: detection% / false-alarm%\n")
    header = "  " + "beta".ljust(7) + "recovery".rjust(9) + "".join(
        f"{f'k={k} ({effective_count_threshold(k, HEADLINE_THRESHOLD)}/{k})':>14}"
        for k in VALIDATOR_COUNTS
    )
    print(header)
    for beta in TARGET_BETAS:
        cells = [
            c for c in summary["cells"]
            if c["target_beta"] == beta and c["threshold"] == HEADLINE_THRESHOLD
        ]
        if not cells:
            continue
        recovery = cells[0]["target_block_recovery_rate"]
        row = f"  {beta:<7.2f}{recovery:>8.0%} "
        for k in VALIDATOR_COUNTS:
            c = next(x for x in cells if x["n_validators"] == k)
            det = "n/a" if c["detection_rate"] is None else f"{c['detection_rate']:.0%}"
            row += f"{det + ' / ' + format(c['false_alarm_rate'], '.0%'):>14}"
        print(row)
    print("\n  'recovery' = how often a single validator recovers the attacked block at")
    print("  all. It is the quantity that drives everything else: the detector runs on")
    print("  validator consensus, so when consensus goes, detection goes with it.")
    print("\n  The beta=0.00 row reads differently: there the attacked block carries no")
    print("  signal, so removing it is legitimate. A flag there is a FALSE ACCUSATION,")
    print("  not a detection, and low is good.")
    print("\n  DO NOT read the k columns as 'more validators help/hurt'. The bracket is")
    print("  the threshold in validators, and rounding makes it uneven: k=3 must be")
    print("  UNANIMOUS while k=5 needs only 4 of 5. Any non-monotonic wobble across k")
    print("  is that rounding, not a property of validator count. Comparing counts")
    print("  fairly needs a count-based rule, which this sweep does not implement.")

    print(f"\nOPERATING CURVE by threshold (attacked-block beta = {curve_beta}, the transition)")
    header = "  " + "threshold".ljust(11) + "".join(f"{f'k={k}':>14}" for k in VALIDATOR_COUNTS)
    print(header)
    for threshold in THRESHOLDS:
        row = f"  {threshold:<11.1f}"
        for k in VALIDATOR_COUNTS:
            c = next(
                x for x in summary["cells"]
                if x["target_beta"] == curve_beta
                and x["n_validators"] == k
                and x["threshold"] == threshold
            )
            det = "n/a" if c["detection_rate"] is None else f"{c['detection_rate']:.0%}"
            row += f"{det + ' / ' + format(c['false_alarm_rate'], '.0%'):>14}"
        print(row)

    print(f"\nFALSE-ALARM ATTRIBUTION (beta={attribution_beta}, k=5, threshold {HEADLINE_THRESHOLD})")
    print(f"  false alarms: {attribution['n_false_alarms']} of {len(attribution_reps)}")
    print(
        f"  of which the researcher's alpha exceeded the validator median by >1.5x: "
        f"{attribution['n_attributable_to_over_sparse_researcher_fit']}"
    )
    print("  (a high ratio means the 1-SE rule returned an over-sparse fit for that")
    print("   resample — the rule misbehaving, not the protocol failing)")

    print(f"\nBLOCK SPLIT PROFILE (beta={strongest}, k=5, pooled)")
    for block, prof in sorted(splits.items()):
        rates = prof["selection_rate"]
        parts = ", ".join(f"{m.split('_')[1]}={rates[m]:.0%}" for m in sorted(rates))
        print(f"  {block} (true signal {prof['true_signal'].split('_')[1]}): {parts}")


if __name__ == "__main__":
    main()
