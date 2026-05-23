# Nondominium — Architecture Reference

Quick reference for ValiChord integration work. Written March 2026 from reading the source at
https://github.com/Sensorica/nondominium. Updated April 2026 after re-reading the `dev` branch.

---

## Overview

Two DNAs as of May 2026: `nondominium` (core) + `lobby` (cross-NDO federation, added PR #103).
HDK `^0.6.0` / HDI `0.6.x`. Tests: Sweettest (Rust, primary) — Tryorama/Vitest tests deprecated in the fork.

```
nondominium.happ
├── nondominium (DNA)
│   ├── zome_person       — agent identity, roles, private data, capability grants, device management
│   ├── zome_resource     — resource specs, NDO Layer 0 identity, economic resources (ValueFlows)
│   ├── zome_gouvernance  — validation, economic events, commitments, PPRs
│   └── misc              — coordinator only; single ping() function (test/debug scaffold)
└── lobby (DNA)           — cross-NDO discovery and agent federation (see Lobby DNA section below)
```

**Shared crates (May 2026):**
- `crates/shared/` (`nondominium_shared`) — `LifecycleStage`, `PropertyRegime`, `ResourceNature` types + shared error types + path helpers. The resource integrity zome re-exports these; refer to `nondominium_shared::types` when reading the source.
- `packages/shared-types/` — TypeScript mirrors (lobby, person, resource, governance, PPR types).

A `nondominium_utils` crate at `crates/utils/` provides cross-zome call helpers (`call_governance_zome`, `call_person_zome`) used by all three coordinator zomes.

---

## zome_person

### Entry types
| Entry | Key fields |
|---|---|
| `Person` | name, avatar_url, bio, hrea_agent_hash (Option, added for hREA bridge) |
| `PrivatePersonData` | legal_name, email, phone, address, timezone, location |
| `PersonRole` | role_name, assigned_to, assigned_by, assigned_at |
| `Device` | device_id, owner_agent, owner_person, status (DeviceStatus enum) |
| `AgentPersonRelationship` | agent, person, relationship_type (AgentPersonRelationshipType enum) |
| `PrivateDataCapabilityMetadata` | grant_hash, granted_to, fields_allowed, expires_at |
| `RevokedGrantMarker` | grant_hash, revoked_at |
| `FilteredPrivateData` | selectively-shared private field subsets (capability-gated partial disclosure) |

Supporting enums: `DeviceStatus` (Active/Inactive/Revoked), `AgentPersonRelationshipType` (Primary/Secondary/Device).

### Role types
```rust
enum RoleType {
    SimpleAgent, AccountableAgent, PrimaryAccountableAgent,
    Transport, Repair, Storage,
}
```

### Key functions
- `create_person()` / `update_person()` / `get_all_persons()` / `get_latest_person()`
- `get_person_profile(AgentPubKey)` / `get_my_person_profile()`
- `assign_person_role()` / `get_my_person_roles()` / `get_person_roles(agent)` / `has_person_role_capability()`
- `promote_agent_to_accountable()` — calls into `zome_gouvernance`
- `promote_agent_with_validation()` / `request_role_promotion()` / `approve_role_promotion()` — enhanced promotion workflow
- `grant_private_data_access()` / `revoke_private_data_access()` — capability grants
- `get_private_data_with_capability()` — capability-gated selective disclosure
- `grant_role_based_private_data_access()` / `create_transferable_private_data_access()`
- `validate_agent_private_data()` — called by gouvernance zome for cross-zome validation
- `validate_agent_private_data_with_grant()` / `validate_capability_grant()`
- `store_private_person_data()` / `update_private_person_data()` / `get_my_private_person_data()`
- `register_device_for_person()` / `get_devices_for_person()` / `get_device_info()` / `deactivate_device()` / `get_my_devices()`
- `add_agent_to_person()` / `remove_agent_from_person()` / `get_agent_person()` / `get_person_agents()` / `is_agent_associated_with_person()`
- `create_rea_agent_bridge()` — cross-DNA call to hREA DNA (proven pattern); called automatically during `create_person()`
- `get_hrea_agents()`

---

## zome_resource

### Entry types
| Entry | Key fields |
|---|---|
| `ResourceSpecification` | name, description, category, tags, is_active |
| `EconomicResource` | quantity, unit, custodian, current_location, **state** |
| `GovernanceRule` | rule_type, rule_data, enforced_by |

### ResourceState (the integration hook — on EconomicResource)
```rust
enum ResourceState {
    PendingValidation,  // ← resources start here
    Active,             // ← ValiChord's Harmony Record drives transition to here
    Maintenance,
    Retired,
    Reserved,
}
```

**Important (April 2026):** The previously-noted TODO to split `ResourceState` into `LifecycleStage`
+ `OperationalState` is now partially implemented — but as a separate entry type, not a replacement.
`LifecycleStage` now lives on `NondominiumIdentity` (see below). `EconomicResource` still carries
`ResourceState` with these 5 variants. The refactor to an `OperationalState` enum on `EconomicResource`
is deferred (REQ-NDO-OS-06).

### NondominiumIdentity (Layer 0 — new as of topeuph-ai fork)

A permanent identity anchor for a resource, separate from the `EconomicResource` instance.
Exists from conception through end-of-life. **Cannot be deleted** (validated by integrity zome).
The original `ActionHash` from `create_ndo()` is the stable Layer 0 identity for all time.

```rust
struct NondominiumIdentity {
    name: String,                              // immutable
    initiator: AgentPubKey,                    // immutable
    property_regime: PropertyRegime,           // immutable
    resource_nature: ResourceNature,           // immutable
    lifecycle_stage: LifecycleStage,           // only mutable field (via update_lifecycle_stage)
    created_at: Timestamp,                     // immutable
    description: Option<String>,               // immutable
    successor_ndo_hash: Option<ActionHash>,    // set once, on → Deprecated
    hibernation_origin: Option<LifecycleStage>, // auto-managed for Hibernating transitions
}
```

`LifecycleStage` (10 variants, mostly monotonic):
```
Ideation → Specification → Development → Prototype → Stable → Distributed → Active
                                                                            ↓
                                                                      Hibernating (reversible)
                                                                            ↓
                                                                  Deprecated (→ EndOfLife only)
                                                                  EndOfLife (terminal)
```

`PropertyRegime`: `Private`, `Commons`, `Collective`, `Pool`, `CommonPool`, `Nondominium`  
`ResourceNature`: `Physical`, `Digital`, `Service`, `Hybrid`, `Information`

**Integration implication:** ValiChord's `HarmonyRecord` can drive BOTH layers:
1. `update_resource_state()` on `EconomicResource`: `PendingValidation` → `Active`
2. `update_lifecycle_stage()` on `NondominiumIdentity`: e.g. `Prototype` → `Stable` (if the
   validation round confirms the resource is production-ready)
The `NdoToTransitionEvent` link type already anticipates this: a link from the NDO action hash
to a triggering `EconomicEvent` (or, in the ValiChord case, the `HarmonyRecord` action hash).

**Custodian constraint on `update_resource_state()` — resolved (May 2026):** NDO confirmed they
will not add a new governance-gated pathway. The custodian gate stays intact. Integration uses
capability slots instead:

- After ValiChord produces the `HarmonyRecord`, the researcher (custodian) writes a capability
  slot link to NDO's DHT: base = `EconomicResource` / `NondominiumIdentity` hash, target =
  `HarmonyRecord` ActionHash, tag = `{agreement_level, validator_count}` as compact msgpack.
  `AgreementLevel` has no serde tag attribute in ValiChord — it serialises as a plain string
  (`"ExactMatch"`, `"WithinTolerance"`, etc.), so NDO can check it without importing ValiChord
  types.
- NDO adds a `GovernanceRuleType::ExternalValidation` variant. When a resource is in
  `PendingValidation`, this rule specifies the required slot type and consensus threshold.
- The researcher calls `update_resource_state()` as normal. The governance rule checks that a
  matching slot link with threshold-meeting tag data is present — if yes, the transition proceeds.

**DHT locality constraint:** `get(action_hash)` in an NDO zome searches NDO's DHT, not
ValiChord's governance DHT — they are separate peer networks. The slot tag carries everything
NDO needs for the threshold check without a cross-network fetch. For full record verification,
NDO can call `get_harmony_record_by_hash(action_hash)` via `OtherCell` on a same-conductor
ValiChord governance cell — both functions are `Unrestricted` and require no capability secret.
`get_harmony_record(ExternalHash)` takes the data hash (ValiChord's `request_ref`);
`get_harmony_record_by_hash(ActionHash)` takes the direct record hash from the slot link target.

### Key functions
- `create_ndo(NdoInput)` — creates a `NondominiumIdentity` (Layer 0 anchor)
- `get_ndo(ActionHash)` / `get_all_ndos()` / `get_my_ndos()`
- `get_ndos_by_lifecycle_stage(LifecycleStage)` / `get_ndos_by_nature(ResourceNature)` / `get_ndos_by_property_regime(PropertyRegime)`
- `update_lifecycle_stage(UpdateLifecycleStageInput)` — only the initiator may call (MVP simplification; full role-based auth deferred)
- `create_economic_resource()` — creates `EconomicResource` in `PendingValidation` state
- `update_economic_resource()` / `get_latest_economic_resource()` / `get_economic_resource_profile()`
- `update_resource_state(UpdateResourceStateInput)` — custodian-only; drives `ResourceState` transitions
- `transfer_custody()` / `get_all_economic_resources()` / `get_my_economic_resources()`
- `get_resources_by_specification()` / `get_resource_specification_with_rules()`
- Full CRUD for `ResourceSpecification` and `GovernanceRule`

### The commented-out call (the integration hook)
Inside `create_economic_resource()`, the cross-zome call to `zome_gouvernance::validate_new_resource`
remains commented out, with the note:

```
// TEMPORARILY COMMENTED OUT - Call governance zome to initiate resource validation
// This implements REQ-GOV-02: Resource Validation
// TODO: Re-enable once cross-zome call issues are resolved
```

This is the exact gap ValiChord fills. Still confirmed as of April 2026 in the topeuph-ai fork.

---

## zome_gouvernance

### Entry types
| Entry | Key fields |
|---|---|
| `ValidationReceipt` | validator, validated_item, validation_type, approved, notes, validated_at |
| `ResourceValidation` | resource, validation_scheme, required_validators, current_validators (u32), status, created_at, updated_at |
| `EconomicEvent` | action (VfAction), provider, receiver, resource_inventoried_as, event_time |
| `Commitment` | action, provider, receiver, due_date, committed_at |
| `Claim` | fulfills, fulfilled_by, claimed_at |
| `PrivateParticipationClaim` | private — participation receipt with cryptographic signature, `ParticipationClaimType`, `PerformanceMetrics` |

### ParticipationClaimType enum (PPR system — 16+ variants)
Covers the full NDO contribution lifecycle: resource creation, custody transfer, maintenance,
storage, transport, governance participation, validation work, end-of-life, and more.
`PerformanceMetrics` struct captures timeliness, quality, reliability, communication,
overall_satisfaction per claim.

### VfAction enum (ValueFlows + Nondominium extensions)
Standard: `Transfer`, `Move`, `Use`, `Consume`, `Produce`, `Work`, `Modify`, `Combine`, `Separate`, `Raise`, `Lower`, `Cite`, `Accept`
Nondominium extensions: `InitialTransfer`, `AccessForUse`, `TransferCustody`

**For validator contributions use `VfAction::Work`.**

### Key functions — validation
- `create_validation_receipt(CreateValidationReceiptInput)` — per-validator receipt
- `create_resource_validation(CreateResourceValidationInput)` — multi-validator consensus record
- `check_validation_status(ActionHash)` — query current consensus state
- `validate_new_resource()` — called by zome_resource (currently commented out)
- `validate_agent_identity()` / `validate_specialized_role()`
- `get_validation_history()` / `get_all_validation_receipts()`
- `create_validation_with_private_data()` — validation pipeline using capability-gated private data

### Key functions — economic events and PPRs
- `log_economic_event(LogEconomicEventInput)` — logs event + auto-generates PPRs
- `log_initial_transfer()` — shorthand for `VfAction::InitialTransfer` events
- `issue_participation_receipts()` — explicit PPR issuance
- `get_my_participation_claims()`
- `sign_participation_claim()` / `validate_participation_claim_signature()` / `validate_participation_claim_signature_enhanced()`
- `derive_reputation_summary()` — aggregate reputation from PPRs
- `propose_commitment()` / `claim_commitment()`
- `get_all_economic_events()` / `get_events_for_resource()` / `get_events_for_agent()`
- `get_all_commitments()` / `get_commitments_for_agent()` / `get_all_claims()` / `get_claims_for_commitment()`

### Key functions — cross-zome (gouvernance → person)
- `request_agent_validation_data()` — calls `zome_person::validate_agent_private_data`
- `request_agent_validation_data_with_grant()` — capability-gated variant
- `validate_agent_for_promotion()` — delegates to above
- `validate_agent_for_custodianship()`
- `get_validation_requirements()`

---

## Cross-zome and cross-DNA call map

```
zome_person ──────────────────────────────► zome_gouvernance
  promote_agent_to_accountable()              (approval logic)

zome_gouvernance ─────────────────────────► zome_person
  request_agent_validation_data()             validate_agent_private_data()
  request_agent_validation_data_with_grant()  validate_agent_private_data_with_grant()

zome_resource ────────────────────────────► zome_gouvernance
  create_economic_resource()                  validate_new_resource()
  [COMMENTED OUT — pending resolution]

zome_person ──────────────────────────────► hREA DNA (separate DNA, proven pattern)
  create_rea_agent_bridge()                   create_rea_agent()
  get_hrea_agents()                           get_rea_agents_from_action_hashes()
```

The hREA cross-DNA bridge is now called automatically from `create_person()`.
ValiChord integration follows the same pattern.

---

## DnaProperties

**Not implemented in Nondominium.** There is no `DnaProperties` struct in any Nondominium zome,
and `dna.yaml` has `properties: ~`. The integration docs should not assume DNA properties exist
on the Nondominium side — any configuration of the integration layer will need to live either
in ValiChord's DNA properties or in an application-layer config.

---

## Participation Receipt (PPR) system

When `log_economic_event()` is called, Nondominium automatically generates
cryptographically-signed `PrivateParticipationClaim` entries for each participant.
The claim type (`ParticipationClaimType`) and `PerformanceMetrics` can be included.

For ValiChord integration: after a Harmony Record is produced, calling
`log_economic_event(VfAction::Work)` for each validator gives them NDO reputation credit
automatically. The `ParticipationClaimType` variant for validation work should be used —
check current enum variants against the repo as they may be extended.

---

## Capability grant system (private data)

`zome_person` implements OAuth-like selective disclosure:
- Grants are field-scoped (e.g. allow access to `email` only), revocable, and optionally transferable
- `grant_private_data_access()` → grantee uses `get_private_data_with_capability()`
- `FilteredPrivateData` entry type holds the disclosed subset
- `zome_gouvernance` can request private data validation without direct access

Philosophically identical to ValiChord's private DNA model — both projects treat raw personal
data as sovereign. No conflict; they cover different lifecycle moments.

---

## Lobby DNA (added May 2026)

A new second DNA providing a global cross-NDO discovery and federation layer. Agents have one `LobbyAgentProfile` visible across all communities; separate NDO-specific `Person` entries (in `zome_person`) remain sovereign to each NDO DHT.

### Entry types
| Entry | Key fields |
|---|---|
| `LobbyAgentProfile` | handle, avatar_url, bio — cross-NDO public face keyed to `lobby_pubkey` |
| `NdoAnnouncement` | NDO discovery record — links a lobby_pubkey to an announced NDO |

### Three-layer identity model

```
Lobby DHT               Group DHT                    NDO DHT
────────────────────    ─────────────────────────    ────────────────────
LobbyAgentProfile       GroupMembership              Person (zome_person)
lobby_pubkey  ────────→ ndo_pubkey_map          ───→ (key that authored
(handle, avatar, bio)   [{ndo_dna_hash,               Person entry)
                          ndo_pubkey}]
```

`GroupMembership.ndo_pubkey_map` is the **MVP identity bridge**: it records `lobby_pubkey → ndo_pubkey` for each NDO a validator belongs to, enabling cross-DHT key resolution without Flowsta. See Decision 4 in `README.md` — this changes the Flowsta picture.

Moss/The Weave integration is optional (post-MVP). Unyt RAVE integration is also post-MVP. The DNA runs fully standalone.

---

## Build and test

```bash
bun run package      # compiles zomes + packs nondominium.happ / .webhapp
```

**Primary test suite: Sweettest (Rust)** — Tryorama (TypeScript) tests are deprecated as of the fork.
```bash
bun run build:happ   # prerequisite before running tests
CARGO_TARGET_DIR=target/native-tests cargo test --package nondominium_sweettest
```

Output: `workdir/nondominium.happ` and `workdir/nondominium.webhapp`

---

## Flowsta Vault — third-system identity layer

Repo: `https://github.com/WeAreFlowsta/flowsta-vault-app`. Not yet integrated into either
project as of April 2026. Identity DNA v1.3 provides `IsSamePersonEntry` for cross-device
key resolution across hApps.

Note: Nondominium's own `Device` + `AgentPersonRelationship` entries now provide
within-Nondominium multi-device tracking. This partially overlaps with Flowsta's purpose
but does not solve the cross-system (ValiChord ↔ Nondominium) key resolution problem.
Flowsta remains the cleanest path for cross-system attribution.

---

*Last updated: May 2026. Re-read against the `dev` branch of https://github.com/Sensorica/nondominium (upstream). Key additions since April 2026: Lobby DNA (PR #103), `crates/shared/` types crate, `packages/shared-types/` TypeScript package, zome_gouvernance split into multiple source files (API unchanged), Sweettest suite added for NDO Layer 0. Custodian constraint section updated to reflect confirmed capability slot approach (NDO team, May 2026); DHT locality constraint documented; `get_harmony_record_by_hash` added to ValiChord governance coordinator.*
