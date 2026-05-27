# HDK Trait Abstraction Plan

**Status:** Deferred — return to this when test coverage gaps justify the effort  
**Estimated effort:** 3 weeks minimum (refactor only), 6–7 weeks full (with mock + unit tests)  
**Last updated:** 2026-05-27

---

## 1. Motivation

Every test in the current suite (96 Tryorama integration tests + 37 sweettest tests) requires a real Holochain conductor. This is correct for DHT-level behaviour, but it means:

- Pure business logic (e.g., badge threshold calculations, access-control checks, commit-reveal phase transitions) cannot be tested in isolation
- Test runs take 30–170 minutes; a single typo in a coordinator zome requires a full rebuild+conductor cycle to catch
- Defensive unit tests for edge cases (malformed inputs, concurrent reveal races) are impractical to write against a live DHT

The single genuine gap identified in the AD4M comparison: AD4M wraps `hdk::prelude::*` behind a trait, making every `#[hdk_extern]` testable with a pure in-memory mock. ValiChord does not.

---

## 2. The `HdkDeps` Trait

Approximately 15–18 HDK functions are called across the four coordinators. The trait would look like:

```rust
pub trait HdkDeps {
    fn create_entry<I>(&self, input: I) -> ExternResult<ActionHash>
    where
        I: Into<EntryTypes>;

    fn update_entry<I>(&self, original: ActionHash, input: I) -> ExternResult<ActionHash>
    where
        I: Into<EntryTypes>;

    fn delete_entry(&self, original: ActionHash) -> ExternResult<ActionHash>;

    fn get<I>(&self, input: I, strategy: GetStrategy) -> ExternResult<Option<Record>>
    where
        I: Into<AnyDhtHash>;

    fn get_links(&self, input: GetLinksInput) -> ExternResult<Vec<Link>>;

    fn create_link<T>(&self, base: T, target: T, link_type: impl LinkTypeFilterExt, tag: impl Into<LinkTag>) -> ExternResult<ActionHash>
    where
        T: Into<AnyLinkableHash>;

    fn delete_link(&self, link: ActionHash) -> ExternResult<ActionHash>;

    fn query(&self, filter: ChainQueryFilter) -> ExternResult<Vec<Record>>;

    fn emit_signal<I>(&self, signal: I) -> ExternResult<()>
    where
        I: serde::Serialize;

    fn call<I, O>(&self, call: Call) -> ExternResult<ZomeCallResponse>;

    fn agent_info(&self) -> ExternResult<AgentInfo>;

    fn create_cap_grant(&self, grant: CapGrantEntry) -> ExternResult<ActionHash>;

    fn schedule(&self, scheduled_fn: String) -> ExternResult<()>;

    fn hash_path(&self, path: Path) -> ExternResult<AnyLinkableHash>;

    fn path_ensure(&self, path: &Path) -> ExternResult<()>;
}
```

A `RealHdk` unit struct implementing `HdkDeps` by delegating to `hdk::prelude::*` would be the production implementation. A `MockHdk` would maintain in-memory maps for unit tests.

---

## 3. Refactoring Pattern

Every `#[hdk_extern]` becomes a thin wrapper over a typed inner function:

```rust
// Before
#[hdk_extern]
pub fn request_validation(input: ValidationRequest) -> ExternResult<ActionHash> {
    let agent = agent_info()?.agent_latest_pubkey;
    let hash = create_entry(EntryTypes::ValidationRequest(input.clone()))?;
    create_link(agent, hash.clone(), LinkTypes::ValidationRequests, ())?;
    emit_signal(ValiChordSignal::RequestCreated { hash: hash.clone() })?;
    Ok(hash)
}

// After
#[hdk_extern]
pub fn request_validation(input: ValidationRequest) -> ExternResult<ActionHash> {
    request_validation_impl(&RealHdk, input)
}

pub(crate) fn request_validation_impl<H: HdkDeps>(
    hdk: &H,
    input: ValidationRequest,
) -> ExternResult<ActionHash> {
    let agent = hdk.agent_info()?.agent_latest_pubkey;
    let hash = hdk.create_entry(EntryTypes::ValidationRequest(input.clone()))?;
    hdk.create_link(agent, hash.clone(), LinkTypes::ValidationRequests, ())?;
    hdk.emit_signal(ValiChordSignal::RequestCreated { hash: hash.clone() })?;
    Ok(hash)
}
```

Unit tests then call `request_validation_impl(&mock_hdk, input)` with a `MockHdk` — no conductor, no WASM, sub-millisecond.

---

## 4. Coordinator Breakdown

| Coordinator | Path | `#[hdk_extern]` count | Lines | Complexity |
|---|---|---|---|---|
| `attestation` | `valichord/coordinator/src/attestation/` | ~35 | ~2,235 | Highest — commit-reveal state machine, phase checks |
| `governance` | `valichord/coordinator/src/governance/` | ~12 | ~1,009 | High — badge logic, threshold calculations, cross-DNA calls |
| `researcher_repository` | `valichord/coordinator/src/researcher_repository/` | ~12 | ~324 | Medium — mostly CRUD |
| `validator_workspace` | `valichord/coordinator/src/validator_workspace/` | ~6 | ~290 | Low — thin wrappers over private entry queries |

**Total:** ~65 externs, ~3,858 lines across four coordinators.

Cross-DNA calls (`call_attestation_zome_opt`) add complexity: the mock must handle `Call` inputs and return plausible `ZomeCallResponse` values. Separate `MockAttestationCell` structs may be needed.

---

## 5. Mock Implementation Strategy

```rust
#[derive(Default)]
pub struct MockHdk {
    pub entries: Arc<Mutex<HashMap<ActionHash, Record>>>,
    pub links: Arc<Mutex<Vec<Link>>>,
    pub agent: AgentPubKey,
    pub call_results: Arc<Mutex<VecDeque<ZomeCallResponse>>>,
    pub signals: Arc<Mutex<Vec<serde_json::Value>>>,
}
```

Key points:
- `create_entry` generates a deterministic fake `ActionHash` (e.g., index-based) and stores in `entries`
- `get_links` filters `links` by base hash and link type
- `query` filters `entries` by entry type
- `call` pops from `call_results` queue — tests push expected responses before calling `_impl`
- `emit_signal` appends to `signals` for assertion

DHT behaviours that mocks cannot simulate:
- Validation callbacks (`validate_*`) — these run in integrity zomes, not coordinators
- DHT propagation timing / `DepMissingFromDht` transience
- Multi-agent state (each mock is single-agent)
- Capability grant checking across agents

These remain covered exclusively by sweettest + Tryorama.

---

## 6. Time Estimate

### Phase 1 — Trait definition + `RealHdk` impl (1 week)
- Define `HdkDeps` trait in `valichord/coordinator/src/hdk_deps.rs`
- Implement `RealHdk` delegating to `hdk::prelude`
- Confirm it compiles to `wasm32-unknown-unknown` with zero behaviour change

### Phase 2 — Refactor coordinators (2–4 weeks)
- Refactor each `#[hdk_extern]` into wrapper + `_impl` pattern
- Estimated per coordinator:
  - `researcher_repository`: 2–3 days
  - `validator_workspace`: 2–3 days
  - `governance`: 4–6 days
  - `attestation`: 8–12 days (most complex; phase-transition logic)

### Phase 3 — `MockHdk` + unit tests (2–3 weeks)
- Implement `MockHdk` with stateful entry/link maps
- Write unit tests for each `_impl` function
- Focus areas: badge threshold edge cases, phase-gate enforcement, malformed-input handling

**Total:** ~3 weeks refactor-only (Phases 1+2, no unit tests written), ~6–7 weeks full (all three phases).

---

## 7. ROI Assessment

**Current coverage already high:** 96 Tryorama tests + 37 sweettest tests exercise the full commit-reveal cycle including multi-agent DHT state. The logic that matters most (DHT propagation, capability checking, multi-agent phase agreement) cannot be unit-tested anyway.

**Where unit tests would genuinely help:**
- Badge threshold calculations in governance (pure arithmetic on counts)
- Phase-gate enforcement (state-machine guards, no DHT needed)
- Malformed-input error paths (missing fields, wrong types)
- Cross-DNA call failure modes (governance `call_attestation_zome_opt` returning `None`)

**Where unit tests cannot help:**
- Any test involving two or more agents
- Tests asserting that entries appear in the DHT for other agents
- Validation callback behaviour
- Timing-dependent gossip scenarios

**Verdict at current stage (v0.5.x):** Not worth doing. The codebase is still evolving; abstracting 65 externs across 3,858 lines carries high merge-conflict risk while the architecture is in flux. Revisit at v1.0 when the four DNAs are feature-complete and the test suite is the bottleneck.

---

## 8. Go / No-Go Criteria

Return to this plan when **two or more** of the following are true:

1. A bug escapes to CI/sweettest that a unit test would have caught in seconds
2. The governance badge logic grows beyond ~500 lines of threshold/calculation code
3. A significant refactor of the commit-reveal state machine is planned (the `_impl` pattern makes refactoring safer)
4. Test suite wall-clock time on CI exceeds 4 hours regularly
5. A new contributor joins who needs faster feedback than sweettest provides

---

## 9. Related Files

- `valichord/coordinator/src/` — all four coordinator implementations
- `docs/7_ValiChord_4-DNA_architecture_technical.md` — architecture overview
- `valichord/sweettest_integration/tests/` — existing coverage that this plan would supplement, not replace
