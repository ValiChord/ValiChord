"""Step 4 — the round: commit all, reveal all, verify every reveal against its seal.

The ordering is enforced by construction, not by convention: `RoundState` refuses
to accept a reveal until every expected commitment is in. That refusal is the
blinding. It is a Python guard rather than a network here — see plan §5, and say
so plainly in anything published.

What this does NOT do is run on Holochain. There is no conductor, no DNA, no
HarmonyRecord. The commit-reveal arithmetic is real; the distribution is not.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from generate import feature_names
from party import (
    RESEARCHER_SEED,
    VALIDATOR_SEEDS,
    Commitment,
    Reveal,
    run_party,
    verify_seal,
)
from protocol import load_protocol


class PrematureRevealError(RuntimeError):
    """Raised when a reveal is offered before every commitment is in.

    This is the blinding guarantee expressed as a type. If this exception can be
    provoked in ordinary use, the demonstration is broken.
    """


@dataclass
class RoundState:
    """Tracks the commit and reveal phases, and enforces the boundary between them."""

    expected_parties: list[str]
    commitments: dict[str, Commitment] = field(default_factory=dict)
    reveals: dict[str, Reveal] = field(default_factory=dict)

    @property
    def commit_phase_complete(self) -> bool:
        return set(self.commitments) == set(self.expected_parties)

    def commit(self, commitment: Commitment) -> None:
        if commitment.party_id in self.commitments:
            raise ValueError(f"{commitment.party_id} has already committed")
        if commitment.party_id not in self.expected_parties:
            raise ValueError(f"{commitment.party_id} is not a party to this round")
        self.commitments[commitment.party_id] = commitment

    def reveal(self, reveal: Reveal) -> None:
        if not self.commit_phase_complete:
            missing = sorted(set(self.expected_parties) - set(self.commitments))
            raise PrematureRevealError(
                f"reveal refused — still awaiting commitments from: {', '.join(missing)}"
            )
        commitment = self.commitments[reveal.party_id]
        if not verify_seal(reveal, commitment):
            raise ValueError(
                f"{reveal.party_id}: reveal does not match commitment "
                f"{commitment.commitment_hash} — rejected"
            )
        self.reveals[reveal.party_id] = reveal


def run_round(out_dir: Path, random_nonces: bool = False) -> dict:
    """Run one full commit-reveal round over the researcher and five validators."""
    record = load_protocol(out_dir)
    protocol = record["protocol"]

    data = np.load(out_dir / "dataset.npz")
    X, y = data["X"], data["y"]
    names = feature_names()

    parties = [("researcher", RESEARCHER_SEED)]
    parties += [(f"validator_{i + 1}", seed) for i, seed in enumerate(VALIDATOR_SEEDS)]

    if len(VALIDATOR_SEEDS) != protocol["n_validators"]:
        raise ValueError(
            f"protocol pre-registered n_validators={protocol['n_validators']} "
            f"but {len(VALIDATOR_SEEDS)} validator seeds are configured"
        )

    # Every party runs and seals before any reveal is offered. Each party's fit
    # sees only its own resample — no party's result is an input to another's.
    sealed: list[tuple[Commitment, Reveal]] = [
        run_party(party_id, seed, X, y, names, random_nonce=random_nonces)
        for party_id, seed in parties
    ]

    state = RoundState(expected_parties=[p for p, _ in parties])

    for commitment, _ in sealed:
        state.commit(commitment)

    for _, reveal in sealed:
        state.reveal(reveal)

    round_record = {
        "protocol_hash": record["protocol_hash"],
        "commitments": [c.to_dict() for c, _ in sealed],
        "reveals": [r.to_dict() for _, r in sealed],
        "all_reveals_verified": len(state.reveals) == len(parties),
    }
    (out_dir / "round.json").write_text(
        json.dumps(round_record, indent=2, sort_keys=True) + "\n"
    )
    return round_record


def demonstrate_blinding(out_dir: Path) -> str:
    """Show the guard firing: a reveal offered mid-commit-phase is refused.

    Included because a blinding claim nobody has seen fail is just an assertion.
    """
    state = RoundState(expected_parties=["researcher", "validator_1"])
    data = np.load(out_dir / "dataset.npz")
    commitment, reveal = run_party(
        "researcher", RESEARCHER_SEED, data["X"], data["y"], feature_names()
    )
    state.commit(commitment)
    try:
        state.reveal(reveal)
    except PrematureRevealError as exc:
        return str(exc)
    raise AssertionError("blinding guard did not fire — the demonstration is broken")


def main() -> None:
    out_dir = Path(__file__).parent / "artifacts"
    record = run_round(out_dir)

    print(f"protocol_hash: {record['protocol_hash']}\n")
    print("Commit phase — hashes only, no supports visible:")
    for c in record["commitments"]:
        print(f"  {c['party_id']:<13} {c['commitment_hash']}")

    print("\nReveal phase — every reveal verified against its seal:")
    for r in record["reveals"]:
        print(
            f"  {r['party_id']:<13} alpha={r['derived_alpha']:.4f}  "
            f"({len(r['support'])}) {', '.join(r['support'])}"
        )

    print(f"\nall reveals verified: {record['all_reveals_verified']}")
    print(f"blinding guard: {demonstrate_blinding(out_dir)}")


if __name__ == "__main__":
    main()
