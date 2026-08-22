"""Bridge between an attestation bundle and the ValiChord Holochain protocol.

This module is **client-side only**. It adds no entry types, changes no integrity
zome, and puts no bundle content on any DHT. See
``docs/PROTOCOL_INTEGRATION_BOUNDARY.md`` for the four preconditions it is built
under; every function here exists to satisfy one of them.

What it does
------------
The protocol identifies the thing under validation by
``ValidationRequest.data_hash``, an ``ExternalHash``. On the Rust side that value
is produced inside the *private* ``researcher_repository`` DNA by
``compute_data_hash(data: Vec<u8>)``, which SHA-256s the bytes it is given and
wraps the digest as an ``ExternalHash``. The data bytes never leave that DNA.

So the client's job is to decide **which bytes** to hand over, and to be able to
predict the resulting ``ExternalHash`` so that a third party can check a
published record against a bundle without running a conductor.

The load-bearing decision, and why
----------------------------------
``data_hash`` is derived from ``content_hash`` — the canonical encoding with
``Bundle.meta`` **excluded** — not from ``bundle_hash``.

``data_hash`` identifies a *claim*, and the same claim submitted twice from two
machines differs in ``generated_at`` and in whatever provenance the harness put
in ``meta``. Under ``bundle_hash`` those would be two unrelated claims; under
``content_hash`` they are one, which is what ``content_hash`` was defined for
("is this the same science?").

.. warning::
   **This makes the ``meta`` trap load-bearing on-chain.** ``meta`` is excluded
   from ``content_hash``, so any value placed there that *could change a result*
   becomes invisible to ``data_hash`` — two materially different claims would
   collide as one identifier, permanently, on an immutable record. The trap is
   documented in ``spec/format-backlog/README.md`` and it is the reason backlog
   items 02-05 (judge configuration, rubric versions, thresholds, repeatability
   conditions) stop being tidy-ups the moment a bridge exists.

   Nothing here can fix that. It is recorded so the cost is chosen rather than
   discovered.

Verification status
-------------------
The ``ExternalHash`` construction below is **observed**, not asserted: the
algorithm was read from ``holo_hash``'s ``encode.rs`` upstream and then checked
against a 39-byte hash produced by a real ValiChord conductor
(``tests/test_protocol.py::test_matches_a_hash_a_real_conductor_produced``).

It has **not** been checked round-trip against a live ``compute_data_hash``
call. That is the remaining gap and it needs a conductor.
"""

from __future__ import annotations

import base64
import hashlib

from .bundle import Bundle
from .canonical import content_hash, content_preimage

__all__ = [
    "EXTERNAL_HASH_PREFIX",
    "holo_dht_location_bytes",
    "external_hash_from_core",
    "encode_holo_hash",
    "decode_holo_hash",
    "submission_bytes",
    "data_hash",
    "data_hash_b64",
    "reproduction_bundle_hash",
]

# ---------------------------------------------------------------------------
# HoloHash primitives
# ---------------------------------------------------------------------------

#: 3-byte multihash prefix for ``ExternalHash``. Confirmed two ways: the comment
#: on ``compute_data_hash`` in ``researcher_repository_coordinator``, and the
#: leading bytes of a real conductor-produced hash (see the test module).
EXTERNAL_HASH_PREFIX = b"\x84\x2f\x24"

HOLO_HASH_CORE_LEN = 32
HOLO_HASH_LOC_LEN = 4
HOLO_HASH_FULL_LEN = len(EXTERNAL_HASH_PREFIX) + HOLO_HASH_CORE_LEN + HOLO_HASH_LOC_LEN


def holo_dht_location_bytes(core32: bytes) -> bytes:
    """Return the 4-byte DHT location for a 32-byte hash core.

    BLAKE2b with a **16-byte** digest over the core, then the four 4-byte groups
    of that digest XOR-folded together. Ported from ``holo_hash::encode``.

    .. note::
       A plausible-sounding wrong version XORs the eight 4-byte groups of the
       *32-byte core* directly, with no BLAKE2b step — that is what a secondary
       summary of the algorithm claimed. It produces a well-formed hash the
       conductor rejects. The test module pins this against a real hash so the
       wrong version cannot pass quietly.
    """
    if len(core32) != HOLO_HASH_CORE_LEN:
        raise ValueError(
            f"only {HOLO_HASH_CORE_LEN}-byte hashes are supported, got {len(core32)}"
        )
    digest = hashlib.blake2b(core32, digest_size=16).digest()
    out = bytearray(digest[0:4])
    for i in range(4, 16, 4):
        out[0] ^= digest[i]
        out[1] ^= digest[i + 1]
        out[2] ^= digest[i + 2]
        out[3] ^= digest[i + 3]
    return bytes(out)


def external_hash_from_core(core32: bytes) -> bytes:
    """Wrap a 32-byte digest as a 39-byte ``ExternalHash``.

    Equivalent to Rust's ``ExternalHash::from_raw_32``.
    """
    if len(core32) != HOLO_HASH_CORE_LEN:
        raise ValueError(
            f"an ExternalHash core is {HOLO_HASH_CORE_LEN} bytes, got {len(core32)}"
        )
    return EXTERNAL_HASH_PREFIX + core32 + holo_dht_location_bytes(core32)


def encode_holo_hash(raw: bytes) -> str:
    """Render a raw HoloHash in the form the conductor and UI use.

    Multibase ``u`` prefix followed by unpadded base64url — e.g.
    ``uhC8k4j2xO83gyCFCBMTAtx2Nyy_i_Yr4oDk-X1XJlbOZsI0-bYNT``.
    """
    if len(raw) != HOLO_HASH_FULL_LEN:
        raise ValueError(f"a HoloHash is {HOLO_HASH_FULL_LEN} bytes, got {len(raw)}")
    return "u" + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_holo_hash(encoded: str) -> bytes:
    """Inverse of :func:`encode_holo_hash`. Raises on anything malformed."""
    if not encoded.startswith("u"):
        raise ValueError("a HoloHash string starts with the multibase prefix 'u'")
    body = encoded[1:]
    raw = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
    if len(raw) != HOLO_HASH_FULL_LEN:
        raise ValueError(f"decoded {len(raw)} bytes, expected {HOLO_HASH_FULL_LEN}")
    return raw


# ---------------------------------------------------------------------------
# Bundle -> protocol
# ---------------------------------------------------------------------------


def submission_bytes(bundle: Bundle) -> bytes:
    """Return the exact bytes to pass to the DNA's ``compute_data_hash``.

    This is the ``content_hash`` preimage: the canonical (RFC 8785) encoding of
    the bundle with ``meta`` removed. Handing these bytes to
    ``compute_data_hash`` yields a ``data_hash`` whose 32-byte core **is** the
    bundle's ``content_hash``, which is what makes :func:`data_hash` predictable
    off-chain.

    These bytes go only to the private, single-agent ``researcher_repository``
    DNA. They are never written to a public DHT (boundary precondition 3.3).
    """
    return content_preimage(bundle)


def data_hash(bundle: Bundle) -> bytes:
    """Return the 39-byte ``ExternalHash`` the protocol will hold for this bundle.

    Computed rather than fetched: a verifier can derive this from a bundle alone
    and compare it against a published ``ValidationRequest`` without trusting
    anyone's report of what was submitted.
    """
    return external_hash_from_core(bytes.fromhex(content_hash(bundle)))


def data_hash_b64(bundle: Bundle) -> str:
    """:func:`data_hash` in the ``uhC8k…`` form used by the conductor and URLs."""
    return encode_holo_hash(data_hash(bundle))


def reproduction_bundle_hash(bundle: Bundle) -> bytes:
    """Return the bytes a validator binds into their sealed attestation.

    Maps to ``ValidationAttestation.reproduction_bundle_hash``, typed
    ``Option<Vec<u8>>`` on the Rust side and treated there as **opaque** — the
    protocol never parses a bundle (boundary precondition 3.2).

    This is ``content_hash``, not ``bundle_hash``: it binds the verdict to the
    validator's own *result*, and must not change because their machine name or
    run timestamp differs.

    .. warning::
       This value is bound into the commitment at seal time. It must be
       byte-identical at commit and at reveal or the reveal fails hash
       verification. Do not recompute it from a re-serialised bundle at reveal
       time; carry the bytes.
    """
    return bytes.fromhex(content_hash(bundle))
