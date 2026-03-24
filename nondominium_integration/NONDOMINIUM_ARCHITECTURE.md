# Nondominium — Architecture Reference

Quick reference for ValiChord integration work. Written March 2026 from reading the source at
https://github.com/Sensorica/nondominium. Update this file if their codebase changes significantly.

---

## Overview

Single DNA (`nondominium`) with three paired integrity/coordinator zomes. HDK `^0.6.0` / HDI `^0.7.0` — identical to ValiChord. Tests use Tryorama + Vitest.

```
nondominium.happ
└── nondominium (DNA)
    ├── zome_person     — agent identity, roles, private data, capability grants
    ├── zome_resource   — resource specs and economic resources (ValueFlows)
    └── zome_gouvernance — validation, economic events, commitments, PPRs
```

---

## zome_person

### Entry types
| Entry | Key fields |
|---|---|
| `Person` | name, avatar_url, bio, hrea_agent_hash |
| `PrivatePersonData` | legal_name, email, phone, address, timezone, location |
| `PersonRole` | role_name, assigned_to, assigned_by, assigned_at |
| `Device` | device_id, owner_agent, owner_person, status |
| `AgentPersonRelationship` | agent, person, relationship_type |
| `PrivateDataCapabilityMetadata` | grant_hash, granted_to, fields_allowed, expires_at |
| `RevokedGrantMarker` | grant_hash, revoked_at |

### Role types
```rust
enum RoleType {
    SimpleAgent, AccountableAgent, PrimaryAccountableAgent,
    Transport, Repair, Storage,
}
```

### Key functions
- `create_person()` / `update_person()` / `get_all_persons()`
- `get_person_profile(AgentPubKey)` / `get_my_person_profile()`
- `assign_person_role()` / `get_my_person_roles()` / `has_person_role_capability()`
- `promote_agent_to_accountable()` — calls into `zome_gouvernance`
- `grant_private_data_access()` / `revoke_private_data_access()` — capability grants
- `get_private_data_with_capability()` — capability-gated selective disclosure
- `validate_agent_private_data()` — called by gouvernance zome for cross-zome validation
- `create_rea_agent_bridge()` — cross-DNA call to hREA DNA (proven pattern)

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

### Key functions
- `create_economic_resource()` — creates resource in `PendingValidation` state
- `update_resource_state(UpdateResourceStateInput)` — drives state transitions
- `transfer_custody()` / `get_all_economic_resources()`
- `get_resources_by_specification()`

### The commented-out call (the integration hook)
Inside `create_economic_resource()`, a cross-zome call to `zome_gouvernance::validate_new_resource`
is commented out, marked "pending cross-zome communication resolution."
ValiChord's commit-reveal is what this was intended to trigger.

---

## zome_gouvernance

### Entry types
| Entry | Key fields |
|---|---|
| `ValidationReceipt` | validator, validated_item, validation_type, approved, notes, validated_at |
| `ResourceValidation` | resource, validation_scheme, required_validators, current_validators, status |
| `EconomicEvent` | action (VfAction), provider, receiver, resource_inventoried_as, event_time |
| `Commitment` | action, provider, receiver, due_date, committed_at |
| `Claim` | fulfills, fulfilled_by, claimed_at |
| `PrivateParticipationClaim` | private — participation receipt tracking |

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

### Key functions — economic events and PPRs
- `log_economic_event(LogEconomicEventInput)` — logs event + auto-generates PPRs
- `issue_participation_receipts()` — explicit PPR issuance
- `sign_participation_claim()` / `validate_participation_claim_signature()`
- `derive_reputation_summary()` — aggregate reputation from PPRs
- `propose_commitment()` / `claim_commitment()`

### Key functions — cross-zome (gouvernance → person)
- `request_agent_validation_data()` — calls `zome_person::validate_agent_private_data`
- `validate_agent_for_promotion()` — delegates to above
- `validate_agent_for_custodianship()`

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

The hREA cross-DNA bridge proves that Nondominium already handles cross-DNA calls.
ValiChord integration follows the same pattern.

---

## Participation Receipt (PPR) system

When `log_economic_event()` is called, Nondominium automatically generates
cryptographically-signed `PrivateParticipationClaim` entries for each participant.
These are the contribution attribution records used for reputation and benefit redistribution.

For ValiChord integration: after a Harmony Record is produced, calling
`log_economic_event(VfAction::Work)` for each validator gives them NDO reputation credit
automatically — no additional code needed.

---

## Capability grant system (private data)

`zome_person` implements OAuth-like selective disclosure:
- Grants are field-scoped (e.g. allow access to `email` only), revocable, and optionally transferable
- `grant_private_data_access()` → grantee uses `get_private_data_with_capability()`
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
