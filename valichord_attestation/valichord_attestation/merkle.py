"""Merkle construction selection.

The construction that produced a bundle's ``outputs_merkle_root`` is determined by
that bundle's ``format_version``. This module maps one to the other, so a bundle
written under any released format version stays verifiable after a newer
construction ships.

Every public function here takes a keyword-only ``format_version``. Where the
caller holds a :class:`~valichord_attestation.bundle.Bundle`, pass
``bundle.format_version`` — never rely on the default, because the default tracks
what this library *writes*, not what the bundle in front of you *used*.

See `spec/v2-backlog/04-version-dispatch.md` for the reasoning, and
`merkle_v1.py` for the frozen v1 construction.
"""

from __future__ import annotations

from types import ModuleType

from . import merkle_v1, merkle_v2

#: format_version → the module implementing that version's construction.
CONSTRUCTIONS: dict[str, ModuleType] = {
    **{v: merkle_v1 for v in merkle_v1.FORMAT_VERSIONS},
    **{v: merkle_v2 for v in merkle_v2.FORMAT_VERSIONS},
}

#: The construction used when writing new bundles.
#:
#: Readers must NOT inherit this. It tracks what the library writes, not what the
#: bundle in front of them used — pass ``bundle.format_version`` when verifying.
#: See `spec/attestation_format_v2.md` §2.
DEFAULT_FORMAT_VERSION = "v2"


class UnknownFormatVersion(ValueError):
    """Raised when a format version has no registered Merkle construction.

    Deliberately not a silent fallback to the default: a bundle declaring a
    version this library does not know is one whose root it cannot reproduce,
    and guessing would produce a confident wrong answer.
    """


def construction_for(format_version: str | None = None) -> ModuleType:
    """Return the Merkle construction module for `format_version`."""
    version = format_version or DEFAULT_FORMAT_VERSION
    try:
        return CONSTRUCTIONS[version]
    except KeyError:
        known = ", ".join(sorted(CONSTRUCTIONS))
        raise UnknownFormatVersion(
            f"No Merkle construction registered for format_version {version!r}. Known: {known}."
        ) from None


def leaf_hash(sample: dict, *, format_version: str | None = None) -> bytes:
    """SHA-256 leaf hash of a per-sample output dict, per the given format version."""
    return construction_for(format_version).leaf_hash(sample)


def merkle_root(samples: list[dict], *, format_version: str | None = None) -> str:
    """Merkle root over per-sample output dicts, as a 64-character hex string."""
    return construction_for(format_version).merkle_root(samples)


def merkle_proof(
    samples: list[dict], index: int, *, format_version: str | None = None
) -> list[dict]:
    """Inclusion proof for the sample at `index`, as a list of path steps."""
    return construction_for(format_version).merkle_proof(samples, index)


def root_from_path(
    leaf: bytes, proof: list[dict], *, format_version: str | None = None
) -> bytes:
    """Walk an inclusion proof from a leaf digest up to the root digest.

    Used by challenge-response verification, which starts from a leaf hash the
    holder supplied rather than a sample it can re-hash.
    """
    return construction_for(format_version).root_from_path(leaf, proof)


def verify_faithfulness(
    root_hex: str,
    sample_index: int,
    sample: dict,
    proof: list[dict],
    *,
    format_version: str | None = None,
) -> bool:
    """Verify that `sample` is included in the tree with root `root_hex`.

    ``format_version`` must match the version of the bundle the root came from.
    It cannot be inferred: a root is 32 bytes of hex under every construction,
    so a root produced by one and checked under another simply returns False —
    indistinguishable from a genuine tampering result. That ambiguity is the
    reason this parameter exists.
    """
    return construction_for(format_version).verify_faithfulness(
        root_hex, sample_index, sample, proof
    )
