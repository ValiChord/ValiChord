# Protocol integration boundary — preconditions for plugging anything into ValiChord

**Status:** normative preconditions. **No integration has been built to these rules yet.**
**Applies to:** any external system proposing to write into, or be read by, the ValiChord
Holochain protocol (`valichord/`).

Normative keywords per BCP 14, as in `valichord_attestation/spec/conformance.md` §1.

> **This is not `INTEGRATION_GUIDE.md`.** That document covers the REST API — how a tool submits
> a deposit over HTTP and reads a verdict back. Nothing in it touches the protocol's trust
> boundary. **This document covers the other question: what must be true before an outside system
> is wired into the protocol itself.**

---

## 1. What this is for

The immediate case is `valichord_attestation`, which is a client-side on-ramp that does not yet
connect to the DHT. But the interesting question is **not** "how do we connect our own library."
It is:

> **How does any outside organisation plug something into this protocol without endangering it?**

A protocol that can only be extended by the people who wrote it is a product with a plugin
folder. The attestation bridge is being treated as the **first instance of a general problem**,
and the rules below are written to be read by someone with no connection to this project.

**Four outside projects already build against the attestation format** and none has touched the
protocol. If and when one wants to, this document is what they will be handed. That is a better
reason to write it now than any internal need.

## 2. Why `valichord_attestation` is a flattering first test case

Stated plainly, because rules derived from an easy case are optimistic in ways nobody notices
until a hard case arrives.

`valichord_attestation` is the **easiest integrator this protocol will ever have**: same author,
same repository, same release cadence, same language ecosystem, no adversarial relationship, and
a threat model written by the same person who wrote the protocol's. A stranger's system has none
of that.

**So the rules below are under-tested in one specific direction: they have never been applied to
an integrator whose incentives differ from ours.** §3.4 is the precondition that will carry that
weight, and it is the one most likely to need strengthening when a genuinely external case
arrives.

⚠️ **A fifth rule is not to be invented in advance.** Rules are added when a case demands one,
not when one can be imagined. Same discipline as `spec/format-backlog/` — the four below each
exist because a specific, identified failure would otherwise occur.

## 3. The four preconditions

An integration that cannot meet all four **MUST NOT** be built. Failing one of these is a signal
to stop, not to negotiate.

### 3.1 An integration MUST NOT require a new entry type, a new link type, or any change to an integrity zome

**The failure this prevents.** Integrity-zome definitions determine the DNA hash. A changed DNA
hash produces a **separate network** — agents on the old and new hashes cannot see each other —
and every previously published HarmonyRecord URL dies.

This is not theoretical. It happened on 2026-08-03 with the Holochain 0.7 migration, was accepted
deliberately, and every published record URL from before that date is gone. That cost is
acceptable once, for the platform. **It is not acceptable on the schedule of somebody else's
feature.**

The rule bites hardest where it matters most: the attestation format has moved v1 → v1.1 → v1.2 →
v2 in four months and has seven open backlog items raised by outside implementers. **If an
integration's data shape lives inside an integrity zome, an outside contributor's good idea
becomes a network split.** Integration shapes stay out of the DNA.

Coordinator-zome changes are a different matter and are permitted: they carry no hash change (see
`CLAUDE.md`, "Coordinator-only upgrade").

### 3.2 An integration's payload MUST NOT be parsed, decoded or verified inside any integrity zome

**The failure this prevents.** `validate()` runs in WASM on **every node that holds the op**, not
once on a server. Work done there is multiplied across the network and is driven by input the
author chose.

Parsing an integration payload in validation therefore hands an attacker unbounded,
network-wide work for the cost of one write — a payload declaring a very large collection is a
validation bomb aimed at every node holding it.

Only **fixed-size** values may be validated: hashes, signatures, counts, enums. If a rule cannot
be enforced in constant time and constant memory, it does not belong in an integrity zome.

### 3.3 Integration payload *content* MUST NOT be written to a public DHT — digests only

**The failure this prevents.** DNA 1 (`attestation`) and DNA 4 (`governance`) are **public and
permanent**. Nothing written there can be redacted, and Holochain has no delete that removes data
from peers who already hold it.

Integration payloads routinely carry free-form provenance authored by tooling rather than by a
person. The concrete case: `Bundle.meta` is an open dict that can contain absolute file paths,
usernames, hostnames, internal endpoints, and command lines — whatever a harness put there.
`content_hash` excludes `meta`; `bundle_hash` does not.

Publishing that content would put uncontrolled, unremovable personal and infrastructural data on
a public network — on a project whose headline claim is that **researcher data never leaves the
researcher's own environment**. A single such write falsifies that claim permanently and in
public.

What crosses the boundary is a **fixed-length digest and nothing else**. Payloads stay with their
holder and are disclosed selectively, on challenge, to a party who asks.

### 3.4 Every value crossing the boundary MUST be declared **asserted** or **observed**, and every guarantee MUST name the layer that provides it

Definitions in `valichord_attestation/spec/conformance.md` §3.17–3.18: **asserted** is supplied by
a party with an interest in the result; **observed** is derived from evidence that party does not
control.

**The failure this prevents is the subtle one, and it is the reason this document exists.**

Two layers can each defer to the other for the same guarantee, with the result that neither
provides it and nothing announces the gap. It is already latent here:
`attestation_format_v1.md` §10(d) states that the format **cannot** detect an adapter dropping
samples, and that *"Valichord's broader protocol… addresses (d)"*. The format is written assuming
the protocol is suspicious of it.

**If the protocol begins treating an integration payload as evidence, that assumption silently
inverts.** Each side believes the other is the backstop. There is no error, no failing test, and
no log line — only a guarantee that two documents each attribute to the other.

Therefore an integration proposal **MUST** state, for every value it passes:

1. whether it is asserted or observed, and by whom;
2. which layer enforces each property claimed of it; and
3. where the format cannot tell asserted from observed, it **MUST** say so explicitly rather
   than let absence read as agreement.

**An integration payload is asserted. It enters the protocol as a claim, never as evidence.**
Independent validators still reproduce the work and produce their own artefacts; the protocol
compares digests and interprets nothing.

## 4. Checklist for an integration proposal

A proposal is reviewable when it answers all six. Anything else is a conversation, not a proposal.

| | Question |
|---|---|
| 1 | Which entry types and link types does it use? *(Existing only — §3.1.)* |
| 2 | What fixed-size values cross the boundary, and what is their exact size? |
| 3 | What does each integrity zome do with them? *(Constant time and memory — §3.2.)* |
| 4 | What is written to a public DHT, in full? *(Digests only — §3.3.)* |
| 5 | For every crossing value: asserted or observed, by whom? *(§3.4.)* |
| 6 | For every property claimed: which layer enforces it, and where is that written down? |

## 5. What this document does not specify

- **A wire format, an API, or a transport.** These are constraints on any design, not a design.
- **Who may integrate.** A governance question, not an architectural one.
- **Whether an integration is worth building.** Meeting all four preconditions makes an
  integration *safe*, never *justified*.

## 6. Current state

`valichord_attestation` already sits on the correct side of this boundary **without a bridge
having been built**, and it is worth recording why, because it is the shape to copy:

- `ValidationAttestation.reproduction_bundle_hash` is `Option<Vec<u8>>` — **opaque bytes**. The
  protocol commits to a bundle hash and never parses a bundle.
- That hash is bound into the sealed commitment, so it cannot be substituted between commit and
  reveal.
- `ValidationRequest.data_hash` is an `ExternalHash` — again a fixed-size value the protocol does
  not interpret.

Nothing further is wired, **nobody has asked for a bridge**, and none is proposed here.

⚠️ **One consequence of §3.1 deserves stating on its own.** The attestation format's late arrival
at the DHT was luck, not judgement, and it was worth a great deal. Format v1's Merkle construction
produced the same root for `[A, B, C]` and `[A, B, C, C]` — a root did not uniquely identify its
leaf list. **Had bundles been on the DHT during v1, every one of those ambiguous roots would now
sit on a permanent, immutable record**, and shipping v2 would not have fixed a single one of them.
A format bug is cheap while it is off-chain and permanent the moment it is not. **Let a format
settle before binding it to something immutable.**
