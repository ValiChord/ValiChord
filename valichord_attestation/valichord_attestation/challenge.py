from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

import jcs


@dataclass
class Challenge:
    """Parameters for a probabilistic challenge against an attestation bundle.

    Attributes:
        bundle_hash: The SHA-256 hex digest of the target bundle (output of hash_bundle).
        verifier_nonce: Verifier-chosen random bytes. Must be at least 16 bytes.
            The holder cannot predict the challenged indices before this is revealed.
        k: Number of samples to challenge.
    """

    bundle_hash: str
    verifier_nonce: bytes
    k: int

    def __post_init__(self) -> None:
        if not self.bundle_hash:
            raise ValueError("Challenge.bundle_hash must not be empty")
        if len(self.verifier_nonce) < 16:
            raise ValueError("Challenge.verifier_nonce must be at least 16 bytes")
        if self.k <= 0:
            raise ValueError("Challenge.k must be a positive integer")


def compute_challenge_hash(challenge: Challenge) -> str:
    """SHA-256 over the JCS canonical encoding of the challenge parameters.

    Canonical form: {"bundle_hash": <str>, "k": <int>, "verifier_nonce_hex": <hex str>}
    JCS sorts keys lexicographically. The nonce is hex-encoded so the dict is
    JSON-serialisable without ambiguity.
    """
    d = {
        "bundle_hash": challenge.bundle_hash,
        "k": challenge.k,
        "verifier_nonce_hex": challenge.verifier_nonce.hex(),
    }
    raw = jcs.canonicalize(d)
    encoded = raw if isinstance(raw, bytes) else raw.encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def derive_seed(challenge: Challenge) -> bytes:
    """HMAC-SHA256(key=verifier_nonce, msg=bundle_hash_ascii).

    Binds the PRNG seed to both the verifier's private nonce and the specific
    bundle being challenged. The holder cannot predict the seed (and therefore
    the indices) without knowing the nonce in advance.
    """
    return hmac.new(
        key=challenge.verifier_nonce,
        msg=challenge.bundle_hash.encode("ascii"),
        digestmod=hashlib.sha256,
    ).digest()


def generate_indices(challenge: Challenge, total_samples: int) -> list[int]:
    """Derive k distinct challenged indices in [0, total_samples) deterministically.

    Algorithm: SHA-256 counter-mode.
        seed = derive_seed(challenge)
        for counter = 0, 1, 2, ...:
            digest = SHA-256(seed || counter.to_bytes(8, 'big'))
            candidate = int.from_bytes(digest, 'big') % total_samples
            if candidate not already selected: add to result

    The counter is an 8-byte big-endian unsigned integer. This construction is
    language-agnostic — any implementation following this spec produces identical
    indices given the same (bundle_hash, verifier_nonce, k, total_samples).

    Raises ValueError if k > total_samples.
    """
    if challenge.k > total_samples:
        raise ValueError(
            f"k ({challenge.k}) exceeds total_samples ({total_samples}): "
            "cannot draw more distinct indices than there are samples"
        )
    seed = derive_seed(challenge)
    indices: list[int] = []
    seen: set[int] = set()
    counter = 0
    while len(indices) < challenge.k:
        digest = hashlib.sha256(seed + counter.to_bytes(8, "big")).digest()
        candidate = int.from_bytes(digest, "big") % total_samples
        if candidate not in seen:
            seen.add(candidate)
            indices.append(candidate)
        counter += 1
    return indices
