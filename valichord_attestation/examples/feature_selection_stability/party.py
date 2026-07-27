"""Step 3 — one party: resample, run the pre-registered rule, seal the support.

Each party draws their OWN bootstrap resample with their own seed, runs the
pre-registered procedure on it, and seals the resulting support set. They
publish only the commitment hash. Nobody sees anybody else's support until
every commitment is in (step 4).

On nonces: a real deployment draws the nonce from the OS CSPRNG, and it must be
unpredictable — a guessable nonce lets an observer brute-force the committed
support, since the support space is small. Here the nonce is derived from the
party's seed so that the whole demonstration is reproducible from the scripts
alone, which is a hard requirement for this artefact. Use --random-nonces to
run it the production way (at the cost of reproducibility).
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, asdict

import jcs
import numpy as np

import lambda_rule

NONCE_BYTES = 32

# Fixed, published party seeds. The researcher's is distinct from the
# validators' so no party can be accused of having reused another's resample.
RESEARCHER_SEED = 1000
VALIDATOR_SEEDS = (2001, 2002, 2003, 2004, 2005)


@dataclass(frozen=True)
class Commitment:
    """What a party publishes in the commit phase — the hash and nothing else."""

    party_id: str
    commitment_hash: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Reveal:
    """What a party publishes in the reveal phase, once all commitments are in."""

    party_id: str
    support: list[str]
    nonce: str
    derived_alpha: float
    resample_seed: int

    def to_dict(self) -> dict:
        return asdict(self)


def canonical_support(support: list[str]) -> bytes:
    """JCS-canonical bytes of a support set.

    Sorted, so two parties who selected the same features commit to the same
    bytes regardless of the order their fit happened to return them in.
    """
    raw = jcs.canonicalize(sorted(support))
    return raw if isinstance(raw, bytes) else raw.encode("utf-8")


def seal(support: list[str], nonce: bytes) -> str:
    """commitment = SHA-256(canonical_support || nonce)."""
    h = hashlib.sha256()
    h.update(canonical_support(support))
    h.update(nonce)
    return h.hexdigest()


def verify_seal(reveal: Reveal, commitment: Commitment) -> bool:
    """Recompute the seal from a reveal and check it against the commitment."""
    if reveal.party_id != commitment.party_id:
        return False
    recomputed = seal(reveal.support, bytes.fromhex(reveal.nonce))
    return recomputed == commitment.commitment_hash


def derive_nonce(seed: int, random_nonce: bool = False) -> bytes:
    """Reproducible-by-default nonce. See the module docstring."""
    if random_nonce:
        return os.urandom(NONCE_BYTES)
    return hashlib.sha256(f"nonce:{seed}".encode("utf-8")).digest()


def bootstrap(X: np.ndarray, y: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Draw a bootstrap resample of the rows: n draws, with replacement."""
    rng = np.random.default_rng(seed)
    n = X.shape[0]
    idx = rng.integers(0, n, size=n)
    return X[idx], y[idx]


def run_party(
    party_id: str,
    seed: int,
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    random_nonce: bool = False,
) -> tuple[Commitment, Reveal]:
    """Run one party end-to-end: resample, fit, seal.

    Returns the commitment (published now) and the reveal (published later).
    Separating them in the return type mirrors the protocol: the caller must
    deliberately choose to release the reveal, and step 4 will not accept it
    until every commitment is in.
    """
    Xb, yb = bootstrap(X, y, seed)
    support_idx, alpha = lambda_rule.fit_support(Xb, yb)
    support = [feature_names[i] for i in support_idx]

    nonce = derive_nonce(seed, random_nonce)
    commitment = Commitment(party_id=party_id, commitment_hash=seal(support, nonce))
    reveal = Reveal(
        party_id=party_id,
        support=sorted(support),
        nonce=nonce.hex(),
        derived_alpha=alpha,
        resample_seed=seed,
    )
    return commitment, reveal


def main() -> None:
    """Run a single party in isolation — a smoke test for the machinery."""
    from pathlib import Path

    from generate import feature_names

    art = Path(__file__).parent / "artifacts"
    data = np.load(art / "dataset.npz")
    X, y = data["X"], data["y"]

    commitment, reveal = run_party("researcher", RESEARCHER_SEED, X, y, feature_names())

    print(f"party:          {commitment.party_id}")
    print(f"resample seed:  {reveal.resample_seed}")
    print(f"derived alpha:  {reveal.derived_alpha:.6f}")
    print(f"support ({len(reveal.support)}): {', '.join(reveal.support)}")
    print(f"commitment:     {commitment.commitment_hash}")
    print(f"seal verifies:  {verify_seal(reveal, commitment)}")


if __name__ == "__main__":
    main()
