# ValiChord × Nondominium — Integrated System Vision

**Status:** Pre-implementation design document — ValiChord protocol is production-grade; integration layer not yet written
**Written:** March 2026 | **Updated:** May 2026
**Based on:** Full read-through of both codebases

---

> **⚠️ Correction (2026-06-16) — the gate must verify the real `HarmonyRecord`, not the slot tag.**
> The integration path and Decision 5 below describe NDO's governance rule checking the capability-slot
> **tag** (`{agreement_level, validator_count}`) to permit a transition. That framing is **superseded**:
> the slot link + tag are written by the *researcher* (incentive to inflate), and NDO can't cross-verify
> the tag at validation time (separate DHTs), so a tag-only gate is forgeable. At decision time the rule
> must **fetch and verify the actual `HarmonyRecord`** (its own `agreement_level`/count meet threshold;
> its `request_ref` binds to *this* resource) — the tag is a pre-filter/hint only. *Sovereignty over
> **when**, not over **what**.* Full reasoning: `GATE_CLAIM_MAPPING_SCOPING.md` §5 +
> `NONDOMINIUM_ARCHITECTURE.md` security caution; reviewer admission in `REVIEWER_SOURCING_SCOPING.md`.

---

## The Core Thesis

Nondominium is a decentralized resource-sharing commons. When someone contributes a resource — a tool, a manufacturing process, a computational workflow, a dataset — it enters `ResourceState::PendingValidation`. There is no mechanism to get it out of that state. The commented-out call to `validate_new_resource()` in `create_economic_resource()` marks exactly where that mechanism was always supposed to plug in.

ValiChord is that mechanism.

The integrated system is a **trusted, ungameable pipeline from resource contribution to active commons infrastructure**, with no central authority at any point in the chain.

---

## What Each System Brings

**Nondominium brings:**
- The resource lifecycle (`EconomicResource`, `ResourceState`, governance rules)
- Contributor identity and role hierarchy (Member → Stewardship → Coordination → Governance)
- The economic accounting layer (`EconomicEvent`, `VfAction`, ValueFlows compliance via hREA)
- The PPR system — bilateral cryptographically-signed participation receipts that build reputation without exposing individual transactions
- Private data capability grants (field-level, revocable, time-limited)
- The hREA bridge — proven cross-DNA call pattern already in production

**ValiChord brings:**
- Blind commit-reveal protocol — validators seal findings independently before seeing any other assessment, using SHA-256(msgpack(attestation) ∥ nonce). The seal is cryptographically binding. No adaptive reveals possible.
- Institutional credentialing — validators hold Ed25519 membrane proofs before entering an Attestation DNA
- Four-DNA sovereignty — researcher's raw data and validator working notes never enter any shared DHT
- The `HarmonyRecord` — deterministic majority consensus with agreement level, immutable once written
- The `ReproducibilityBadge` — a cryptographically traceable Gold/Silver/Bronze/Failed credential, linked to the HarmonyRecord that produced it, linked to every ValidationAttestation that fed it
- `ValidatorReputation` — per-discipline agreement rate, average time invested, certification tier (Provisional/Standard/Advanced/Certified)
- `AgentIdentityAttestation` — mutual Ed25519 proof that two device keys belong to the same person
- `valichord_attestation` Python library — standalone evidence layer for AI evaluation runs; builds a deterministic SHA-256 bundle + Merkle tree over per-sample outputs. Expands the class of validatable NDO resources to include AI benchmark claims; the bundle hash becomes the `data_hash` when entering the full commit-reveal protocol

**What neither needs to rebuild:** Nondominium does not need a blind validation protocol. ValiChord does not need contribution tracking or resource lifecycle management. The cross-DNA call pattern is already proven in Nondominium's hREA bridge.

---

## The End-to-End System

### Act 1 — Resource Contribution (Nondominium)

A contributor creates a resource in Nondominium:

```
zome_resource::create_economic_resource({
    spec_hash: ...,
    quantity: 1.0,
    unit: "workflow",
})
→ ResourceState::PendingValidation
→ [integrated: fires ValiChord validation round automatically]
```

The commented-out call to `validate_new_resource()`, once wired, passes the NDO resource hash to ValiChord and opens a `ValidationRequest`. The researcher simultaneously locks their expected results — metric values, effect sizes, whatever the pre-registered protocol specifies — before validators see anything.

### Act 2 — Blind Validation (ValiChord)

Three to seven validators, each holding a valid institutional credential (membrane proof for the Attestation DNA), claim the study. They are matched by discipline. COI is enforced: no one from the researcher's institution may claim.

Each validator independently runs the analysis. Then:

1. `seal_private_attestation()` — validator enters their findings. A 32-byte nonce is generated. The attestation is serialised to MessagePack and SHA-256(msgpack ∥ nonce) is computed. The private entry containing findings, nonce, and hash is written to the validator's private Workspace DNA — it never leaves their device. Only the hash goes to the shared DHT via `notify_commitment_sealed()`.

2. Once all validators' hashes are on the DHT, `PhaseMarker::RevealOpen` is written. No one can see anyone else's assessment — all that exists on the shared DHT is a set of opaque hashes.

3. The researcher reveals their expected results. ValiChord verifies: SHA-256(msgpack(metrics) ∥ nonce) == the hash they committed earlier. Mismatch → rejected.

4. Each validator calls `submit_attestation()`, passing their sealed findings and nonce. ValiChord verifies the hash matches the `CommitmentAnchor` they filed in step 1. If it matches, the `ValidationAttestation` is written to the shared DHT — immutably and permanently.

**The guarantee:** the assessment that gets written is provably the same one that was sealed before unblinding. There is no mechanism to change your answer after seeing others'.

**This protocol is now running end-to-end.** As of v0.5.0 (May 2026), 3 Claude AI validators plus a researcher all commit-reveal simultaneously on a live Holochain conductor on Oracle. The resulting `HarmonyRecord` is queryable at a permanent public URL (`GET /record/<hash>`) with no authentication required. A working demo is at `demo/ai_validator.py` — see `demo/DECENTRALISED_DEMO.md`.

### Act 3 — Consensus (ValiChord Governance DNA)

When the last validator reveals, `check_and_create_harmony_record()` fires:

- Sorts validator-attestation pairs deterministically (by validator pubkey) so two concurrent finalisations always produce identical content
- Derives majority outcome (plurality vote across Reproduced / PartiallyReproduced / FailedToReproduce / UnableToAssess)
- Derives agreement level from success rate: ≥90% → ExactMatch, ≥70% → WithinTolerance, ≥50% → DirectionalMatch
- Writes an immutable `HarmonyRecord`
- Issues a `ReproducibilityBadge`: Gold (≥7 validators, ExactMatch), Silver (≥5, WithinTolerance+), Bronze (≥3, DirectionalMatch+), FailedReproduction if divergent
- Updates each validator's `ValidatorReputation` in their discipline

### Act 4 — Resource Activation (Nondominium)

ValiChord's governance DNA operates only within ValiChord's governance DHT — it cannot write
to NDO's DHT directly. The activation path goes through the researcher (custodian), who is a
participant on both DHTs.

The researcher observes the completed `HarmonyRecord` in their ValiChord client (or is notified
by the UI). They perform two steps:

**Step 4a — Write the capability slot link [NDO]**

```
write_valichord_slot({
    resource_hash:        <NDO EconomicResource / NondominiumIdentity hash>,
    harmony_record_hash:  <ValiChord HarmonyRecord ActionHash>,
    request_ref:          <ValiChord ExternalHash — the SHA-256 data hash>,
    agreement_level:      "ExactMatch",   // plain string — AgreementLevel has no serde tag
    validator_count:      3,
})
→ creates link: base = resource_hash, target = harmony_record_hash,
               tag = {agreement_level, validator_count} as msgpack
```

**Step 4b — Transition resource state [NDO]**

```
zome_resource::update_resource_state({ resource_hash, new_state: Active })
→ NDO GovernanceRuleType::ExternalValidation checks the slot tag against its threshold
→ threshold met → ResourceState: PendingValidation → Active
→ NondominiumIdentity lifecycle advanced via update_lifecycle_stage() if required
   (NdoToTransitionEvent link points to the HarmonyRecord ActionHash)
```

NDO's `ResourceValidation` entry is not used — the `HarmonyRecord` is the authoritative record.
The full audit trail (HarmonyRecord → each ValidationAttestation → each CommitmentAnchor) is
permanently queryable on ValiChord's governance and attestation DHTs. For callers who want to
verify the full record, `get_harmony_record_by_hash(ActionHash)` on ValiChord's governance
coordinator returns the complete entry; both governance read functions are `Unrestricted`.

### Act 5 — Validator Attribution (Nondominium PPR System)

For each validator who completed the round:

```
zome_gouvernance::log_economic_event({
    action_type: VfAction::Work,
    provider: validator_ndo_agent_key,
    generate_pprs: true,
})
→ 2 bilateral PrivateParticipationClaims generated automatically
→ feeds into derive_reputation_summary()
```

Validators earn NDO reputation for completing ValiChord rounds. This closes the economic loop: validation contributes to a validator's standing in the Sensorica commons, not just to ValiChord's internal reputation ledger.

---

## What the System Produces — For Each Party

**Researcher who contributed a resource:**
- `ResourceState::Active` — their resource is trusted infrastructure in the NDO commons
- `ReproducibilityBadge` — cryptographically traceable credential with full audit trail
- Verifiable provenance: anyone can follow the chain backwards from badge → HarmonyRecord → each individual ValidationAttestation → each CommitmentAnchor → original ValidationRequest

**Validator who participated:**
- `ValidatorReputation` update: +1 validation, updated agreement_rate, potential tier promotion (Provisional → Standard → Advanced → Certified)
- NDO PPRs: participation receipts that accrue in Nondominium's reputation system
- `AccountableAgent` status in Nondominium — required for custody and economic responsibility

**Commons participant asking "can I trust this resource?":**
- Check `ResourceState` → Active
- Follow to `ResourceValidation` → approved, 5 validators
- Follow to `ReproducibilityBadge` → SilverReproducible
- Follow to `HarmonyRecord` → WithinTolerance, 5 validators, avg 3,600 seconds
- Follow to each `ValidationAttestation` → individual findings, confidence levels, deviation flags
- Check each `ValidatorReputation` → Certified tier, 78% agreement rate, 12 prior validations in discipline

**No central authority to trust. The chain is the proof.**

---

## The Identity Problem and Its Solutions

ValiChord knows validators by their ValiChord device `AgentPubKey`. Nondominium knows them by their NDO agent key. These may differ if someone joined each system from a different device.

**Within ValiChord** (implemented, 2026-03-25): `AgentIdentityAttestation` — both device keys jointly sign a canonical 78-byte payload (sorted pubkeys). `get_linked_agents()` resolves any key to all linked alternates. Reputation continuity is maintained across device rotation.

**Within Nondominium** (implemented, May 2026): The new Lobby DNA provides a three-layer identity model. `GroupMembership.ndo_pubkey_map` records `lobby_pubkey → ndo_pubkey` per NDO for every validator in a Group. This is the MVP bridge for cross-DHT identity within Nondominium — without Flowsta.

**Across systems** (Decision 4, updated): When `log_economic_event(VfAction::Work, provider: X)` fires, X must be the validator's NDO key. The Lobby DNA's `GroupMembership.ndo_pubkey_map` can resolve this if both the ValiChord key and the NDO key are registered in a shared Nondominium Group — the likely case for single-device validators. Flowsta Vault's `IsSamePersonEntry` remains the cleanest path for multi-device validators where keys differ across systems. See Decision 4 in `README.md` for the three options.

---

## Decisions — resolved and open

| # | Question | Resolution / Status |
|---|---|---|
| 1 | Who owns validation state? | ✓ **Resolved (May 2026):** `HarmonyRecord` is canonical. NDO governance rules check a capability slot link + tag. `ResourceValidation` not used. |
| 5 | Who drives the state transition? | ✓ **Resolved (May 2026):** Custodian gate stays intact. Researcher writes slot link from NDO agent context, then calls existing `update_resource_state()`. NDO adds `GovernanceRuleType::ExternalValidation`. Open sub-question: slot-writing function location (`zome_resource` vs `zome_gouvernance`). |
| 2 | Membrane proofs vs NDO roles | Open: auto-promote on ValiChord credential vs independent enrollment |
| 3 | Who creates the NDO resource? | Open: researcher-first in NDO (Option A, less coupling) vs ValiChord cross-app call (Option B) |
| 4 | Cross-system identity | Open: NDO Lobby `GroupMembership` as MVP bridge (Option A) vs Flowsta required (Option B) vs both with fallback (Option C) |

**Deployment note:** ValiChord's `round_timeout_secs` is a DNA property (default 604800 s / 7 days). Rounds that have not reached full quorum within this window can be force-finalised by `force_finalize_round()` on the governance DNA. Sensorica should decide at deployment time whether 7 days is appropriate for their validation workflows — it is set in `governance/dna.yaml` and baked into the DNA hash, so changing it requires a new DNA.

---

## Real-World Example: The Concordia Biosensor Calibration Protocol

### Background

A researcher at Concordia University — affiliated with Sensorica — has developed an open-source calibration protocol for low-cost water quality biosensors. The protocol specifies how to calibrate pH, dissolved oxygen, and nitrate readings using a defined reagent sequence and statistical correction model. It is intended to become shared infrastructure: any Sensorica member building environmental monitoring devices should be able to rely on it.

The problem: how does anyone know the protocol actually works? The researcher says it does. But other builders will stake their devices on it. They need proof that is not just the researcher's word.

This is the exact problem the integrated system solves.

---

### Step-by-Step Walkthrough

**Day 0 — Researcher registers the protocol**

Dr. Yemi Adeyemi publishes her calibration protocol on OSF with a pre-registered analysis plan. She then registers it in Nondominium as a new resource:

```
zome_resource::create_economic_resource({
    spec_hash: biosensor_calibration_spec_hash,
    quantity: 1.0,
    unit: "protocol",
})
```

The resource enters `ResourceState::PendingValidation`. The integration layer fires `ValidationRequest` in ValiChord automatically, using the OSF DOI as `protocol_ref` and a SHA-256 hash of the protocol document bundle as `data_hash`. The `ValidationTier` is set to Enhanced (requires 5 validators). Discipline: `ComputationalBiology`.

Dr. Adeyemi also calls `lock_researcher_result()` in her Researcher Repository DNA — she commits to her expected calibration metric values (pH accuracy within ±0.05, DO saturation within ±2%, nitrate detection threshold at 0.1 mg/L). A SHA-256 hash of those values and a nonce goes to the shared DHT. Her actual numbers stay private on her device.

---

**Days 1–14 — Validators claim and work**

Five validators with ComputationalBiology credentials see the pending study appear in their ValiChord interface. Each has previously registered with an institutional credential (a lab at McGill, ETH Zürich, UC Davis, Wageningen, and the Sensorica community lab). Their membrane proofs are Ed25519 signatures from their institutional issuers, baked into the Attestation DNA.

None of them are from Concordia. COI check passes.

Each validator independently:
1. Downloads the protocol document from the OSF link in `ValidationRequest.data_access_url`
2. Runs the calibration sequence using their own biosensor hardware and reagents
3. Records their measured values against Dr. Adeyemi's stated expected values

There is no coordination between them. They do not know what each other found.

---

**Day 14 — Commit phase**

Each validator calls `seal_private_attestation()`:

- Validator A (McGill): found pH accuracy ±0.04, DO ±1.8%, nitrate threshold 0.09 mg/L → outcome: `Reproduced`
- Validator B (ETH Zürich): found pH accuracy ±0.06, DO ±2.1%, nitrate threshold 0.11 mg/L → outcome: `PartiallyReproduced` (nitrate slightly outside tolerance)
- Validator C (UC Davis): found pH accuracy ±0.04, DO ±1.9%, nitrate threshold 0.10 mg/L → outcome: `Reproduced`
- Validator D (Wageningen): found pH accuracy ±0.05, DO ±2.0%, nitrate threshold 0.10 mg/L → outcome: `Reproduced`
- Validator E (Sensorica lab): found pH accuracy ±0.07, DO ±2.3%, nitrate threshold 0.13 mg/L → outcome: `PartiallyReproduced`

For each: nonce generated, attestation serialised to MessagePack, SHA-256(msgpack ∥ nonce) computed. The hash — not the result — is published to the shared Attestation DHT as a `CommitmentAnchor`. The actual findings stay private.

All five hashes land on the DHT. `check_all_commitments_sealed_inner()` counts five CommitmentAnchors against `num_validators_required = 5`. The gate opens. `PhaseMarker::RevealOpen` is written.

---

**Day 15 — Reveal phase**

Dr. Adeyemi sees the `RevealOpen` phase marker. She calls `reveal_researcher_result()`, passing her original metrics and nonce. ValiChord recomputes SHA-256(msgpack(metrics) ∥ nonce) and matches it against the `ResearcherResultCommitment` she filed on Day 0. It matches. Her expected values are written to the shared DHT as a `ResearcherReveal`.

Each validator calls `submit_attestation()`, passing their findings and nonce. ValiChord:
1. Fetches their `CommitmentAnchor`
2. Recomputes SHA-256(msgpack(attestation) ∥ nonce)
3. Verifies it matches the hash they committed on Day 14
4. Writes the `ValidationAttestation` immutably to the shared DHT

Four validators reproduced or partially reproduced. One partially reproduced. The sealed findings are now permanent, public, and provably identical to what was assessed before unblinding.

---

**Day 15 — Consensus**

The fifth attestation fires `check_and_create_harmony_record()`. Governance DNA:

- Counts outcomes: 3× Reproduced, 2× PartiallyReproduced
- Majority: `Reproduced`
- Success rate: 5/5 = 100% (both Reproduced and PartiallyReproduced count as success)
- Agreement level: `ExactMatch` (≥90%)
- Validator count: 5
- Badge threshold: Silver requires ≥5 validators + WithinTolerance or better → `SilverReproducible`

Writes:

```
HarmonyRecord {
    request_ref: biosensor_calibration_hash,
    outcome: Reproduced,
    agreement_level: ExactMatch,
    participating_validators: [mcgill_key, eth_key, ucdavis_key, wagen_key, sensorica_key],
    validation_duration_secs: 86400 * 14,
    discipline: ComputationalBiology,
}

ReproducibilityBadge {
    study_ref: biosensor_calibration_hash,
    issued_to: yemi_adeyemi_key,
    badge_type: SilverReproducible,
    harmony_record_ref: harmony_record_hash,
}
```

Both entries are immutable. They cannot be deleted or updated.

---

**Day 15 — Resource activation**

ValiChord's governance DNA calls into Nondominium:

```
zome_gouvernance::create_validation_receipt() — for each of the 5 validators
zome_gouvernance::create_resource_validation() — status: "approved", 5/5 validators
zome_resource::update_resource_state({ new_state: Active })
```

The biosensor calibration protocol is now `ResourceState::Active` in the Nondominium commons. Any Sensorica member building an environmental monitoring device can reference it with confidence. They can query the `ResourceValidation` entry, follow the link to the `ReproducibilityBadge`, and see the full audit trail down to individual validator assessments.

---

**Day 15 — Validator attribution**

For each of the five validators, Nondominium fires:

```
zome_gouvernance::log_economic_event({
    action_type: VfAction::Work,
    provider: validator_ndo_key,
    generate_pprs: true,
})
```

Two bilateral `PrivateParticipationClaim` entries are generated per validator — one for the validator, one for the community. These feed into `derive_reputation_summary()`. The validators' NDO standing increases. A validator who completes many such rounds accrues reputation as a trusted expert in their discipline within the Sensorica commons, independent of any single organisation's endorsement.

Each validator's `ValidatorReputation` in ValiChord also updates: +1 validation, updated agreement_rate. The Sensorica lab validator (Validator E), having completed 5 validations total now with a 60% agreement rate, holds their `Standard` tier (first threshold crossed). The Wageningen validator, with 22 completions and an 83% agreement rate, promotes to `Advanced`.

---

**Six months later — A builder trusts the protocol**

A hardware contributor in Nairobi, building a low-cost water quality monitoring node for a community project, wants to use Dr. Adeyemi's calibration protocol. They check the resource in Nondominium:

```
zome_resource::get_economic_resource(resource_hash)
→ ResourceState: Active

zome_gouvernance::check_validation_status(resource_hash)
→ ResourceValidation { status: "approved", validators_required: 5, current: 5 }
→ harmony_record_ref: [hash]
→ badge_ref: [hash]

[Follow badge_ref]
→ ReproducibilityBadge { badge_type: SilverReproducible }

[Follow harmony_record_ref]
→ HarmonyRecord { outcome: Reproduced, agreement_level: ExactMatch, 5 validators }

[Follow each ValidatorReputation]
→ Senior tier (Wageningen), Certified (McGill), Certified (ETH), Certified (UC Davis), Certified (Sensorica)
```

They use the protocol. Not because they trust Dr. Adeyemi. Not because Sensorica endorses it. Because five independent experts, none from the same institution as the researcher, attempted to reproduce it and 100% of them succeeded — and every step of that process is permanently recorded, verifiable, and unforgeable.

---

## What This System Is, Philosophically

Nondominium solves the governance problem for shared resources: how do you run a commons without an owner? ValiChord solves the provenance problem: how do you know a resource is what it claims to be, without trusting the person claiming it?

Together they produce a commons where resources earn their Active status through cryptographically rigorous peer review, validators earn standing through demonstrated accuracy, and the entire history of every validation round is permanently, immutably, publicly auditable — with no platform, no admin, and no single point of trust at any stage.

That is what neither system does alone.

---

## Further Reading

- [Nondominium Architecture Reference](NONDOMINIUM_ARCHITECTURE.md) — zome structure, entry types, function signatures
- [Integration Design Notes](README.md) — the gap, what each project provides, open design decisions
- [4-DNA Architecture](../docs/7_ValiChord_4-DNA_architecture_technical.md) — ValiChord's four-DNA sovereignty model
- [How a Validation Round Works](../docs/15_How_a_Validation_Round_Works.md) — step-by-step commit-reveal walkthrough
- [Nondominium repository](https://github.com/Sensorica/nondominium)
- [Flowsta Vault](https://github.com/WeAreFlowsta/flowsta-vault-app) — cross-system identity resolution
