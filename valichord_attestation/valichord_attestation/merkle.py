from __future__ import annotations

import hashlib

import jcs


def leaf_hash(sample: dict) -> bytes:
    """SHA-256 of the JCS-canonical encoding of a per-sample output dict.

    This is the protocol-defining leaf hash function for the Merkle tree.
    It is public because challenge responses reference it by name.
    """
    raw = jcs.canonicalize(sample)
    encoded = raw if isinstance(raw, bytes) else raw.encode("utf-8")
    return hashlib.sha256(encoded).digest()


def _hash_pair(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(left + right).digest()


def _build_tree(leaves: list[bytes]) -> list[list[bytes]]:
    """Build a complete binary Merkle tree from leaf hashes.

    Returns a list of levels: level[0] = leaves (unpadded), level[-1] = [root].
    Odd-length levels are padded by duplicating the last node before pairing.
    """
    if not leaves:
        raise ValueError("Cannot build a Merkle tree from an empty sample list")
    levels: list[list[bytes]] = [leaves[:]]
    current = leaves[:]
    while len(current) > 1:
        if len(current) % 2 == 1:
            current = current + [current[-1]]
        current = [_hash_pair(current[i], current[i + 1]) for i in range(0, len(current), 2)]
        levels.append(current[:])
    return levels


def merkle_root(samples: list[dict]) -> str:
    """Compute the Merkle root of a list of per-sample output dicts.

    Each sample dict is JCS-encoded then SHA-256 hashed to form a leaf.
    Returns the root as a 64-character hex string.
    """
    leaves = [leaf_hash(s) for s in samples]
    tree = _build_tree(leaves)
    return tree[-1][0].hex()


def merkle_proof(samples: list[dict], index: int) -> list[dict]:
    """Generate a Merkle inclusion proof for the sample at `index`.

    Returns a list of steps, each a dict with:
        "sibling"  — hex-encoded sibling hash
        "position" — "right" if the sibling is the right child (current is left),
                     "left"  if the sibling is the left child (current is right)

    The verifier reconstructs the root by combining current with each sibling
    in the stated position at each level.
    """
    leaves = [leaf_hash(s) for s in samples]
    tree = _build_tree(leaves)
    proof: list[dict] = []
    idx = index
    for level in tree[:-1]:
        padded = level + [level[-1]] if len(level) % 2 == 1 else level
        sibling_idx = idx ^ 1
        position = "right" if idx % 2 == 0 else "left"
        proof.append({"position": position, "sibling": padded[sibling_idx].hex()})
        idx //= 2
    return proof


def verify_faithfulness(
    root_hex: str,
    sample_index: int,
    sample: dict,
    proof: list[dict],
) -> bool:
    """Verify that `sample` at `sample_index` is included in the Merkle tree.

    `sample_index` is accepted for API consistency with sparse-proof variants
    (where the index determines path direction without a full proof list) but is
    not used in this implementation — the `proof` list encodes all path directions.
    """
    _ = sample_index
    current = leaf_hash(sample)
    for step in proof:
        sibling = bytes.fromhex(step["sibling"])
        if step["position"] == "right":
            current = _hash_pair(current, sibling)
        else:
            current = _hash_pair(sibling, current)
    return current.hex() == root_hex
