# Backlog: hardware provenance for researcher and validator

**Status:** Open. **Category: 🟠 expensive after the next network break, and 🔴 for records already written.**
**Needs the rebuild window: yes.**
**Raised by:** Ceri, 2026-08-22 — *"info such as the hardware of the researcher and validator
should also be part of the harmony record."*
**Related:** 01 (same integrity-zome change; scope together), and format-backlog 05
(repeatability vs reproducibility, which is the vocabulary for what this field is *for*).

## Problem

**There is no hardware field anywhere.** Not on `HarmonyRecord`, whose eight fields are
`request_ref`, `outcome`, `agreement_level`, `participating_validators`, `validator_types`,
`validation_duration_secs`, `discipline`, `validators_requested`
(`governance_integrity/src/lib.rs`). Not in the attestation bundle either.

So when a researcher and a validator get different results, **the record cannot say whether the
environment differed**. A disagreement that was caused by hardware reads identically to a
disagreement about the science.

This is the same shape as the problem `validators_requested` was added to fix: *"5 validators"*
read the same whether 5 of 5 or 5 of 7 reported, and the fix was to record the missing number
rather than to reason about it later.

## Why it is 🔴 as well as 🟠

Every HarmonyRecord written before this field exists will never have it. The environment of those
rounds is not recoverable afterwards — nobody kept it. So the cost is not only the network break;
it is that the records written in the meantime are permanently thinner than the ones written after.

That does not make it urgent. It makes it a thing to decide deliberately rather than to arrive at.

## ⚠️ The reason this is not obvious: DNA 4 is public and permanent

Hardware detail is identifying. GPU model, RAM, OS build, driver version and hostname together
fingerprint a machine, often a lab, sometimes a person.

Publishing that for **validators**, permanently and publicly, cuts against the rest of the design.
It would build a standing public inventory of who owns what equipment and when they were working
— and it cannot be withdrawn, because nothing on that DHT can. For a validator using a personal
machine it is straightforwardly personal data on a network with no delete.

The protocol's headline privacy claim is that sensitive data cannot reach the shared network *by
architecture rather than policy*. A free-text hardware string on a public immutable record would
be the first thing to test that claim, and it would fail it.

## Three shapes, in order of what they give away

| | Shape | Explains result differences? | Fingerprint risk |
|---|---|---|---|
| **A** | **Coarse class only** — e.g. datacentre GPU / consumer GPU / CPU-only | Most of them | Very low |
| **B** | **Detail held privately, digest on the public record** | All of them, on challenge | Low — the detail is disclosed to someone who asks, not broadcast |
| **C** | **Full detail public** | All of them, immediately | High, permanent, unwithdrawable |

**B is the shape the rest of the protocol already uses** — commit publicly, disclose selectively.
It also matches `docs/PROTOCOL_INTEGRATION_BOUNDARY.md` §3.3, which says payload *content* stays
off a public DHT and only digests cross. **It is not decided, and it is Ceri's call.**

## Open

- **Which of A / B / C**, and whether researcher and validator get the same treatment. A
  researcher publishing their own environment is a different consent question from a validator
  having theirs published.
- **What counts as "hardware".** CPU, GPU, RAM, OS, driver, container image, random seed handling?
  For AI evaluation, GPU non-determinism and batch size can move results; OS build usually cannot.
  An over-broad field invites a fingerprint for no analytical gain.
- **Who asserts it?** Self-reported by definition, so it is **asserted, not observed**
  (`spec/conformance.md` §3.17–3.18). The record must not imply it was verified. Nothing in the
  protocol can check it.
- **Optional or required?** A required field that people fill with `"unknown"` is worse than an
  optional one, because absence at least reads as absence.

## Not open

- It does not go on a public DHT as free text. See above.
