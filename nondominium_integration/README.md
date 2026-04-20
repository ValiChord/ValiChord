# ValiChord × Nondominium — Integration Notes

**Status:** Pre-implementation. Design decisions open. No integration code written yet.
**Authors:** Ceri John (ValiChord), in dialogue with Tiberius Brastaviceanu and Sacha (Sensorica)
**Last updated:** April 2026

> **Context:** ValiChord is production-grade and running end-to-end. The full 3-validator blind commit-reveal protocol is live on Oracle (v0.3.0) — researcher and validators all commit-reveal simultaneously, producing a permanent HarmonyRecord with a shareable public URL. The Feynman AI research agent integration is complete (ValiChord skill in Feynman 0.2.16, PR #23 closed). The Nondominium integration builds on this foundation — ValiChord's outcomes feed into Nondominium's resource validation and contribution accounting. See `feynman_integration/INTEGRATION_VISION.md` for the Feynman integration that is already live.

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
    pub current_validators: Vec<AgentPubKey>,
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
| `zome_person::promote_agent_to_accountable()` | Role promotion pathway for enrolling ValiChord validators in NDO |
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

### What neither project needs to rebuild

ValiChord does not need to build contribution tracking — Nondominium's PPR system handles it.
Nondominium does not need to build a blind validation protocol — ValiChord provides it.
Neither project needs to build cross-DNA call infrastructure — Nondominium's hREA bridge demonstrates the pattern works.

---

## Version alignment

Both projects target the same Holochain release:

| Dependency | ValiChord | Nondominium |
|---|---|---|
| `hdk` | `0.6` | `0.6.0` |
| `hdi` | `0.7` | `0.6.x` |
| Test framework | Tryorama + Vitest | Tryorama + Vitest |

No version upgrades required on either side to begin integration work.

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
Each validator is promoted to accountable agent in NDO **[NDO]** `zome_person::promote_agent_to_accountable()`
Each validator publishes their profile in ValiChord **[VC]** `attestation::publish_validator_profile()`

**Step 3 — Commit phase**
Each validator seals their findings locally **[VC]** `validator_workspace::seal_private_attestation()`
Commitment hash published to shared DHT **[VC]** `attestation::notify_commitment_sealed()` — no content, hash only
No NDO action at this stage.

**Step 4 — Reveal phase**
After all commits are present, each validator reveals **[VC]** `attestation::submit_attestation()`
Protocol verifies `SHA-256(attestation || nonce) == CommitmentAnchor.commitment_hash` before accepting

**Step 5 — Harmony Record → NDO**
ValiChord governance DNA produces the consensus outcome **[VC]** `governance::finalize_harmony_record()`
Result written into Nondominium **[NDO]** `zome_gouvernance::create_validation_receipt()` per validator
Resource state transitioned **[NDO]** `zome_resource::update_resource_state()` → `Active`
NDO `NondominiumIdentity` lifecycle advanced **[NDO]** `zome_resource::update_lifecycle_stage()` (e.g. `Prototype` → `Stable`), with `NdoToTransitionEvent` link pointing to the `HarmonyRecord` hash

> **Constraint (April 2026):** `update_resource_state()` is custodian-gated — only the resource custodian can call it. ValiChord's governance DNA is not the custodian. See Decision 5 below.

**Step 6 — Validator contributions logged**
For each validator **[NDO]** `zome_gouvernance::log_economic_event(VfAction::Work)` → PPRs issued automatically
Validators receive contribution attribution in Nondominium's reputation system for completing a ValiChord round.

---

## Three design decisions before any code

These are open questions. They need agreement between both teams before integration coding begins.

### Decision 1 — Ownership of validation state

Nondominium has a `ResourceValidation` entry with `required_validators`, `current_validators`, and `status`. ValiChord has `ValidationRequest` with its own multi-validator tracking.

**Option A:** ValiChord's commit-reveal runs autonomously. On completion, it writes the outcome into Nondominium's `ResourceValidation.status`. NDO is the authoritative state; ValiChord feeds it.

**Option B:** ValiChord's `HarmonyRecord` is the authoritative record. Nondominium's `ResourceValidation` is not used for ValiChord-validated resources. NDO governance rules check for a linked `HarmonyRecord` instead.

Option A is simpler to implement. Option B avoids duplication but requires Nondominium's governance rules to understand ValiChord entry types.

### Decision 2 — Membrane proofs and NDO roles

ValiChord validators hold an Ed25519 institutional credential (membrane proof) that grants access to the Attestation DNA. Nondominium validators hold an `AccountableAgent` role granted via `zome_person::promote_agent_to_accountable()`, which calls into `zome_gouvernance` for approval.

These are currently independent systems. Should holding a valid ValiChord membrane proof be sufficient to trigger NDO role promotion automatically? Or should they remain independent, with validators enrolling separately in each system?

The answer depends on whether Sensorica wants ValiChord's credential system to be the trust anchor, or whether NDO's own governance process should remain the gatekeeper.

### Decision 3 — Resource creation ownership

Who creates the `EconomicResource` in Nondominium?

**Option A:** The researcher creates it through Nondominium tooling first, then provides the NDO resource hash to ValiChord when opening a validation round. ValiChord attaches to an existing NDO resource.

**Option B:** ValiChord's researcher workflow creates the NDO resource as part of study registration — a cross-app call from ValiChord's Researcher Repository DNA to `zome_resource::create_economic_resource()`.

Option A requires less integration code and preserves NDO as the canonical resource registry. Option B gives researchers a unified workflow but tightly couples the two systems at creation time.

### Decision 5 — Who is authorised to transition resource state?

`update_resource_state()` in the fork is currently custodian-gated: only the agent holding custody of
the `EconomicResource` can drive it from `PendingValidation` to `Active`. ValiChord's governance DNA
is not the custodian, so it cannot call this directly.

> **Architecture update (April 2026):** The earlier ValiChord design had a `harmony_record_creator_key`
> DNA property that identified a single trusted agent as the HarmonyRecord author. That key has been
> removed. `HarmonyRecord` creation is now **participatory** — any validator who participated in the
> round may call `check_and_create_harmony_record` and trigger finalisation. This changes Option A
> slightly: the integration layer can no longer rely on a single fixed agent to call
> `validate_and_activate_resource()`; it must accept calls from any member of `participating_validators`.

**Option A:** Add a governance-authorised pathway — a new `validate_and_activate_resource()` function
that accepts a `HarmonyRecord` action hash instead of requiring custodianship. The integration layer
calls this from any participating validator; the function verifies the referenced `HarmonyRecord`
(and that the caller is in `participating_validators`) before transitioning state.

**Option B:** Keep the custodian gate. After ValiChord produces the `HarmonyRecord`, the researcher
(who is the custodian) is notified and calls `update_resource_state()` themselves, passing the
`HarmonyRecord` hash as the triggering event reference. ValiChord triggers the notification;
the transition remains a human (or Feynman) action.

Option A is a tighter integration but requires a new Nondominium function and a multi-caller trust
decision (any participating validator, not a single fixed key). Option B is looser but keeps NDO's
custodian model intact and avoids coupling the two DNAs at the Rust level.

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

Should both systems assume validators use Flowsta Vault, making `IsSamePersonEntry` resolution the standard path for cross-system attribution? Or should Flowsta be optional, with a manual key-mapping fallback?

**Option A — Flowsta required for cross-system validators.** Integration code assumes the Flowsta Identity DNA is available. Key resolution is automated. Validators who don't use Flowsta Vault must register the same keypair in both systems manually.

**Option B — Flowsta optional.** Integration maintains a separate key-mapping table in one or both systems. Flowsta resolution is used when available, manual fallback otherwise.

Option A is cleaner and avoids duplicating Flowsta's work. Option B is more permissive but adds maintenance surface. The decision hinges on whether both teams are willing to make Flowsta Vault a prerequisite for validators who participate in both systems.

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

*This document was written after reading both codebases. All function names, entry types, and zome references correspond to the current state of each repository as of March 2026.*
