# v2 backlog item: Merkle leaf/node domain separation

**Status:** Deferred from the 2026-07-05 security/efficiency audit (item 3 of "still deferred").
**Blocks:** nothing — it is a `format_version` bump, not a fix to shipped bundles.
**Related:** `02-odd-node-promotion.md` (same construction change, same release).

## Problem

`merkle.py` hashes leaves and internal nodes identically:

```python
def leaf_hash(sample: dict) -> bytes:
    return hashlib.sha256(jcs.canonicalize(sample)).digest()

def _hash_pair(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(left + right).digest()
```

Nothing distinguishes "this digest is a leaf" from "this digest is an interior node". That
is the precondition for the classical Merkle second-preimage attack: an attacker who knows
a tree can present an interior node as though it were a leaf, or claim a different tree
shape yielding the same root. RFC 6962 §2.1 exists to prevent exactly this, by prefixing
`0x00` before leaf data and `0x01` before concatenated children.

## How exploitable is it today

Not, in practice, and the reason matters for how urgently this is treated.

A leaf preimage is JCS-canonical JSON of a dict — valid UTF-8 beginning with `{`. An
interior preimage is exactly 64 bytes, being two concatenated SHA-256 digests. To pass an
interior node off as a leaf an attacker needs two digests whose concatenation is valid JCS
JSON, and they cannot choose those digests. The domains are effectively disjoint.

But that is a property of the encoding, not a property anyone stated or enforces. It holds
only while every leaf is a JCS-encoded dict. The moment a leaf may be a string, a byte
string, or a pre-hashed value, the separation disappears silently and nothing in the test
suite would notice.

So: not an emergency, and not something to leave resting on an accident either. This is
hygiene that removes a class of reasoning rather than a live vulnerability.

## v1.2 position

Bare hashing, as above. `tests/vectors/merkle_v1_2.json` pins it with seven cases.

## Proposed v2 direction

Adopt RFC 6962 §2.1 as written, rather than borrowing the prefixes alone:

```
MTH({})     = SHA-256()
MTH({d0})   = SHA-256(0x00 || d0)
MTH(D[n])   = SHA-256(0x01 || MTH(D[0:k]) || MTH(D[k:n]))    where k = largest power of 2 < n
```

Taking the whole definition rather than the prefixes also resolves `02` and `03`, which is
the argument for doing it in one move. The falsify-cookbook Pattern 13 demo took the
prefixes without the tree-shape rule and reproduced the odd-node bug independently — a
worked example of why piecemeal adoption is the wrong instinct.

## Open questions

1. Does `leaf_hash` remain public? It is currently exported and the challenge-response
   spec (§7) references it by name, so a v2 rename would break that reference. Likely
   answer: keep the name, change the body, and let `format_version` carry the difference.
2. Does the leaf prefix go before the JCS bytes (`SHA-256(0x00 || jcs(sample))`) or before
   an already-computed digest? RFC 6962 prefixes the raw leaf data, which argues for the
   former. State it explicitly in the spec either way — this is precisely the kind of
   detail a reimplementation gets wrong silently.
