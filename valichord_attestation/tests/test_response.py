import copy
import pytest
from valichord_attestation import build_bundle
from valichord_attestation.challenge import Challenge, compute_challenge_hash
from valichord_attestation.response import (
    ChallengeResponse,
    ResponseSample,
    build_response,
    verify_response,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

NONCE = bytes(range(16))
SAMPLES = [{"index": i, "output": str(i * 7), "correct": i % 3 != 0} for i in range(20)]


def _bundle(samples=None):
    s = samples or SAMPLES
    return build_bundle(
        model_id="test-model",
        task_id="test-task",
        raw_metrics=[{"key": "accuracy", "value": 0.75}],
        samples=s,
        generated_at="2026-01-01T00:00:00+00:00",
    )


def _challenge(k=5, samples=None):
    from valichord_attestation import hash_bundle
    bundle = _bundle(samples)
    bh = hash_bundle(bundle)
    return Challenge(bundle_hash=bh, verifier_nonce=NONCE, k=k), bundle


# ---------------------------------------------------------------------------
# ResponseSample construction
# ---------------------------------------------------------------------------


def test_response_sample_valid():
    rs = ResponseSample(sample_index=0, sample_content_hash="a" * 64, merkle_path=[])
    assert rs.sample_index == 0


def test_response_sample_rejects_none_content_hash():
    with pytest.raises(ValueError, match="sample_content_hash"):
        ResponseSample(sample_index=0, sample_content_hash=None, merkle_path=[])


def test_response_sample_rejects_none_merkle_path():
    with pytest.raises(ValueError, match="merkle_path"):
        ResponseSample(sample_index=0, sample_content_hash="a" * 64, merkle_path=None)


# ---------------------------------------------------------------------------
# ChallengeResponse construction
# ---------------------------------------------------------------------------


def test_challenge_response_valid():
    cr = ChallengeResponse(challenge_hash="a" * 64, samples=[])
    assert cr.challenge_hash == "a" * 64


def test_challenge_response_rejects_empty_challenge_hash():
    with pytest.raises(ValueError, match="challenge_hash"):
        ChallengeResponse(challenge_hash="", samples=[])


def test_challenge_response_rejects_none_samples():
    with pytest.raises(ValueError, match="samples"):
        ChallengeResponse(challenge_hash="a" * 64, samples=None)


# ---------------------------------------------------------------------------
# build_response
# ---------------------------------------------------------------------------


def test_build_response_returns_challenge_response():
    challenge, bundle = _challenge(k=3)
    response = build_response(challenge, SAMPLES)
    assert isinstance(response, ChallengeResponse)


def test_build_response_contains_k_samples():
    challenge, bundle = _challenge(k=4)
    response = build_response(challenge, SAMPLES)
    assert len(response.samples) == 4


def test_build_response_challenge_hash_matches():
    challenge, bundle = _challenge(k=3)
    response = build_response(challenge, SAMPLES)
    assert response.challenge_hash == compute_challenge_hash(challenge)


def test_build_response_indices_are_valid():
    challenge, bundle = _challenge(k=5)
    response = build_response(challenge, SAMPLES)
    for s in response.samples:
        assert 0 <= s.sample_index < len(SAMPLES)


def test_build_response_indices_are_distinct():
    challenge, bundle = _challenge(k=10)
    response = build_response(challenge, SAMPLES)
    indices = [s.sample_index for s in response.samples]
    assert len(indices) == len(set(indices))


def test_build_response_content_hashes_are_hex():
    challenge, bundle = _challenge(k=3)
    response = build_response(challenge, SAMPLES)
    for s in response.samples:
        assert len(s.sample_content_hash) == 64
        assert all(c in "0123456789abcdef" for c in s.sample_content_hash)


def test_build_response_merkle_path_format():
    challenge, bundle = _challenge(k=3)
    response = build_response(challenge, SAMPLES)
    for s in response.samples:
        for step in s.merkle_path:
            assert "position" in step
            assert "sibling" in step
            assert step["position"] in ("left", "right")
            assert len(step["sibling"]) == 64


def test_build_response_k_exceeds_samples_raises():
    challenge = Challenge(bundle_hash="a" * 64, verifier_nonce=NONCE, k=25)
    with pytest.raises(ValueError, match="total_samples"):
        build_response(challenge, SAMPLES)


# ---------------------------------------------------------------------------
# verify_response — happy path
# ---------------------------------------------------------------------------


def test_verify_response_round_trip():
    challenge, bundle = _challenge(k=5)
    response = build_response(challenge, SAMPLES)
    assert verify_response(challenge, response, bundle) is True


def test_verify_response_k_equals_one():
    challenge, bundle = _challenge(k=1)
    response = build_response(challenge, SAMPLES)
    assert verify_response(challenge, response, bundle) is True


def test_verify_response_k_equals_total():
    challenge, bundle = _challenge(k=len(SAMPLES))
    response = build_response(challenge, SAMPLES)
    assert verify_response(challenge, response, bundle) is True


def test_verify_response_small_sample_set():
    tiny = [{"v": i} for i in range(3)]
    from valichord_attestation import hash_bundle
    bundle = _bundle(tiny)
    bh = hash_bundle(bundle)
    challenge = Challenge(bundle_hash=bh, verifier_nonce=NONCE, k=2)
    response = build_response(challenge, tiny)
    assert verify_response(challenge, response, bundle) is True


# ---------------------------------------------------------------------------
# verify_response — tampered data → False
# ---------------------------------------------------------------------------


def test_verify_rejects_tampered_sample_content_hash():
    challenge, bundle = _challenge(k=3)
    response = build_response(challenge, SAMPLES)
    tampered = copy.deepcopy(response)
    tampered.samples[0] = ResponseSample(
        sample_index=tampered.samples[0].sample_index,
        sample_content_hash="0" * 64,
        merkle_path=tampered.samples[0].merkle_path,
    )
    assert verify_response(challenge, tampered, bundle) is False


def test_verify_rejects_tampered_merkle_path():
    challenge, bundle = _challenge(k=3)
    response = build_response(challenge, SAMPLES)
    tampered = copy.deepcopy(response)
    bad_path = [{"position": s["position"], "sibling": "0" * 64}
                for s in tampered.samples[0].merkle_path]
    tampered.samples[0] = ResponseSample(
        sample_index=tampered.samples[0].sample_index,
        sample_content_hash=tampered.samples[0].sample_content_hash,
        merkle_path=bad_path,
    )
    assert verify_response(challenge, tampered, bundle) is False


def test_verify_rejects_mismatched_challenge():
    from valichord_attestation import hash_bundle
    challenge_a, bundle = _challenge(k=3)
    response = build_response(challenge_a, SAMPLES)
    challenge_b = Challenge(
        bundle_hash=hash_bundle(bundle),
        verifier_nonce=bytes(range(16, 32)),
        k=3,
    )
    assert verify_response(challenge_b, response, bundle) is False


def test_verify_rejects_wrong_index_set():
    challenge, bundle = _challenge(k=3)
    response = build_response(challenge, SAMPLES)
    tampered = copy.deepcopy(response)
    # Swap one sample_index for one not in the expected set
    s = tampered.samples[0]
    unexpected_idx = next(
        i for i in range(len(SAMPLES))
        if i not in {x.sample_index for x in tampered.samples}
    )
    tampered.samples[0] = ResponseSample(
        sample_index=unexpected_idx,
        sample_content_hash=s.sample_content_hash,
        merkle_path=s.merkle_path,
    )
    assert verify_response(challenge, tampered, bundle) is False


# ---------------------------------------------------------------------------
# verify_response — missing/None fields raise (R4 hash-collision safety)
# ---------------------------------------------------------------------------


def test_verify_raises_on_empty_challenge_hash():
    challenge, bundle = _challenge(k=3)
    # Bypass __post_init__ to reach the guard inside verify_response directly.
    bad_response = ChallengeResponse.__new__(ChallengeResponse)
    bad_response.challenge_hash = ""
    bad_response.samples = []
    with pytest.raises(ValueError, match="challenge_hash"):
        verify_response(challenge, bad_response, bundle)


def test_verify_raises_on_none_samples():
    challenge, bundle = _challenge(k=3)
    bad_response = ChallengeResponse.__new__(ChallengeResponse)
    bad_response.challenge_hash = "a" * 64
    bad_response.samples = None
    with pytest.raises(ValueError, match="samples"):
        verify_response(challenge, bad_response, bundle)


def test_verify_raises_on_none_sample_content_hash():
    challenge, bundle = _challenge(k=1)
    response = build_response(challenge, SAMPLES)
    tampered = copy.deepcopy(response)
    s = tampered.samples[0]
    bad_rs = ResponseSample.__new__(ResponseSample)
    bad_rs.sample_index = s.sample_index
    bad_rs.sample_content_hash = None
    bad_rs.merkle_path = s.merkle_path
    tampered.samples[0] = bad_rs
    with pytest.raises(ValueError, match="sample_content_hash"):
        verify_response(challenge, tampered, bundle)


def test_verify_raises_on_none_merkle_path():
    challenge, bundle = _challenge(k=1)
    response = build_response(challenge, SAMPLES)
    tampered = copy.deepcopy(response)
    s = tampered.samples[0]
    bad_rs = ResponseSample.__new__(ResponseSample)
    bad_rs.sample_index = s.sample_index
    bad_rs.sample_content_hash = s.sample_content_hash
    bad_rs.merkle_path = None
    tampered.samples[0] = bad_rs
    with pytest.raises(ValueError, match="merkle_path"):
        verify_response(challenge, tampered, bundle)


def test_verify_raises_on_malformed_merkle_path_step():
    challenge, bundle = _challenge(k=1)
    response = build_response(challenge, SAMPLES)
    tampered = copy.deepcopy(response)
    s = tampered.samples[0]
    bad_rs = ResponseSample(
        sample_index=s.sample_index,
        sample_content_hash=s.sample_content_hash,
        merkle_path=[{"wrong_key": "value"}],
    )
    tampered.samples[0] = bad_rs
    with pytest.raises(ValueError, match="sibling.*position|position.*sibling"):
        verify_response(challenge, tampered, bundle)
