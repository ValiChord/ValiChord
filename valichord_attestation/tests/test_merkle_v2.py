"""Tests for the v2 Merkle construction (RFC 6962 §2.1).

Two kinds of test here, deliberately. Most check properties. A few hand-compute
the expected digest from hashlib directly, so the implementation is checked
against the RFC rather than only against itself — a construction that is
self-consistently wrong would pass every property test in this file.

See `spec/v2-backlog/01`, `02` and `03`.
"""

from __future__ import annotations

import hashlib

import jcs
import pytest

from valichord_attestation import merkle_v1, merkle_v2

S = [{"index": i, "output": str(i)} for i in range(9)]


def _jcs(sample: dict) -> bytes:
    raw = jcs.canonicalize(sample)
    return raw if isinstance(raw, bytes) else raw.encode("utf-8")


def _mth_bottom_up(samples: list[dict]) -> str:
    """A second reading of RFC 6962 §2.1, in a deliberately different shape.

    Bottom-up, level by level, no recursion, odd tail node promoted rather than
    duplicated — where merkle_v2 recurses on a split at the largest power of two
    below n. Used as an oracle: an implementation checked only against itself
    proves consistency, not correctness, and two shapes agreeing is evidence that
    the RFC was read the same way twice.

    That the two shapes coincide at all is an assumption, so it is tested across
    a range rather than asserted. Prompted by Cüneyt Öztürk doing the same on the
    falsify-cookbook side (falsify-cookbook#4) — his two implementations and these
    two all agree, which is what the vectors actually rest on.
    """
    if not samples:
        return hashlib.sha256(b"").hexdigest()
    level = [hashlib.sha256(b"\x00" + _jcs(s)).digest() for s in samples]
    while len(level) > 1:
        nxt = [
            hashlib.sha256(b"\x01" + level[i] + level[i + 1]).digest()
            for i in range(0, len(level) - 1, 2)
        ]
        if len(level) % 2:
            nxt.append(level[-1])
        level = nxt
    return level[0].hex()


def _gen(n: int, salt: int = 0) -> list[dict]:
    return [{"index": i, "output": str(i * 7 + salt), "correct": i % 2 == 0} for i in range(n)]


# ---------------------------------------------------------------------------
# Checked against the RFC by hand, not against ourselves
# ---------------------------------------------------------------------------

def test_empty_root_is_sha256_of_nothing() -> None:
    """MTH({}) = SHA-256()."""
    assert merkle_v2.merkle_root([]) == hashlib.sha256(b"").hexdigest()


def test_single_leaf_is_prefixed_not_passed_through() -> None:
    """MTH({d0}) = SHA-256(0x00 || d0). v1 returned the bare leaf here."""
    expected = hashlib.sha256(b"\x00" + _jcs(S[0])).hexdigest()
    assert merkle_v2.merkle_root([S[0]]) == expected
    assert merkle_v2.merkle_root([S[0]]) != merkle_v1.merkle_root([S[0]])


def test_two_leaves_hand_computed() -> None:
    """MTH(D[2]) = SHA-256(0x01 || leaf0 || leaf1)."""
    leaf0 = hashlib.sha256(b"\x00" + _jcs(S[0])).digest()
    leaf1 = hashlib.sha256(b"\x00" + _jcs(S[1])).digest()
    expected = hashlib.sha256(b"\x01" + leaf0 + leaf1).hexdigest()
    assert merkle_v2.merkle_root(S[:2]) == expected


def test_three_leaves_hand_computed_split_at_two() -> None:
    """n=3 splits at k=2: SHA-256(0x01 || MTH(D[0:2]) || leaf2).

    This is the case v1 got wrong. The odd leaf is carried up unchanged, not
    duplicated and paired with itself.
    """
    leaves = [hashlib.sha256(b"\x00" + _jcs(s)).digest() for s in S[:3]]
    left = hashlib.sha256(b"\x01" + leaves[0] + leaves[1]).digest()
    expected = hashlib.sha256(b"\x01" + left + leaves[2]).hexdigest()
    assert merkle_v2.merkle_root(S[:3]) == expected


@pytest.mark.parametrize(
    "n,k", [(2, 1), (3, 2), (4, 2), (5, 4), (7, 4), (8, 4), (9, 8), (16, 8), (17, 16)]
)
def test_split_point_is_largest_power_of_two_below_n(n: int, k: int) -> None:
    assert merkle_v2._split_point(n) == k


# ---------------------------------------------------------------------------
# 02 — the collision is gone
# ---------------------------------------------------------------------------

def test_duplicated_final_sample_no_longer_collides() -> None:
    """The v1 defect, inverted. [A,B,C] and [A,B,C,C] must now differ."""
    a, b = S[:3], S[:3] + [S[2]]
    assert merkle_v1.merkle_root(a) == merkle_v1.merkle_root(b)  # the old behaviour
    assert merkle_v2.merkle_root(a) != merkle_v2.merkle_root(b)  # the fix


@pytest.mark.parametrize("n", range(1, 9))
def test_appending_a_duplicate_changes_the_root(n: int) -> None:
    base = S[:n]
    assert merkle_v2.merkle_root(base) != merkle_v2.merkle_root(base + [base[-1]])


# ---------------------------------------------------------------------------
# 01 — domain separation
# ---------------------------------------------------------------------------

def test_leaf_and_node_hashing_differ_on_the_same_bytes() -> None:
    """The point of the prefixes: one digest cannot be read as both."""
    payload = b"x" * 64
    assert hashlib.sha256(b"\x00" + payload).digest() != hashlib.sha256(b"\x01" + payload).digest()


def test_an_interior_digest_is_not_a_valid_leaf_of_its_own_subtree() -> None:
    """A two-leaf root must not equal the leaf hash of the concatenated children."""
    leaves = [merkle_v2.leaf_hash(s) for s in S[:2]]
    interior = merkle_v2._hash_pair(leaves[0], leaves[1])
    assert interior != hashlib.sha256(b"\x00" + leaves[0] + leaves[1]).digest()


# ---------------------------------------------------------------------------
# Proofs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", range(1, 10))
def test_every_proof_verifies(n: int) -> None:
    samples = S[:n]
    root = merkle_v2.merkle_root(samples)
    for i in range(n):
        proof = merkle_v2.merkle_proof(samples, i)
        assert merkle_v2.verify_faithfulness(root, i, samples[i], proof)
        assert merkle_v2.root_from_path(merkle_v2.leaf_hash(samples[i]), proof).hex() == root


def test_a_proof_does_not_verify_a_different_sample() -> None:
    root = merkle_v2.merkle_root(S[:5])
    proof = merkle_v2.merkle_proof(S[:5], 0)
    assert not merkle_v2.verify_faithfulness(root, 0, S[1], proof)


def test_a_v1_proof_does_not_verify_under_v2() -> None:
    """Cross-version proofs must fail rather than accidentally validate."""
    root_v2 = merkle_v2.merkle_root(S[:5])
    proof_v1 = merkle_v1.merkle_proof(S[:5], 2)
    assert not merkle_v2.verify_faithfulness(root_v2, 2, S[2], proof_v1)


def test_single_leaf_proof_is_empty() -> None:
    assert merkle_v2.merkle_proof([S[0]], 0) == []


def test_proof_rejects_empty_and_out_of_range() -> None:
    with pytest.raises(ValueError):
        merkle_v2.merkle_proof([], 0)
    with pytest.raises(IndexError):
        merkle_v2.merkle_proof(S[:3], 3)


# ---------------------------------------------------------------------------
# The two constructions are genuinely different everywhere
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", range(1, 9))
def test_v1_and_v2_roots_never_coincide(n: int) -> None:
    assert merkle_v1.merkle_root(S[:n]) != merkle_v2.merkle_root(S[:n])


def test_order_still_matters() -> None:
    assert merkle_v2.merkle_root(S[:4]) != merkle_v2.merkle_root(list(reversed(S[:4])))


# ---------------------------------------------------------------------------
# Cross-implementation agreement
# ---------------------------------------------------------------------------

def test_recursive_and_bottom_up_agree_across_a_range() -> None:
    """Two shapes of the same RFC, over n = 0..64 with two sample sets each.

    The single strongest check in this file. The hand-computed tests above pin
    n = 0..3; this covers every tree shape up to 64 leaves, including the whole
    uneven-split region where left is a perfect subtree and right is a short one.
    """
    for n in range(0, 65):
        for salt in (0, 3):
            s = _gen(n, salt)
            assert merkle_v2.merkle_root(s) == _mth_bottom_up(s), f"disagree at n={n}, salt={salt}"


@pytest.mark.parametrize(
    "n,expected",
    [
        (5, "48392a70e7e048e4840d4e52cf8b68d957a60fe0b66185eaeccb1ca124f65fc7"),
        (6, "5fbeada770b285b0b1e512823a49818080d4e2f680b6e147aee4663ea0cdda86"),
        (7, "41ea9dc8dfbdf1bed157bf8b8600ebed7acba4a4987874f26864ed33acbbfedf"),
    ],
)
def test_uneven_split_region_matches_an_outside_implementation(n: int, expected: str) -> None:
    """Roots computed independently by Cüneyt Öztürk (falsify-cookbook#4, 2026-08-18).

    5 ≤ n ≤ 7 is where promote-don't-duplicate is least obvious: the split is
    uneven and the right subtree is the short one. Both vector files stop at
    n = 4, so until these landed nothing outside this repository had checked the
    region. These are pinned here pending the same cases arriving in
    tests/vectors/merkle_v2.json.
    """
    assert merkle_v2.merkle_root(_gen(n)) == expected
