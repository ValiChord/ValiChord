# Nondominium — Architecture Reference

Quick reference for ValiChord integration work. Written March 2026 from reading the source at
https://github.com/Sensorica/nondominium. Updated April 2026 after re-reading the `dev` branch.

> **Companion scoping notes** (pre-design, for Tiberius's integration build — written 2026-06-16,
> closing the two open design questions from the 2026-06-14/15 Discord agreement):
> - [`REVIEWER_SOURCING_SCOPING.md`](./REVIEWER_SOURCING_SCOPING.md) — *who validates*: credential
>   membrane vs in-DHT moderation, and who operates the admission gate.
> - [`GATE_CLAIM_MAPPING_SCOPING.md`](./GATE_CLAIM_MAPPING_SCOPING.md) — *what gets committed at the
>   gate*: the reference-fingerprint claim + designer/reviewer roles mapped onto the commit-reveal
>   data model. Feeds the capability-slot-link handoff in the `zome_resource` section below.

---

## Overview

Three DNAs as of May 2026: `nondominium` (core) + `lobby` (cross-NDO federation, added PR #103) + `group` (per-group coordination DHT, added PR #107).
HDK `^0.6.0` / HDI `0.6.x`. Tests: Sweettest (Rust, primary) — Tryorama/Vitest tests deprecated in the fork.

```
nondominium.happ
├── nondominium (DNA)
│   ├── zome_person       — agent identity, roles, private data, capability grants, device management
│   ├── zome_resource     — resource specs, NDO Layer 0 identity, economic resources (ValueFlows)
│   ├── zome_gouvernance  — validation, economic events, commitments, PPRs
│   └── misc              — coordinator only; single ping() function (test/debug scaffold)
├── lobby (DNA)           — cross-group discovery and federation (see Lobby DNA section below)
└── group (DNA)           — per-group coordination; provisioned as a cloned cell per group (see Group DNA section below)
```

**Hierarchy (PR #107):** Lobby → Groups → NDOs. The Lobby DHT is now the registry for group cells, not NDOs directly. NDOs are discovered through their host group cell.

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
  matching slot link is present and that **the actual `HarmonyRecord` it points at** meets threshold
  — see the security caution below; it must NOT decide from the slot tag alone.

> **⚠️ Security caution — do not gate on the slot tag alone (corrects earlier "tag is sufficient"
> framing).** The slot link and its `{agreement_level, validator_count}` tag are written by the
> **researcher** — the party with incentive to inflate the result — and NDO's link `validate()`
> cannot cross-fetch ValiChord's record at validation time (separate DHT networks, no network calls
> in validation). A tag-only gate is therefore forgeable two ways: (i) a tag that overstates the
> record it points at, and (ii) a target pointing at a real-but-unrelated good record from another
> study. **At decision time the governance rule must fetch the real record** (Path 2,
> `get_harmony_record_by_hash` via same-conductor `OtherCell`) and verify (a) the record's *own*
> `agreement_level` + validator count meet threshold and (b) its `request_ref` binds to *this*
> resource's deposited data. The tag is a fast pre-filter / display hint only. Principle:
> *sovereignty over **when** (custodian keeps the trigger), never over **what** the record says.*
> This closes the *forged-result* hole; the distinct *captured/fake-reviewer* hole is closed upstream
> by reviewer admission + independence (see `REVIEWER_SOURCING_SCOPING.md`). Full scoping:
> `GATE_CLAIM_MAPPING_SCOPING.md` §5.

**DHT locality constraint:** `get(action_hash)` in an NDO zome searches NDO's DHT, not
ValiChord's governance DHT — they are separate peer networks. So the gate's record verification
uses a same-conductor cross-cell read, not a raw `get()`: NDO calls
`get_harmony_record_by_hash(action_hash)` via `OtherCell` on a co-located ValiChord governance cell
— both functions are `Unrestricted` and require no capability secret. The slot tag can carry the
threshold fields for a cheap pre-filter, but (per the caution above) is not sufficient on its own
for the gate decision. `get_harmony_record(ExternalHash)` takes the data hash (ValiChord's
`request_ref`); `get_harmony_record_by_hash(ActionHash)` takes the direct record hash from the slot
link target.

**Capability-slot pattern now formalised + has precedents (added 2026-06-17 — based on branch
`feat/ndo-layer0-ui-102`, NOT yet merged to main; verify before relying on it).** The branch promotes
the capability slot to a first-class, two-tier governance concept (`ndo_prima_materia.md` §6;
`requirements/governance.md` §3.3) and ships **two worked external integrations as templates: Unyt
(`UnytAgreement`, §6.6) and Flowsta (`FlowstaIdentity`, §6.7).** ValiChord maps onto the identical
pattern as a third instance:
- **Tier 1 (permissionless):** the slot link above — a discoverable signal, not enforced.
- **Tier 2 (mandatory):** the custodian endorses a `GovernanceRule` making the slot a precondition for
  a transition. Our proposed `GovernanceRuleType::ExternalValidation` is the analogue of Unyt's
  `EconomicAgreement` rule.
- **The cross-DNA fetch above is the house pattern, not a novel ask.** Unyt's rule, at full
  enforcement, does the same thing for the same reason: it does *not* trust the slot tag — the
  transition request carries a `rave_hash` and the governance zome **queries the Unyt DHT via
  cross-DNA `call()`** to retrieve and validate the actual RAVE proof. This both vindicates the
  security caution above and pre-empts the "verifying means reaching into ValiChord's separate
  network" objection.
- **Gap to fill:** the SlotType vocabulary (`ndo_prima_materia.md` §6.2 —
  `Documentation`/`IssueTracker`/`FabricationQueue`/`GovernanceDAO`/`UnytAgreement`/`FlowstaIdentity`/
  `CustomApp`) has **no validation/reproducibility slot**. ValiChord would add one (e.g.
  `ValidationAttestation`) targeting the `HarmonyRecord` `ActionHash`.

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
| `ResourceValidation` | resource, validation_scheme, required_validators, current_validators (u32), status (`ResourceValidationStatus` enum: `Pending`/`Approved`/`Rejected`), created_at, updated_at |
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

## Lobby DNA (added May 2026, updated PR #107)

A global cross-community discovery and federation layer. Agents have one `LobbyAgentProfile` visible across all communities; separate NDO-specific `Person` entries (in `zome_person`) remain sovereign to each NDO DHT.

**PR #107 change:** `NdoAnnouncement` is gone. The Lobby DHT now registers group cells, not NDOs directly. Use `GroupAnnouncement` for discovery.

### Entry types
| Entry | Key fields |
|---|---|
| `LobbyAgentProfile` | handle, avatar_url, bio — cross-community public face keyed to `lobby_pubkey` |
| `GroupAnnouncement` | `group_name`, `group_dna_hash` (DnaHash — stable CellId key), `network_seed`, `description`, `registered_by` (AgentPubKey, must equal action.author). Immutable after creation. |

Link types: `AllLobbyAgents` (Path → LobbyAgentProfile), `AllGroupAnnouncements` (Path("lobby.groups") → GroupAnnouncement), `AgentToGroupAnnouncements` (AgentPubKey → GroupAnnouncement).

**Key functions (lobby coordinator):** `announce_group`, `get_all_group_announcements`, `get_group_announcement_by_dna_hash`, `get_my_group_announcements`.

### Three-layer identity model

```
Lobby DHT                    Group DHT              NDO DHT
─────────────────────────    ──────────────────     ────────────────────
LobbyAgentProfile            GroupProfile           Person (zome_person)
GroupAnnouncement  ────────→ GroupMembership   ───→ (key that authored
(group_dna_hash)             (group_hash,           Person entry)
                              role)
```

Cross-DHT key resolution (lobby_pubkey → ndo_pubkey) is not yet implemented in the Group DNA `GroupMembership` struct — it only carries `group_hash` and `role`. Full cross-system identity attribution remains post-MVP; Flowsta is still the intended path for that.

Moss/The Weave integration is optional (post-MVP). Unyt RAVE integration is also post-MVP. The DNA runs fully standalone.

---

## Group DNA (added PR #107)

Per-group coordination layer. Each group runs as its own **cloned cell** (separate DHT, same DNA template), provisioned via `clone_cell` with `clone_limit: 64` in `happ.yaml`. Groups are announced via `GroupAnnouncement` on the Lobby DHT.

### Entry types
| Entry | Key fields |
|---|---|
| `GroupProfile` | `name` (non-empty, max 100 chars), `description` (optional). Identity and timestamp from action header. |
| `GroupMembership` | `group_hash` (ActionHash), `role` (optional String). Joining agent is the action author. |
| `WorkLog` | `group_hash`, `description` (non-empty), `hours` (f32, must be > 0). Author and timestamp from action header. |
| `SoftLink` | `group_hash`, `target_ndo_hash` (ActionHash), `description` (optional). Planning-only link from group to NDO — does NOT generate PPRs or EconomicEvents (ADR-GROUP-04). |

### Link types
`AllGroups` (Anchor → GroupProfile), `GroupUpdates` (GroupProfile → GroupProfile), `GroupToMembers` (GroupProfile → GroupMembership), `MemberToGroups` (AgentPubKey → GroupProfile), `GroupToWorkLogs` (GroupProfile → WorkLog), `AgentToWorkLogs` (AgentPubKey → WorkLog), `GroupToSoftLinks` (GroupProfile → SoftLink).

### Key functions
- `create_group`, `get_group`, `get_my_group`, `update_group` (NotAuthor guard)
- `join_group` (AlreadyMember guard), `leave_group`, `get_group_members`, `is_member`
- `log_work`, `get_work_logs`, `get_my_work_logs`, `delete_work_log` (NotAuthor guard)
- `create_soft_link`, `get_soft_links`, `delete_soft_link` (NotAuthor guard), `init`

### Integration note
`SoftLink` is the planning-level connection between a Group and the NDOs it hosts. For ValiChord integration, the capability slot link approach (see zome_resource integration section) targets the `EconomicResource` / `NondominiumIdentity` hash — this is in the NDO DHT and unaffected by the Group DNA addition. Groups are a discovery and coordination layer; ValiChord writes into the NDO layer.

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

## Nondominium Design System (separate repo, reviewed 2026-06-14)

Repo: `https://github.com/Sensorica/nondominium-design-system` (default branch `master`, last
pushed 2026-06-06). This is the **frontend design system for the Nondominium hApp — not the
protocol**. It is the visual layer that sits on top of the three DNAs above; it deliberately
contains **no Holochain wiring** (zome calls, Effect-TS services, stores all stay in the hApp —
see its `docs/INTEGRATION.md`). MVP/early maturity: several tabs are explicit stubs, the built
custom-element bundle is a `.gitkeep` placeholder.

Stack: SvelteKit 2 + Svelte 5 + UnoCSS + Melt UI. Apache-2.0. **Same stack as `valichord-ui`** —
if we ever render NDO entities in our own UI we could consume `@nondominium/ndo-ui` directly.

Two delivery layers:
- `@nondominium/ndo-ui` — Svelte 5 component library (primitives: `NdoBadge`, `NdoButton`,
  `NdoCard`, `Modal`; patterns: `NdoDetailLayout`, `NdoIdentityPanel`, `LifecycleTransitionModal`,
  lobby/group views).
- `ndo-*` custom elements (`<ndo-badge>`, `<ndo-button>`, `<ndo-card>`, `<ndo-status-dot>`) —
  framework-agnostic web components for plain-HTML embeds.

### Why it matters for ValiChord — it is the visual counterpart to our integration hook

Our backend hook drives two transitions from a ValiChord `HarmonyRecord`:
1. `EconomicResource`: `PendingValidation → Active`
2. `NondominiumIdentity.lifecycle_stage`: e.g. `Prototype → Stable`

The design system now encodes **exactly that lifecycle as a UI state machine**. From
`packages/ndo-ui/src/domain/lifecycle-transitions.ts` — and it matches our `LifecycleStage`
flow almost exactly:

```
Ideation → Specification → Development → Prototype → Stable → Distributed → Active
Active → Hibernating → Deprecated → EndOfLife   (Hibernating reversible to its origin stage)
```

There is a `LifecycleTransitionModal.svelte` — the UI a custodian uses to approve a stage
transition. A ValiChord validation round is exactly the evidence that should gate
`Prototype → Stable` (or `PendingValidation → Active`). **Concrete integration target:** a
ValiChord reproducibility status/badge inside `NdoIdentityPanel.svelte` ("reproduced by N
validators — HarmonyRecord uhC8k…"), with the `LifecycleTransitionModal` surfacing the
HarmonyRecord as the justification for the transition. This is the front-end pairing for the
capability-slot-link approach in the zome_resource section above.

### Re-look 2026-06-16 — the design system has NO evidence/validation concept (sharpened finding)

Re-reviewed given the confirmed integration. **The repo is unchanged since 2026-06-06** (recent
commits are only Sensorica's "Complexity Oriented Programming" / "Associative CryptoEconomics"
house-philosophy docs), so the above is current. Two checks, with the integration lens, found the
front-end half of the same gap as the backend gate-verification point:

1. **Repo-wide code search → zero hits** for `valichord`, `harmony`, `attestation`, `external`,
   `evidence`, `validat*`, `reproduc*`, `verif*`, `review`. The design system models no concept of
   external validation evidence anywhere.
2. **`LifecycleTransitionModal.svelte` is a pure stage-picker.** It gates a transition only on
   `allowedTransitions()` (is the stage-move structurally legal) — it requires **no evidence or
   justification**. The `onconfirm` payload is just `{ newStage, successorHash? }` (successor only
   for `Deprecated`). So today a custodian can advance a resource `Prototype → Stable` by selecting
   the stage and confirming — nothing backs it up. **This is the "trust the claimant" gap seen from
   the UI side** — the front-end mirror of the slot-tag-vs-real-record point in the zome_resource
   security caution above.

**Implication (small, well-scoped — a blank to fill, not a rebuild):** the integration needs (a) an
evidence/required-validation branch in `LifecycleTransitionModal` that surfaces the ValiChord
`HarmonyRecord` and blocks confirm until a verified record is present for transitions that require
it, and (b) the `NdoIdentityPanel` reproducibility badge above. The "some transitions must be backed
by verified evidence" concept exists on **neither** side yet (backend or UI) — the capability slot +
this modal branch are exactly where it gets wired. Frame on the call as *the natural place ValiChord
plugs into their existing lifecycle modal*, not as a flaw in their MVP.

### Cross-checks against this doc

- `domain/enums.ts` confirms the same 10 `LifecycleStage` variants and 5 `ResourceNature`
  variants documented above — our architecture doc is current.
- **Regime nuance:** the UI MVP surfaces **4** `PropertyRegime` values
  (`Private, Commons, Nondominium, CommonPool`) and treats `Collective` and `Pool` as
  "forward compatibility" only. Our 6-variant list is not wrong, just ahead of the UI.
- The repo also carries Sensorica's own framing (`Associative-CryptoEconomics.md`, a
  "complexity-oriented programming" methodology skill) — their house style, nothing we adopt,
  and not aligned with how we frame ValiChord (de-crypto).

---

*Last updated: 2026-06-16. Added companion scoping-note pointers (top) + the zome_resource security
caution (gate must verify the real HarmonyRecord, not the researcher-written slot tag), and a
re-look of the design system (unchanged since 2026-06-06): its `LifecycleTransitionModal` is a pure
stage-picker with no evidence/validation concept anywhere in the repo — the front-end mirror of the
gate-verification gap, and the blank ValiChord fills. Previous update (2026-06-14): added the
Nondominium Design System section (separate repo `Sensorica/nondominium-design-system`) —
frontend-only, MVP, encodes the `LifecycleStage` transition machine + `LifecycleTransitionModal`;
the ValiChord-badge-in-`NdoIdentityPanel` integration target identified. Previous update
(2026-05-27): Group DNA
(PR #107) — per-group cloned cell, `SoftLink` (Lobby → Groups → NDOs hierarchy);
`NdoAnnouncement` replaced by `GroupAnnouncement` in Lobby DNA; `ResourceValidationStatus`
typed as enum (`Pending`/`Approved`/`Rejected`) in zome_gouvernance;
`GroupMembership.ndo_pubkey_map` noted as not yet implemented. Cross-zome call to
`validate_new_resource` still commented out (TODO wording only changed).*
