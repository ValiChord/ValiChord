import pytest
from valichord_attestation.challenge import (
    Challenge,
    compute_challenge_hash,
    derive_seed,
    generate_indices,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

BUNDLE_HASH = "a" * 64
NONCE_16 = bytes(range(16))         # exactly 16 bytes
NONCE_32 = bytes(range(32))         # 32 bytes — valid
ALT_NONCE = bytes(range(1, 17))     # different 16-byte nonce
ALT_BUNDLE_HASH = "b" * 64


# ---------------------------------------------------------------------------
# Challenge construction
# ---------------------------------------------------------------------------


def test_challenge_valid_construction():
    c = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=5)
    assert c.bundle_hash == BUNDLE_HASH
    assert c.verifier_nonce == NONCE_16
    assert c.k == 5


def test_challenge_rejects_empty_bundle_hash():
    with pytest.raises(ValueError, match="bundle_hash"):
        Challenge(bundle_hash="", verifier_nonce=NONCE_16, k=5)


def test_challenge_rejects_short_nonce_15():
    with pytest.raises(ValueError, match="16 bytes"):
        Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=b"\x00" * 15, k=5)


def test_challenge_rejects_empty_nonce():
    with pytest.raises(ValueError, match="16 bytes"):
        Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=b"", k=5)


def test_challenge_rejects_zero_k():
    with pytest.raises(ValueError, match="positive"):
        Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=0)


def test_challenge_rejects_negative_k():
    with pytest.raises(ValueError, match="positive"):
        Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=-1)


def test_challenge_accepts_exactly_16_byte_nonce():
    c = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=b"\xff" * 16, k=1)
    assert len(c.verifier_nonce) == 16


def test_challenge_accepts_k_equals_one():
    c = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=1)
    assert c.k == 1


# ---------------------------------------------------------------------------
# derive_seed
# ---------------------------------------------------------------------------


def test_derive_seed_returns_32_bytes():
    c = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=5)
    seed = derive_seed(c)
    assert isinstance(seed, bytes)
    assert len(seed) == 32


def test_derive_seed_deterministic():
    c = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=5)
    assert derive_seed(c) == derive_seed(c)


def test_derive_seed_changes_with_nonce():
    c1 = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=5)
    c2 = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=ALT_NONCE, k=5)
    assert derive_seed(c1) != derive_seed(c2)


def test_derive_seed_changes_with_bundle_hash():
    c1 = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=5)
    c2 = Challenge(bundle_hash=ALT_BUNDLE_HASH, verifier_nonce=NONCE_16, k=5)
    assert derive_seed(c1) != derive_seed(c2)


# ---------------------------------------------------------------------------
# generate_indices
# ---------------------------------------------------------------------------


def test_generate_indices_returns_correct_count():
    c = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=5)
    indices = generate_indices(c, 100)
    assert len(indices) == 5


def test_generate_indices_in_range():
    c = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=20)
    indices = generate_indices(c, 50)
    assert all(0 <= i < 50 for i in indices)


def test_generate_indices_distinct():
    c = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=30)
    indices = generate_indices(c, 100)
    assert len(indices) == len(set(indices))


def test_generate_indices_deterministic():
    c = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=5)
    assert generate_indices(c, 100) == generate_indices(c, 100)


def test_generate_indices_changes_with_nonce():
    c1 = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=5)
    c2 = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=ALT_NONCE, k=5)
    assert generate_indices(c1, 100) != generate_indices(c2, 100)


def test_generate_indices_changes_with_bundle_hash():
    c1 = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=5)
    c2 = Challenge(bundle_hash=ALT_BUNDLE_HASH, verifier_nonce=NONCE_16, k=5)
    assert generate_indices(c1, 100) != generate_indices(c2, 100)


def test_generate_indices_k_equals_total():
    c = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=10)
    indices = generate_indices(c, 10)
    assert sorted(indices) == list(range(10))


def test_generate_indices_k_equals_one():
    c = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=1)
    indices = generate_indices(c, 100)
    assert len(indices) == 1
    assert 0 <= indices[0] < 100


def test_generate_indices_k_exceeds_total_raises():
    c = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=10)
    with pytest.raises(ValueError, match="total_samples"):
        generate_indices(c, 5)


def test_generate_indices_k_equals_total_plus_one_raises():
    c = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=11)
    with pytest.raises(ValueError, match="total_samples"):
        generate_indices(c, 10)


# ---------------------------------------------------------------------------
# Cross-platform determinism (fixed test vector)
# Computed from the reference implementation; any conforming implementation
# must produce identical values given the same inputs.
# ---------------------------------------------------------------------------

# Inputs: bundle_hash='a'*64, verifier_nonce=bytes(range(16)), k=5, total=100
_EXPECTED_SEED_HEX = "4b763d6f418f14dd085e3458c666fd9a00b6cd0132da3a049c07f96a1d9582f7"
_EXPECTED_INDICES = [9, 69, 33, 74, 38]


def test_fixed_vector_seed():
    c = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=5)
    assert derive_seed(c).hex() == _EXPECTED_SEED_HEX


def test_fixed_vector_indices():
    c = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=5)
    assert generate_indices(c, 100) == _EXPECTED_INDICES


# ---------------------------------------------------------------------------
# compute_challenge_hash
# ---------------------------------------------------------------------------


def test_compute_challenge_hash_returns_64_char_hex():
    c = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=5)
    h = compute_challenge_hash(c)
    assert isinstance(h, str)
    assert len(h) == 64
    assert all(ch in "0123456789abcdef" for ch in h)


def test_compute_challenge_hash_deterministic():
    c = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=5)
    assert compute_challenge_hash(c) == compute_challenge_hash(c)


def test_compute_challenge_hash_changes_with_nonce():
    c1 = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=5)
    c2 = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=ALT_NONCE, k=5)
    assert compute_challenge_hash(c1) != compute_challenge_hash(c2)


def test_compute_challenge_hash_changes_with_bundle_hash():
    c1 = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=5)
    c2 = Challenge(bundle_hash=ALT_BUNDLE_HASH, verifier_nonce=NONCE_16, k=5)
    assert compute_challenge_hash(c1) != compute_challenge_hash(c2)


def test_compute_challenge_hash_changes_with_k():
    c1 = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=5)
    c2 = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=10)
    assert compute_challenge_hash(c1) != compute_challenge_hash(c2)


def test_fixed_vector_challenge_hash():
    c = Challenge(bundle_hash=BUNDLE_HASH, verifier_nonce=NONCE_16, k=5)
    assert compute_challenge_hash(c) == "4bdbf0004d21cb047cc9029b5c214ea5d26cc87b2c76e45116d17779b4782e95"
