# ValiChord Integration: Verification Closure for the Nondominium Object

**Status**: Post-MVP Design Document — **Proposed** (external contribution, not yet adopted)
**Created**: 2026-08-16
**Authors**: ValiChord project (Ceri John), for review by the Nondominium project
**Relates to**: `ndo_prima_materia.md`, `unyt-integration.md`, `flowsta-integration.md`,
`specifications/governance/private-participation-receipt.md`,
`specifications/adr/ADR-010-013-per-ndo-cells.md`

---

## Table of Contents

1. [Framing: what this document proposes](#1-framing-what-this-document-proposes)
2. [The verification closure problem](#2-the-verification-closure-problem)
3. [What ValiChord is, and what it is not](#3-what-valichord-is-and-what-it-is-not)
4. [ValiChord as validation operator](#4-valichord-as-validation-operator)
5. [Integration architecture](#5-integration-architecture)
6. [Constraints introduced by per-NDO cells](#6-constraints-introduced-by-per-ndo-cells)
7. [Where reviewers come from](#7-where-reviewers-come-from)
8. [Nondominium as instantiation example](#8-nondominium-as-instantiation-example)
9. [Integration path](#9-integration-path)
10. [Requirements](#10-requirements)
11. [Honest limits](#11-honest-limits)

---

## 1. Framing: what this document proposes

This document follows the pattern established by `unyt-integration.md` and `flowsta-integration.md`:
an external capability that connects to the generic NDO through the capability slot mechanism and a
standard `GovernanceRule`, requiring no modification to the NDO's core data model.

Like those two, the ValiChord integration is designed to be:

- **Optional, on Benkler's terms** — the NDO functions without it. Independent reproduction is the most
  expensive form of evidence there is: it costs other people's time, equipment and materials. By the
  information-opportunity-cost argument in §2.2 of `ndo_prima_materia.md`, that overhead should be paid
  only where the coordination it enables is worth more than the coordination it consumes. Most
  resources never need it. A design about to be fabricated across a network does. Verification is
  therefore a capability activated at a specific transition, in the same pay-as-you-grow shape as layer
  activation — not a tax on every resource.
- **Modular** — it connects through the capability slot surface (`ndo_prima_materia.md` §6) and a
  `GovernanceRule`, in the same shape as Unyt's `EconomicAgreement` and Flowsta's `IdentityVerification`.
- **Lifecycle-aware** — verification requirements can differ by stage. A resource under development
  need not be independently verified; the same resource transitioning to `Active` or to a distributed
  stage may require it.
- **Domain-agnostic** — the mechanism does not know what is being verified. It carries numbers and
  compares them under a pinned tolerance.

ValiChord is an existing, running Holochain application, not a proposal to build one. This document
describes how it would attach, and is written to be argued with.

---

## 2. The verification closure problem

The PPR system solves accountability *between agents*. Every economic interaction generates two
bi-directional, cryptographically signed receipts, and reputation derives from their accumulation.
It is a complete answer to "was this agent reliable in their dealings with me?"

The PPR specification states its own boundary precisely:

> **Implicit Resource Validation**: Resource validation is implicit through agent validation (except
> for creation events)

That parenthesis is the whole of this document's subject.

Where two agents transact, each is a witness to the other, and validation falls out of the interaction.
Where a resource is **created** — or where a lifecycle transition asserts something about the resource
itself rather than about a dealing between parties — there is no counterparty to witness it. The
custodian asserts; the DHT records the assertion. The record is faithful, tamper-evident, and
attributable, and it is a record *of a claim*, not of a check.

This is the **verification closure problem**. Two agents can be perfectly accountable to one another
and both be wrong about whether the thing works. Provenance closure — knowing exactly who said what,
when — does not produce verification closure, and no amount of additional signing produces it either.
Closing it requires a party who was not involved to arrive at the same result independently.

### 2.1 The requirement already exists

This is not a capability the NDO lacks a place for. It is a capability the NDO has **already
specified and not yet built.**

`ndo_prima_materia.md` §5.3 defines the maturity chain, and one transition in it is unlike the others:

```
Prototype --> Stable : "Accept (peer validated)"
```

The authorization table in the same section names what governs it:

| Transition | Authorized by |
|---|---|
| Development → Prototype | Custodian + governance validation |
| **Prototype → Stable** | **Multi-agent peer validation (configurable N-of-M)** |
| Stable → Distributed | Custodian |

Every neighbouring transition is authorised by a custodian. This one requires **multi-agent peer
validation at a configurable threshold** — and no mechanism is specified anywhere for producing it.

The definitions explain why it is the exception. `Prototype` is *"PoC exists, not production-ready."*
`Stable` is *"Production-ready, **design is replicable**."* The transition asserts replicability, which
is a claim about the world that the custodian is not in a position to establish alone. Their own model
recognises this and asks for independent agreement.

**What is enforced today is weaker than what is specified.** §5.3 records the MVP honestly:
transitions are validated in the integrity zome (`validate_update_nondominium_identity`), the
**initiator alone** may call `update_lifecycle_stage`, the role-based authorization table is target
behaviour under REQ-NDO-LC-07 rather than current enforcement, and the governance zome does not yet
act as state transition operator (REQ-ARCH-07). So the party proposing the resource can currently
declare its design replicable, unilaterally, with the DHT faithfully recording that they said so.

ValiChord produces exactly the artefact the specified rule needs: agreement among N independent
parties at a stated threshold, sealed before any could see another's finding.

### 2.2 The second gap, at creation

The same absence appears one layer down. `EconomicResource` carries `ResourceState::PendingValidation`
as its default, and the cross-zome call that would resolve it — `create_economic_resource()` →
`validate_new_resource()` — remains commented out in `zome_resource/src/economic_resource.rs`. In the
target architecture this becomes `OperationalState::PendingValidation → Available`, triggered by
"peer validation approved" (§5.4). The state exists in both the current and the target model; the
evidence source does not.

**These are two distinct dimensions and should not be conflated.** `LifecycleStage` lives on
`NondominiumIdentity` and describes what the artefact has become; `OperationalState` lives on the
`EconomicResource` instance and describes what process is acting on it. A `Prototype` can be
`InTransit`. The `Prototype → Stable` gate is the primary target of this document because
replicability is precisely what independent reproduction establishes. The creation-time check is a
secondary, and simpler, application of the same mechanism.

One naming hazard worth flagging for implementers: **`Active` appears in both enums with different
meanings** — `LifecycleStage::Active` is "in normal use", while the current `ResourceState::Active` is
the post-validation operational state. Any rule payload should name the enum explicitly.

Three properties are needed for such evidence to be worth gating on:

1. **Independence** — the verifier is not the claimant, and did not observe other verifiers before
   committing.
2. **Non-repudiation** — no party can revise their finding after seeing the others'.
3. **Verifiability at decision time** — the governance rule can fetch and check the evidence itself,
   rather than trusting a summary written by the party who benefits from it.

---

## 3. What ValiChord is, and what it is not

### 3.0 In the project's own terms

§3.4 of `ndo_prima_materia.md` states the open problem this integration addresses, in the project's
own words:

> The honest challenge of COP, noted in the complexity_oriented_programming archive: tooling.
> Debuggers, type systems, and unit tests all assume reducibility. **COP requires new verification
> paradigms** — closer to simulation and formal methods than conventional testing.

The answer recorded there is Sweettest: multi-agent testing of the *backend*. That verifies the
software behaves as written. It cannot verify a claim the software merely records — that a design is
replicable, that a signature is what a genuine component produces. Those are claims about the world,
and no amount of testing the zome establishes them.

ValiChord is a verification paradigm of the kind §3.4 asks for, and it is COP-shaped rather than
reductive. It does not check a claim against a specification, because for empirical claims there is no
specification to check against. It observes whether independent agents, acting locally and without
sight of each other, converge. In the vocabulary of §3.3, this is the same move Holochain makes with
validation itself: **there is no global state machine deciding truth; coherence emerges from the
aggregate of local findings.** In the vocabulary of the §3.2 table, it replaces a single source of
truth with a coherence protocol.

The correspondence extends to the failure mode. Emergent coherence can be wrong — locally valid
actions can aggregate into a wrong global picture, and independent labs can converge on a wrong
value. §11 is explicit about that, and the honesty is not incidental. A verification paradigm for COP
has to report what it observed rather than what it concluded, because concluding requires the
reducibility COP denies it.

### 3.1 The mechanism

ValiChord is a Holochain protocol for blind, independent reproduction of a claim. A claimant deposits
a claim and seals it. Independent validators each attempt to reproduce it and seal their findings
before any is visible. All reveals open together, hash-verified against the seals. The result is a
`HarmonyRecord`: a tamper-evident entry carrying the outcome, an agreement level, and the set of
participating validators.

The property that matters for governance is structural rather than procedural: **no participant can
change their claim after seeing another's.** Sealing precedes revelation, and the seal is a hash
commitment the coordinator verifies at reveal. Convergence is therefore evidence, not coordination.

### 3.2 What it does not provide

- **It does not establish correctness.** `Reproduced` means an independent party arrived at the same
  result as the claimant. It does not mean the result is right. Systematic error shared across
  validators — a miscalibration every lab has in common — produces genuine agreement on a wrong
  answer. This limit is structural and is not softened anywhere in ValiChord's own documentation.
- **It does not certify instruments or method.** If the pinned procedure is poor, the record faithfully
  certifies that several parties followed a poor procedure and agreed.
- **It does not solve admission.** Who is allowed to validate is a governance question, addressed in
  §7 and deliberately left on the Nondominium side.
- **It does not detect out-of-band collusion.** Blinding prevents copying, not conspiracy. Sybil
  resistance depends on cross-system person identity, which is Flowsta's territory, not ValiChord's.

Stated positively: ValiChord converts an assertion into a checkable record of independent agreement,
with honest bounds on what that agreement means.

---

## 4. ValiChord as validation operator

In the vocabulary of `unyt-integration.md`, Unyt is the **economic operator**: it closes the loop
between observation and settlement. ValiChord occupies the analogous position for evidence — a
**validation operator** closing the loop between assertion and verification.

The parallel is exact in one respect worth drawing out. At full enforcement, Unyt's governance rule
does not trust the capability-slot tag; the transition request carries a `rave_hash`, and the
governance zome queries the Unyt DHT to retrieve and validate the actual RAVE against the transition
context — a Record of Agreement Verifiably Executed, per `unytco/smart_agreement_library`, which is
the record of one execution of a Smart Agreement. ValiChord's gate must work identically: fetch the
real `HarmonyRecord`, check its own agreement level and validator count against the threshold, and
confirm its request reference binds to *this* resource.

The reason is the same in both cases. A slot tag is written by the party who benefits from the
transition. It is a discovery hint, never an authority.

Nondominium has since arrived at this doctrine independently. ADR-012 rules that a reader does not
trust `anchor.ndo_dna_hash`, but re-derives the clone from `(network_seed, properties)` and compares.
Verify-the-referent is therefore already the house pattern in two places. The ValiChord gate is a
third application of a rule the project has settled on, not an imported constraint.

---

## 5. Integration architecture

### 5.1 The two tiers

Following `ndo_prima_materia.md` §6:

- **Tier 1 — the capability slot.** A `CapabilitySlot` link from the NDO's Layer 0 identity hash to
  the `HarmonyRecord` `ActionHash`, carrying the standard `CapabilitySlotTag` from §8.3. Permissionless
  by design guarantee (REQ-NDO-CS-02), and authoritative for nothing.
- **Tier 2 — the governance rule.** A custodian-endorsed rule making a qualifying record a
  precondition of a lifecycle transition.

**The tag carries no claim, and this is the right design.** `CapabilitySlotTag` is
`{ slot_type, attached_at, label: Option<String> }`. There is no field for an agreement level or a
validator count, and none should be added. The security requirement in §4 is that the gate must not
decide from anything the beneficiary wrote — and a tag structure that cannot express the verdict
enforces that by construction rather than by discipline. At most, `label` may carry a human-readable
display hint for a browser; nothing should parse it.

**Slot type.** The vocabulary in §8.3 is explicitly extensible, and REQ-NDO-CS-04 requires support for
`CustomApp(String)`. Two options, in ascending order of commitment:

1. **`CustomApp("valichord")`** — available under the existing vocabulary with no change to the enum.
   Adequate for a pilot.
2. **A dedicated variant**, following the `UnytAgreement(String)` precedent set by REQ-NDO-CS-07,
   where the string carries a network identifier for the verifying network. Preferable if
   verification becomes a first-class precondition, because it makes the slot legible to a reader who
   does not know the convention.

This document proposes (2) but does not depend on it. Note also REQ-NDO-CS-03: the governance zome is
already specified to let custodians mark individual slots trusted or untrusted, which is the natural
home for revoking a slot that points at a record later found defective.

**Implementation status.** `CapabilitySlot` is listed in §8.4 under *"Planned additions (post-MVP —
not yet in `LinkTypes` enum)"*, and REQ-NDO-CS-01 is marked ❌. Tier 1 is therefore specified but not
built; there is nothing to link against today. This is a shared dependency with the Unyt and Flowsta
integration paths, not specific to this one.

### 5.2 The rule needs no type change

The implemented integrity type is open:

```rust
pub struct GovernanceRule {
  pub rule_type: String,           // e.g. "access_requirement", "usage_limit", "transfer_conditions"
  pub rule_data: String,           // JSON-encoded rule parameters
  pub enforced_by: Option<String>, // Role required to enforce this rule
}
```

So the gate is expressible today as `rule_type: "external_validation"` with the required slot type and
threshold carried as JSON in `rule_data`. **No enum variant, no integrity-zome change, and therefore
no DNA-hash change is required on the Nondominium side.** The `GovernanceRuleType` enum in the v1.0
design document is a documentation question, not a blocker.

What is missing is not the rule but the **operator that evaluates it**. `zome_gouvernance` currently
carries `agreement`, `commitment`, `contribution`, `economic_event`, `hard_link`, `ppr`,
`private_data_validation` and `validation` — there is no rule-evaluation module. No Tier-2 rule of any
kind is enforceable until governance-as-operator lands. This is a sequencing dependency shared with
Unyt and Flowsta, not specific to this integration.

### 5.3 The handoff

Written against the `Prototype → Stable` transition, the case §5.3 already flags as requiring N-of-M
peer validation.

1. ValiChord produces a `HarmonyRecord`.
2. The custodian writes the Tier-1 slot link on the NDO's Layer 0 identity hash.
3. The initiator calls `update_lifecycle_stage(Prototype → Stable)`.
4. The governance operator evaluates the `external_validation` rule: it fetches the actual
   `HarmonyRecord`, checks agreement level and validator count against the threshold, and confirms the
   record's request reference binds to this NDO.
5. On success the transition is written; the integrity zome's existing monotonic-chain validation
   continues to apply independently.
6. `refresh_ndo_anchor_lifecycle_stage` re-syncs the cached `lifecycle_stage` on the group cell's
   `NdoAnchor`, so group browsers reflect the new stage.

**Step 4 is the whole change.** Steps 1–3 and 5–6 already exist or are already specified. What does
not exist is a governance evaluation between the initiator's call and the integrity zome's write —
which is REQ-ARCH-07 (governance zome as state transition operator) and REQ-NDO-LC-07 (role-based
transition authorization), both deferred. This integration does not need new machinery so much as it
needs an evidence source for machinery the project has already committed to building.

The N-of-M threshold in step 4 is **Nondominium policy**, and §5.3 already describes it as
configurable. ValiChord's own badge tiers are illustrative placeholders, not statistically-derived
thresholds, and should not be imported as if they were.

The principle throughout: **sovereignty over *when*, never over *what* the record says.** The custodian
keeps the trigger. The record's contents are not theirs to restate.

---

## 6. Constraints introduced by per-NDO cells

ADR-010–013 changed the shape this integration attaches to, in three ways that matter.

**The gate is per-cell.** The `ndo` DNA is built from the same `zome_resource` and `zome_gouvernance`
wasms as the shared `nondominium` cell, so `create_economic_resource()` and the commented-out
`validate_new_resource` call exist inside *every* NDO clone. The gate therefore fires once per NDO,
addressed by that NDO's `DnaHash`, rather than once per network.

**`zome_person` is not in the `ndo` cell.** Roles, administration status, affiliation and capability
grants remain in the shared cell. Anything the gate needs to know about *who* a reviewer is — including
any conflict-of-interest check based on shared affiliation — is a cross-cell read from where the gate
executes. This is the single largest open design question in the integration, and it is raised in §10.

**Both identity shapes coexist.** For a migrated NDO the durable identity is the clone's `DnaHash`,
with the `create_ndo()` `ActionHash` surviving as `NdoAnchor.identity_action_hash`. NDOs created before
the migration remain in the shared cell behind a legacy read fallback. Any gate implementation must
handle both.

One further note on sequencing: the `NdoToTransitionEvent` link type is implemented, but as a link
only — cross-zome event validation is deferred, lifecycle transitions do not yet emit an
`EconomicEvent` (REQ-NDO-LC-02 / LC-03), and `transition_event_hash` is `null` in the MVP. A gated
transition therefore does not currently mint PPRs. If verification participation should accrue
reputation, that is an existing dependency to schedule, not something this integration provides on its
own — and the link type being present means the wiring is anticipated rather than absent.

---

## 7. Where reviewers come from

Admission and independence are different problems and land on opposite sides of the boundary.

**Independence** is ValiChord's structural job and holds regardless of how the pool is sourced: seal
before seeing, simultaneous reveal, hash-verified commitments.

**Admission** — who is permitted into a validation round — is Nondominium's, and should stay there. It
is a governance decision, the project already has role and administration machinery for it, and
placing a ValiChord-side authority in the trust path would make a general-purpose verifier
domain-specific.

Two mechanisms are available. ValiChord supports a credential membrane enforced at network join, via
a DNA property naming an issuing authority; this is built and running. Nondominium's own model is
in-DHT moderated membership, which is visible, reversible and pluralistic. The recommended starting
point is delegation: ValiChord runs an open membrane, and Nondominium's governance is the sole gate on
who is invited to a round.

Worth noting that these are less far apart than they were. ADR-013 binds immutable classification into
clone DNA properties and describes the result as hash physics rather than a rule someone can forget —
which is precisely the argument for a membrane. If a domain later requires structurally enforced,
certificate-backed admission, the hybrid arrangement (ValiChord's issuer set to a Nondominium
authority key) is available without disturbing anything in this document.

**Neither mechanism establishes independence.** A fully credentialed pool can still collude out of
band, and one actor can still hold two keys. Those residual risks are addressed by pool diversity and
by cross-system person identity — Flowsta's `IsSamePersonEntry`, currently unpopulated — and should not be
attributed to either admission mechanism.

---

## 8. Nondominium as instantiation example

The motivating case is medical-device fabrication, where the `Prototype → Stable` transition carries
real consequence and the resource's fitness is a claim about the physical world. Note that the chain
is monotonic — no stage skipping — so `Stable` is unavoidably on the path to `Distributed` and
`Active`. Whatever evidence gates it gates everything downstream of it.

ValiChord's fit there is narrower than "verify the device". The claim it verifies is a **reference
fingerprint**: the electrical response signature a genuine component produces when pinged according to
a pinned procedure. The originator deposits the claim and the procedure and seals it; independent
labs obtain genuine parts, run the same procedure, and seal their measurements; all reveal together.

Two adjacent things sit outside that, for different reasons worth separating.

**Whether the fingerprint discriminates genuine parts from counterfeits** is a metrology question, not
a reproducibility one. This is a structural limit rather than a scoping choice: independent parties
converging on the same signature does not establish that the signature identifies anything. No version
of this mechanism reaches it.

**Firmware verification** is a different case. It is a hash comparison, so every honest party gets the
identical verdict and independent agreement adds no information — Nondominium can do it directly. That
is an argument from value, not from capability: the protocol would happily carry it, there is simply
no reason to pay for independence where honest verdicts cannot differ. If a deployment turns out to
need the two bound into one record, that is a conversation rather than a redesign.

The pinned procedure is the crux. Blinding is meaningless unless the method is frozen before anyone
measures — stimulus, measurement points, environmental conditions, and the tolerance basis all hashed
into the deposited bundle. Otherwise validators measure different things, or the tolerance is fitted to
the results after the fact.

This also composes with existing practice rather than displacing it. Where a design already publishes
an Open Know-How manifest with a content hash, that hash is a natural design-provenance anchor, with
the verification record covering the fabrication half.

---

## 9. Integration path

| Stage | Work | Depends on |
|---|---|---|
| 0 | Agree the boundary: Nondominium owns admission and the threshold; ValiChord owns independence | this document |
| 1 | Add a validation slot type to the `SlotType` vocabulary | slot surface implemented |
| 2 | Define the `external_validation` rule payload schema (`rule_data` JSON) | none — `rule_type` is already open |
| 3 | Implement the rule evaluation: fetch record, check threshold, bind to resource | governance-as-operator |
| 4 | Resolve the cross-cell read for reviewer roles and affiliation | §6, open question |
| 5 | Anchor re-sync after a gated transition | `refresh_ndo_anchor_lifecycle_stage` |
| 6 | Optional: PPR minting for verification participation | REQ-NDO-LC-02 / LC-03 |

Stages 1–3 are the minimum viable gate. Stage 0 costs a conversation.

---

## 10. Requirements

Continuing the Capability Surface series from §9.5 of `ndo_prima_materia.md`, which currently ends at
`REQ-NDO-CS-15`. Numbers are proposed, for the project to accept, renumber or reject.

- **REQ-NDO-CS-16** — The `SlotType` enum SHOULD support a validation variant whose target is an
  external verification record action hash, following the `UnytAgreement(String)` precedent in
  REQ-NDO-CS-07. Until then, `CustomApp(String)` per REQ-NDO-CS-04 is sufficient.
- **REQ-NDO-CS-17** — Any Accountable Agent SHALL be able to attach a validation capability slot to any
  NDO without custodian permission (Tier 1), consistent with REQ-NDO-CS-02.
- **REQ-NDO-CS-18** — The `GovernanceRule` type SHALL support a `rule_type` of `"external_validation"`,
  expressing the required slot type, minimum agreement level and minimum validator count in
  `rule_data`. No change to the `GovernanceRule` struct is required, since `rule_type` is a `String`.
- **REQ-NDO-CS-19** — Evaluation of an `external_validation` rule SHALL fetch the referenced record and
  verify its own agreement level and validator count. It SHALL NOT decide from the
  `CapabilitySlotTag`, which by design carries no verdict.
- **REQ-NDO-CS-20** — Evaluation SHALL confirm the referenced record binds to the resource under
  transition, rejecting a record that is internally valid but relates to a different subject.
- **REQ-NDO-CS-21** — The agreement-level and validator-count thresholds SHALL be per-NDO policy, not
  protocol constants.
- **REQ-NDO-CS-22** — A gated lifecycle transition SHALL re-sync the cached `lifecycle_stage` on the
  hosting group's `NdoAnchor` via `refresh_ndo_anchor_lifecycle_stage`.
- **REQ-NDO-CS-23** — Admission to a validation round SHALL be determined by Nondominium governance,
  not by the verification protocol.

**Open question for the project.** REQ-NDO-CS-23, and any affiliation-based conflict-of-interest check,
both need `zome_person` data — which is not present in the `ndo` cell where the rule executes. Three
options, each with a different failure mode:

1. **Cross-cell read at decision time.** Freshest, but couples rule evaluation to the availability of
   the shared cell.
2. **Cache the relevant facts on the NDO cell.** Fast and self-contained, but a suspension written in
   the shared cell may not be visible at the gate — the same staleness class as the anchor's cached
   `lifecycle_stage`.
3. **Carry the reviewer set as signed data inside the verification record.** Self-contained and
   verifiable without a second read, but fixes the reviewer set at round time rather than at decision
   time.

The choice is Nondominium's; it is a governance question wearing an architecture costume.

---

## 11. Honest limits

- **Reproduced is not correct.** Independent agreement on a wrong value is possible and the record
  cannot detect it. This is the most important sentence in the document.
- **Schema gap for hardware.** The attestation schema carries metric values but no units, ambient
  conditions or reference-instrument identity. A credible hardware round needs those so third parties
  can check for correlated error after reveal. Adding them is an integrity-zome change on the ValiChord
  side and is scheduled, not done.
- **Latency.** A hardware round takes days or weeks — sourcing parts and measuring — not seconds. The
  protocol tolerates asynchronous rounds, but the governance UX must expect them.
- **Lot variation.** Validators measuring different lots of a genuine part may legitimately diverge.
  Whether a different lot counts as the same reference is a policy call for whoever authors the bundle.
- **Nothing here is enforceable yet.** Governance-as-operator is unimplemented, and the slot surface
  exists in specification rather than in code. This document describes an attachment point, not a
  working integration.
