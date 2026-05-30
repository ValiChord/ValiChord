"""Outcome and agreement-level derivation for the public demo.

SINGLE SOURCE OF TRUTH. Mirrors the authoritative on-chain Rust logic in
valichord/shared_types/src/lib.rs (`derive_majority_outcome` +
`derive_agreement_level`). The HarmonyRecord written to the DHT remains
authoritative; these functions reproduce its computation from the same
validator verdicts so the demo's *displayed* outcome / agreement_level match
the on-chain record — and each other.

Why this module exists: the agreement level used to be computed in three
different places, inconsistently:
  - the custom ("Your Hypothesis") path took it from a free-form Claude
    adjudication call, decoupled from the validator verdicts — so the page
    could show "3/3 Reproduced" beside an "WithinTolerance" label;
  - the free paths keyed ExactMatch off any_rate (Reproduced + Partial) instead
    of full_rate (Reproduced only) — the inverse error.
Both are fixed by routing every path through the functions below.

Agreement-level thresholds (must stay in lockstep with the Rust source):
    full_rate >= 0.90 -> ExactMatch       (full_rate = Reproduced / total)
    any_rate  >= 0.70 -> WithinTolerance  (any_rate  = (Reproduced + Partial) / total)
    any_rate  >= 0.50 -> DirectionalMatch
    any_rate  >  0     -> Divergent
    any_rate  == 0     -> UnableToAssess
ExactMatch keys off full_rate, never any_rate: an all-PartiallyReproduced panel
is WithinTolerance at best, and an all-Reproduced panel is ExactMatch.
"""

# Different demo paths emit different strings for the "did not reproduce"
# outcome — the claim path uses "NotReproduced", the computational paths use
# "FailedToReproduce". Both normalise to the same bucket and neither counts
# toward agreement; the on-chain enum is FailedToReproduce.
_FAILED = {"FailedToReproduce", "NotReproduced"}


def _counts(outcomes):
    """(reproduced, partial, failed, unable) over a list of outcome strings."""
    reproduced = sum(1 for o in outcomes if o == "Reproduced")
    partial    = sum(1 for o in outcomes if o == "PartiallyReproduced")
    failed     = sum(1 for o in outcomes if o in _FAILED)
    unable     = len(outcomes) - reproduced - partial - failed
    return reproduced, partial, failed, unable


def derive_agreement_level(outcomes):
    """Mirror shared_types::derive_agreement_level."""
    if not outcomes:
        return "UnableToAssess"
    total = len(outcomes)
    reproduced, partial, _, _ = _counts(outcomes)
    full_rate = reproduced / total
    any_rate  = (reproduced + partial) / total
    if full_rate >= 0.90:
        return "ExactMatch"
    if any_rate >= 0.70:
        return "WithinTolerance"
    if any_rate >= 0.50:
        return "DirectionalMatch"
    if (reproduced + partial) > 0:
        return "Divergent"
    return "UnableToAssess"


def derive_majority_outcome(outcomes):
    """Mirror shared_types::derive_majority_outcome — plurality vote, tie
    precedence Reproduced > PartiallyReproduced > FailedToReproduce > UnableToAssess.
    Returns the on-chain-canonical outcome string."""
    if not outcomes:
        return "UnableToAssess"
    reproduced, partial, failed, unable = _counts(outcomes)
    top = max(reproduced, partial, failed, unable)
    if reproduced == top:
        return "Reproduced"
    if partial == top:
        return "PartiallyReproduced"
    if failed == top:
        return "FailedToReproduce"
    return "UnableToAssess"
