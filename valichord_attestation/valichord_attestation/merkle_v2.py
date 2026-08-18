"""The v2 Merkle construction: RFC 6962 §2.1, adopted whole.

This replaces the v1 construction (see `merkle_v1.py`) and fixes three things
recorded in `spec/v2-backlog/`:

- **01, domain separation.** Leaves are hashed with a ``0x00`` prefix and interior
  nodes with ``0x01``, so no digest can be read as both. v1 hashed them
  identically.
- **02, odd-node handling.** The tree splits at the largest power of two below
  ``n`` and carries the odd subtree up unchanged. v1 padded odd levels by
  duplicating the last node, so ``[A, B, C]`` and ``[A, B, C, C]`` shared a root.
- **03, edge cases.** The empty tree and the single leaf now have stated values
  rather than incidental ones.

RFC 6962 §2.1, with ``d(i)`` the JCS encoding of sample ``i``::

    MTH({})   = SHA-256()
    MTH({d0}) = SHA-256(0x00 || d0)
    MTH(D[n]) = SHA-256(0x01 || MTH(D[0:k]) || MTH(D[k:n]))

where ``k`` is the largest power of two strictly less than ``n``.

The whole definition is taken rather than the prefixes alone. The falsify-cookbook
Pattern 13 demo took the prefixes and kept its own padding rule, and reproduced
the v1 odd-node collision independently — piecemeal adoption of a hash
construction is how you end up with a fourth incompatible tree.
"""

from __future__ import annotations

import hashlib

import jcs

#: Format versions whose ``outputs_merkle_root`` is produced by this construction.
FORMAT_VERSIONS = ("v2",)

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"

#: MTH({}) — the empty tree. Defined by RFC 6962 so that a conforming
#: implementation has an answer rather than a guess. `build_bundle` refuses an
#: empty sample list independently: the format defines a value the reference
#: implementation declines to emit.
EMPTY_ROOT = hashlib.sha256(b"").digest()


def _split_point(n: int) -> int:
    """Largest power of two strictly less than `n`. RFC 6962's `k`."""
    if n < 2:
        raise ValueError(f"split point is only defined for n >= 2, got {n}")
    return 1 << ((n - 1).bit_length() - 1)


def leaf_hash(sample: dict) -> bytes:
    """``SHA-256(0x00 || JCS(sample))`` — the domain-separated leaf hash."""
    raw = jcs.canonicalize(sample)
    encoded = raw if isinstance(raw, bytes) else raw.encode("utf-8")
    return hashlib.sha256(LEAF_PREFIX + encoded).digest()


def _hash_pair(left: bytes, right: bytes) -> bytes:
    """``SHA-256(0x01 || left || right)`` — the domain-separated interior node."""
    return hashlib.sha256(NODE_PREFIX + left + right).digest()


def _mth(leaves: list[bytes]) -> bytes:
    """Merkle Tree Hash over already-prefixed leaf digests.

    Takes leaf digests rather than samples because the recursion bottoms out on a
    single leaf, which RFC 6962 defines as already carrying its ``0x00`` prefix.
    """
    if not leaves:
        return EMPTY_ROOT
    if len(leaves) == 1:
        return leaves[0]
    k = _split_point(len(leaves))
    return _hash_pair(_mth(leaves[:k]), _mth(leaves[k:]))


def merkle_root(samples: list[dict]) -> str:
    """Merkle root over per-sample output dicts, as a 64-character hex string.

    Unlike v1, an empty list is not an error here — RFC 6962 gives it a value.
    Whether an empty sample list makes an attestable bundle is a separate
    question, answered by `build_bundle`, which rejects it.
    """
    return _mth([leaf_hash(s) for s in samples]).hex()


def _audit_path(leaves: list[bytes], index: int) -> list[dict]:
    """RFC 6962 §2.1.1 audit path, ordered leaf-first."""
    n = len(leaves)
    if n == 1:
        return []
    k = _split_point(n)
    if index < k:
        sibling = _mth(leaves[k:])
        return _audit_path(leaves[:k], index) + [
            {"position": "right", "sibling": sibling.hex()}
        ]
    sibling = _mth(leaves[:k])
    return _audit_path(leaves[k:], index - k) + [
        {"position": "left", "sibling": sibling.hex()}
    ]


def merkle_proof(samples: list[dict], index: int) -> list[dict]:
    """Generate a Merkle inclusion proof for the sample at `index`.

    Returns a list of steps, each a dict with:
        "sibling"  — hex-encoded sibling hash
        "position" — "right" if the sibling is the right child (current is left),
                     "left"  if the sibling is the left child (current is right)

    Same step format and same leaf-first ordering as v1, so the shape of a proof
    is unchanged across versions — only the values differ.
    """
    if not samples:
        raise ValueError("Cannot build a Merkle proof over an empty sample list")
    if not 0 <= index < len(samples):
        raise IndexError(f"sample index {index} out of range for {len(samples)} samples")
    return _audit_path([leaf_hash(s) for s in samples], index)


def root_from_path(leaf: bytes, proof: list[dict]) -> bytes:
    """Walk an inclusion proof from a leaf digest up to the root digest."""
    current = leaf
    for step in proof:
        sibling = bytes.fromhex(step["sibling"])
        if step["position"] == "right":
            current = _hash_pair(current, sibling)
        else:
            current = _hash_pair(sibling, current)
    return current


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
    return root_from_path(leaf_hash(sample), proof).hex() == root_hex
