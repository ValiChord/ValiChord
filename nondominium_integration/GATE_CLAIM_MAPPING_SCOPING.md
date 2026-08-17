# ValiChord × Nondominium — What Gets Committed at the Gate (Scoping Note)

**Status:** Scoping / pre-design. Written 2026-06-16. Companion to `REVIEWER_SOURCING_SCOPING.md`.
**Scope:** The second of the two open design questions from the 2026-06-14/15 Discord agreement —
*what specifically gets committed and reproduced at the gate*, mapping the reference-fingerprint
claim and Nondominium's designer/reviewer roles onto ValiChord's commit-reveal data model.
**Reads alongside:** `NONDOMINIUM_ARCHITECTURE.md` (the capability-slot-link handoff this note feeds
into). A separate internal worked-example covers the general *whole-device* reproducibility case
(same sensor family, different claim).

---

> **🔄 Update 2026-08-16 — re-verified against `dev`. One item is materially *easier* than recorded;
> four are new constraints from ADR-010–013.** Architecture delta in `NONDOMINIUM_ARCHITECTURE.md`.
>
> **✅ Step 3 needs no enum variant from them — this supersedes flag (1) of the 2026-07-08 update.**
> The *implemented* integrity type is open-ended:
> ```rust
> pub struct GovernanceRule {
>   pub rule_type: String,           // e.g. "access_requirement", "usage_limit", "transfer_conditions"
>   pub rule_data: String,           // JSON-encoded rule parameters
>   pub enforced_by: Option<String>, // Role required to enforce this rule
> }
> ```
> The `GovernanceRuleType` enum that lacks `ExternalValidation` lives in the **v1.0 design document**,
> not in the code. In code, `rule_type: "external_validation"` with `rule_data` as JSON is expressible
> **today — no enum PR, no integrity-zome change, no DNA-hash change on their side.** The June/July
> framing of step 3 as "a request we must make explicitly" overstated the ask. It is now a
> documentation-and-policy conversation, not a code change.
>
> **⚠️ But `SlotType` does not exist in code at all.** No slot-named file anywhere in the tree. The
> two-tier capability-slot pattern is design-document material (`ndo_prima_materia.md` §6), so **Tier 1
> is unimplemented too**, not just Tier 2. Step 2 of the handoff has nothing to write against yet.
>
> **⚠️ Governance-as-operator still unimplemented — re-verified 2026-08-16.** `zome_gouvernance`'s
> coordinator modules are `agreement`, `commitment`, `contribution`, `economic_event`, `hard_link`,
> `ppr`, `private_data_validation`, `validation`. There is no rule-evaluation or operator module. The
> sequencing dependency from 2026-07-08 stands unchanged.
>
> **⚠️ Step 2's base hash moved.** `NondominiumIdentity` now lives inside the NDO's own clone cell
> (ADR-010), so the slot link is written *there*, and for a migrated NDO the durable identity is the
> cell's `DnaHash` — the `create_ndo()` `ActionHash` survives as `NdoAnchor.identity_action_hash`.
> Pre-migration NDOs still sit in the shared cell, so **any gate implementation must handle both shapes.**
>
> **⚠️ Steps 4–5 now run inside one of N clone cells.** The `create_economic_resource()` →
> `validate_new_resource()` pair exists in every `ndo` clone, so the cross-cell fetch of the
> `HarmonyRecord` originates from a *cloned* cell rather than the shared `nondominium` cell. Worth
> confirming with Tiberius how a clone addresses the ValiChord governance cell.
>
> **🆕 A step 6 is missing from the handoff below.** `lifecycle_stage` is now *also* cached on
> `NdoAnchor` in the group cell. After a successful transition the anchor must be re-synced via
> `refresh_ndo_anchor_lifecycle_stage`, or the group's browser view goes stale. Convergence is
> pull-based; `remote_signal` push is `TODO(signals)` in their own ADR.
>
> **⚠️ The PPR sink does not fire yet.** Lifecycle transitions do not currently emit an
> `EconomicEvent` (REQ-NDO-LC-02 / LC-03); `transition_event_hash` is `null` in the MVP. Any step that
> assumes `log_economic_event()` runs on the gated transition — and therefore mints PPRs — is
> premature.
>
> **✅ ADR-012 doubles the precedent for step 5.** *"A reader does not trust `anchor.ndo_dna_hash`. It
> re-derives the clone from (network_seed, properties) and compares."* Verify-the-referent is now the
> house pattern **twice over** — Unyt's RAVE fetch and their own anchor check. Lead with this.

---

## 1. Be precise about *which* claim is at the gate

Tiberius's gate authorises a `Prototype → Stable/Distributed` transition for a medical-device
resource on the basis of **technical (fabrication) validation**. Within that, ValiChord verifies
exactly **one** kind of claim — and it is *not* the whole device:

> **The reference-fingerprint claim:** *"This is the electrical response signature a genuine
> [MP3V5010DP] pressure sensor produces when pinged per the pinned procedure."*

This is the claim Pryderi scoped as ValiChord's real fit. It is what later feeds counterfeit
detection, but ValiChord verifies *establishing the reference*, not the detection method.

**Explicitly out of scope at this gate** (Pryderi's two limits, confirmed):
- **Whether the fingerprint discriminates genuine from counterfeit** — metrology / live R&D, not a
  reproducibility claim. ValiChord's layer doesn't touch it.
- **Firmware verification** — a straight hash check (matches or doesn't). No independent agreement
  needed to confirm a checksum; ValiChord would be overkill. Nondominium does this directly.

So the gate may invoke ValiChord for the *reference-fingerprint* sub-claim while handling the
firmware hash itself and treating the metrology question as separate evidence.

---

## 2. Role mapping (Nondominium → ValiChord)

| Nondominium role | ValiChord role | What they do at the gate |
|---|---|---|
| Resource **designer / originator** (creates the `NondominiumIdentity` / `EconomicResource`) | **Researcher** (claimant) | Deposits the reference-fingerprint claim + pinned ping procedure; commits it. |
| Technical **reviewers** (peer-review the fabrication claim; `AccountableAgent`+ / admitted reviewers) | **Validators** | Independently obtain genuine sensors, run the pinned ping, attest blind whether the signature reproduces. |
| **Governance zome** (governance-as-operator) | *consumer* of the `HarmonyRecord` | Reads the result via the capability slot and authorises the lifecycle transition. |

Two protocol modes fit, and the choice is a real design decision:

- **Claim-relative (as built — recommended for the gate).** The designer commits a reference
  profile as the researcher claim; reviewers reproduce *against it*; `AgreementLevel` is computed
  relative to the designer's revealed claim. Matches "designer proposes the reference, reviewers
  peer-review it." Uses the protocol exactly as it stands.
- **Leaderless convergence (Pryderi's stated natural endpoint).** No privileged first lab; all
  labs symmetric; the record certifies they converged on the same signature. This is closer to how
  a *canonical* reference would ultimately be established — but the protocol as built is
  researcher-claim-relative (it has a `ResearcherReveal` and agreement is claim-relative). True
  leaderless mode needs adaptation (no researcher claim; agreement computed among validators only)
  → Phase 1+, not the MVP gate. **Recommendation: ship claim-relative now, note leaderless as the
  maturity target.**

---

## 3. Data-model mapping (the core of this note)

What each protocol artifact carries, for the reference-fingerprint claim. Hashes and entry names
are ValiChord's as-built (see `NONDOMINIUM_ARCHITECTURE.md` for the entry definitions).

| ValiChord artifact | DNA | Here it holds |
|---|---|---|
| **`data_hash`** (`ExternalHash`, SHA-256) on `ValidationRequest` | 3 | Hash of the **deposited claim bundle**: the part number + lot/provenance of the genuine reference samples, the **pinned ping procedure** (stimulus, measurement points, conditions), the tolerance basis, and the reference signature spec. Pinning this up front is the crux (§4). |
| **`metrics`** (`Vec<MetricResult>`) in researcher `LockedResult` (private) | 1 | The designer's claimed **reference signature**: the characteristic response values (e.g. response at each stimulus point) that define "genuine". |
| **`ResearcherResultCommitment.result_commitment_hash`** = `SHA-256(msgpack(metrics) ‖ nonce)` | 3 | Published **before** any reviewer measures — binds the designer's reference claim without revealing it. |
| **`ResearcherReveal.metrics`** | 3 | The reference signature, revealed **after** all reviewers commit; coordinator verifies the hash. |
| **`ValidatorPrivateAttestation`** (`outcome`, `outcome_summary.key_metrics`, `confidence`, …) | 2 | Each reviewer's **own measured signature** + their `AttestationOutcome`, held private until reveal. |
| **`CommitmentAnchor.commitment_hash`** = `SHA-256(msgpack(ValidationAttestation) ‖ nonce)` | 3 | Each reviewer's sealed verdict — frozen and invisible to others (the blinding). |
| **`ValidationAttestation`** (the reveal) | 3 | `Reproduced` / `PartiallyReproduced` / `FailedToReproduce` / `UnableToAssess`, revealed simultaneously, hash-verified against the commitment. |
| **`HarmonyRecord`** (`outcome`, `agreement_level`, `participating_validators`, …) | 4 | The tamper-evident certificate: *"N independent labs reproduced the reference signature for `<part>` — `ExactMatch`/`WithinTolerance`."* |

**Critical constraint — the `HarmonyRecord` is outcome-level only.** It carries `outcome`,
`AgreementLevel`, the validator set, duration and discipline — **not** each lab's per-metric
numbers. The individual measured signatures live on DNA-3 `ValidationAttestation` reveals (publicly
fetchable), but they are *not* aggregated into the on-chain record. So the gate sees "they agreed,
at this level"; reconstructing the per-lab numeric panel is a separate read across the attestations.
(This matches the PEP Master finding: per-builder numerics don't survive into the `HarmonyRecord`.)

**Reused as-is:** the numeric tolerance + agreement machinery built for CORE-Bench (`match_value`,
tolerance pinned at commit, `derive_agreement_level` / `derive_majority_outcome`). The Holochain
layer is source-agnostic — it doesn't care the number came from an electrical ping rig.

**On-ramp — they already hash the design bundle (OKH manifest).** The deposit-and-hash step is not a
new ask for PEP Master: the canonical "Organic Controller 2024" build already publishes an **OKH
(Open Know-How) `okh-manifest.yml`** whose SHA-256 (`72986C99…57F6DA7`) covers all design files.
That existing design-provenance hash is a natural fit for `ValidationRequest.protocol_ref` (the
method/design anchor), with `data_hash` carrying the reference-signature dataset + pinned procedure.
This also mirrors Sensorica's own two-part trust model — *"certainty of provenance for the design,
plus an on-demand verification method for the fabrication"* — where the OKH hash is the
design-provenance half and ValiChord is the fabrication-verification half.

---

## 4. The pinned-procedure crux

Blinding is meaningless unless the *method* is frozen before anyone measures. The deposited bundle
**must** contain a pinned ping procedure (stimulus waveform/levels, measurement points, environmental
conditions, the tolerance basis) hashed into `data_hash`. Otherwise reviewers measure different
things, or the tolerance is retrofitted to the results. This is the same discipline as a pinned
`test_protocol` block — including the unresolved **tolerance-basis** question (of-reading vs
of-full-scale materially changes the pass band; confirm with the device's actual spec before
fixing the bundle).

---

## 5. The gate handoff (after the HarmonyRecord exists)

Per `NONDOMINIUM_ARCHITECTURE.md` (custodian gate stays intact; no new governance-gated pathway):

1. ValiChord produces the `HarmonyRecord` (DNA 4).
2. The designer/custodian writes a **capability-slot link** on Nondominium's DHT: base =
   `EconomicResource` / `NondominiumIdentity` hash, target = `HarmonyRecord` `ActionHash`, tag =
   `{agreement_level, validator_count}` as compact msgpack. (`AgreementLevel` has no serde tag — it
   serialises as a plain string like `"ExactMatch"`, so Nondominium reads it without importing
   ValiChord types.)
   > **⚠️ Corrected 2026-08-16 — the tag shape above is not theirs.** `ndo_prima_materia.md` §8.3
   > specifies `CapabilitySlotTag { slot_type: SlotType, attached_at: Timestamp, label: Option<String> }`.
   > There is **no field for an agreement level or validator count**, and we should not ask for one.
   > The security note below argues the gate must never decide from the tag; a tag that *cannot*
   > express the verdict enforces that structurally instead of by discipline. Put a display hint in
   > `label` if a browser needs one, and have nothing parse it.
   >
   > On the slot type: §8.3's `SlotType` enum is `Documentation`, `IssueTracker`, `FabricationQueue`,
   > `GovernanceDAO`, `VersionGraph`, `DigitalAsset`, `WeaveWAL`, `FlowstaIdentity`,
   > `UnytAgreement(String)`, `CustomApp(String)`. **`CustomApp("valichord")` works today** under
   > REQ-NDO-CS-04 — so the "SlotType has no validation slot" gap flagged on 2026-07-08 is a
   > preference, not a blocker. A dedicated variant modelled on `UnytAgreement(String)` (REQ-NDO-CS-07)
   > is the better ask, not a required one.
   >
   > **But `CapabilitySlot` is not in the implemented `LinkTypes` enum** — §8.4 lists it under
   > "Planned additions (post-MVP)", and REQ-NDO-CS-01 is marked ❌. There is nothing to link against
   > yet. Note REQ-NDO-CS-02 makes permissionless attachment a *design guarantee*, so Tier 1 needs no
   > custodian permission once it exists, and REQ-NDO-CS-03 already anticipates marking individual
   > slots trusted/untrusted — the natural revocation path for a slot pointing at a bad record.
3. Nondominium adds a `GovernanceRuleType::ExternalValidation` rule specifying the required slot
   type + consensus threshold for medical-device resources.
   > **Corrected 2026-08-16:** no enum variant is needed. The implemented `GovernanceRule.rule_type`
   > is a `String`, so this is `rule_type: "external_validation"` with the threshold and required
   > slot type carried as JSON in `rule_data`. Expressible today without touching their integrity
   > zome. What is still missing is the *operator* that evaluates it at transition time.
4. The custodian calls `update_lifecycle_stage()` (Prototype → Stable) / `update_resource_state()`
   (PendingValidation → Active); the governance rule **verifies the actual `HarmonyRecord`** before
   permitting the transition — it does **not** decide from the slot tag alone (see security note).
5. **The verification must read the real record, not just the researcher-written tag.** Nondominium
   calls `get_harmony_record_by_hash(ActionHash)` via `OtherCell` on a same-conductor ValiChord
   governance cell (both `Unrestricted`), then checks: (a) the record's *own* `agreement_level` +
   validator count meet threshold, and (b) the record's `request_ref` binds to **this** resource's
   deposited data. The slot tag is a fast pre-filter / display hint only.
6. **🆕 Re-sync the anchor (added 2026-08-16).** A successful transition must call
   `refresh_ndo_anchor_lifecycle_stage` so the cached `lifecycle_stage` on the group cell's
   `NdoAnchor` reflects the new stage. Their ADR resolves the anchor **by NDO identity**, not by
   action hash, precisely because the client knows the NDO rather than the anchor's
   original-vs-latest hashes. Skipping this leaves every group browser showing the pre-gate stage.

> **Security note (do not gate on the tag alone — the central call-prep point).** The slot link and
> its tag are written by the **researcher** (the party with incentive to inflate the result), and
> NDO's link `validate()` cannot cross-fetch ValiChord's record at validation time (separate DHT
> networks, no network calls in validation). So a tag-only gate is forgeable two ways: (i) a tag that
> overstates the record it points at, and (ii) a target pointing at a real-but-unrelated good record
> from another study. **Closing this requires step 5's fetch + resource-binding check at decision
> time.** Principle: *sovereignty over **when** (custodian keeps the trigger), never over **what** the
> record says.* This closes the *forged-result* hole; the distinct *captured/fake-reviewer* hole is
> closed upstream by reviewer admission + independence (`REVIEWER_SOURCING_SCOPING.md`), not by this fetch.

> **Update 2026-07-08:** the branch caveat below is lifted — the two-tier capability-slot pattern is
> now formalised in NDO's v1.0 architecture design (`documentation/specifications/ndo-v1-architecture-design.md`
> on their active branch `ndo-layer1`), with `SlotType` grown to include `VersionGraph`, `DigitalAsset`,
> `WeaveWAL` (still no validation slot — the gap stands). **Two flags for the call:** (1) their v1.0
> `GovernanceRuleType` enum does **not** include `ExternalValidation` — step 3's "Nondominium adds" is a
> request we must make explicitly, not something already planned; (2) governance-as-operator (the
> machinery that evaluates any rule at transition time) is specified but **unimplemented** (their
> #41–#44), so no Tier-2 rule of any kind is enforceable until it lands — sequencing dependency, not a
> design problem.

> **Precedent confirms this design (added 2026-06-17, based on NDO branch `feat/ndo-layer0-ui-102` —
> not yet merged to main, so subject to change).** The branch formalises the capability-slot surface
> as a first-class, two-tier pattern (`ndo_prima_materia.md` §6; `requirements/governance.md` §3.3),
> with **two worked external integrations already written into the spec: Unyt (`UnytAgreement` slot,
> §6.6) and Flowsta (`FlowstaIdentity` slot, §6.7).** ValiChord maps onto the *same* pattern as a
> third instance: **Tier 1** = the permissionless capability-slot link (step 2 — a discoverable
> signal); **Tier 2** = a custodian-endorsed `GovernanceRule` that makes it a precondition (step 3).
> Crucially, the Unyt rule is the direct template for our `ExternalValidation` rule: at full
> enforcement Unyt does **not** trust the slot tag — the transition request carries a proof
> (`rave_hash`) and the governance zome **queries the Unyt DHT via cross-DNA `call()` to retrieve and
> validate the actual RAVE**, confirming its inputs match the transition context. That is structurally
> identical to step 5's fetch-and-bind check. Two consequences: (i) our "verify the real record, not
> the tag" stance is the *house pattern*, not a novel ask; (ii) the expected "but verifying means
> reaching into ValiChord's separate network" objection is already answered — Unyt does exactly that
> cross-DNA fetch. One gap to fill: the SlotType vocabulary (§6.2) has no validation/reproducibility
> slot yet — ValiChord would add one (e.g. `ValidationAttestation`) pointing at the `HarmonyRecord`
> `ActionHash`. **Framing for the call: ValiChord = a new SlotType + a Tier-2 `ExternalValidation`
> GovernanceRule modelled on Unyt's `EconomicAgreement`/RAVE pattern.**

The threshold in step 3 is **Nondominium's policy to set**, not a ValiChord constant — consistent
with treating validator-count/badge-tier as a per-domain parameter, not a fixed ladder (the 3/5/7
badge counts are illustrative placeholders, not statistically-derived thresholds).

---

## 6. Honest limits specific to this mapping

- **Schema gap — units / ambient / reference-instrument fields don't exist yet.** `ValidatorPrivateAttestation`
  / `OutcomeSummary` carry `key_metrics` but **no** units, environmental conditions, reference-instrument
  serial, or free-text note. A credible hardware round needs those (to let third parties check for
  correlated-error non-independence post-reveal). Adding them is an **integrity-zome change → changes
  the DNA hash → Phase 1 / Version B**, not a coordinator hot-swap. This is the single biggest
  protocol gap for the hardware gate.
- **Reproduced ≠ correct.** The record proves independent labs converged on the same signature — not
  that the signature is the *right* reference, nor that it discriminates counterfeits. That's the
  metrology question, deliberately out of scope (§1).
- **Reference-instrument / ping-rig trust is not certified by ValiChord.** If every lab's rig is
  miscalibrated the same way, you get agreement on a wrong signature. State the rig as the trust
  anchor ValiChord does not itself certify (a future overlay could require a calibration-cert attestation).
- **Independence is admission-orthogonal and not Sybil-proof.** Covered in the reviewer-sourcing note:
  commit-reveal stops peeking, not out-of-band collusion or one-actor-two-keys; `person_key` / Flowsta
  `IsSamePerson` is the (currently absent) cross-system dedupe.
- **Latency.** A hardware round takes days/weeks (source parts + measure), not seconds. The protocol
  tolerates async rounds (`force_finalize_round` exists) but the gate UX must expect it.
- **Component/lot substitution.** Reviewers measuring different lots of "genuine" parts may legitimately
  diverge. A `DeviationType` exists in the type system; whether a different lot counts as "the same
  reference" is the bundle author's policy call.

---

## 7. Open questions to put to Tiberius

1. **Claim-relative or leaderless?** For the MVP gate, is a designer/originator committing the
   reference profile acceptable (claim-relative, ships now), or does the medical-device case require
   the leaderless/symmetric mode from the outset (Phase 1+ protocol work)?
2. **Does the gate need the per-lab numeric panel, or is the outcome-level `HarmonyRecord` enough?**
   If the panel is required for the governance decision, that's a read-aggregation layer to build
   (the data is on the attestations; the record doesn't carry it).
3. **Which fields must each reviewer record?** If units + ambient + rig-serial are required (likely
   for medical-grade), that's the integrity-zome change in §6 — schedule it as Version B.
4. **What's the pinned tolerance basis** for the actual sensor and ping method (of-reading vs FSS), and
   who authors the pinned procedure — the designer, or Nondominium governance?
5. **Threshold + firmware split:** confirm the gate invokes ValiChord only for the reference-fingerprint
   sub-claim, with Nondominium doing the firmware hash check itself and treating metrology separately.

---

*Together with `REVIEWER_SOURCING_SCOPING.md`, this closes the two open design questions from the
Discord agreement: who validates (sourcing) and what they commit/reproduce (this note). Both are
pre-design scoping for Tiberius's build — neither is a now-action.*
