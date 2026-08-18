# v2 backlog item: promote odd nodes instead of duplicating them

**Status:** Found 2026-08-17 while reviewing `merkle.py` against the falsify-cookbook
Pattern 13 demo. Not on the 2026-07-05 audit list — this one was missed.
**Related:** `01-merkle-domain-separation.md` (same construction change, same release).

## Problem

`_build_tree` pads an odd level by duplicating its last node:

```python
if len(current) % 2 == 1:
    current = current + [current[-1]]
```

So a sample list and the same list with its final sample repeated produce an identical
root. Pinned as a vector in `tests/vectors/merkle_v1_2_odd_node.json`:

```
[A, B, C]     -> 82dbd49432097a1998c98526931b4b12dbd1e17b067dcfc3fc463b476841a9f4
[A, B, C, C]  -> 82dbd49432097a1998c98526931b4b12dbd1e17b067dcfc3fc463b476841a9f4
```

The root therefore does not identify the leaf list, which is the one thing a Merkle root
is supposed to do. This is the same defect as CVE-2012-2459 in Bitcoin's block Merkle
tree, and it arises from the same padding rule.

## How exploitable is it today

Partially mitigated, and worth being precise about why.

`samples_completed` is a separate bundle field and is included in `content_hash`, so a
bundle claiming 3 samples and one claiming 4 do not compare equal even when their roots
match. A verifier checking the count would notice the discrepancy.

But the mitigation is external to the tree. Anything reasoning about the root alone — a
selective-disclosure proof, a cross-bundle comparison keyed on `outputs_merkle_root`, a
future protocol that carries the root without the count — inherits the ambiguity. The
Holochain side stores `outputs_merkle_root` as the `data_hash` of a `ValidationRequest`,
which is exactly that case.

## v1.2 position

Duplication, as above. Pinned by vector, with a test that asserts the collision still
reproduces and a docstring stating it documents a limitation rather than endorsing one.

## Proposed v2 direction

RFC 6962 §2.1 splits at the largest power of two below `n` and promotes the odd subtree
unchanged. No padding, so no collision:

```
MTH(D[n]) = SHA-256(0x01 || MTH(D[0:k]) || MTH(D[k:n]))    where k = largest power of 2 < n
```

Adopting `01` in full delivers this for free. There is no version of v2 where domain
separation lands and this does not.

## Open questions

1. When the construction changes, `test_odd_node_padding_collision_is_still_present`
   must be **inverted**, not deleted — asserting the two inputs now produce different
   roots. The contributor's docstring already says so. Inverting it is the regression test
   that this item actually shipped.
2. Does anything downstream key on `outputs_merkle_root` in a way that assumed uniqueness?
   `content_hash` includes it, and the Holochain `ValidationRequest.data_hash` carries it.
   Neither breaks, but both should be re-read once rather than assumed.
