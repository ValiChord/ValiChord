"""Tests for Merkle construction selection by format version.

The rest of the suite proves the refactor changed no behaviour. These prove the
dispatch layer itself does something, which is otherwise invisible while only one
construction is registered.

See `spec/v2-backlog/04-version-dispatch.md`.
"""

from __future__ import annotations

import pytest

from valichord_attestation import merkle_v1, merkle_v2
from valichord_attestation.bundle import Bundle, Metric
from valichord_attestation.challenge import Challenge
from valichord_attestation.merkle import (
    DEFAULT_FORMAT_VERSION,
    UnknownFormatVersion,
    construction_for,
    leaf_hash,
    merkle_proof,
    merkle_root,
    root_from_path,
    verify_faithfulness,
)
from valichord_attestation.response import build_response, verify_response

SAMPLES = [{"index": i, "output": str(i)} for i in range(5)]


# ---------------------------------------------------------------------------
# Version → construction mapping
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("version", merkle_v1.FORMAT_VERSIONS)
def test_v1_versions_map_to_v1_construction(version: str) -> None:
    assert construction_for(version) is merkle_v1


def test_none_selects_the_default() -> None:
    assert construction_for(None) is construction_for(DEFAULT_FORMAT_VERSION)


def test_unknown_version_raises_rather_than_falling_back() -> None:
    """A silent fallback would produce a confident wrong root for an unknown bundle."""
    with pytest.raises(UnknownFormatVersion) as exc:
        construction_for("v99")
    assert "v99" in str(exc.value)


def test_unknown_version_error_names_what_is_known() -> None:
    with pytest.raises(UnknownFormatVersion) as exc:
        construction_for("nonsense")
    assert "v1.2" in str(exc.value)


# ---------------------------------------------------------------------------
# The wrappers agree with the construction they dispatch to
# ---------------------------------------------------------------------------

def test_explicit_version_matches_the_default() -> None:
    assert merkle_root(SAMPLES) == merkle_root(SAMPLES, format_version=DEFAULT_FORMAT_VERSION)


def test_the_default_is_not_a_v1_version() -> None:
    """Guards against the default silently reverting: v1 is frozen, not current."""
    assert DEFAULT_FORMAT_VERSION not in merkle_v1.FORMAT_VERSIONS


def test_wrappers_match_the_underlying_module() -> None:
    assert merkle_root(SAMPLES, format_version="v1.2") == merkle_v1.merkle_root(SAMPLES)
    assert leaf_hash(SAMPLES[0], format_version="v1.2") == merkle_v1.leaf_hash(SAMPLES[0])
    assert merkle_proof(SAMPLES, 2, format_version="v1.2") == merkle_v1.merkle_proof(SAMPLES, 2)


def test_wrappers_match_the_v2_module() -> None:
    assert merkle_root(SAMPLES, format_version="v2") == merkle_v2.merkle_root(SAMPLES)
    assert leaf_hash(SAMPLES[0], format_version="v2") == merkle_v2.leaf_hash(SAMPLES[0])
    assert merkle_proof(SAMPLES, 2, format_version="v2") == merkle_v2.merkle_proof(SAMPLES, 2)


@pytest.mark.parametrize("fn", [merkle_root, leaf_hash, verify_faithfulness, root_from_path])
def test_every_wrapper_rejects_an_unknown_version(fn) -> None:
    """Whatever the entry point, an unrecognised version must not be guessed at."""
    args = {
        "merkle_root": ([SAMPLES],),
        "leaf_hash": ([SAMPLES[0]],),
        "verify_faithfulness": (["deadbeef", 0, SAMPLES[0], []],),
        "root_from_path": ([b"\x00" * 32, []],),
    }[fn.__name__][0]
    with pytest.raises(UnknownFormatVersion):
        fn(*args, format_version="v99")


# ---------------------------------------------------------------------------
# root_from_path is the single path-walking implementation
# ---------------------------------------------------------------------------

def test_root_from_path_agrees_with_verify_faithfulness() -> None:
    """These were two separate implementations before; they must not drift apart."""
    root = merkle_root(SAMPLES)
    for i in range(len(SAMPLES)):
        proof = merkle_proof(SAMPLES, i)
        walked = root_from_path(leaf_hash(SAMPLES[i]), proof).hex()
        assert walked == root
        assert verify_faithfulness(root, i, SAMPLES[i], proof)


# ---------------------------------------------------------------------------
# verify_response takes its construction from the bundle, not the default
# ---------------------------------------------------------------------------

def _bundle(root: str, total: int, format_version: str = "v1.2") -> Bundle:
    return Bundle(
        format_version=format_version,
        generated_at="2026-08-18T00:00:00+00:00",
        model_id="m",
        task_id="t",
        metrics=[Metric(key="accuracy", value=1.0)],
        samples_total=total,
        samples_completed=total,
        outputs_merkle_root=root,
    )


def test_verify_response_uses_the_bundle_version() -> None:
    challenge = Challenge(bundle_hash="a" * 64, verifier_nonce=bytes(range(16)), k=3)
    response = build_response(challenge, SAMPLES, format_version="v1.2")
    bundle = _bundle(merkle_root(SAMPLES, format_version="v1.2"), len(SAMPLES), "v1.2")
    assert verify_response(challenge, response, bundle) is True


def test_verify_response_rejects_a_bundle_declaring_an_unknown_version() -> None:
    """Better to raise than to check a root against a construction we guessed."""
    challenge = Challenge(bundle_hash="a" * 64, verifier_nonce=bytes(range(16)), k=3)
    response = build_response(challenge, SAMPLES)
    bundle = _bundle(merkle_root(SAMPLES), len(SAMPLES), "v99")
    with pytest.raises(UnknownFormatVersion):
        verify_response(challenge, response, bundle)
