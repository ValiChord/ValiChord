# attestation format v2 — backlog

> ## ✅ All four shipped, 2026-08-18. v2 is the current format.
>
> Spec: `../attestation_format_v2.md`. Construction: `merkle_v2.py`.
> Vectors: `../../tests/vectors/merkle_v2.json`. Example: `../../examples/simple_eval_v2.json`.
>
> | | | |
> |---|---|---|
> | 01 | domain separation | RFC 6962 `0x00`/`0x01` prefixes |
> | 02 | odd-node promotion | collision gone; the v1.2 vector proves it under both |
> | 03 | empty and single leaf | both defined; `build_bundle` still refuses empty |
> | 04 | version dispatch | construction selected from `bundle.format_version` |
>
> **The files below are kept unedited as the design record** — the problem each
> item solved, what was known at the time, and the open questions. Where a file
> says "proposed", read it as "was proposed, and shipped". Two answers came from
> outside the notes rather than from them, and are worth carrying forward:
>
> - `04` predicted the awkward call site would be `verify_faithfulness`. It was
>   also `verify_response`, which held a **second inlined copy of the pair
>   hashing** — found only by reading the file. A v2 that shipped without that
>   fix would have left challenge-response silently computing v1 paths.
> - `03` asked whether an empty sample list should be a valid bundle.
>   `build_bundle` had already answered by rejecting it, so the format defines a
>   root the reference implementation declines to emit.

This directory tracks the changes that require a `format_version` bump to `"v2"`.
Each file is a proposal skeleton: problem, the v1.2 position, the proposed v2 direction,
open questions.

Section 12 of `spec/attestation_format_v1.md` is the rule that put them here:

> **Breaking changes** (removing required fields, changing canonical encoding rules,
> changing Merkle construction) MUST increment to `"v2"`.

All four items below change the Merkle construction or how it is selected, so they are one
release, not four. Shipping them separately would mean three intermediate constructions,
each of which someone could implement against.

## Why this exists as a directory rather than a line in PROJECT_STATUS

Item 01 was recorded on 2026-07-05 as one line in a security-audit entry, and on
2026-08-16 an outside contributor was told it was "on our v2 consideration list" — which
was true, but took a targeted search of the repo to confirm. A roadmap that only one
person can find is a roadmap that gets restated from memory. Two external projects are
now scoping work around v2; they need to be able to read it.

## Files

- `01-merkle-domain-separation.md` — RFC 6962 leaf/node prefixes; no second-preimage separation today
- `02-odd-node-promotion.md` — odd levels are padded by duplication, so two sample lists share a root
- `03-empty-and-single-leaf.md` — neither case is defined in the spec; the library's behaviour is incidental
- `04-version-dispatch.md` — how v1.1/v1.2 bundles stay verifiable once the construction changes

01 and 02 are both solved by adopting RFC 6962 §2.1 wholesale rather than borrowing from
it piecemeal. 03 falls out of the same decision. **04 is the item that determines whether
v2 is buildable**, and it is the only one that is genuinely open design rather than
adopting a standard.

## Who is waiting on this

Three parties are implementing against v1.2 as of 2026-08-18, and two of them know the
construction is moving:

| Who | What | Told about v2? |
|---|---|---|
| `studio-11-co/falsify-cookbook` | Pattern 13 demo; wrote the v1.2 conformance vectors in `tests/vectors/` | yes — already implements RFC 6962 and has offered to write the v2 vector set |
| Future AGI (`tfc/utils`) | JCS + Merkle module for eval-run export | yes — advised to build RFC 6962 rather than mirror v1.2 |
| BRONCO (`KeilerHirsch-Labs`) | crosswalk of its measurement requirements onto v1.2 | yes — told the tree is provisional, the field set is not |

The falsify demo already implements the target construction. That means v2 has a reference
implementation, written by someone outside this project, before v2 exists here.

## Sequencing note

`tests/vectors/merkle_v1_2.json` pins the current construction with seven cases and a
documented collision. Those vectors must **not** be edited when v2 lands — they are what
keeps old bundles verifiable (see `04`). A v2 vector set is a new file alongside them.
