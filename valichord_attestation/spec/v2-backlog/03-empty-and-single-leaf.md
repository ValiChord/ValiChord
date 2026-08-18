# v2 backlog item: define the empty and single-leaf cases

**Status:** Surfaced 2026-08-18. The v1.2 conformance vectors pin single-leaf behaviour but
not the empty case, and neither is stated in the spec.
**Related:** `01-merkle-domain-separation.md` — RFC 6962 defines both, so adopting it
answers this item rather than requiring a separate decision.

## Problem

Two edge cases have behaviour but no specification.

**Empty input.** `_build_tree` raises:

```python
if not leaves:
    raise ValueError("Cannot build a Merkle tree from an empty sample list")
```

That is a reasonable choice. It is also invisible to anyone reading
`spec/attestation_format_v1.md`, which says only that `outputs_merkle_root` is a
"SHA-256 hex Merkle root over per-sample output dicts". A reimplementation has three
defensible options — raise, return `SHA-256("")` per RFC 6962, or return a zero root — and
no way to discover which one interoperates.

**Single leaf.** `merkle_root([x])` returns `leaf_hash(x)` unchanged, because the
while-loop never executes. So for `n = 1` the root *is* the leaf, with no additional
hashing. Under RFC 6962 the single-leaf root is `SHA-256(0x00 || d0)`, which differs.

The v1.2 vector set covers `single_sample`, so that one is now pinned by test even though
it remains unstated in prose. The empty case is pinned by nothing.

## Why this is the same class of defect as 02

Two implementations disagree, both believe they conform, and nothing detects it. The
odd-node collision was findable because someone implemented the construction properly and
compared. These two are worse in one respect: they will not show up in any comparison that
uses a normal-sized sample list, so the first time they bite is on a degenerate input in
production.

## v1.2 position

- empty: raises `ValueError`, undocumented
- single leaf: returns the bare leaf hash, undocumented in prose, pinned by vector

## Proposed v2 direction

Adopt RFC 6962's definitions along with the rest of §2.1:

```
MTH({})   = SHA-256()                    # empty tree has a defined root
MTH({d0}) = SHA-256(0x00 || d0)          # single leaf is hashed, not passed through
```

Then decide separately whether the *library* still refuses empty input at the API
boundary. Those are different questions: the format can define a root for the empty tree
while `build_bundle` continues to reject a bundle with zero samples as meaningless. If it
does refuse, say so in the spec rather than leaving it as an implementation detail.

## Open questions

1. Should an empty sample list be a valid bundle at all? A run that completed zero samples
   is arguably a failed run, not an attestable one. `samples_completed: 0` with a defined
   root is representable; whether it should be is a separate call.
2. If the library keeps raising, does the conformance suite pin that as an error case, or
   pin the RFC value that the format defines but the library never emits? Suggest the
   former, matching the existing reject-vector convention — with a note that the format
   defines a value the reference implementation declines to produce.
