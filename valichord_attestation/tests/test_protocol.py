"""Tests for the bundle -> ValiChord protocol bridge.

The load-bearing test in this file is
:func:`test_matches_a_hash_a_real_conductor_produced`. Everything else checks
self-consistency, which a wrong implementation can satisfy perfectly well.
"""

from __future__ import annotations

import base64
import hashlib

import pytest

from valichord_attestation.bundle import Bundle, Metric
from valichord_attestation.canonical import (
    bundle_to_dict,
    content_hash,
    content_preimage,
    hash_bundle,
)
from valichord_attestation.protocol import (
    EXTERNAL_HASH_PREFIX,
    HOLO_HASH_FULL_LEN,
    data_hash,
    data_hash_b64,
    decode_holo_hash,
    encode_holo_hash,
    external_hash_from_core,
    holo_dht_location_bytes,
    reproduction_bundle_hash,
    submission_bytes,
)

# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------

# A real HarmonyRecord ExternalHash, produced by a running ValiChord conductor
# on the Oracle demo server and recorded in
# demo/bundles_worked_example/bundle_capsule-0851068_v1_*.json.
#
# Its DHT location bytes were not computed by this library and cannot have been
# influenced by it. That is what makes it evidence rather than a restatement.
REAL_CONDUCTOR_HASH = "uhC8k4j2xO83gyCFCBMTAtx2Nyy_i_Yr4oDk-X1XJlbOZsI0-bYNT"


def _sample_bundle(meta: dict | None = None) -> Bundle:
    return Bundle(
        format_version="v2",
        generated_at="2026-08-22T09:00:00+00:00",
        model_id="gpt-4o-2024-08-06",
        task_id="gsm8k",
        metrics=[Metric(key="accuracy", value=0.847, stderr=0.011)],
        samples_total=10,
        samples_completed=10,
        outputs_merkle_root="a" * 64,
        meta=meta,
    )


# ---------------------------------------------------------------------------
# The test that can actually fail for the right reason
# ---------------------------------------------------------------------------


def test_matches_a_hash_a_real_conductor_produced():
    """Our location algorithm reproduces a hash Holochain itself generated.

    If this fails, the port of ``holo_hash::encode`` is wrong and every
    ``data_hash`` this module produces would be rejected by a conductor.
    """
    raw = decode_holo_hash(REAL_CONDUCTOR_HASH)

    assert len(raw) == HOLO_HASH_FULL_LEN == 39
    assert raw[:3] == EXTERNAL_HASH_PREFIX

    core = raw[3:35]
    location_from_the_conductor = raw[35:]

    assert holo_dht_location_bytes(core) == location_from_the_conductor
    # And the whole hash rebuilds from its core alone.
    assert external_hash_from_core(core) == raw


def test_the_plausible_wrong_algorithm_does_not_pass():
    """Negative control: XOR-folding the core directly must NOT match.

    A secondary summary of the algorithm described it as XORing the eight
    4-byte groups of the 32-byte core, with no BLAKE2b step. That is wrong, and
    this test is here so the wrong version cannot be reintroduced and pass the
    test above by accident.
    """
    raw = decode_holo_hash(REAL_CONDUCTOR_HASH)
    core, real_location = raw[3:35], raw[35:]

    wrong = bytearray(4)
    for i in range(0, 32, 4):
        for j in range(4):
            wrong[j] ^= core[i + j]

    assert bytes(wrong) != real_location
    assert holo_dht_location_bytes(core) == real_location


# ---------------------------------------------------------------------------
# HoloHash primitives
# ---------------------------------------------------------------------------


def test_encode_decode_round_trips():
    raw = decode_holo_hash(REAL_CONDUCTOR_HASH)
    assert encode_holo_hash(raw) == REAL_CONDUCTOR_HASH


def test_encoding_is_unpadded_base64url():
    encoded = encode_holo_hash(decode_holo_hash(REAL_CONDUCTOR_HASH))
    assert encoded.startswith("u")
    assert "=" not in encoded
    assert "+" not in encoded and "/" not in encoded


@pytest.mark.parametrize("bad_len", [0, 31, 33, 36, 39])
def test_location_requires_exactly_32_bytes(bad_len):
    with pytest.raises(ValueError):
        holo_dht_location_bytes(b"\x00" * bad_len)


def test_external_hash_requires_exactly_32_bytes():
    with pytest.raises(ValueError):
        external_hash_from_core(b"\x00" * 31)


def test_decode_rejects_a_missing_multibase_prefix():
    with pytest.raises(ValueError):
        decode_holo_hash(REAL_CONDUCTOR_HASH[1:])


def test_decode_rejects_a_wrong_length():
    short = "u" + base64.urlsafe_b64encode(b"\x00" * 20).decode().rstrip("=")
    with pytest.raises(ValueError):
        decode_holo_hash(short)


def test_encode_rejects_a_wrong_length():
    with pytest.raises(ValueError):
        encode_holo_hash(b"\x00" * 38)


# ---------------------------------------------------------------------------
# Bundle -> protocol
# ---------------------------------------------------------------------------


def test_submission_bytes_are_the_content_hash_preimage():
    """The invariant the whole bridge rests on.

    The DNA SHA-256s whatever bytes it is handed. If these bytes are not the
    content_hash preimage, data_hash stops being predictable off-chain and a
    verifier can no longer check a published record against a bundle.
    """
    b = _sample_bundle(meta={"host": "laptop-01"})
    assert hashlib.sha256(submission_bytes(b)).hexdigest() == content_hash(b)


def test_data_hash_core_is_the_content_hash():
    b = _sample_bundle()
    assert data_hash(b)[3:35].hex() == content_hash(b)


def test_data_hash_is_a_well_formed_external_hash():
    raw = data_hash(_sample_bundle())
    assert len(raw) == 39
    assert raw[:3] == EXTERNAL_HASH_PREFIX
    assert raw[35:] == holo_dht_location_bytes(raw[3:35])


def test_data_hash_b64_decodes_back():
    b = _sample_bundle()
    assert decode_holo_hash(data_hash_b64(b)) == data_hash(b)


def test_meta_does_not_change_the_identity_of_a_claim():
    """Two submissions of the same science from different machines are one claim.

    This is the reason data_hash derives from content_hash rather than
    bundle_hash, and it is the property that would break if that changed.
    """
    plain = _sample_bundle()
    with_provenance = _sample_bundle(meta={"host": "ci-runner-7", "run": 3})

    assert hash_bundle(plain) != hash_bundle(with_provenance)
    assert data_hash(plain) == data_hash(with_provenance)


def test_a_different_result_is_a_different_claim():
    a = _sample_bundle()
    b = _sample_bundle()
    b.metrics = [Metric(key="accuracy", value=0.912, stderr=0.011)]

    assert data_hash(a) != data_hash(b)


def test_a_different_merkle_root_is_a_different_claim():
    a = _sample_bundle()
    b = _sample_bundle()
    b.outputs_merkle_root = "b" * 64

    assert data_hash(a) != data_hash(b)


def test_reproduction_bundle_hash_is_32_raw_bytes_of_content_hash():
    b = _sample_bundle(meta={"host": "validator-2"})
    rbh = reproduction_bundle_hash(b)

    assert len(rbh) == 32
    assert rbh.hex() == content_hash(b)


def test_reproduction_bundle_hash_survives_a_provenance_change():
    """It binds a verdict to a result, not to the machine that produced it.

    A validator whose hostname differs must not produce a different binding —
    the value is sealed into the commitment and must match byte-for-byte at
    reveal.
    """
    assert reproduction_bundle_hash(_sample_bundle()) == reproduction_bundle_hash(
        _sample_bundle(meta={"host": "elsewhere"})
    )


# ---------------------------------------------------------------------------
# The extraction in canonical.py must not have changed any hash
# ---------------------------------------------------------------------------


def test_content_preimage_still_produces_the_documented_content_hash():
    for meta in (None, {}, {"a": 1}, {"nested": {"b": [1, 2, 3]}}):
        b = _sample_bundle(meta=meta)
        assert hashlib.sha256(content_preimage(b)).hexdigest() == content_hash(b)


def test_content_preimage_excludes_meta_and_nothing_else():
    b = _sample_bundle(meta={"secret": "path/to/home"})
    text = content_preimage(b).decode("utf-8")

    assert "secret" not in text
    assert "path/to/home" not in text
    for key in bundle_to_dict(b):
        if key != "meta":
            assert f'"{key}"' in text
