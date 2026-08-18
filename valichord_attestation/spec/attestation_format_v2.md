# Valichord attestation bundle — format v2

**Status:** current. Supersedes v1.2 for newly written bundles.
**Scope of change:** the Merkle construction, and nothing else.

v2 exists because §12 of `attestation_format_v1.md` requires it:

> **Breaking changes** (removing required fields, changing canonical encoding
> rules, changing Merkle construction) MUST increment to `"v2"`.

Read `attestation_format_v1.md` for everything this document does not mention.
Every field, the JCS canonicalisation, `bundle_hash` and `content_hash`, the
challenge-response protocol and the threat model are unchanged and are not
restated here.

---

## 1. What changed

The Merkle tree over per-sample outputs now follows **RFC 6962 §2.1**, adopted
whole rather than in part.

With `d(i)` the JCS-canonical encoding of sample `i`:

```
MTH({})   = SHA-256()
MTH({d0}) = SHA-256(0x00 || d0)
MTH(D[n]) = SHA-256(0x01 || MTH(D[0:k]) || MTH(D[k:n]))
```

where `k` is the largest power of two strictly less than `n`.

Inclusion proofs follow RFC 6962 §2.1.1. The wire format of a proof step is
unchanged from v1 — a list of `{"position": "left"|"right", "sibling": "<64 hex>"}`
ordered leaf-first — so only the values differ, not the shape.

### 1.1 Leaf and interior nodes are domain-separated

A leaf digest is `SHA-256(0x00 || …)`; an interior digest is `SHA-256(0x01 || …)`.
Under v1 both were bare `SHA-256`, so no digest could be distinguished from the
other by inspection. That is the precondition for the classical Merkle
second-preimage attack, in which an interior node is presented as a leaf.

This was not exploitable in v1 in practice: a v1 leaf preimage was JCS JSON
beginning with `{`, an interior preimage was 64 arbitrary bytes, and the domains
did not overlap. But that was a property of the encoding rather than one the
format stated, and it would have disappeared silently the first time a leaf was
permitted to be anything other than a JSON object.

### 1.2 Odd nodes are promoted, not duplicated

v1 padded an odd level by duplicating its last node before pairing. Consequently
a sample list and the same list with its final sample repeated produced the same
root:

```
v1:  [A, B, C]  and  [A, B, C, C]   ->  same root
v2:  [A, B, C]  and  [A, B, C, C]   ->  different roots
```

This is the defect class of CVE-2012-2459. Under v1 a Merkle root did not
uniquely identify its leaf list. `samples.completed` is a separate committed
field, so a *bundle* remained distinguishable, but a root considered alone did
not — and roots are carried alone, for example as `ValidationRequest.data_hash`
on the Holochain side.

### 1.3 The empty and single-leaf cases are defined

| | v1 | v2 |
|---|---|---|
| empty list | raises; no defined root | `SHA-256()` |
| single sample | root **is** the bare leaf hash | `SHA-256(0x00 \|\| d0)` |

Neither case was stated in the v1 spec, so a reimplementation had to guess and
could not discover which guess interoperated.

**A defined root for the empty tree does not make an empty bundle valid.**
`build_bundle` rejects an empty sample list, and this specification does not
require an implementation to emit a bundle for a run with no completed samples.
The two questions are separate: the format defines the value so implementations
agree, the builder declines to produce it.

---

## 2. Migration

**Existing bundles do not change and must not be rewritten.**

Migration here means selecting a construction, not regenerating artefacts. A
bundle declares its own `format_version`, and that field determines which
construction produced its `outputs_merkle_root`:

| `format_version` | construction |
|---|---|
| `v1`, `v1.1`, `v1.2` | the v1 construction (`merkle_v1.py`) |
| `v2` | RFC 6962 §2.1 (`merkle_v2.py`) |

A verifier MUST select the construction from the bundle under examination, and
MUST NOT assume the version it writes. A root is 64 hex characters under every
version, so checking a v1.2 root under v2 does not error — it returns *does not
verify*, which is indistinguishable from genuine tampering. An implementation
that cannot determine the version MUST refuse rather than guess.

Reference implementation: `valichord_attestation.merkle.construction_for()`
raises `UnknownFormatVersion` for any version it does not recognise, rather than
falling back to a default.

### 2.1 For holders answering a challenge

A `ChallengeResponse` is verified against a specific bundle's root, so its leaf
hashes and proofs MUST be built under that bundle's version. `build_response`
takes a `format_version` for this reason. A response built under v2 against a
v1.2 bundle fails verification and is indistinguishable from a dishonest one.

### 2.2 What does not change

`bundle_hash` and `content_hash` are unchanged in construction. They cover the
bundle's fields, including `outputs_merkle_root` as a stored string, so they
inherit the new root for new bundles without any change to how they are
computed. Two bundles over the same samples, one v1.2 and one v2, have different
`content_hash` values — correctly, because they attest under different rules.

---

## 3. Conformance

`tests/vectors/merkle_v1_2.json` and `merkle_v1_2_odd_node.json` pin the v1
construction, including the odd-node collision, and are **frozen**. They are the
evidence that bundles written under v1.x still verify, and they must not be
edited or retargeted when a later version ships.

`tests/vectors/merkle_v2.json` pins this construction. A v3 would add a third
file rather than modify either.

An implementation claiming v2 conformance should reproduce every expected root
in the v2 file, and should additionally distinguish the two inputs in the
odd-node file — which is the single clearest check that the tree-shape rule was
adopted and not only the prefixes.
