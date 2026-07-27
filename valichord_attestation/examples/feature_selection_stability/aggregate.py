"""Step 5 — exact-match verdict, per-feature frequency, and per-block frequency.

Three readings of the same round, reported together and deliberately:

  1. Exact-match verdict — expected to FAIL, shown failing, with the reason.
     Under correlated blocks, honest independent parties pick different members
     of the same block, so an exact-match rule returns "not reproduced" every
     time and tells the reader nothing.

  2. Per-feature selection frequency — the informative result. A split between
     two members of one block IS the finding: it says the data cannot
     distinguish them.

  3. Per-block selection frequency — the discriminating statistic (plan §3.4).
     Without it, honest disagreement and the lambda-shopping attack are
     indistinguishable: both look like "the parties disagreed".

Framing discipline: validator disagreement here is the expected and correct
behaviour of the method. It must never be presented as ValiChord failing to
reproduce. Every divergence is attributed to correlated-block ambiguity
explicitly, before any summary line is written.
"""

from __future__ import annotations

import json
from pathlib import Path

from generate import block_of, feature_names

# The fraction of validators that must select SOME member of a block before the
# block counts as "the validators agree this block matters". Deliberately a
# parameter, not a constant of nature — see plan §6 on leaving the threshold
# unset for the same reason polite-shrink refuses to pick R.
BLOCK_CONSENSUS_THRESHOLD = 0.8


def validator_reveals(round_record: dict) -> list[dict]:
    return [r for r in round_record["reveals"] if r["party_id"] != "researcher"]


def researcher_reveal(round_record: dict) -> dict:
    for r in round_record["reveals"]:
        if r["party_id"] == "researcher":
            return r
    raise ValueError("round record has no researcher reveal")


def exact_match_verdict(reveals: list[dict]) -> dict:
    """Do all validators report byte-identical support sets?

    Expected to be False. Reported anyway, because showing the naive metric
    failing — and explaining why — is more useful than quietly not computing it.
    """
    supports = {r["party_id"]: frozenset(r["support"]) for r in reveals}
    distinct = set(supports.values())
    return {
        "reproduced": len(distinct) == 1,
        "n_distinct_supports": len(distinct),
        "n_parties": len(supports),
    }


def feature_frequency(reveals: list[dict]) -> dict[str, float]:
    """Fraction of validators selecting each feature. All 40 reported, including zeros."""
    n = len(reveals)
    counts = {name: 0 for name in feature_names()}
    for r in reveals:
        for name in r["support"]:
            counts[name] += 1
    return {name: counts[name] / n for name in counts}


def block_frequency(reveals: list[dict]) -> dict[str, float]:
    """Fraction of validators selecting AT LEAST ONE member of each block.

    This is what separates "the data cannot tell blk2_f0 from blk2_f2" (block
    frequency 5/5, split across members) from "this block was dropped".
    """
    n = len(reveals)
    blocks = sorted({b for b in (block_of(name) for name in feature_names()) if b})
    counts = {b: 0 for b in blocks}
    for r in reveals:
        hit = {block_of(name) for name in r["support"]}
        for b in blocks:
            if b in hit:
                counts[b] += 1
    return {b: counts[b] / n for b in blocks}


def flagged_blocks(
    validator_supports: list[list[str]],
    researcher_support: list[str],
    threshold: float = BLOCK_CONSENSUS_THRESHOLD,
) -> list[dict]:
    """The detector, as a pure function over support sets.

    THIS IS THE SINGLE DEFINITION of the lambda-shopping signature. Both the
    single-round report and the sweep call it. If the two ever computed the
    signature separately they would eventually disagree, and the sweep's
    detection rate would stop describing the thing the report demonstrates.

    The signature is not "the researcher disagreed" — that happens honestly all
    the time under correlated blocks. It is: the validators reach consensus that
    a block carries signal, and the researcher's published support contains NO
    member of that block. Dropping the block is what a penalty search buys you;
    dropping a particular member of it is not.

    Limits, stated here rather than in a footnote: this works because the block
    structure is known by construction. On real data the blocks are estimated,
    and a shopper who drops a feature the validators were also going to drop is
    indistinguishable from an honest party. Detectable, not undeniable.
    """
    freqs = block_frequency([{"support": s} for s in validator_supports])
    researcher_blocks = {block_of(name) for name in researcher_support}
    return [
        {"block": b, "validator_block_frequency": freq}
        for b, freq in sorted(freqs.items())
        if freq >= threshold and b not in researcher_blocks
    ]


def shopping_signature(
    round_record: dict, threshold: float = BLOCK_CONSENSUS_THRESHOLD
) -> dict:
    """Apply the detector to a round record. See `flagged_blocks`."""
    vals = validator_reveals(round_record)
    researcher = researcher_reveal(round_record)

    flagged = flagged_blocks(
        [r["support"] for r in vals], researcher["support"], threshold
    )
    return {
        "threshold": threshold,
        "flagged_blocks": flagged,
        "detected": bool(flagged),
    }


def analyse(round_record: dict) -> dict:
    vals = validator_reveals(round_record)
    researcher = researcher_reveal(round_record)
    freq = feature_frequency(vals)

    return {
        "protocol_hash": round_record["protocol_hash"],
        "n_validators": len(vals),
        "exact_match": exact_match_verdict(vals),
        "feature_frequency": freq,
        "block_frequency": block_frequency(vals),
        "researcher_support": researcher["support"],
        "researcher_alpha": researcher["derived_alpha"],
        "validator_alphas": {r["party_id"]: r["derived_alpha"] for r in vals},
        "shopping_signature": shopping_signature(round_record),
    }


def write_results(out_dir: Path) -> dict:
    round_record = json.loads((out_dir / "round.json").read_text())
    results = analyse(round_record)
    (out_dir / "results.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n"
    )
    return results


def format_report(results: dict) -> str:
    lines = []
    n = results["n_validators"]

    em = results["exact_match"]
    lines.append("1. EXACT-MATCH VERDICT (the naive metric)")
    lines.append(f"   reproduced: {em['reproduced']}   "
                 f"({em['n_distinct_supports']} distinct supports across {em['n_parties']} validators)")
    lines.append("   Expected. Under rho=0.95 blocks, honest parties pick different")
    lines.append("   members of the same block. This metric cannot tell that apart from")
    lines.append("   genuine disagreement, which is why it is not the verdict.")

    lines.append("\n2. PER-FEATURE SELECTION FREQUENCY (the informative result)")
    freq = results["feature_frequency"]
    selected = {k: v for k, v in freq.items() if v > 0}
    for name in sorted(selected, key=lambda k: (-selected[k], k)):
        bar = "#" * int(round(selected[name] * n))
        lines.append(f"   {name:<10} {int(round(selected[name] * n))}/{n}  {bar}")
    unselected = len(freq) - len(selected)
    lines.append(f"   ({unselected} of {len(freq)} features never selected)")

    lines.append("\n3. PER-BLOCK SELECTION FREQUENCY (the discriminating statistic)")
    for b, v in sorted(results["block_frequency"].items()):
        members = {k: freq[k] for k in freq if k.startswith(b) and freq[k] > 0}
        split = ", ".join(
            f"{k}={int(round(members[k] * n))}/{n}" for k in sorted(members)
        )
        lines.append(f"   {b}: {int(round(v * n))}/{n} of validators   [{split}]")
    lines.append("   A block at 5/5 whose members split is the data saying it cannot")
    lines.append("   distinguish them. That split is the finding, not a failure.")

    sig = results["shopping_signature"]
    lines.append("\n4. LAMBDA-SHOPPING SIGNATURE")
    if sig["detected"]:
        for f in sig["flagged_blocks"]:
            lines.append(
                f"   FLAGGED {f['block']}: validators select it at "
                f"{f['validator_block_frequency']:.0%}, researcher dropped it entirely"
            )
    else:
        lines.append(f"   none — no block above the {sig['threshold']:.0%} consensus")
        lines.append("   threshold is absent from the researcher's support.")

    return "\n".join(lines)


def main() -> None:
    out_dir = Path(__file__).parent / "artifacts"
    results = write_results(out_dir)
    print(format_report(results))


if __name__ == "__main__":
    main()
