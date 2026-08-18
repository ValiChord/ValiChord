# Nondominium — Architecture Reference

Quick reference for ValiChord integration work. Written March 2026 from reading the source at
https://github.com/Sensorica/nondominium. Updated April 2026 after re-reading the `dev` branch, and
**refreshed 2026-08-16 against `dev` for ADR-010–013 (per-NDO cells)** — see the re-check block below.

> **Reading order.** The dated re-check blocks are newest-first and are the current truth. The
> reference body beneath them is the March/April reading with corrections marked inline; where a
> block and the body disagree, the block wins.

> **Companion scoping notes** (pre-design, for Tiberius's integration build — written 2026-06-16,
> closing the two open design questions from the 2026-06-14/15 Discord agreement):
> - [`REVIEWER_SOURCING_SCOPING.md`](./REVIEWER_SOURCING_SCOPING.md) — *who validates*: credential
>   membrane vs in-DHT moderation, and who operates the admission gate.
> - [`GATE_CLAIM_MAPPING_SCOPING.md`](./GATE_CLAIM_MAPPING_SCOPING.md) — *what gets committed at the
>   gate*: the reference-fingerprint claim + designer/reviewer roles mapped onto the commit-reveal
>   data model. Feeds the capability-slot-link handoff in the `zome_resource` section below.

---

> **🔄 Re-check 2026-08-16 — branch `dev` (the trunk; `main` has been stale since 2026-05-15).**
> **`ADR-010`–`ADR-013` (accepted, implemented in v0.1.0, PR #128, `Closes #120`) re-shaped Layer 0.**
> Headline: **the integration seam is unchanged; the topology around it is not.**
>
> 1. **✅ The seam is intact.** `ResourceState` still has the same five variants with
>    `PendingValidation` as `#[default]`, and the `validate_new_resource` cross-zome call is **still
>    commented out** (`economic_resource.rs` ~line 91, same TODO text). Re-verified on `dev`
>    2026-08-16 — four months after the April confirmation. Our gap-to-fill stands.
> 2. **Five roles now, not three** (`workdir/happ.yaml`): `lobby`, `nondominium`, **`hrea`**,
>    `group` (`deferred`, `clone_limit: 64`), `ndo` (`deferred`, `clone_limit: 512`). The ADR-006
>    hREA delegation flagged in point 5 of the 2026-07-08 re-check has landed as a provisioned role.
> 3. **⚠️ The `ndo` DNA is the same zome code as `nondominium`, minus `zome_person` and `misc`.**
>    `dnas/ndo/workdir/dna.yaml` builds from the identical `zome_resource_*` / `zome_gouvernance_*`
>    wasms — there is no separate `dnas/ndo/zomes/` tree. Two consequences for us:
>    - `create_economic_resource()` **and the commented-out call** exist inside *every* NDO clone, so
>      the gate fires **per-cell, not once per network**.
>    - **`zome_person` is absent from the `ndo` cell.** Agent identity, roles, private data,
>      capability grants and device management stay in the shared `nondominium` cell, so any
>      role/credential check the gate needs is a **cross-cell read from where the gate fires**. This
>      is the single biggest new constraint on `REVIEWER_SOURCING_SCOPING.md`.
> 4. **One cloned cell per NDO (ADR-010).** The Layer 0 `NondominiumIdentity` genesis entry now lives
>    inside the NDO's own clone, not the shared `nondominium` cell. Pre-migration NDOs remain in the
>    shared cell behind a legacy read fallback (`ndo.service.ts`) — **both shapes are live at once.**
> 5. **The NDO's permanent identity is its `DnaHash` (ADR-013)**, bound through clone DNA properties.
> 6. **⚠️ The "DnaProperties — Not implemented" section below is now wrong** and is corrected in place.
> 7. **No global registry (ADR-011).** Discovery is per-group: `NdoAnchor` entries in each group's
>    clone cell, *"the ONLY pointer any NDO read path follows"*. Carries `ndo_dna_hash`,
>    `network_seed`, `identity_action_hash`, and a cached best-effort `lifecycle_stage`.
> 8. **✅ ADR-012 is our own gate correction, arrived at independently.** *"A reader does not trust
>    `anchor.ndo_dna_hash`. It re-derives the clone from (network_seed, properties) and compares."*
>    That is structurally identical to our 2026-06-16 correction — don't trust the researcher-written
>    slot tag, fetch and verify the actual `HarmonyRecord`. **Lead with this in conversation:** the
>    verify-the-referent doctrine is now theirs, not something we are importing.
> 9. **⚠️ Lifecycle transitions do not yet emit an `EconomicEvent`** (REQ-NDO-LC-02 / LC-03);
>    `transition_event_hash` is `null` in the MVP. Our Step 6 PPR sink assumes `log_economic_event()`
>    fires on the transition the gate drives. It does not yet.
> 10. **Toolchain:** `hdi ^0.7.0`, `hdk ^0.6.0`, `holochain =0.6.0`. A `chore/holochain-0.7` branch
>    exists (last commit 2026-08-11) but has not merged. **ValiChord's `main` is already on 0.7** — we
>    are ahead of them here, which is a no-ask conversation opener.
> 11. **Documentation gap worth naming.** `documentation/requirements/post-mvp/` is where an accepted
>    external integration lives — `flowsta-integration.md` (2026-03-24) and `unyt-integration.md`
>    (2026-03-11), both "Post-MVP Design Document", both `Relates to: ndo_prima_materia.md`. **There is
>    no `valichord-integration.md`.** Writing one, in that format, is the concrete small ask — it is
>    how an integration becomes legible to the project's own architecture, and it costs a document
>    rather than code.
>
> Source: `documentation/specifications/adr/ADR-010-013-per-ndo-cells.md`. Its long-form design of
> record is `.local/nondominium-architecture-design-2026-08-08.md`, deliberately kept out of the
> repo — the ADR is the only public trace, so cite the ADR.

---

> **📖 Read of `ndo_prima_materia.md` §4–§5 (2026-08-16) — the lifecycle model, first-hand.**
> Previously taken second-hand from our own notes. Five findings, one of which is the strongest
> integration argument we have.
>
> 1. **🎯 They have already specified our gate and not built it.** §5.3's transition table:
>    `Prototype --> Stable : "Accept (peer validated)"`, authorized by **"Multi-agent peer validation
>    (configurable N-of-M)"**. Every neighbouring transition is custodian-authorised; this one is not,
>    and **no mechanism is specified for producing that validation.** `Stable` is defined as
>    *"Production-ready, design is replicable"* — replicability is the claim, and independent
>    reproduction is what establishes it. **Lead the pitch with this**, not with the commented-out
>    `validate_new_resource` call.
> 2. **What is enforced is weaker than what is specified.** MVP: transitions validated in the
>    *integrity* zome (`validate_update_nondominium_identity`); **only the `initiator`** may call
>    `update_lifecycle_stage`; the role table is target behaviour (REQ-NDO-LC-07); the governance zome
>    is not yet the state transition operator (REQ-ARCH-07). So today the proposer can unilaterally
>    declare their own design replicable. The forward chain is **monotonic — no stage skipping** — so
>    `Stable` is on the path to everything downstream.
> 3. **`LifecycleStage` and `OperationalState` are orthogonal — do not conflate them** (our earlier
>    notes did). `LifecycleStage` (10 variants, on `NondominiumIdentity`, **implemented**) describes
>    what the artefact has become. `OperationalState` (on `EconomicResource`, **not implemented** —
>    `ResourceState` is still the conflated enum) describes what process is acting on it. The target
>    creation-time check is `OperationalState::PendingValidation → Available`, **not** `→ Active`.
>    ⚠️ **`Active` exists in both enums with different meanings** — always name the enum.
> 4. **⚠️ Our 2026-07-08 flag #4 was wrong.** It recorded `PropertyRegime` as "officially reduced to 4
>    variants — `Collective` and `Pool` removed from the Rust + shared-types". Verified in
>    `crates/shared/src/types.rs` on `dev`: **six variants** — `Private`, `Commons`, `Collective`,
>    `Pool`, `CommonPool`, `Nondominium`. The *UI* `packages/shared-types` exposes four, and prima
>    materia §4.2 calls the reconciliation deferred. The Rust is the authority; the note was reversed
>    or never right.
> 5. **Their own docs are mid-reconciliation.** §4.2 still states the `create_ndo` action hash is "the
>    permanent, stable Layer 0 identity" (REQ-NDO-L0-02), while ADR-013 makes the clone's `DnaHash` the
>    permanent identity. The ADR is newer and declares itself load-bearing over the three-layer model,
>    so it wins — but expect the tension to surface in conversation, and don't cite §4.2 as current.
>
> Layer 0 is ✅ implemented; Layers 1 and 2 remain post-MVP, and §5.2's layer-activation coupling is
> "not yet enforced in code" — lifecycle stage currently advances on Layer 0 independently.

---

> **📖 Read of `ndo_prima_materia.md` §2, §3, §7 (2026-08-16) — the conceptual frame. Use this
> vocabulary; it is how they argue.**
>
> 1. **🎯 §3.4 names our problem as their open problem.** Verbatim: *"Debuggers, type systems, and unit
>    tests all assume reducibility. **COP requires new verification paradigms** — closer to simulation
>    and formal methods than conventional testing."* Their answer so far is Sweettest — which verifies
>    the *backend*, not claims the backend records. **This is the second-strongest opening after the
>    `Prototype → Stable` gap, and it pairs with it: they named the transition and they named the
>    missing paradigm, separately.**
> 2. **§3.3 is our mechanism in their words.** *"Holochain's agent-centric model: there is no global
>    state machine. Each agent runs local validation rules, and global coherence emerges from the
>    aggregate of local actions."* Commit-reveal applies that to empirical claims — no authority
>    decides, agreement emerges from independent local findings. The §3.2 table's *"single source of
>    truth → distributed state with coherence protocols"* is the sentence to reuse: ValiChord is a
>    coherence protocol.
> 3. **§2.2 (Benkler) is the argument for staying optional.** Coordination overhead should not exceed
>    the value of the coordination it enables — the "pay-as-you-grow" justification for layer
>    activation. Independent reproduction is *expensive* evidence (other people's time, rigs,
>    materials), so it belongs at specific high-consequence transitions rather than universally. Frame
>    optionality as cost-matching, not as hedging.
> 4. **§2.3 (Morin, Retroactive) supports the transition framing** — *"lifecycle stage changes are
>    triggered by economic events (outputs of the system feeding back as inputs)"*, and §3.4:
>    lifecycle transitions are *"feedback arcs"*, not state-machine edges. A verification round is such
>    a feedback arc.
> 5. **⚠️ Do not pitch this as a state machine or a checklist.** §2.1 argues fixed classification at
>    t=0 is *"an FSM in disguise"* and categorically incompatible with complex human systems; §3.2
>    frames the shift as *"programmer as god → programmer as ecologist"*. Language implying we
>    determine or certify correctness reads as the reductive paradigm they are explicitly rejecting.
>    "Observes whether independent parties converge" is native; "validates that the design is correct"
>    is not — and is also false.
> 6. **§7 status snapshot corroborates §8.4.** Patterns 1 (Identity Anchor) and 5 (Tombstone) are in
>    MVP code; **Patterns 2, 3 and 6 "depend on link types not yet in `zome_resource`"** — Pattern 6 is
>    the `CapabilitySlot` surface, so this is a third independent confirmation that Tier 1 is
>    unbuilt. Note `NdoHardLink` (#103, in `zome_gouvernance`) is a *different* cross-NDO attachment
>    mechanism, explicitly distinguished from Pattern 6 — don't conflate them.
> 7. **A second doc/ADR tension.** Pattern 1 says the genesis action hash is the stable namespace and
>    *"nothing else in the system references a resource by any other handle"* — which ADR-013's
>    `DnaHash` identity contradicts, same as §4.2. Two independent sightings of the same unreconciled
>    seam.

---

> **🔄 Re-check 2026-07-08 — branch `ndo-layer1` (their active dev line, 66 commits ahead of a stale `main`).**
> The `feat/ndo-layer0-ui-102` work referenced below is merged into this line (#103 Lobby DNA, #107 Group
> DNA, #108 Layer 0 UI). Key movements since the 2026-06-16 update:
>
> 1. **The capability-slot two-tier pattern is now formalised in their v1.0 architecture design**
>    (`documentation/specifications/ndo-v1-architecture-design.md`, with ADR-001–006) — no longer
>    branch-caveated requirements material. The `SlotType` vocabulary grew (`VersionGraph`,
>    `DigitalAsset`, `WeaveWAL` added alongside `FlowstaIdentity`, `UnytAgreement(String)`,
>    `CustomApp(String)`) but **still has no validation/reproducibility slot** — our gap-to-fill stands.
> 2. **⚠️ `GovernanceRuleType` in the v1.0 design has NO `ExternalValidation` variant** (it has
>    `AccessRequirement`, `MaintenanceSchedule`, `RoleRequirement`, `UsageLimit`, `TransferCondition`,
>    `IdentityVerification` (Flowsta), `EconomicAgreement` (Unyt stub)). The variant Decision 5 assumes
>    NDO "adds" is not in their design doc — it must be explicitly requested/PR'd, or ValiChord rides
>    `CustomApp` semantics. Raise this with Tiberius before any gate implementation.
> 3. **Governance-as-operator is still NOT implemented** (their #41–#44; specified in
>    `documentation/specifications/governance/`). This is the machinery any Tier-2 gate rule executes
>    inside — **the ValiChord gate cannot be enforced until it lands**, whichever rule variant is used.
> 4. **`PropertyRegime` officially reduced to 4 variants** — `Collective` and `Pool` were *removed from
>    the Rust + shared-types* after design review (stronger than the "UI surfaces 4, others
>    forward-compat" note below): `Private`, `Commons`, `Nondominium`, `CommonPool`.
> 5. **v1.0 commits to dual-DNA hREA delegation (ADR-006):** VF core types (EconomicResource,
>    EconomicEvent, Commitment, Agreement, Process) move to the vendored hREA DNA; NDO keeps only
>    governance/identity/accountability extensions. Integration implication: `create_economic_resource`
>    and `log_economic_event` call shapes will change when that migration lands — but the PPR system
>    (our Step 6 sink) is explicitly "preserved unchanged" (design §8), and it stays NDO-side.
> 6. **Layer 1 (Specification activation) has not started** despite the branch name; Layer 0 is complete
>    (#80, #84 categorization anchors). `validate_new_resource` **still commented out** — re-verified in
>    `economic_resource.rs` on `ndo-layer1` 2026-07-08.
> 7. Device management is implemented in `zome_person/src/device_management.rs` (register/list/
>    deactivate devices per person, DeviceUpdates chains) — the within-NDO half of the identity story;
>    cross-system resolution still Flowsta. Push-based group signals landed on the branch
>    ("feat(signals)" commit) though their own IMPLEMENTATION_STATUS still says not started.
>
> Full recon notes: memory `project_nondominium_recon_2026-07-08.md`.

---

## Overview

**Five roles as of August 2026** (was three in May). `hdi ^0.7.0` / `hdk ^0.6.0` / `holochain =0.6.0`.
Tests: Sweettest (Rust, primary) + Playwright browser e2e — Tryorama/Vitest tests deprecated in the fork.

```
nondominium.happ
├── lobby (DNA)           — cross-group discovery and federation (see Lobby DNA section below)
├── nondominium (DNA)     — the shared cell; the ONLY cell with zome_person
│   ├── zome_person       — agent identity, roles, private data, capability grants, device management
│   ├── zome_resource     — resource specs, NDO Layer 0 identity, economic resources (ValueFlows)
│   ├── zome_gouvernance  — validation, economic events, commitments, PPRs
│   └── misc              — coordinator only; single ping() function (test/debug scaffold)
├── hrea (DNA)            — vendored hREA; VF core types per ADR-006
├── group (DNA)           — per-group coordination; cloned per group (deferred, clone_limit 64)
└── ndo (DNA)             — ONE CLONE PER NDO (deferred, clone_limit 512) — ADR-010
    ├── zome_resource     — same wasm as nondominium's
    └── zome_gouvernance  — same wasm as nondominium's
                             ⚠️ NO zome_person in this cell
```

**⚠️ The `ndo` DNA is not new code.** `dnas/ndo/workdir/dna.yaml` builds from the identical
`zome_resource_*` / `zome_gouvernance_*` wasms as `nondominium`; there is no `dnas/ndo/zomes/` tree.
So `create_economic_resource()` and the commented-out `validate_new_resource` call live in **every NDO
clone** — the ValiChord gate fires per-cell, not once per network — while `zome_person` (roles,
credentials, capability grants) stays behind in the shared cell, one hop away.

**Hierarchy:** Lobby → Groups → NDOs. The Lobby DHT is the registry for group cells. Each group cell
holds `NdoAnchor` entries pointing at NDO clones (ADR-011); there is no global NDO registry. NDOs
created before the migration still live in the shared `nondominium` cell behind a legacy read fallback,
so **both shapes coexist**.

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

> **⚠️ Superseded 2026-08-16 (ADR-010/013).** This entry now lives **inside the NDO's own clone cell**,
> not the shared `nondominium` cell, and the stable Layer 0 identity for a migrated NDO is the cell's
> **`DnaHash`**, not the `create_ndo()` `ActionHash` — the action hash survives as
> `NdoAnchor.identity_action_hash`, a pointer *into* the clone. NDOs created before the migration still
> live in the shared cell with the old semantics, so a read path must handle both. The description
> below remains accurate for the entry's own fields and immutability rules.

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

`PropertyRegime`: `Private`, `Commons`, `Nondominium`, `CommonPool` — 4 variants as of `ndo-layer1`
(`Collective` and `Pool` removed from Rust + shared-types after design review; earlier 6-variant list obsolete)  
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

> **⚠️ Corrected 2026-08-16 — that tag shape is ours, not theirs, and should be dropped.**
> `ndo_prima_materia.md` §8.3 specifies the real structure:
> ```rust
> pub struct CapabilitySlotTag {
>     pub slot_type: SlotType,
>     pub attached_at: Timestamp,
>     pub label: Option<String>,   // human-readable label for this specific slot
> }
> ```
> **No agreement-level or validator-count field exists, and we should not ask for one.** The security
> caution below says the gate must never decide from the tag; a tag that cannot express the verdict
> enforces that structurally rather than by discipline. Use `label` for a display hint at most, and
> parse nothing from it. Every occurrence of the `{agreement_level, validator_count}` tag in these
> notes (`README.md`, `INTEGRATION_VISION.md`, `GATE_CLAIM_MAPPING_SCOPING.md`) is superseded by this.
>
> `SlotType` (same section) is `Documentation`, `IssueTracker`, `FabricationQueue`, `GovernanceDAO`,
> `VersionGraph`, `DigitalAsset`, `WeaveWAL`, `FlowstaIdentity`, `UnytAgreement(String)`,
> `CustomApp(String)`. **`CustomApp("valichord")` is usable today** under REQ-NDO-CS-04, so the
> "no validation slot" gap recorded on 2026-07-08 is a preference, not a blocker. A dedicated variant
> modelled on `UnytAgreement(String)` (REQ-NDO-CS-07) is the better ask.
>
> **Not yet implemented:** §8.4 lists `CapabilitySlot` under "Planned additions (post-MVP — not yet in
> `LinkTypes` enum)" and REQ-NDO-CS-01 is marked ❌. There is nothing to link against today.
> REQ-NDO-CS-02 makes permissionless attachment a design guarantee once it exists; REQ-NDO-CS-03
> already anticipates marking individual slots trusted/untrusted.
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
  [COMMENTED OUT — pending resolution]        [still commented out on dev, 2026-08-16]

zome_person ──────────────────────────────► hREA DNA (separate DNA, proven pattern)
  create_rea_agent_bridge()                   create_rea_agent()
  get_hrea_agents()                           get_rea_agents_from_action_hashes()
```

The hREA cross-DNA bridge is now called automatically from `create_person()`.
ValiChord integration follows the same pattern.

> **⚠️ Updated 2026-08-16 — this map is drawn for the shared `nondominium` cell and is now
> incomplete.** Since ADR-010 the same `zome_resource` ↔ `zome_gouvernance` pair is instantiated in
> **every `ndo` clone cell**, so the `create_economic_resource()` → `validate_new_resource()` edge —
> the ValiChord gate — exists once per NDO, addressed by that NDO's `DnaHash`.
>
> The consequential asymmetry: **`zome_person` is not in the `ndo` cell.** Both `zome_person` edges
> above (agent validation data, capability grants) cross a cell boundary when the caller is inside an
> NDO clone. Anything the gate needs about *who* a reviewer is — roles, credentials, private data
> grants — is a cross-cell read from where the gate fires.
>
> Per ADR-012 a reader must also **re-derive the target `DnaHash` from `(network_seed, properties)`
> and compare it against `anchor.ndo_dna_hash`** rather than trusting the anchor. Any ValiChord call
> path that resolves an NDO through a group anchor inherits that obligation.

---

## DnaProperties

> **⚠️ Corrected 2026-08-16 — this section said "Not implemented". That is no longer true.**
> The text below it is kept because it still describes the *base* `dna.yaml` files correctly.

**Implemented, and load-bearing, for `ndo` clone cells (ADR-013).** `NdoDnaProperties` has exactly
one definition — `crates/shared/src/types.rs` — mirrored by the UI and the Sweettest suite (a
hand-kept mirror already drifted once, on a stale `initiator` field):

```rust
pub struct NdoDnaProperties {
  pub name: String,
  pub property_regime: PropertyRegime,
  pub resource_nature: ResourceNature,
  pub created_at: Timestamp,
}
```

`validate_create_nondominium_identity` (`dnas/nondominium/zomes/integrity/zome_resource`) rejects a
`create_ndo` whose classification diverges from the cell's properties. Their framing: *"Immutability
is then hash physics, not a validation rule someone can forget"* — changing a classification field
changes the `DnaHash`, i.e. a different network.

Two caveats that matter if we bind anything to these properties:
- **`initiator` is deliberately NOT bound.** Holochain 0.6.0 transports clone properties as
  `YamlProperties(serde_yaml::Value)`, which has no binary variant, and an `AgentPubKey` in properties
  hangs `createCloneCell` from the JS client. `initiator` stays authoritative on the entry and is
  cached on the anchor for display only. **Do not treat it as DnaHash-bound.**
- **`created_at` is not a uniqueness source** — microseconds derived from a millisecond wall clock.
  Distinctness comes from the per-NDO `network_seed`, which is also DnaHash input.

**Skip path:** the shared `nondominium` cell has `properties: ~`, so deserialising to
`NdoDnaProperties` fails and the binding check is skipped. Legacy shared-cell NDOs keep working.

**Base `dna.yaml` files still carry `properties: ~`** for `lobby`, `nondominium`, `hrea`, `group` and
the `ndo` *template* — properties are supplied per-clone at `create_clone_cell` time, not in the
manifest. Configuration of the integration layer itself still has no home on the Nondominium side, so
it continues to belong in ValiChord's DNA properties or an application-layer config.

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

*Last updated: 2026-07-08. Re-check against branch `ndo-layer1` (their active line): capability-slot
pattern formalised in the v1.0 architecture design (ADRs); `GovernanceRuleType` v1.0 enum has NO
`ExternalValidation` variant (Decision 5 assumption — must be requested explicitly);
governance-as-operator still unimplemented (#41–#44) and is the enforcement dependency for any gate
rule; `PropertyRegime` reduced to 4 variants in code; dual-DNA hREA delegation committed (ADR-006, PPR
preserved); `validate_new_resource` still commented out; Layer 1 not started. Previous update
(2026-06-16): added companion scoping-note pointers (top) + the zome_resource security
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
