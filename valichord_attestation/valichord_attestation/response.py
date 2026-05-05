from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .bundle import Bundle
from .challenge import Challenge, compute_challenge_hash, generate_indices
from .merkle import leaf_hash, merkle_proof


@dataclass
class ResponseSample:
    """One sample's contribution to a ChallengeResponse.

    Attributes:
        sample_index: Position of this sample in the original log.
        sample_content_hash: SHA-256(JCS(sample_dict)) — the same leaf hash used
            in the Merkle tree. The verifier can confirm this hash chains to the
            bundle's outputs_merkle_root without receiving the raw sample content.
        merkle_path: Inclusion proof from this leaf to the root, in the format
            returned by merkle.merkle_proof(): a list of
            {"position": "left"|"right", "sibling": "<64 hex chars>"} steps.
    """

    sample_index: int
    sample_content_hash: str
    merkle_path: list

    def __post_init__(self) -> None:
        if self.sample_content_hash is None:
            raise ValueError("ResponseSample.sample_content_hash must not be None")
        if self.merkle_path is None:
            raise ValueError("ResponseSample.merkle_path must not be None")


@dataclass
class ChallengeResponse:
    """A log holder's response to a probabilistic challenge.

    Attributes:
        challenge_hash: compute_challenge_hash(challenge) — binds this response
            to a specific challenge so it cannot be replayed against a different one.
        samples: One ResponseSample per challenged index, in index-list order.
    """

    challenge_hash: str
    samples: list

    def __post_init__(self) -> None:
        if not self.challenge_hash:
            raise ValueError("ChallengeResponse.challenge_hash must not be empty")
        if self.samples is None:
            raise ValueError("ChallengeResponse.samples must not be None")


def build_response(challenge: Challenge, log_samples: list[dict]) -> ChallengeResponse:
    """Build a ChallengeResponse from the log holder's full sample list.

    Determines the challenged indices deterministically from the challenge,
    then for each index computes the leaf hash and a Merkle inclusion proof.
    The response contains only hashes and proof paths — no raw sample content.

    Args:
        challenge: The Challenge issued by the verifier.
        log_samples: The holder's complete ordered list of per-sample output dicts.

    Returns:
        A ChallengeResponse ready to hand to the verifier.

    Raises:
        ValueError: if challenge.k exceeds len(log_samples).
    """
    total_samples = len(log_samples)
    indices = generate_indices(challenge, total_samples)
    ch = compute_challenge_hash(challenge)

    samples_out: list[ResponseSample] = []
    for idx in indices:
        content_hash = leaf_hash(log_samples[idx]).hex()
        path = merkle_proof(log_samples, idx)
        samples_out.append(
            ResponseSample(
                sample_index=idx,
                sample_content_hash=content_hash,
                merkle_path=path,
            )
        )

    return ChallengeResponse(challenge_hash=ch, samples=samples_out)


def verify_response(
    challenge: Challenge,
    response: ChallengeResponse,
    bundle: Bundle,
) -> bool:
    """Verify a ChallengeResponse against a bundle.

    Returns True if and only if:
    - response.challenge_hash matches compute_challenge_hash(challenge).
    - The response covers exactly the expected set of indices.
    - Every Merkle path reconstructs to bundle.outputs_merkle_root.

    Missing or None required fields raise ValueError (hash-collision safety:
    a missing field must never silently produce a matching hash).
    Cryptographic failures return False.

    Args:
        challenge: The original Challenge the response is answering.
        response: The ChallengeResponse from the log holder.
        bundle: The attested bundle (provides outputs_merkle_root and samples_total).
    """
    if not response.challenge_hash:
        raise ValueError("ChallengeResponse.challenge_hash must not be empty")
    if response.samples is None:
        raise ValueError("ChallengeResponse.samples must not be None")

    if response.challenge_hash != compute_challenge_hash(challenge):
        return False

    expected_indices = set(generate_indices(challenge, bundle.samples_total))
    response_indices = {s.sample_index for s in response.samples}
    if response_indices != expected_indices:
        return False

    root = bundle.outputs_merkle_root
    for sample in response.samples:
        if sample.sample_content_hash is None:
            raise ValueError(
                f"ResponseSample at index {sample.sample_index} has None sample_content_hash"
            )
        if sample.merkle_path is None:
            raise ValueError(
                f"ResponseSample at index {sample.sample_index} has None merkle_path"
            )
        for step in sample.merkle_path:
            if "sibling" not in step or "position" not in step:
                raise ValueError(
                    f"merkle_path step at index {sample.sample_index} "
                    "is missing 'sibling' or 'position'"
                )

        current = bytes.fromhex(sample.sample_content_hash)
        for step in sample.merkle_path:
            sibling = bytes.fromhex(step["sibling"])
            if step["position"] == "right":
                current = hashlib.sha256(current + sibling).digest()
            else:
                current = hashlib.sha256(sibling + current).digest()

        if current.hex() != root:
            return False

    return True
