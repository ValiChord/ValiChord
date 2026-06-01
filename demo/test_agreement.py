"""Unit tests for demo/agreement.py — the single source of truth for the demo's
outcome + agreement-level display.

These mirror the Rust unit tests for shared_types::derive_agreement_level /
derive_majority_outcome so the demo display can never drift from the authoritative
on-chain HarmonyRecord. Pure functions — run instantly, no conductor:

    python3 demo/test_agreement.py
"""
from agreement import derive_agreement_level, derive_majority_outcome


def check(label, got, want):
    status = "ok" if got == want else "FAIL"
    print(f"  [{status}] {label}: got {got!r}, want {want!r}")
    assert got == want, f"{label}: {got!r} != {want!r}"


def test_agreement_level():
    # The reported bug: 3/3 Reproduced must be ExactMatch, never WithinTolerance.
    check("3x Reproduced",            derive_agreement_level(["Reproduced"] * 3), "ExactMatch")
    # 2 Reproduced + 1 Partial: full_rate 0.67 (<0.90), any_rate 1.0 → WithinTolerance.
    check("2 Reproduced + 1 Partial", derive_agreement_level(["Reproduced", "Reproduced", "PartiallyReproduced"]), "WithinTolerance")
    # All partial: any_rate 1.0 but full_rate 0 → WithinTolerance, NOT ExactMatch.
    check("3x Partial",               derive_agreement_level(["PartiallyReproduced"] * 3), "WithinTolerance")
    # 9 Reproduced + 1 Failed: full_rate 0.90 → ExactMatch (matches Rust test).
    check("9 Reproduced + 1 Failed",  derive_agreement_level(["Reproduced"] * 9 + ["FailedToReproduce"]), "ExactMatch")
    # 7 Reproduced + 3 Failed: full 0.70 (<0.90), any 0.70 → WithinTolerance (matches Rust test).
    check("7 Reproduced + 3 Failed",  derive_agreement_level(["Reproduced"] * 7 + ["FailedToReproduce"] * 3), "WithinTolerance")
    # any_rate 2/3 = 0.667 → DirectionalMatch.
    check("1R 1P 1F",                 derive_agreement_level(["Reproduced", "PartiallyReproduced", "FailedToReproduce"]), "DirectionalMatch")
    # any_rate 1/3 = 0.333 (>0) → Divergent.
    check("1 Reproduced + 2 Failed",  derive_agreement_level(["Reproduced", "FailedToReproduce", "FailedToReproduce"]), "Divergent")
    # No successes → UnableToAssess. "NotReproduced" must count as failed (claim-path vocab).
    check("3x NotReproduced",         derive_agreement_level(["NotReproduced"] * 3), "UnableToAssess")
    check("empty",                    derive_agreement_level([]), "UnableToAssess")


def test_majority_outcome():
    check("3x Reproduced",            derive_majority_outcome(["Reproduced"] * 3), "Reproduced")
    check("2 Reproduced + 1 Partial", derive_majority_outcome(["Reproduced", "Reproduced", "PartiallyReproduced"]), "Reproduced")
    check("3x Partial",               derive_majority_outcome(["PartiallyReproduced"] * 3), "PartiallyReproduced")
    check("3x NotReproduced→Failed",  derive_majority_outcome(["NotReproduced"] * 3), "FailedToReproduce")
    # Tie Reproduced/Partial/Failed at 1 each → Reproduced wins (Rust tie precedence).
    check("tie 1R 1P 1F",             derive_majority_outcome(["Reproduced", "PartiallyReproduced", "FailedToReproduce"]), "Reproduced")
    check("2 Failed + 1 Reproduced",  derive_majority_outcome(["FailedToReproduce", "FailedToReproduce", "Reproduced"]), "FailedToReproduce")


import json
import os
from pathlib import Path


def repo_root() -> Path:
    """Locate the repo root (the dir containing valichord/shared_types) so the
    shared golden fixture resolves from any layout. Fails loudly — never a silent
    skip. Override with VALICHORD_REPO_ROOT."""
    env = os.environ.get("VALICHORD_REPO_ROOT")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "valichord" / "shared_types").is_dir():
            return parent
    raise RuntimeError(
        "repo root not found above test_agreement.py (no valichord/shared_types); "
        "set VALICHORD_REPO_ROOT"
    )


def test_golden_vectors_match_python_derivation():
    fixture = repo_root() / "valichord" / "shared_types" / "tests" / "agreement_golden.json"
    vectors = json.loads(fixture.read_text())
    assert len(vectors) >= 7
    for v in vectors:
        assert derive_agreement_level(v["outcomes"]) == v["agreement_level"], v
        assert derive_majority_outcome(v["outcomes"]) == v["majority_outcome"], v


if __name__ == "__main__":
    print("test_agreement_level:")
    test_agreement_level()
    print("test_majority_outcome:")
    test_majority_outcome()
    print("\nAll agreement/outcome derivation tests passed.")
