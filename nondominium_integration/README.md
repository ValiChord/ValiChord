# ValiChord × Nondominium — Integration Notes

**Status:** Pre-implementation. Design decisions open. No integration code written yet.
**Authors:** Ceri John (ValiChord), in dialogue with Tiberius Brastaviceanu and Sacha (Sensorica)
**Last updated:** May 2026

> **Context:** ValiChord is production-grade and running end-to-end. The full 3-validator blind commit-reveal protocol is live on Oracle (v0.5.0) — researcher and validators all commit-reveal simultaneously, producing a permanent HarmonyRecord with a shareable public URL. The Nondominium integration builds on this foundation — ValiChord's outcomes feed into Nondominium's resource validation and contribution accounting.

---

> **⚠️ Correction (2026-06-16) — the gate must verify the real `HarmonyRecord`, not the slot tag.**
> Sections below (Step 5, Decision 1, Decision 5) describe NDO's governance rule checking the
> capability-slot **tag** (`{agreement_level, validator_count}`) to permit a transition. That framing
> is **superseded**: the slot link + tag are written by the *researcher* (who has incentive to inflate),
> and NDO can't cross-verify the tag at validation time (separate DHTs), so a tag-only gate is
> forgeable. At decision time the rule must **fetch and verify the actual `HarmonyRecord`** (its own
> `agreement_level`/count meet threshold; its `request_ref` binds to *this* resource) — the tag is a
> pre-filter/hint only. Principle: *sovereignty over **when**, not over **what** the record says.* Full
> reasoning (and the offline signature-verification alternative): `GATE_CLAIM_MAPPING_SCOPING.md` §5 +
> the `NONDOMINIUM_ARCHITECTURE.md` security caution. See also `REVIEWER_SOURCING_SCOPING.md`.

> **📌 Update (2026-06-17) — and NDO's own codebase now confirms this is the house pattern.** Their
> active branch `feat/ndo-layer0-ui-102` (not yet merged to main) formalises the capability slot as a
> first-class **two-tier** governance concept with two worked external integrations as templates: Unyt
> (`UnytAgreement`) and Flowsta (`FlowstaIdentity`). **ValiChord is the natural third instance** — a new
> SlotType (e.g. `ValidationAttestation`) + a Tier-2 `ExternalValidation` rule modelled on Unyt's
> `EconomicAgreement`. Notably, Unyt's rule already does exactly what the correction above requires: it
> does *not* trust the slot tag — it carries a proof and **queries the Unyt DHT cross-DNA to validate
> the real RAVE**. So "verify the real record, not the tag" is their existing pattern, and the
> "verifying means reaching into ValiChord's network" objection is already answered. Detail (caveated as
> branch-based): `GATE_CLAIM_MAPPING_SCOPING.md` §5 + `NONDOMINIUM_ARCHITECTURE.md` capability-slot section.

---

## Why this document exists

During early collaboration discussions with the Sensorica team, both codebases were read in parallel. What emerged was not a vague architectural compatibility — it was a specific, locatable gap in Nondominium that ValiChord's commit-reveal protocol is shaped to fill.

This document records what was found, proposes a concrete integration path, and names the three design decisions that need to be agreed before any code is written.

---

## The gap: a commented-out call

In Nondominium's `zome_resource` coordinator, `create_economic_resource()` contains a cross-zome call that is currently commented out:

```rust
// zome_resource coordinator — create_economic_resource()
// Disabled pending cross-zome communication resolution:
// validate_new_resource(ValidateNewResourceInput { ... })
```

The intent is clear: when a new `EconomicResource` is created, it enters state `ResourceState::PendingValidation`. Something external is meant to drive it to `Active`. That something is multi-validator consensus — exactly what ValiChord provides.

This is not a speculative fit. The Nondominium data model already anticipates it:

```rust
pub struct ResourceValidation {
    pub resource: ActionHash,
    pub validation_scheme: String,
    pub required_validators: u32,
    pub current_validators: u32,
    pub status: ...,
}
```

ValiChord's blind commit-reveal produces a `HarmonyRecord` — a cryptographically locked multi-validator consensus result. Wiring that outcome into `ResourceValidation.status` and calling `update_resource_state()` to transition the resource to `Active` is the natural integration point.

---

## What each project already provides

### Nondominium brings

| Component | What it offers |
|---|---|
| `EconomicResource` + `ResourceState` | The NDO data model and state machine ValiChord's outcomes feed into |
| `zome_gouvernance::create_validation_receipt()` | A ready-made sink for ValiChord's per-validator attestations |
| `zome_gouvernance::create_resource_validation()` | Multi-validator consensus tracking, already structured |
| `zome_gouvernance::log_economic_event(VfAction::Work)` | Participation Receipts (PPRs) — automatic contribution attribution for validators |
| `zome_person::promote_agent_with_validation()` | Role promotion pathway for enrolling ValiChord validators in NDO |
| hREA bridge pattern | Cross-DNA call pattern already in production use — ValiChord integration follows the same approach |
| Capability-based private data grants | Selective disclosure of private data without exposing it — philosophically identical to ValiChord's private DNAs |

### ValiChord brings

| Component | What it offers |
|---|---|
| Blind commit-reveal protocol | `seal_private_attestation()` → `submit_attestation()` — validators cannot see each other's findings before committing |
| `CommitmentAnchor` | SHA-256 hash of sealed attestation published to DHT before reveal — cryptographically un-gameable |
| `HarmonyRecord` + `ReproducibilityBadge` | Structured consensus outcome with reproducibility tier, agreement level, and deviation types |
| `ValidatorPrivateAttestation` | Private DNA entry — raw findings never reach the shared DHT |
| Membrane proof system | Ed25519 institutional credentials — validators are verified before joining a round |
| 4-DNA sovereignty model | Researcher's raw data stays in a private DNA. Only hashes move into the shared DHT. Compatible with Nondominium's private data philosophy |
| `valichord_attestation` Python library | Standalone evidence layer for AI evaluation runs — builds a deterministic SHA-256 bundle + Merkle tree over per-sample outputs. Expands the class of validatable NDO resources to include AI benchmark claims; the bundle hash becomes the `data_hash` when entering the full commit-reveal protocol |

### What neither project needs to rebuild

ValiChord does not need to build contribution tracking — Nondominium's PPR system handles it.
Nondominium does not need to build a blind validation protocol — ValiChord provides it.
Neither project needs to build cross-DNA call infrastructure — Nondominium's hREA bridge demonstrates the pattern works.

---

## Version alignment

| Dependency | ValiChord | Nondominium |
|---|---|---|
| `hdk` | `=0.6.1` | `^0.6.0` |
| `hdi` | `=0.7.1` | `^0.6.x` |
| Test framework | Sweettest + Tryorama/Vitest | Sweettest (primary; Tryorama deprecated in fork) |

Compatible — same minor version. No upgrades required to begin integration work.

**Note (April 2026):** Nondominium has no `DnaProperties` struct and `dna.yaml` has `properties: ~`.
Any integration configuration (e.g. ValiChord callback URL or contract address) cannot live in
Nondominium DNA properties — it must live in ValiChord's DNA properties or in an application-layer
config agreed at deployment time.

---

## Proposed integration path

A study validation round would proceed as follows. Steps marked **[NDO]** are calls into Nondominium zomes. Steps marked **[VC]** are calls into ValiChord DNAs.

**Step 1 — Study registered**
Researcher creates the study as an NDO resource **[NDO]** `zome_resource::create_economic_resource()` → state: `PendingValidation`
ValiChord opens a validation round **[VC]** `attestation::create_validation_request()`

**Step 2 — Validators enrolled**
Each validator is promoted to accountable agent in NDO **[NDO]** `zome_person::promote_agent_with_validation()`
Each validator publishes their profile in ValiChord **[VC]** `attestation::publish_validator_profile()`

**Step 3 — Commit phase**
Each validator seals their findings locally **[VC]** `validator_workspace::seal_private_attestation()`
Commitment hash published to shared DHT **[VC]** `attestation::notify_commitment_sealed()` — no content, hash only
No NDO action at this stage.

**Step 4 — Reveal phase**
After all commits are present, each validator reveals **[VC]** `attestation::submit_attestation()`
Protocol verifies `SHA-256(attestation || nonce) == CommitmentAnchor.commitment_hash` before accepting

**Step 5 — Harmony Record → NDO slot → state transition**
ValiChord governance DNA produces the consensus outcome **[VC]** `governance::check_and_create_harmony_record()`
Researcher observes the completed `HarmonyRecord` in their ValiChord client
Researcher writes a capability slot link to NDO's DHT **[NDO]** — base: resource hash, target: `HarmonyRecord` ActionHash, tag: `{agreement_level, validator_count}` as msgpack
Researcher calls `update_resource_state()` as normal **[NDO]** — NDO's `GovernanceRuleType::ExternalValidation` rule checks the slot tag and permits the transition → `Active`
NDO `NondominiumIdentity` lifecycle advanced **[NDO]** `zome_resource::update_lifecycle_stage()` (e.g. `Prototype` → `Stable`), with `NdoToTransitionEvent` link pointing to the `HarmonyRecord` ActionHash

> **Architecture (May 2026):** ValiChord's governance DNA participates only in ValiChord's governance DHT — it cannot write to NDO's DHT directly. The slot link is written by the researcher from their NDO agent context. The researcher is already the one calling `update_resource_state()`, so this adds one preceding step. See Decision 5 below.

**Step 6 — Validator contributions logged**
For each validator **[NDO]** `zome_gouvernance::log_economic_event(VfAction::Work)` → PPRs issued automatically
Validators receive contribution attribution in Nondominium's reputation system for completing a ValiChord round.

---

## Design decisions

Decisions 1 and 5 are resolved by agreement with the NDO team (May 2026). Decisions 2, 3, and 4 remain open.

### Decision 1 — Ownership of validation state ✓ RESOLVED: Option B

**Option B confirmed (May 2026):** ValiChord's `HarmonyRecord` is the authoritative record.
NDO's `ResourceValidation` entry is not used for ValiChord-validated resources. Instead, NDO's
governance rules check for a capability slot link from the resource hash to a `HarmonyRecord`
ActionHash, with the slot tag encoding `agreement_level` and `validator_count`. The governance
rule verifies the tag data meets the configured threshold — no ValiChord Rust crate dependency
needed, since `AgreementLevel` serialises as a plain string in msgpack.

**DHT locality note:** `get(action_hash)` in an NDO zome will not find a ValiChord
`HarmonyRecord` — they are on separate DHT networks. Threshold verification uses the slot tag.
Full record verification (validator identities, discipline, full outcome) uses
`get_harmony_record_by_hash(ActionHash)` via `OtherCell` on a same-conductor ValiChord
governance cell — both ValiChord read functions are `Unrestricted` and require no capability
secret. Note: `get_harmony_record(ExternalHash)` takes ValiChord's `request_ref` (data hash);
`get_harmony_record_by_hash(ActionHash)` takes the record hash directly from the slot link
target.

### Decision 2 — Membrane proofs and NDO roles

ValiChord validators hold an Ed25519 institutional credential (membrane proof) that grants access to the Attestation DNA. Nondominium validators hold an `AccountableAgent` role granted via `zome_person::promote_agent_with_validation()`, which calls into `zome_gouvernance` for approval.

These are currently independent systems. Should holding a valid ValiChord membrane proof be sufficient to trigger NDO role promotion automatically? Or should they remain independent, with validators enrolling separately in each system?

The answer depends on whether Sensorica wants ValiChord's credential system to be the trust anchor, or whether NDO's own governance process should remain the gatekeeper.

### Decision 3 — Resource creation ownership

Who creates the `EconomicResource` in Nondominium?

**Option A:** The researcher creates it through Nondominium tooling first, then provides the NDO resource hash to ValiChord when opening a validation round. ValiChord attaches to an existing NDO resource.

**Option B:** ValiChord's researcher workflow creates the NDO resource as part of study registration — a cross-app call from ValiChord's Researcher Repository DNA to `zome_resource::create_economic_resource()`.

Option A requires less integration code and preserves NDO as the canonical resource registry. Option B gives researchers a unified workflow but tightly couples the two systems at creation time.

### Decision 5 — Who is authorised to transition resource state? ✓ RESOLVED: capability slot approach

**Resolved (May 2026):** NDO confirmed they will not add a new `validate_and_activate_resource()`
function. The custodian gate stays intact. The integration uses capability slots instead.

**Confirmed approach:**
- NDO adds a `GovernanceRuleType::ExternalValidation` variant. When a resource is in
  `PendingValidation`, this rule specifies the required slot type (`valichord_harmony_record`),
  minimum validator count, and required agreement level.
- After ValiChord produces the `HarmonyRecord`, the researcher (custodian) writes a capability
  slot link to NDO's DHT from their NDO agent context: base = resource hash, target = `HarmonyRecord`
  ActionHash, tag = `{agreement_level, validator_count}` encoded as msgpack.
- The researcher then calls the existing `update_resource_state()`. The governance rule checks
  the slot: if a link with threshold-meeting tag data exists, the transition to `Active` proceeds.
  The custodian gate is unchanged — sovereignty over the transition stays with the researcher.

**Open sub-question (still to confirm with NDO):** where does the slot-writing function live —
`zome_resource` (alongside the state transition logic) or `zome_gouvernance` (alongside the
validation machinery)?

---

## Flowsta: a third system that bridges the identity gap

In March 2026, during the same period this integration was being scoped, Tiberius Brastaviceanu (Nondominium) and Soushi888 discussed integrating Flowsta Vault into Nondominium. Flowsta solves a multi-device identity problem that both ValiChord and Nondominium share independently — and its presence changes the integration design.

### The shared problem

Both systems key identity records to a device `AgentPubKey`:

- ValiChord DNA 3 `ValidatorProfile` and DNA 4 `ValidatorReputation` are indexed by device key
- Nondominium's `AgentPersonRelationship` and `Device` entries track device-to-person mappings internally

Neither system has a cross-system proof that two keys in different hApps belong to the same person.

### What Flowsta provides

Flowsta's Identity DNA (v1.3) writes `IsSamePersonEntry` records to a shared DHT — mutually signed by all device keys derived from the same BIP39 recovery phrase. Any app can query these to resolve multiple `AgentPubKey`s to one person, across DNAs and hApps.

Repo: `https://github.com/WeAreFlowsta/flowsta-vault-app`

### Impact on the integration path

**Step 2 — Validator identity linking (new, optional step)**
If validators use Flowsta Vault, their ValiChord device key and Nondominium agent key can be resolved to a single person via `IsSamePersonEntry`. This should be performed during onboarding and stored as a reference.

**Step 5–6 — Attribution across systems**
When ValiChord calls `log_economic_event(VfAction::Work)` in Nondominium for each validator, the `provider` must be the validator's NDO agent key. If ValiChord and NDO keys differ (different devices), Flowsta's identity links provide the resolution path.

Without Flowsta, the integration must either assume both systems use the same key (brittle) or implement its own cross-system key mapping (duplicated effort).

**Reputation continuity**
ValiChord `ValidatorReputation` is keyed by device `AgentPubKey`. A validator who rotates a device loses reputation continuity. ValiChord now has a native solution: `AgentIdentityAttestation` (implemented 2026-03-25) lets two agent keys jointly attest they share a logical identity via mutual Ed25519 signatures. `get_linked_agents()` resolves a key to all its linked alternates. This fixes the within-ValiChord continuity problem without Flowsta. For cross-system attribution (ValiChord key → NDO key), Flowsta's `IsSamePersonEntry` remains the cleanest path where validators use both systems from different devices.

### Design decision before integration code

See Decision 4 below.

### Decision 4 — Flowsta as shared identity layer

**Updated May 2026:** Nondominium's new **Lobby DNA** (PR #103) changes this picture. `GroupMembership.ndo_pubkey_map` records `lobby_pubkey → ndo_pubkey` for each NDO a validator belongs to. This is Nondominium's own MVP bridge for cross-DHT identity — without Flowsta.

This means: if a validator's ValiChord key and their NDO key are both registered in the same Nondominium Group, the mapping already exists in the Group DHT. The integration layer can query `GroupMembership.ndo_pubkey_map` to resolve the ValiChord key → NDO key for PPR attribution.

Flowsta remains relevant for validators using **different devices** for ValiChord and Nondominium (different physical keypairs), where the Group DHT mapping would not exist. For single-device validators it may be unnecessary.

**Option A — Use Lobby DNA GroupMembership as the MVP bridge.** Query `ndo_pubkey_map` at attribution time. Flowsta optional and post-MVP. Validators register the same key in both systems or join a shared Nondominium Group.

**Option B — Flowsta required for cross-system validators.** `IsSamePersonEntry` resolution is the standard path. Automated, device-agnostic. Validators who don't use Flowsta must register the same keypair in both systems manually.

**Option C — Flowsta optional with GroupMembership fallback.** Try GroupMembership first; fall back to Flowsta if keys differ; fall back to manual table if neither available.

Option A unblocks the MVP integration without a Flowsta dependency. Option B is cleanest long-term for multi-device validators. Option C is most permissive but adds complexity.

---

## What this integration is not

ValiChord is not a replacement for Nondominium's governance system. Nondominium's `zome_gouvernance` handles economic events, commitments, claims, and reputation across the full lifecycle of an NDO. ValiChord handles one specific moment in that lifecycle — the cryptographically verifiable peer validation of a study's reproducibility.

ValiChord is also designed to remain independent: usable outside any single ecosystem, applicable to any domain requiring high-integrity verification. This is not in conflict with serving as Nondominium's integrity layer — it is the condition under which that role is most credible.

---

## Further reading

- [ValiChord and the Digital Commons](../docs/18_ValiChord_and_Open_Cooperativism.md) — ValiChord's philosophical alignment with commons-based peer production and Ostrom's design principles
- [How a Validation Round Works](../docs/15_How_a_Validation_Round_Works.md) — step-by-step walk through the commit-reveal protocol
- [4-DNA Architecture](../docs/7_ValiChord_4-DNA_architecture_technical.md) — technical reference for the four-DNA sovereignty model
- [Nondominium repository](https://github.com/Sensorica/nondominium) — Sensorica's hApp
- [Flowsta Vault](https://github.com/WeAreFlowsta/flowsta-vault-app) — multi-device identity layer; Identity DNA v1.3 provides `IsSamePersonEntry` cross-system key resolution

---

*Written March 2026 after reading both codebases. Updated May 2026: version table corrected (ValiChord now 0.6.1), Decision 4 updated for Nondominium Lobby DNA (PR #103) and GroupMembership identity bridge. Decisions 1 and 5 marked resolved following NDO team response (May 2026): capability slot approach confirmed, custodian gate preserved. Integration path Step 5 rewritten to reflect slot-based activation. DHT locality constraint documented.*
