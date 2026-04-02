# Nondominium — Architecture Reference

Quick reference for ValiChord integration work. Written March 2026 from reading the source at
https://github.com/Sensorica/nondominium. Updated April 2026 after re-reading the `dev` branch.

---

## Overview

Single DNA (`nondominium`) with three paired integrity/coordinator zomes plus one utility coordinator.
HDK `0.6.0` / HDI `0.6.x` — identical to ValiChord. Tests use Tryorama + Vitest.

```
nondominium.happ
└── nondominium (DNA)
    ├── zome_person       — agent identity, roles, private data, capability grants, device management
    ├── zome_resource     — resource specs and economic resources (ValueFlows)
    ├── zome_gouvernance  — validation, economic events, commitments, PPRs
    └── misc              — coordinator only; single ping() function (test/debug scaffold)
```

A `nondominium_utils` crate at `crates/utils/` provides shared error types (`ResourceError`,
`GovernanceError`, `PersonError`) and cross-zome call helpers (`call_governance_zome`,
`call_person_zome`) used by all three coordinator zomes.

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

### ResourceState (the integration hook)
```rust
enum ResourceState {
    PendingValidation,  // ← resources start here
    Active,             // ← ValiChord's Harmony Record drives transition to here
    Maintenance,
    Retired,
    Reserved,
}
```

**Note:** A large TODO comment in the integrity zome documents a planned future split into
`LifecycleStage` (10 variants: Ideation → EndOfLife) and `OperationalState` (7 variants).
This is not yet implemented. `ResourceState` with these 5 variants remains live.

### Key functions
- `create_economic_resource()` — creates resource in `PendingValidation` state
- `update_economic_resource()` / `get_latest_economic_resource()` / `get_economic_resource_profile()`
- `update_resource_state(UpdateResourceStateInput)` — drives state transitions
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

This is the exact gap ValiChord fills. Still confirmed as of April 2026.

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

## Build and test

```bash
bun run package      # compiles zomes + packs nondominium.happ
bun run test         # Tryorama + Vitest
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

*Last updated: April 2026. Re-read against the `dev` branch of https://github.com/Sensorica/nondominium.*
