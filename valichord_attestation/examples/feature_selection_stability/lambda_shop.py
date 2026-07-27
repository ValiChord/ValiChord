"""Step 6 — the adversarial exhibit: lambda-shopping, and what catches it.

The attack: a researcher who wants a particular block of features absent from
their model does not have to fabricate anything. They search the penalty until
those coefficients hit exactly zero, then publish the resulting model. Every
number in the published artefact is true. Nothing in it reveals how many values
of lambda were tried, or that the final one was chosen for what it excluded.

Two halves, and the exhibit is worthless without both:

  (a) The published artefact is IDENTICAL IN FORM to an honest one. Same
      estimator, same data, same support-definition, a perfectly ordinary
      penalty value. Self-policing record-keeping does not help unless the
      recorder chose to record every attempt — and the attacker is the recorder.

  (b) The protocol CATCHES it, because the validators derived their own lambdas
      from their own resamples and never saw the researcher's. The block the
      researcher dropped is one the validators agree carries signal.

The honest limit is exhibited too: shopping WITHIN a block — dropping one member
of a correlated pair — is not flagged, and cannot be, because honest parties do
that all the time. See plan §6.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import aggregate
from generate import block_of, feature_names
from lambda_rule import fit_support_at_alpha
from party import RESEARCHER_SEED, Commitment, Reveal, bootstrap, derive_nonce, seal

# The block to make disappear. blk2 carries the weakest true signal
# (coefficient 1.0), so it is the cheapest one to shop away — which is exactly
# why an attacker would pick it.
TARGET_BLOCK = "blk2"

# Search grid for the attack. Ascending: the attacker takes the SMALLEST penalty
# that achieves the goal, because a conspicuously large one invites questions.
SHOP_GRID = np.linspace(0.05, 3.0, 400)


def shop_for_alpha(
    X: np.ndarray, y: np.ndarray, names: list[str], target_block: str
) -> tuple[float, list[str]]:
    """Search lambda upward until no member of `target_block` survives.

    Returns (alpha, support). Raises if the grid is exhausted.
    """
    for alpha in SHOP_GRID:
        support_idx = fit_support_at_alpha(X, y, float(alpha))
        support = [names[i] for i in support_idx]
        if not any(block_of(n) == target_block for n in support):
            return float(alpha), sorted(support)
    raise RuntimeError(f"grid exhausted without dropping {target_block}")


def shop_within_block(
    X: np.ndarray, y: np.ndarray, names: list[str], target_feature: str
) -> tuple[float, list[str]]:
    """Search lambda until one specific feature drops, without killing its block.

    This is the attack the protocol CANNOT distinguish from honesty.

    Note the attacker is not omnipotent here: raising the penalty removes
    features in order of weakness, so only a comparatively weak member can be
    shopped away while its block survives. Targeting the STRONGEST member of a
    block exhausts the grid — by the time the penalty is high enough to remove
    it, every weaker member has already gone and the whole block is absent,
    which is the case part (b) catches.
    """
    target_block = block_of(target_feature)
    for alpha in SHOP_GRID:
        support_idx = fit_support_at_alpha(X, y, float(alpha))
        support = [names[i] for i in support_idx]
        if target_feature not in support and any(
            block_of(n) == target_block for n in support
        ):
            return float(alpha), sorted(support)
    raise RuntimeError(f"grid exhausted without dropping {target_feature}")


def substitute_researcher(round_record: dict, alpha: float, support: list[str]) -> dict:
    """Rebuild the round with a shopped researcher and the same honest validators.

    The validators are untouched: their commitments and reveals are exactly the
    ones from the honest round. That is the point — the attacker cannot reach
    them, and does not know what they will say.
    """
    shopped = dict(round_record)
    nonce = derive_nonce(RESEARCHER_SEED)

    shopped["reveals"] = [
        Reveal(
            party_id="researcher",
            support=support,
            nonce=nonce.hex(),
            derived_alpha=alpha,
            resample_seed=RESEARCHER_SEED,
        ).to_dict()
        if r["party_id"] == "researcher"
        else r
        for r in round_record["reveals"]
    ]
    shopped["commitments"] = [
        Commitment(party_id="researcher", commitment_hash=seal(support, nonce)).to_dict()
        if c["party_id"] == "researcher"
        else c
        for c in round_record["commitments"]
    ]
    return shopped


def model_card(label: str, alpha: float, support: list[str]) -> dict:
    """The artefact a reader of the published model would actually see.

    Deliberately the fields a model card or a model-risk submission carries. The
    honest and shopped versions differ only in the penalty value and the feature
    list — and neither difference is legible as misconduct to someone holding
    just one of them.
    """
    return {
        "model": label,
        "estimator": "sklearn.linear_model.Lasso",
        "penalty_alpha": round(alpha, 6),
        "n_features_selected": len(support),
        "features_used": support,
        "postcode_analogue_used": any(block_of(n) == TARGET_BLOCK for n in support),
    }


def main() -> None:
    out_dir = Path(__file__).parent / "artifacts"
    round_record = json.loads((out_dir / "round.json").read_text())
    data = np.load(out_dir / "dataset.npz")
    names = feature_names()

    honest = aggregate.researcher_reveal(round_record)
    Xb, yb = bootstrap(data["X"], data["y"], RESEARCHER_SEED)

    alpha, support = shop_for_alpha(Xb, yb, names, TARGET_BLOCK)

    print("(a) THE PUBLISHED ARTEFACT — the two a reader could be handed\n")
    honest_card = model_card("honest", honest["derived_alpha"], honest["support"])
    shopped_card = model_card("shopped", alpha, support)
    for card in (honest_card, shopped_card):
        print(f"  {card['model']}:")
        for k in ("estimator", "penalty_alpha", "n_features_selected", "postcode_analogue_used"):
            print(f"    {k}: {card[k]}")
        print()
    print("  Both are true. Neither records how many alphas were tried. The shopped")
    print(f"  penalty ({alpha:.4f}) is an unremarkable number; nothing marks it as chosen")
    print(f"  because it was the smallest one that removed {TARGET_BLOCK}.\n")

    print("(b) WHAT THE PROTOCOL SEES\n")
    shopped_round = substitute_researcher(round_record, alpha, support)
    (out_dir / "round_shopped.json").write_text(
        json.dumps(shopped_round, indent=2, sort_keys=True) + "\n"
    )

    for label, record in (("honest round", round_record), ("shopped round", shopped_round)):
        sig = aggregate.shopping_signature(record)
        verdict = "FLAGGED" if sig["detected"] else "clean"
        detail = ", ".join(
            f"{f['block']} at {f['validator_block_frequency']:.0%} validator consensus"
            for f in sig["flagged_blocks"]
        )
        print(f"  {label:<15} {verdict}{'  — ' + detail if detail else ''}")

    print("\n(c) THE HONEST LIMIT — shopping WITHIN a block\n")
    within_alpha, within_support = shop_within_block(Xb, yb, names, "blk2_f2")
    within_round = substitute_researcher(round_record, within_alpha, within_support)
    within_sig = aggregate.shopping_signature(within_round)
    print(f"  dropped blk2_f2 at alpha={within_alpha:.4f}, kept the block via "
          f"{[n for n in within_support if block_of(n) == TARGET_BLOCK]}")
    print(f"  protocol verdict: {'FLAGGED' if within_sig['detected'] else 'clean'}")
    print("  Clean, and correctly so. Honest parties substitute within a correlated")
    print("  block constantly. The protocol detects a dropped BLOCK, not a dropped")
    print("  FEATURE — detectable, not undeniable. Say this in the write-up.")


if __name__ == "__main__":
    main()
