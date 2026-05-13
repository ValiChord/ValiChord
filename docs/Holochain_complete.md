# ValiChord: Complete Holochain Build Guide Knowledge Base
## For handover to new chat sessions
## Compiled: 2026-02-28 — covers ALL pages of the Holochain Build Guide

---

## COVERAGE STATUS

All pages of the Holochain Build Guide have been read and synthesised. Sections 1–25 are from the Build Guide. Sections 26–43 were added from direct crate source analysis (`hdk`, `hdi`, `holochain_integrity_types`, `holochain_zome_types`, `holochain_conductor_api`) and cover API surface NOT in the Build Guide: clone cells, scheduled functions, countersigning, source chain migration, deferred membrane proofs, app status model, app websocket auth tokens, full admin API, FlatOp validation pattern, LinkQuery full filter surface, ChainFilter/LimitConditions, entry/link size limits, GetStrategy, ChainTopOrdering, updated NetworkConfig, signal subscription filtering, warrant types detail, and rate limiting types.

---

## 1. ZOMES

**Two types: integrity and coordinator.** Both are WebAssembly modules (Rust compiled to `wasm32-unknown-unknown`).

**Integrity zome** (use `hdi` crate, not `hdk`):
- Defines data model: entry types (`#[hdk_entry_types]`) and link types (`#[hdk_link_types]`)
- Defines `validate` callback — the ONLY place validation logic lives
- Cannot have side effects, cannot write data, cannot access time-varying data
- Keep small — every change including dependency updates changes the DNA hash, creating a new empty network
- Use `hdi` not `hdk` — smaller, more stable, appropriate subset

**Coordinator zome** (use `hdk` crate):
- Holds back-end logic: CRUD functions, peer communication, signals
- Defines `init`, `post_commit`, `recv_remote_signal` callbacks
- Can depend on integrity zome types by importing them as a Cargo dependency
- KNOWN BUG: coordinator zome can currently only safely depend on ONE integrity zome — always list the dependency explicitly in dna.yaml

**Defining a function:**
```rust
use hdk::prelude::*;

#[hdk_extern]
pub fn say_hello(name: String) -> ExternResult<String> {
    Ok(format!("Hello {}!", name))
}
```
- Single input parameter, returns `ExternResult<T>`
- Input must be serde-deserializable, output serde-serializable
- The `#[hdk_extern]` macro handles WASM memory pointer passing

**WASM constraints** — third-party crates cannot use: OS clock, RNG, filesystem, POSIX, iostreams, networking, multithreading, async/await, WebAssembly JavaScript API, WASI.

---

## 2. CALLBACKS AND LIFECYCLE HOOKS

### Integrity zome callbacks

**`validate`** — takes `Op`, returns `ValidateCallbackResult`. Called when authoring AND when validating others' DHT ops. Must be deterministic. Cannot have side effects.

**`genesis_self_check`** — runs before network join, no DHT access. Format validation only.

### Coordinator zome callbacks

**`init`** — lazy (called on first zome function call, not immediately on cell creation). Takes no args, returns `InitCallbackResult`. Used to create capability grants, register agent links, etc. If ANY zome's init returns `Fail`, cell initialization fails and data is rolled back. If `UnresolvedDependencies`, retried at next call. `InitZomesComplete` action written once all inits succeed — guarantees init never called again. Can force eager init with explicit call (Holochain 0.5+).

**`recv_remote_signal`** — receives remote signals. Takes arbitrary type, returns `ExternResult<()>`. Routes from sender coordinator zome to receiver coordinator zome with SAME NAME. Requires Unrestricted capability grant in init.

**`post_commit`** — called AFTER successful source chain write. Takes `Vec<SignedActionHashed>`. Must return `ExternResult<()>`. MUST NOT write data. Can call other zome functions or emit signals. Tagged `#[hdk_extern(infallible)]` — cannot return errors, must handle all failures internally. Good for pinging peers after data is confirmed written.

**Key insight for ValiChord:** `post_commit` is the right place to send remote signals to other validators after a commitment or reveal is confirmed written. This avoids pointing peers to data that doesn't exist yet (which would happen if you signal within the main function before commit).

---

## 3. DNAs

**DNA = integrity section + coordinator section.** `dna.yaml` manifest.

**Integrity modifiers** (contribute to DNA hash): `network_seed`, `properties`, integrity zomes. Coordinator zomes do NOT affect DNA hash.

**DNA properties** — arbitrary YAML constants baked into DNA hash. Access with `#[dna_properties]` macro:
```rust
#[dna_properties]
pub struct DnaProperties {
    pub authorized_joining_certificate_issuer: AgentPubKey,
    pub discipline: String,
    pub minimum_validators: u32,
}
// Use: DnaProperties::try_from_dna_properties()?
```
ValiChord usage: embed issuing authority key, discipline, minimum validator thresholds per network. Changing properties = new DNA hash = new network. Use for tamper-evident, stable, per-network configuration.

**Known bug:** coordinator zome can currently only safely depend on ONE integrity zome. Always list explicitly:
```yaml
coordinator_zomes:
  - name: my_coordinator
    dependencies:
      - name: my_integrity  # always explicit even if only one
```

---

## 4. hApps

**hApp = bundle of DNAs + optional web UI.** `happ.yaml` manifest.

Each role in hApp filled by a DNA. Roles have name, provisioning strategy, DNA path, modifiers, clone_limit. DNA `installed_hash` can be specified to ensure integrity at install time.

**Packaging:** `hc app pack` → `.happ` bundle. `hc web-app pack` → `.webhapp` bundle.

**Distribution options:**
- Holochain Launcher (Electron-based runtime, devHub/hApp store)
- Kangaroo (Electron template, Windows/macOS/Linux)  
- p2p Shipyard (Tauri-based, adds Android support)

**`allow_deferred_memproofs: false`** — set true to hold hApp disabled until membrane proofs provided. Advanced, leave false for most hApps.

---

## 5. WORKING WITH DATA

**Record = entry + action.** Primary unit of data. Action contains: agent ID, timestamp, action type, previous action hash, sequence index.

**Entry types:** `Create` and `Update` (entry creation actions). `Delete` and link actions have no entry.

**Same entry content + different creation actions = different records** — each can be treated as an independent piece of data.

**CRUD model is additive — data is never deleted:**
- `Create` — stores entry at entry hash, action as metadata at entry hash
- `Update` — same as Create, plus marks original entry/action as updated
- `Delete` — marks entry creation action as dead via metadata; entry itself only dead when ALL creation actions deleted
- `CreateLink` — action stored as metadata at base address
- `DeleteLink` — marks specific create-link action as dead

**Private entries** — actions are still public; only entry content stays private on author's device.

**Default CRUD rules:** `get` returns oldest-timestamped, valid, live creation action. Updates not retrieved by default — must use `get_details`. Multiple updates create branching (Git-like). Entry dead only when ALL creation actions deleted.

---

## 6. ENTRIES

**Define entry type in integrity zome:**
```rust
#[hdk_entry_helper]
pub struct ValidationAttestation {
    pub research_hash: ExternalHash,  // SHA-256 of research file
    pub validator_pubkey: AgentPubKey,
    pub commitment: Vec<u8>,          // blinded commitment
    pub protocol_round: u32,
}

#[hdk_entry_types]
#[unit_enum(UnitEntryTypes)]
enum EntryTypes {
    ValidationAttestation(ValidationAttestation),
    #[entry_type(visibility = "private")]
    ValidatorWorkspace(ValidatorWorkspace),
    #[entry_type(required_validations = 7)]
    HarmonyRecord(HarmonyRecord),
}
```

**Create:** `create_entry(&EntryTypes::ValidationAttestation(entry))?` → returns `ActionHash`.

**Update:** `update_entry(old_action_hash, &EntryTypes::Foo(new_entry))?`
- Update patterns: list (all updates reference original Create), or chain (each references previous Update)

**Delete:** `delete_entry(action_hash)?` — marks action dead, not entry content

**Retrieve:**
- `get(hash, GetOptions::network())` → `Option<Record>` — only live, valid data
- `get_details(action_hash, ...)` → `Option<Details::Record>` — includes updates, deletes, validation status
- `get_details(entry_hash, ...)` → `Option<Details::Entry>` — all creation actions, updates, deletes for that entry

**Identifiers:**
- `EntryHash` — identifies entry content (multiple records can share same entry hash)
- `ActionHash` — identifies specific record instance (author + time + content)
- `AgentPubKey` — agent identity, usable as DHT address
- `ExternalHash` — 32-byte identifier for data outside DHT (e.g. SHA-256 of research files)

**Relaxed chain top ordering** — for entries with no dependencies on other data, use `create(CreateInput { chain_top_ordering: ChainTopOrdering::Relaxed, ... })` to reduce transaction rollbacks.

---

## 7. LINKS, PATHS, AND ANCHORS

**Links** attach as metadata to an address (base), pointing to another address (target). Contains: base, target, type, optional tag (up to 1 KB arbitrary bytes — useful for search indexes/summaries).

**Define link type in integrity zome:**
```rust
#[hdk_link_types]
enum LinkTypes {
    ValidatorToAttestation,
    ResearchHashToAttestation,
    AttestationByDiscipline,
}
```

**Create:** `create_link(base, target, LinkTypes::ValidatorToAttestation, tag_bytes)?`
Links cannot be updated, only created or deleted. Multiple identical links are each distinct.

**Delete:** `delete_link(create_link_action_hash, GetOptions::network())?`
Use `local()` only if you know the original link is definitely local (e.g. you created it).

**Retrieve:**
- `get_links(LinkQuery::try_new(base, LinkTypes::Foo)?, GetStrategy::default())` — live links only
- `get_links_details(...)` — live and dead links
- `count_links(...)` — efficient count (but still goes to network currently)
- Filter by tag prefix: `.tag_prefix("year:196".as_bytes().to_owned().into())`

**Paths** — hierarchies of anchors. Built-in pattern for collections, indexes, taxonomies.
```rust
let path = Path::from("attestations_by_discipline.computational_biology")
    .typed(LinkTypes::AttestationByDisciplineAnchor)?;
path.ensure()?;  // creates if not exists, no-op if already exists
create_link(path.path_entry_hash()?, target, LinkTypes::AttestationByDiscipline, ())?;
```

**ValiChord patterns:**
- Link from discipline path to ValidatorAttestation entries for discipline-based discovery
- Link from research_hash (ExternalHash) to attestation entries
- Link from validator pubkey to their attestation actions
- Be careful of DHT hot spots — use hierarchical paths to spread load (e.g. by discipline, then by month)

**Community libraries:**
- holochain-prefix-index — starts-with text search
- holochain-time-index — time-bucketed index

---

## 8. QUERYING SOURCE CHAINS

**Own chain:** `query(ChainQueryFilter::new().entry_type(...).include_entries(true))?` → `Vec<Record>`

**Another agent's chain (coordinator):** `get_agent_activity(agent_id, filter, ActivityRequest::Full, GetOptions::network())?` *(4th param required since HDK 0.6.1)*
- Returns action hashes + chain status (valid/invalid/forked) + warrants
- Does NOT include entry data — must do separate DHT gets for entries
- Design zome functions as single-query functions returning hashes, let client do follow-up calls

**During validation:** `must_get_agent_activity(agent_id, ChainFilter::new(prev_hash).until_timestamp(t))?`
- Returns actual action data (not just hashes) for a bounded contiguous slice
- Best used in `RegisterAgentActivity` op validation (authority already has data locally)
- Can enforce rate limiting, account balance checks, history-based rules

**ChainQueryFilter options:**
- `sequence_range()` — by index or hash range
- `entry_type()` — filter by entry type
- `action_type()` — filter by action type
- `include_entries(true)` — retrieve entry data (ignored by get_agent_activity)
- `descending()` — reverse chronological

**Important:** DHT requests can fail. Build retry logic. Don't chain multiple queries in one zome function if any individual one failing would waste prior work.

---

## 9. VALIDATION RECEIPTS

Peers send validation receipts to the action author after integrating a DHT operation. Author's conductor tracks these to gauge DHT propagation.

**Default:** 5 receipts per operation needed before author considers publishing complete. Override per entry type with `required_validations` field.

**Caveats:** Receipts accumulate over time but validators may disappear. Receipt count reflects state shortly after authoring, not ongoing availability. Treat as rough gauge of initial propagation only.

**ValiChord use:** Check if attestation entries have been received by sufficient validators before proceeding to next protocol phase. Use `has_action_been_fully_published()` pattern as a safeguard, but don't rely on it as a security guarantee.

```rust
let sets = get_validation_receipts(GetValidationReceiptsInput { action_hash })?;
let is_published = sets.iter().all(|set| set.receipts_complete);
```

Receipts only available in the authoring conductor's cells (and other cells with same DNA on same conductor).

---

## 10. CELL INTROSPECTION

**`dna_info()`** — available to both coordinator and integrity. Returns name, hash, modifiers (network_seed, properties), zome_names.

**`zome_info()`** — available to both. Returns name, id, properties, entry_defs, extern_fns, zome_types.

**`agent_info()`** — coordinator ONLY. Returns agent_initial_pubkey, chain_head (advances in scratch space as you write in current function).

**`call_info()`** — coordinator ONLY. Returns provenance (who signed the call), function_name, as_at (persisted chain state at call start — doesn't change as you write within function), cap_grant.

**Key difference:** `agent_info().chain_head` advances as you write in current function (scratch space state). `call_info().as_at` stays fixed (persisted state at call start). Use `as_at` for snapshot at call time, `chain_head` for current scratch state.

**ValiChord use:** Check `call_info().provenance == agent_info().agent_initial_pubkey` to verify a call is coming from the same agent (not a remote peer). Use for protecting write functions in Attestation DNA.

---

## 11. CRYPTOGRAPHY FUNCTIONS

(From previous session — documented in scaffold v4)

- **Blake2b-256** — Holochain's internal hashing algorithm. Used for ActionHash, EntryHash, AgentPubKey. NOT SHA-256.
- **SHA-256** — for research file fingerprints. Requires external crate (`ring` or `sha2`) compiled to WASM. Store result as `ExternalHash` (32-byte type).
- **`sign(agent_pubkey, data)`** — sign arbitrary data with agent's key
- **`verify_signature(pubkey, signature, data)`** — verify a signature
- **`hash_entry(entry)`** — get Blake2b-256 hash of entry content
- **`x_salsa20_poly1305_encrypt/decrypt`** — authenticated encryption
- **`create_x25519_keypair`**, **`x_25519_x_salsa20_poly1305_encrypt/decrypt`** — key agreement + encryption

---

## 12. MISCELLANEOUS HOST FUNCTIONS

All coordinator-only:

**`sys_time()`** — current system time as `Timestamp`. NOT available in integrity zome (would break validation determinism).

**`random_bytes(n)`** — OS RNG, returns `Bytes`. Not provably random, not seedable/repeatable. NOT available in integrity zome.

**Logging** — use `tracing` crate macros (`trace!`, `debug!`, `info!`, `warn!`, `error!`). Set `WASM_LOG` env var. Available in any `#[hdk_extern]` function.

**ValiChord note:** sys_time and random_bytes cannot be used in validate(). Use them in coordinator functions only (e.g., generating nonces for commit-reveal in coordinator, not in validation of those commits).

---

## 13. CAPABILITIES

(From previous session — documented in scaffold v4)

**Three levels:**
- `Unrestricted` — any caller, no secret needed
- `Transferable` — any caller with the right secret
- `Assigned` — caller must have secret AND sign with authorized key

**Author grant** — same-agent calls (cells in same hApp instance) have implicit grant. No explicit capability needed for within-node cross-DNA coordination.

**Without explicit grants,** remote callers get `ZomeCallResponse::Unauthorized` even on intended-public functions.

**Setup in `init()` callback:**
```rust
#[hdk_extern]
pub fn init() -> ExternResult<InitCallbackResult> {
    // Grant unrestricted access to recv_remote_signal
    let mut functions = BTreeSet::new();
    functions.insert((zome_info()?.name, "recv_remote_signal".into()));
    create_cap_grant(ZomeCallCapGrant {
        tag: "unrestricted-remote-signals".into(),
        access: CapAccess::Unrestricted,
        functions: GrantedFunctions::Listed(functions),
    })?;
    Ok(InitCallbackResult::Pass)
}
```

**ValiChord capability map:**
- Attestation DNA: Unrestricted for `recv_remote_signal`, `read_attestations`, `check_protocol_phase`
- Governance/Harmony Records DNA: Unrestricted for all read functions (HTTP Gateway access for non-participants)
- Researcher Repository DNA: Author grant handles all (private, same-agent only)
- Validator Workspace DNA: Author grant handles all (private, same-agent only)
- Write/commit functions in Attestation DNA: Assigned to credentialed validators only

---

## 14. GENESIS SELF-CHECK + VALIDATE_AGENT_JOINING

(From previous session — documented in scaffold v4)

**Two-stage membrane proof:**

Stage 1 — `genesis_self_check(data: GenesisSelfCheckData)`: runs BEFORE network join, no DHT access. Format-only validation. Protects joining agent from committing malformed proof. Return `GenesisSelfCheckCallbackResult::Valid` or `::Invalid`.

Stage 2 — `validate_agent_joining` pattern in `validate()`: runs after network join, has DHT access. Full credential verification. Must cover everything Stage 1 covers plus DHT-dependent checks (does issuing authority exist on DHT? is their credential valid? is their signature over joining agent's key?).

---

## 15. SIGNALS

(From previous session — documented in scaffold v4)

**Local signals** (`emit_signal`) — sent to front ends on same device. Send-and-forget.

**Remote signals** (`send_remote_signal`) — sent to other agents in SAME DNA's network. Send-and-forget, no delivery guarantee, no persistence.

**CRITICAL:** Signals CANNOT drive protocol phase transitions. If validator offline when signal fires, they miss the transition. Phase transitions must be driven by coordinator functions polling DHT state (check if all expected commitment entries exist, then proceed). Use signals for UI notification only.

**`post_commit` + signal pattern** for safe peer notification:
1. Write commitment to DHT (returns immediately, not yet persisted)
2. `post_commit` fires after successful write
3. Send remote signal from `post_commit` to notify peer their action is needed

---

## 16. CALLING ZOME FUNCTIONS / CROSS-DNA CALLS

(From previous session — documented in scaffold v4)

**Within same cell:** direct function calls, no inter-zome call needed.

**Within same hApp (same agent, different DNA):** `call(CallTargetCell::OtherRole("role_name"), ...)` — author grant applies automatically.

**Same DNA, different agent:** `call_remote(agent_pubkey, zome_name, fn_name, cap_secret, payload)` — requires unrestricted grant or capability claim on receiver.

**CRITICAL CONSTRAINT — call_remote blocked across different DNA networks.** Alice's Attestation DNA CANNOT call_remote to Bob's Researcher Repository DNA. They are in different networks. All inter-validator coordination happens within Attestation DNA's shared network. Data from private DNAs must be explicitly passed by the owning agent.

**ValiChord cross-DNA call map:**
- Researcher → Attestation: researcher calls `submit_for_validation(research_hash, metadata)` in their own Attestation cell — author grant handles it
- Validator A Attestation → Validator B Attestation: `call_remote` within shared Attestation DHT network — valid
- Attestation → Researcher Repository: CANNOT do call_remote across networks; researcher must push data themselves

---

## 17. MUST_GET_* HOST FUNCTIONS

For use in `validate()` callbacks — the ONLY DHT retrieval functions available in validation.

**Why:** validation must be deterministic. Functions like `get_links` can vary by current metadata state. `must_get_*` functions retrieve only addressable content (not state-changing metadata).

**If data not found:** returns `ValidateCallbackResult::UnresolvedDependencies` — validation retried later, not treated as failure.

**`must_get_entry(entry_hash)`** — get entry content only, ignores validity.

**`must_get_action(action_hash)`** — get action only, ignores validity.

**`must_get_valid_record(action_hash)`** — get record AND fail if record is marked invalid by validators. Enables inductive validation (building on guaranteed-valid prior records). Note: only checks StoreRecord op validity, not other ops from same action.

**`must_get_agent_activity(agent_id, ChainFilter::new(prev_hash).until_timestamp(t))`** — bounded contiguous slice of source chain. Best used in RegisterAgentActivity op validation. Expensive if entries needed (separate network requests per hash). Timestamps are self-reported — agents can falsify them.

**Inductive validation pattern:** use `must_get_valid_record` to ensure referenced prior records are valid before building validation logic on top of them.

---

## 18. DHT OPERATIONS

Each action produces multiple DHT ops sent to different authorities:

**All actions produce:**
- `RegisterAgentActivity` — basis: author pubkey; appends to replica of author's source chain; detects forks
- `StoreRecord` — basis: action hash; stores action + optional entry

**Create additionally produces:**
- `StoreEntry` — basis: entry hash; stores entry content (NOT produced for private entries)

**Update additionally produces:**
- `StoreEntry` (new entry)
- `RegisterUpdate` — basis: original entry hash AND original action hash; marks original as updated

**Delete additionally produces:**
- `RegisterDelete` — basis: original entry hash AND original action hash; marks original as deleted

**CreateLink:**
- `RegisterCreateLink` — basis: link base address

**DeleteLink:**
- `RegisterDeleteLink` — basis: link base address AND original create-link action hash

**Warrant ops** — produced by validators when they discover invalid ops. Basis: author's pubkey. System-only, no validation code needed.

**Validation splitting:** you can write different validation logic for each op type. Scaffolding tool makes sensible defaults (validates at StoreRecord/StoreEntry level, forwards to your stub functions). You can split validation work: e.g. write-privilege checks in RegisterAgentActivity, data structure checks in StoreEntry.

**ValiChord consideration:** put critical security validation logic (credential checking, commitment structure) in StoreRecord path so `must_get_valid_record` truly reflects overall validity.

---

## 19. GETTING AN AGENT'S STATUS

(From previous session)

`get_agent_activity(agent_id, filter, ActivityRequest::Full, GetOptions::network())` returns `AgentActivity` with: *(4th `GetOptions` param required since HDK 0.6.1)*
- `status: ChainStatus` — Valid, Invalid(warrant), Forked(warrant), Empty
- `valid_activity: Vec<(u32, ActionHash)>` — sequence index + hash
- `warrants: Vec<Warrant>`

**Warrants** — created by validators when they detect invalid ops. Collected at agent's pubkey address. Application layer must use warrants to gate interactions with bad actors (the network doesn't block them automatically — on roadmap but not current behaviour).

**`WarrantOp` struct** — the DHT op type that carries a warrant. Implements `Deref<Target = SignedWarrant>` (i.e. `Signed<Warrant>`), so all `SignedWarrant` accessors are available directly on a `WarrantOp`.

Key methods:
- `op.get_type() -> WarrantOpType` — discriminates the warrant kind
- `op.timestamp() -> Timestamp` — when the warrant was issued
- `op.warrant() -> &Warrant` — the underlying `Warrant` value
- `op.action() -> &Action` — the action the warrant is about (via `Deref`)
- `op.signature() -> &Signature` — validator's signature (via `Deref`)
- `WarrantOp::sign(keystore, warrant).await -> LairResult<WarrantOp>` — sign a raw `Warrant` into a publishable op (system/conductor use; app zomes don't call this directly)

`WarrantOp` is `From<Signed<Warrant>>` and converts `Into<DhtOp>` / `Into<DhtOpLite>`. It is fully serialisable (`Serialize`/`Deserialize`, `TryFrom<SerializedBytes>`).

Application zomes receive warrants via `get_agent_activity` (as `Vec<Warrant>` in `AgentActivity.warrants`) — `WarrantOp` is the conductor/DHT layer representation; the zome-facing type is `Warrant`.

**ValiChord warrant-gating pattern** — check `activity.warrants` before accepting an agent into protocol flow:

```rust
let activity = get_agent_activity(
    suspect_agent.clone(),
    ChainQueryFilter::new(),
    ActivityRequest::Full,
    GetOptions::network(),   // required since HDK 0.6.1
)?;

if !activity.warrants.is_empty() {
    return Err(wasm_error!(WasmErrorInner::Guest(
        "Agent has outstanding warrants — protocol participation refused".into()
    )));
}
```

Three meaningful locations in ValiChord (Phase 1 backlog, alongside reputation system):
1. **`claim_study`** — before accepting a validator into the quorum
2. **`notify_commitment_sealed`** — before writing their CommitmentAnchor to the shared DHT
3. **`check_and_create_harmony_record`** — before including a validator's attestation in a HarmonyRecord

For case 3, `WarrantOp.timestamp()` lets you filter to warrants issued *after* the study was submitted, treating pre-existing warrants differently from warrants received mid-round.

**Critical caveat:** the network does NOT block warranted agents from writing ops — a warranted agent can still submit data. The warrant check gates whether ValiChord *accepts* them into protocol flow. Place checks in coordinator zome logic only, not in `validate()` (validation runs on all peers and must not use network calls).

---

## 20. TESTING WITH TRYORAMA

JavaScript-based test framework. Write scenarios as async functions.

```javascript
test("two agents attest", async () => {
    await runScenario(async scenario => {
        const playerConfig = {
            appBundleSource: { type: "path", value: `${process.cwd()}/../workdir/valichord.happ` },
            options: {
                rolesSettings: {
                    attestation: {
                        type: "provisioned",
                        value: { modifiers: { properties: { minimum_validators: 3 } } }
                    }
                }
            }
        };
        const [alice, bob] = await scenario.addPlayersWithApps([playerConfig, playerConfig]);

        // Alice submits research
        const attestationHash = await alice.appWs.callZome({
            role_name: "attestation",
            zome_name: "attestation_coordinator",
            fn_name: "submit_for_validation",
            payload: { research_hash: researchHash }
        });

        // Wait for DHT sync before Bob tries to retrieve
        const attestationDnaHash = alice.cells.find(c => c.name === "attestation")?.cell_id[0];
        await dhtSync([alice, bob], attestationDnaHash);

        // Bob retrieves and validates
        const result = await bob.appWs.callZome({ ... });
    });
});
```

**Key functions:**
- `scenario.addPlayerWithApp(config)` — single agent
- `scenario.addPlayersWithApps([config, config])` — multiple agents
- `dhtSync([alice, bob], dnaHash)` — wait for peers to sync
- `bob.conductor.shutDown()` / `bob.conductor.startUp()` — simulate disruptions
- Signal handler: `bob.appWs.on("signal", handler)` — wrap in Promise for async test

**ValiChord testing patterns:**
- Test offline scenario: validator B offline when A commits → B comes back → check B can still complete protocol by polling DHT
- Test membrane proof: agent with invalid credentials fails to join Attestation DNA
- Test CANNOT do: remote signal triggers phase transition (design around DHT polling instead)

---

## 21. OPERATING A hAPP

**Distribution:** Kangaroo (Electron, Windows/macOS/Linux) or p2p Shipyard (Tauri, adds Android).

**Auto-update caveat:** updating bundled hApp file does NOT replace it for existing auto-update users. Cannot update coordinator zomes via auto-update to existing users. Bump leftmost version integer for incompatible changes.

**DHT availability:** the DHT only exists while agents are running cells. For production: run always-on nodes (self-hosted or cloud VMs) to ensure continuous availability.

**Network infrastructure required (0.6.1 / iroh era):**
- Kitsune2 bootstrap server — peer discovery (HTTP) + SBD (WebSocket) on same port
- iroh relay server — QUIC NAT traversal for production deployments (optional for direct LAN)
- All agents in a DNA must use the SAME bootstrap server to find each other
- Configure in `kangaroo.config.ts`: `bootstrapUrl` (https://), `signalUrl` (wss://), optionally `relayUrl`

**ValiChord operational note:** The Governance/Harmony Records DNA (public DHT) benefits most from always-on nodes. Researcher Repository and Validator Workspace are private per-agent — no always-on nodes needed for those. Attestation DNA needs good availability during active validation rounds.

---

## 22. VALICHORD-SPECIFIC PATTERNS AND DECISIONS

### Four-DNA architecture (from Arthur Brock session)
1. **Researcher Repository DNA** — private, local only. Researcher's own research files and metadata. No external access.
2. **Validator Workspace DNA** — private per validator. Their working notes, intermediate calculations. No external access.
3. **Attestation DNA** — shared DHT, credentialed membrane. Commit-reveal protocol. All inter-validator coordination happens here. HTTP Gateway for public read.
4. **Governance/Harmony Records DNA** — public DHT, open read. Final validated outcomes, journal links, funder records. HTTP Gateway for non-participant access.

### Commit-reveal protocol in Attestation DNA
- **Round 1 Commit:** validator creates `CommitmentEntry` (blinded hash of their assessment) — written to Attestation DHT
- **Phase transition:** coordinator function polls DHT — checks if ALL expected validators have written CommitmentEntry — then opens reveal window
- **Round 2 Reveal:** validator creates `RevealEntry` (actual assessment + nonce) — DHT validates hash matches commitment
- **Collusion detection:** coordinator logic (NOT validation) compares reveals after all submitted — statistical analysis belongs in coordinator, not validate()
- **`post_commit`** sends remote signal to other validators after commit/reveal written — signals are notification only, protocol machinery is DHT-poll-driven

### Membership control (Attestation DNA membrane)
- `genesis_self_check`: format-only check of joining credential before network join
- `validate_agent_joining`: full credential check with DHT access — verify issuing authority exists, their credential is valid, signature over joining agent's key is correct
- `#[dna_properties]` stores `authorized_joining_certificate_issuer: AgentPubKey` — baked into DNA hash, tamper-evident

### Source chain querying for ValiChord
- Researcher's own commitments: `query(filter)` on their own Researcher Repository chain
- Check if a validator has submitted for a given validation round: `get_agent_activity(validator_pubkey, filter)` in Attestation coordinator — returns action hashes, then get entries
- Rate limiting: use `must_get_agent_activity` in validate() with timestamp filter (but note timestamps are self-reported)

### Validation receipts for protocol
- After writing CommitmentEntry, can check `has_action_been_fully_published()` before considering commitment submitted
- Not a security guarantee — use as a UX indicator only

### Warrant handling
- On warrants detected via `get_agent_activity`, application coordinator logic must gate future interactions with that agent
- Network does NOT automatically block warranted agents (current behaviour)
- Store warrant status in application state and check before accepting protocol participation from a given agent

### Identifiers
- Research files: `ExternalHash` (SHA-256 via `sha2` crate, external to Holochain DHT)
- Attestation entries: `ActionHash` (identifies specific validator's specific attestation instance)
- Commitment linkage: link from research file `ExternalHash` to attestation `ActionHash`
- Validator discovery: link from validator `AgentPubKey` to their attestation actions

### Testing priorities (Tryorama)
1. Membrane proof acceptance/rejection for Attestation DNA
2. Commit-reveal round with DHT sync between validators
3. Phase transition driven by DHT polling (NOT signals)
4. Offline validator scenario — validator returns and can complete protocol
5. Collusion detection in coordinator (post-reveal comparison)
6. Warrant detection and gating

---

## 23. SCAFFOLD STATUS

Current scaffold: **valichord_scaffold_4.rs** — single-file representation of all four DNAs. Accurate against all Build Guide pages.

Deferred: restructuring into actual four-DNA module structure. That belongs to when Shin Sakamoto (potential Lead Engineer) is on board.

Key corrections in scaffold v3 and v4:
- Warrant mechanism softened (application layer gates, network doesn't)
- Blake2b vs SHA-256 distinction
- ExternalHash for research file fingerprints
- Gaming/collusion detection moved from validate() to coordinator
- call_remote cross-DNA constraint documented
- Signal → phase transition removed; DHT polling substituted
- Capability grants and init() documented
- DNA properties pattern documented
- Two-stage membrane proof pattern documented

---

## 24. CONNECTING A FRONT END

Front ends connect to a hApp via the **application API** over a **local WebSocket interface only** — not exposed to external network adapters. This is a security measure: only processes on the same device can reach the hApp.

**Where the front end runs:** on each agent's own device, distributed with the hApp and a Holochain runtime. There is no application server. The conductor runs locally, exposes a local WebSocket, and the front end connects to that.

**JavaScript client library:** `@holochain/client` (TypeScript). Rust client also available.

**Connecting:**
```typescript
import { AppWebsocket, HolochainError } from '@holochain/client';

const getHolochainClient = (() => {
    let client: AppWebsocket | undefined;
    return async () => {
        if (client === undefined) {
            client = await AppWebsocket.connect();
            // installedAppId is available on the connected client
        }
        return client;
    };
})();
```

**No URI needed** — Holochain runtimes that serve a web UI inject a constant into the page containing the WebSocket URI. The client looks for that automatically. If building a standalone front end outside a runtime, pass the URI manually to `AppWebsocket.connect`.

**Dev runtime:** `hc-spin` (scaffolded hApps) — starts conductor, installs hApp, serves UI. `npm run start` compiles back end to `.happ` and launches two instances for testing.

**Supported UI frameworks** (scaffolding tool): Lit, React, Svelte, Vue, plain JS/TS.

**What the front end can do via AppWebsocket:**
- Call zome functions (`callZome`)
- Listen to local signals (`appWs.on("signal", handler)`)
- Clone cells (`createCloneCell`)
- Get app info

**ValiChord note:** The ValiChord UI connects to whichever local conductor the researcher or validator is running. The researcher's UI connects to their local Researcher Repository and Attestation cells. A validator's UI connects to their Validator Workspace and Attestation cells. There is no shared server — each participant runs their own conductor.

---

## 25. HOLOCHAIN 0.6.0 CONDUCTOR CONFIG — LEGACY (tx5/WebRTC era)

> **Current ValiChord target is 0.6.1 (iroh/QUIC transport).** See §40 for the current NetworkConfig reference. This section is retained for historical context and for understanding the 0.6.0→0.6.1 migration.

### NetworkConfig fields (holochain_conductor_api 0.6.0 — tx5 era)

```yaml
network:
  bootstrap_url: https://...      # kitsune2 bootstrap server (peer discovery)
  signal_url: wss://...           # SBD signal server (tx5/WebRTC signalling) — obsolete under iroh
  webrtc_config: ...              # Optional WebRTC peer connection config — obsolete under iroh
  target_arc_factor: 1            # 0 = leacher (no gossip contribution)
  advanced:                       # DEAD CONFIG under iroh — remove from conductor-config.yaml
    tx5Transport:                 # iroh is the default transport in 0.6.1; this block is ignored
      signalAllowPlainText: true
      timeoutS: 60
      dangerForceSignalRelay: false
    coreBootstrap:
      serverUrl: ...              # Overridden by bootstrap_url if both set
```

**IMPORTANT:** `mem_bootstrap`, `disable_bootstrap`, `disable_publish`, `disable_gossip` are `#[cfg(feature = "test-utils")]` — they only exist in test builds, NOT the production `holochain` binary. Do not add them to conductor-config.yaml.

### ~~tx5 single-agent "Peer connection failed" issue~~ — RESOLVED IN 0.6.1

In Holochain 0.6.0, `get_links` propagated ANY tx5 send error as a fatal WasmError. This was the primary motivation for the `_retryOnTx5` / `retryOnNetworkError` wrappers in the demo node scripts.

**This issue is resolved in 0.6.1.** iroh/QUIC is the default transport and does not produce "Peer connection failed" errors. The retry wrappers have been generalised to catch timeout/channel-drop errors rather than tx5-specific ones.

For local dev, `kitsune2-bootstrap-srv` is still required for peer discovery:

```bash
cargo install kitsune2_bootstrap_srv --version 0.4.1 --locked
kitsune2-bootstrap-srv --listen 127.0.0.1:9000 --sbd-disable-rate-limiting &
```

The binary handles BOTH bootstrap (HTTP) and SBD (WebSocket) on the same port. No `advanced.tx5Transport` config is needed.

### HTTP Gateway (hc-http-gw 0.3.1) — verified from source

URL format: `GET /{dna_hash}/{app_id}/{zome_name}/{fn_name}?payload=<base64>`

- `payload` query parameter: base64url WITH `=` padding (`BASE64_URL_SAFE` = Rust base64 crate URL_SAFE engine with PAD)
- axum's `Query` extractor URL-decodes the parameter automatically (`%3D` → `=`)
- Payload is base64url of the JSON-encoded zome input (e.g., a quoted hash string `"uhCkk..."`)
- On success returns JSON-encoded zome output
- Error "Invalid base64 encoding" = the base64 decode failed before reaching Holochain
- `max_identifier_chars` limit: 100 characters for app_id, zome_name, fn_name
- Allowed functions configured via env var: `HC_GW_ALLOWED_FNS_{APP_ID}=zome/fn,zome/fn`

### ExternalHash in JavaScript (@holochain/client)

```js
import { hashFrom32AndType, HoloHashType, encodeHashToBase64 } from '@holochain/client';
// sha256hex: 32-byte hex string (e.g. from Node crypto.createHash('sha256').digest())
const externalHash = hashFrom32AndType(Buffer.from(sha256hex, 'hex'), HoloHashType.External);
const hashB64 = encodeHashToBase64(externalHash);  // "uhC8k..." string
```

To build a gateway payload from an ExternalHash:
```js
const b64 = Buffer.from(JSON.stringify(hashB64)).toString('base64url');  // no-pad
const gatewayPayload = b64 + '='.repeat((4 - b64.length % 4) % 4);      // add padding
```

---

## 26. CLONE CELLS (runtime DNA cloning)

Clone cells let a coordinator zome spawn new cells from the same base DNA at runtime with a different `network_seed` or `properties`, creating a distinct DHT space. Used for multi-instance or per-group spaces.

**HDK functions (callable from zome code):**
- `create_clone_cell(CreateCloneCellInput) -> ExternResult<ClonedCell>` — spawn a new cell; at least one of `network_seed` or `properties` in `modifiers` must differ from the original DNA
- `disable_clone_cell(DisableCloneCellInput) -> ExternResult<()>` — disable without deleting
- `enable_clone_cell(EnableCloneCellInput) -> ExternResult<ClonedCell>` — re-enable a disabled clone
- `delete_clone_cell(DeleteCloneCellInput) -> ExternResult<()>` — permanently delete a disabled clone

**Key types:**
- `CreateCloneCellInput { cell_id, modifiers: DnaModifiersOpt, membrane_proof, name }`
- `ClonedCell { cell_id, clone_id, original_dna_hash, dna_modifiers, name, enabled }` — returned on create/enable
- `CloneCellId` enum — identify by `CloneId` (e.g. `"my_role.0"`) or `DnaHash`

**happ.yaml:** `clone_limit: u32` per role (default `0` = no clones allowed). `CellProvisioning::CloneOnly` installs the DNA but creates no base cell — only clones are ever instantiated.

**App interface equivalents:** `AppRequest::CreateCloneCell`, `DisableCloneCell`, `EnableCloneCell` — mirror the HDK calls but are invoked from the front end.

---

## 27. SCHEDULED FUNCTIONS (cron / ephemeral timers)

The only mechanism for background/autonomous zome behaviour without an external client call. Functions can be scheduled to run once after a delay or on a recurring crontab.

**Register a schedule (from any coordinator function or `init`):**
```rust
schedule("my_scheduled_fn")?;  // idempotent — no-op if already scheduled
```

**Schedulable function signature** — must use `infallible`:
```rust
#[hdk_extern(infallible)]
fn my_scheduled_fn(_: Option<Schedule>) -> Option<Schedule> {
    // input: Schedule returned last time (None on first invocation)
    // return None to unschedule, or a new Schedule to reschedule
    Some(Schedule::Persisted("0 * * * * * *".into()))  // every minute
}
```

**`Schedule` enum:**
- `Schedule::Persisted(String)` — crontab string; survives conductor reboot; must return same crontab each time to maintain
- `Schedule::Ephemeral(Duration)` — fires once after duration; does NOT survive reboot; `Duration::ZERO` = next scheduler tick (~100ms)

**Caveats:**
- `init` is lazy — `schedule()` called in `init` may not fire for a long time if the cell is never called
- Scheduled functions always run as the cell's chain author; calling capability grants do NOT carry forward
- If the function call fails, it is unscheduled automatically
- An invalid crontab string causes the schedule to be dropped silently

---

## 28. COUNTERSIGNING (multi-agent atomic entry commit)

Allows 2–8 agents to atomically commit a shared entry that appears on all their source chains simultaneously, locked by a time-bounded session. Feature-gated `unstable-countersigning`.

**Flow:**
1. Coordinator picks a session window: `session_times_from_millis(ms)` → `CounterSigningSessionTimes`
2. Build a `PreflightRequest` with all signers, entry hash, and session times — the SAME struct goes to every participant
3. Each participant: `accept_countersigning_preflight_request(preflight)` — locks their local chain for the session duration
4. All signers create their countersigned entry (`Entry::CounterSign(session_data, app_bytes)`) within the session window
5. Conductor coordinates publication and emits `SystemSignal::SuccessfulCountersigning`

**Key types:**
- `PreflightRequest { app_entry_hash, signing_agents: CounterSigningAgents, optional_signing_agents, minimum_optional_signing_agents, enzymatic: bool, session_times, action_base, preflight_bytes }`
- `CounterSigningAgents = Vec<(AgentPubKey, Vec<Role>)>` — `Role(u8)` is opaque to the conductor
- `MIN_COUNTERSIGNING_AGENTS = 2`, `MAX_COUNTERSIGNING_AGENTS = 8`
- `SESSION_ACTION_TIME_OFFSET = 1000ms` — actions are timestamped 1 second after session start
- `SESSION_TIME_FUTURE_MAX = 6000ms` — max amount session start can be in the future from any agent's perspective

**Enzymatic mode:** `enzymatic: true` designates the first signing agent (index 0) as coordinator; they must appear first in both signing and optional lists.

**M-of-N optional signers:** `optional_signing_agents` + `minimum_optional_signing_agents` allow sessions where only M of N optional participants must respond.

**App interface (feature-gated):**
- `AppRequest::GetCountersigningSessionState(CellId)` → `Option<CountersigningSessionState>`
- `AppRequest::AbandonCountersigningSession(CellId)` — force-abandon an unresolved session
- `AppRequest::PublishCountersigningSession(CellId)` — force-publish; emits `SystemSignal::SuccessfulCountersigning`

---

## 29. SOURCE CHAIN MIGRATION (`close_chain` / `open_chain`)

When a hApp DNA is upgraded to a new DNA hash (not just a coordinator hot-swap), agents can formally migrate their source chain across the hash boundary.

**HDK functions:**
- `close_chain(new_target: Option<MigrationTarget>) -> ExternResult<ActionHash>` — must be the LAST action on the old chain. System validation rejects any further actions after this.
- `open_chain(prev_target: MigrationTarget, close_hash: ActionHash) -> ExternResult<ActionHash>` — records on the new chain that it continues from the old one. Holochain does not enforce calling this, but app validation can require it to verify imported data provenance.

**`MigrationTarget`** — identifies the DNA + agent the chain migrated to/from.

**`GetCompatibleCells` admin call** (feature-gated `unstable-migration`) — searches installed cells whose DNA manifest `lineage` field lists a given DNA hash; enables migration-aware installs without knowing the exact new DNA hash in advance.

**`UseExisting` provisioning strategy is deprecated since 0.6.0-dev.17.** Use `UpdateCoordinators` (admin hot-swap) or `call()` with `CallTargetCell` for cross-app calls instead.

---

## 30. DEFERRED MEMBRANE PROOFS

Membrane proofs can be omitted at install time and provided later before the app is enabled. Useful when the proof is obtained asynchronously (e.g. from a third-party credentialing service).

**happ.yaml:** `allow_deferred_memproofs: true` at top level of `AppManifestV0` (default `false`).

**Flow:**
1. `AdminRequest::InstallApp` with no membrane proofs → app sits in `AppStatus::AwaitingMemproofs`
2. Client calls `AppRequest::ProvideMemproofs(MemproofMap)` → `AppResponse::Ok`
3. Client calls `AppRequest::EnableApp` → app moves to `Running`

`AppRequest::EnableApp` ONLY works in the `Disabled(DisabledAppReason::NotStartedAfterProvidingMemproofs)` state. Any other enable attempt goes through `AdminRequest::EnableApp`.

---

## 31. APP STATUS MODEL

**`AppStatus`** (serialized as `{"type": "...", "value": ...}`):
- `Running` — cells active, zome calls accepted
- `Disabled(DisabledAppReason)` — zome calls rejected; not started on conductor reboot
- `AwaitingMemproofs` — installed with `allow_deferred_memproofs: true`; not yet enabled

**`DisabledAppReason`:**
- `User` — disabled by user via `AdminRequest::DisableApp`
- `Error(String)` — conductor disabled due to internal error
- `NotStartedAfterProvidingMemproofs` — memproofs provided but `AppRequest::EnableApp` not yet called

**`AppStatusFilter`** used in `AdminRequest::ListApps { status_filter: Option<AppStatusFilter> }` — filter by `Running`, `Disabled`, or `AwaitingMemproofs`.

**`AppInfo` structure:**
```rust
pub struct AppInfo {
    pub installed_app_id: InstalledAppId,
    pub cell_info: IndexMap<RoleName, Vec<CellInfo>>,  // ordered: provisioned, enabled clones, disabled clones
    pub status: AppStatus,
    pub agent_pub_key: AgentPubKey,
    pub manifest: AppManifest,      // original manifest with installed DNA hashes filled in
    pub installed_at: Timestamp,
}
```

**`CellInfo` variants:**
- `CellInfo::Provisioned(ProvisionedCell { cell_id, dna_modifiers, name })` — base cell
- `CellInfo::Cloned(ClonedCell { cell_id, clone_id, original_dna_hash, dna_modifiers, name, enabled })` — runtime clone; `enabled` distinguishes active vs. disabled
- `CellInfo::Stem(StemCell { ... })` — deferred cell not yet instantiated (not fully implemented)

---

## 32. APP WEBSOCKET AUTHENTICATION TOKEN (0.6.x)

Connecting a client to the app interface now requires a one-time token.

**Flow:**
1. Admin side: `AdminRequest::IssueAppAuthenticationToken(IssueAppAuthenticationTokenPayload)` → `AdminResponse::AppAuthenticationTokenIssued { token, expires_at }`
2. Client: first message on the app WebSocket must be `AppAuthenticationRequest { token }`
3. Token is consumed on use. Revoke unused tokens with `AdminRequest::RevokeAppAuthenticationToken(token)`.

---

## 33. ADMIN API — ADDITIONAL CALLS

Undocumented `AdminRequest` variants beyond what the Build Guide covers:

- **`UpdateCoordinators(UpdateCoordinatorsPayload)`** — hot-swap coordinator zomes for a live DNA without restarting. Replaces zomes with matching names, appends new ones. Key for zero-downtime coordinator upgrades (integrity zomes cannot be hot-swapped).
- **`RevokeZomeCallCapability { action_hash, cell_id }`** — revoke a previously-granted cap grant by its `ActionHash`
- **`StorageInfo`** → `AdminResponse::StorageInfo(StorageInfo)` — disk usage across all installed apps
- **`DumpNetworkMetrics { dna_hash, include_dht_summary }`** / **`DumpNetworkStats`** — Kitsune2 peer-level diagnostics
- **`DumpConductorState`** — full in-memory + SQLite state as JSON (introspection only)
- **`DeleteCloneCell(DeleteCloneCellPayload)`** — permanently delete a disabled clone cell (admin-level counterpart to `AppRequest::DisableCloneCell`)
- **`UninstallApp { installed_app_id, force: bool }`** — `force: true` overrides dependency guards
- **`ListCapabilityGrants { installed_app_id, include_revoked }`** → `AppCapGrantInfo` — inspect all cap grants

**`AppRequest::ListWasmHostFunctions`** — returns all host function names supported by this conductor version; useful for conditional feature detection.

---

## 34. `FlatOp` / `OpHelper` PATTERN FOR VALIDATION

The raw `Op` enum requires deep matching to access entry/link data. HDI provides a higher-level `FlatOp<ET, LT>` that pre-deserialises your app's entry and link types.

**Usage:**
```rust
pub fn validate(op: Op) -> ExternResult<ValidateCallbackResult> {
    match op.flattened::<EntryTypes, LinkTypes>()? {
        FlatOp::StoreEntry(OpEntry::CreateEntry { app_entry, .. }) => {
            match app_entry {
                EntryTypes::ValidationAttestation(att) => validate_attestation(&att),
                EntryTypes::HarmonyRecord(rec) => validate_harmony_record(&rec),
            }
        }
        FlatOp::RegisterCreateLink { link_type, base, target, tag, .. } => {
            match link_type {
                LinkTypes::StudyToValidation => validate_study_link(&base, &target),
            }
        }
        _ => Ok(ValidateCallbackResult::Valid),
    }
}
```

**`FlatOp<ET, LT>` variants:** `StoreRecord(OpRecord<ET,LT>)`, `StoreEntry(OpEntry<ET>)`, `RegisterAgentActivity(OpActivity<ET::Unit, LT>)`, `RegisterCreateLink`, `RegisterDeleteLink`, `RegisterUpdate`, `RegisterDelete`.

**`Op` helper methods** (available without matching): `op.author()`, `op.timestamp()`, `op.action_seq()`, `op.prev_action()`, `op.action_type()` — common metadata accessible directly.

**`OpHelper::flattened<ET, LT>(&self)`** — the method on `Op` that returns `Result<FlatOp<ET,LT>, WasmError>`.

---

## 35. `LinkQuery` — FULL FILTER SURFACE

`GetLinksInput` (the wire type underlying `get_links` in HDK 0.6.x) supports richer filters than `tag_prefix` alone:

```rust
pub struct GetLinksInput {
    pub base_address: AnyLinkableHash,
    pub link_type: LinkTypeFilter,
    pub get_options: GetOptions,          // Network vs Local
    pub tag_prefix: Option<LinkTag>,      // raw byte prefix filter
    pub after: Option<Timestamp>,         // only links created AFTER this time
    pub before: Option<Timestamp>,        // only links created BEFORE this time
    pub author: Option<AgentPubKey>,      // only links created BY this agent
}
```

The `after`/`before` and `author` filters are not mentioned in the Build Guide.

**`LinkTypeFilter` variants:**
- `Types(Vec<(ZomeIndex, Vec<LinkType>)>)` — specific types from named integrity zomes
- `Dependencies(Vec<ZomeIndex>)` — all types from a zome's dependency graph; useful when one integrity zome is shared across multiple coordinators

**Tag prefix note:** operates on raw bytes, not a string prefix. Cast your prefix to bytes explicitly: `LinkTag::from("year:2025".as_bytes())`.

---

## 36. `ChainFilter` / `LimitConditions` for `must_get_agent_activity`

`ChainFilter` controls how far back `must_get_agent_activity` walks the source chain:

```rust
pub struct ChainFilter {
    pub chain_top: ActionHash,
    pub limit_conditions: LimitConditions,
    pub include_cached_entries: bool,
}
```

**`LimitConditions` variants:**
- `ToGenesis` (default) — walk all the way back to genesis
- `Take(u32)` — return exactly N actions backwards from `chain_top` (error if 0)
- `UntilTimestamp(Timestamp)` — stop at first action older than timestamp (must reach an action older than threshold OR genesis for a deterministic success)
- `UntilHash(ActionHash)` — stop at a specific action hash; returns `UntilHashAfterChainHead` error if that hash is newer than `chain_top`

**`include_cached_entries: bool`** — when `true`, returns full entry content for entries with `cache_at_agent_activity: true` on their `EntryDef`, saving a separate DHT fetch per entry.

**`cache_at_agent_activity` on `EntryDef`** — opt-in per entry type to cache entries alongside `RegisterAgentActivity` ops at the agent activity authority. Reduces `must_get_agent_activity` hop count at the cost of more DHT storage in the agent's neighbourhood. Set in the integrity zome:
```rust
#[entry_type(cache_at_agent_activity = true)]
MyImportantEntry(MyImportantEntry),
```

---

## 37. ENTRY AND LINK SIZE LIMITS

Hard limits enforced by the conductor — serialised msgpack payload must fit within these:

- **`ENTRY_SIZE_LIMIT = 4_000_000` bytes (4 MB)** — entries larger than this are rejected. The 4 MB is on the *serialized* entry content, not the Rust struct size.
- **Link tag hard limit: 1 KB (1024 bytes)** — exceeding this causes a validation failure. The tag is serialized as-is; do not embed large blobs in link tags.

---

## 38. `GetStrategy` AND `GetOptions`

All DHT reads accept a strategy controlling whether a network fetch is attempted:

**`GetStrategy` enum:**
- `GetStrategy::Network` (default) — fetch latest metadata from network, fall back to local cache. If the calling agent IS the authority, no network call is made.
- `GetStrategy::Local` — return only locally cached data. No network call. Use in validation callbacks (where network access is restricted) and for known-local reads (e.g. data you just wrote in the same call).

**`GetOptions`** wraps `GetStrategy`. Accepted by `get_links`, `get_agent_activity`, `delete_link`.

`must_get_*` functions always use deterministic local/authority access — `GetStrategy` does not apply to them.

---

## 39. `ChainTopOrdering` AND `HeadMoved` ERRORS

By default every source chain write requires the chain to be at a known tip (`ChainTopOrdering::Strict`). If two concurrent zome calls attempt to write, one will fail with `HeadMoved`.

**`ChainTopOrdering::Relaxed`** — the write succeeds even if the chain head moved since the call started; the conductor rebases the new action onto the actual current tip.

Used in `CreateInput`, `CreateLinkInput`, `DeleteInput`, `DeleteLinkInput`. Pass it as:
```rust
create(CreateInput {
    entry_location: ...,
    entry_visibility: ...,
    chain_top_ordering: ChainTopOrdering::Relaxed,
})?;
```

**When to use:** fire-and-forget link creation, gossip-based writes, any scenario where exact chain position doesn't matter and `HeadMoved` retries from the client are undesirable.

---

## 40. `NetworkConfig` — CURRENT (Holochain 0.6.1 / iroh/QUIC era)

iroh/QUIC is the default transport in 0.6.1. The `advanced.tx5Transport` block is dead config and should be removed from conductor-config.yaml files. See §25 for the legacy tx5 config (historical reference only).

```yaml
network:
  bootstrap_url: https://...       # kitsune2 bootstrap server — peer discovery
  signal_url: wss://...            # SBD WebSocket server — kept for tx5 fallback; still used by kitsune2-bootstrap-srv 0.4.1
  relay_url: https://...           # iroh relay for QUIC NAT traversal (needed for production; optional for direct LAN/loopback)
  base64_auth_material_bootstrap: ... # URL-safe base64 auth token for bootstrap
  base64_auth_material_relay: ...     # URL-safe base64 auth token for relay
  target_arc_factor: 1.0           # 0.0 = leacher (no DHT gossip contribution)
  # webrtc_config / advanced.tx5Transport — REMOVE; dead under iroh default
```

**`ConductorConfig` new fields:**
- `db_max_readers: u16` — SQLite read connection pool size (default: max(cpu_count×2, 8))
- `incoming_request_concurrency_limit: u16` — max parallel authority responses (default: `db_max_readers - 3`)
- `tuning_params: ConductorTuningParams` — retry/timeout overrides including `sys_validation_retry_delay`, `countersigning_resolution_retry_delay`, `countersigning_resolution_retry_limit`

**Per-app network overrides** in `AppManifestV0`: `bootstrap_url` and `signal_url` can be specified per-app, overriding the conductor-level config for all cells of that app.

---

## 41. SIGNAL SUBSCRIPTION FILTERING

App WebSocket clients can filter which signals they receive per-cell:

**`SignalSubscription { installed_app_id, filters: SignalFilterSet }`** — sent from client to conductor.

**`SignalFilterSet` variants:**
- `SignalFilterSet::Include(HashMap<CellId, SignalFilter>)` — allowlist: only signals from listed cells pass through
- `SignalFilterSet::Exclude(HashMap<CellId, SignalFilter>)` — denylist: block listed cells (empty `Exclude` = allow all, which is the default)
- `SignalFilterSet::allow_all()` / `SignalFilterSet::block_all()` — convenience constructors

`SignalFilter` is currently a passthrough (no per-signal content filtering yet); reserved for future sub-signal filtering.

---

## 42. WARRANT TYPES (detail)

**`Warrant { proof: WarrantProof, author, timestamp, warrantee }`** — a signed attestation of wrongdoing authored by a network validator.

**`WarrantProof::ChainIntegrity(ChainIntegrityWarrant)`** — the only current variant. Two sub-variants:
- `ChainIntegrityWarrant::InvalidChainOp { action_author, action, chain_op_type }` — someone authored an invalid action
- `ChainIntegrityWarrant::ChainFork { chain_author, action_pair, seq }` — two actions with the same sequence number, proving a source-chain fork

**Conductor-level blocks** (not accessible from zomes, for reference): `BlockTarget` system flags a `CellId` or IP address. `CellBlockReason::InvalidOp(DhtOpHash)` or `CellBlockReason::BadCrypto`. This is internal to the conductor; app zomes can only observe warrants via `get_agent_activity`.

---

## 43. RATE LIMITING TYPES

Present in the types but conductor enforcement is still maturing:

- **`RateWeight { bucket_id: u8, units: u8 }`** — attached to non-entry actions (links, deletes)
- **`EntryRateWeight { bucket_id: u8, units: u8, rate_bytes: u8 }`** — attached to entry-creating actions
- `RateBucketId`, `RateUnits`, `RateBytes`, `RateBucketCapacity` — type aliases used in action structs and validation contexts

The rate limiting system is present in integrity types but the full validator logic and conductor enforcement details are still evolving. Treat as a known-incomplete area.

---

## HANDOVER NOTES FOR NEW CHAT

1. Read this file first — it is the complete knowledge base.
2. Read the session summary at top of transcript to understand project context.
3. Check journal.txt at /mnt/transcripts/journal.txt for full session history.
4. Files in /mnt/user-data/uploads contain source documents.
5. ValiChord scaffold latest version: valichord_scaffold_4.rs
6. Pending actions: send Arthur Brock email (drafted), contact Shin Sakamoto (Discord DM drafted), find Cardiff University PI for UKRI grant, follow up with Jamison Day (CTO candidate).
7. The entire Holochain Build Guide has now been read — no more pages to fetch.
