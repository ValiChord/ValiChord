import pytest
from valichord_attestation.merkle import merkle_root, merkle_proof, verify_faithfulness


SAMPLES = [
    {"index": 0, "output": "42", "correct": True},
    {"index": 1, "output": "7", "correct": False},
    {"index": 2, "output": "100", "correct": True},
    {"index": 3, "output": "13", "correct": True},
]


def test_root_is_64_char_hex():
    root = merkle_root(SAMPLES)
    assert isinstance(root, str)
    assert len(root) == 64
    assert all(c in "0123456789abcdef" for c in root)


def test_root_deterministic():
    assert merkle_root(SAMPLES) == merkle_root(SAMPLES)


def test_root_sensitive_to_sample_content():
    modified = [{"index": 0, "output": "43", "correct": True}] + SAMPLES[1:]
    assert merkle_root(SAMPLES) != merkle_root(modified)


def test_root_sensitive_to_sample_order():
    reordered = [SAMPLES[1], SAMPLES[0]] + SAMPLES[2:]
    assert merkle_root(SAMPLES) != merkle_root(reordered)


def test_root_sensitive_to_extra_field():
    extra = [{"index": 0, "output": "42", "correct": True, "note": "extra"}] + SAMPLES[1:]
    assert merkle_root(SAMPLES) != merkle_root(extra)


def test_empty_samples_raises():
    with pytest.raises(ValueError, match="empty"):
        merkle_root([])


def test_proof_and_verify_for_each_index():
    root = merkle_root(SAMPLES)
    for i in range(len(SAMPLES)):
        proof = merkle_proof(SAMPLES, i)
        assert verify_faithfulness(root, i, SAMPLES[i], proof), f"proof failed at index {i}"


def test_verify_rejects_tampered_sample():
    root = merkle_root(SAMPLES)
    tampered = {"index": 0, "output": "WRONG", "correct": False}
    proof = merkle_proof(SAMPLES, 0)
    assert not verify_faithfulness(root, 0, tampered, proof)


def test_verify_rejects_wrong_sample_for_proof():
    root = merkle_root(SAMPLES)
    proof_for_0 = merkle_proof(SAMPLES, 0)
    # sample 1's data with sample 0's proof
    assert not verify_faithfulness(root, 0, SAMPLES[1], proof_for_0)


def test_verify_rejects_wrong_root():
    root = merkle_root(SAMPLES)
    bad_root = "0" * 64
    proof = merkle_proof(SAMPLES, 0)
    assert not verify_faithfulness(bad_root, 0, SAMPLES[0], proof)


def test_single_sample():
    single = [{"output": "42", "correct": True}]
    root = merkle_root(single)
    proof = merkle_proof(single, 0)
    assert verify_faithfulness(root, 0, single[0], proof)


def test_two_samples():
    two = SAMPLES[:2]
    root = merkle_root(two)
    for i in range(2):
        proof = merkle_proof(two, i)
        assert verify_faithfulness(root, i, two[i], proof)


def test_odd_number_of_samples():
    three = SAMPLES[:3]
    root = merkle_root(three)
    for i in range(3):
        proof = merkle_proof(three, i)
        assert verify_faithfulness(root, i, three[i], proof)


def test_five_samples():
    five = SAMPLES + [{"index": 4, "output": "77", "correct": True}]
    root = merkle_root(five)
    for i in range(5):
        proof = merkle_proof(five, i)
        assert verify_faithfulness(root, i, five[i], proof)


def test_proof_structure():
    proof = merkle_proof(SAMPLES, 0)
    assert len(proof) > 0
    for step in proof:
        assert "sibling" in step
        assert "position" in step
        assert step["position"] in ("left", "right")
        assert len(step["sibling"]) == 64


def test_root_is_deterministic_across_calls():
    r1 = merkle_root(SAMPLES)
    r2 = merkle_root(SAMPLES)
    assert r1 == r2
