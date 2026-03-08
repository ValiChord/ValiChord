# ValiChord: Complete Holochain Build Guide Knowledge Base
## For handover to new chat sessions
## Compiled: 2026-02-28 — covers ALL pages of the Holochain Build Guide

---

## COVERAGE STATUS

All pages of the Holochain Build Guide have been read and synthesised. Previous sessions covered: validate-callback, getting-an-agents-status, cryptography-functions, cloning, identifiers, validation-overview, calling-zome-functions, dnas, genesis-self-check-callback, signals, capabilities. This session adds: zomes, callbacks-and-lifecycle-hooks, happs, working-with-data, entries, links-paths-and-anchors, querying-source-chains, validation-receipts, cell-introspection, miscellaneous-host-functions, must-get-host-functions, dht-operations, testing-with-tryorama, operating-a-happ.

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

**Another agent's chain (coordinator):** `get_agent_activity(agent_id, filter, ActivityRequest::Full)?`
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

`get_agent_activity(agent_id, filter, ActivityRequest::Full)` returns `AgentActivity` with:
- `status: ChainStatus` — Valid, Invalid(warrant), Forked(warrant), Empty
- `valid_activity: Vec<(u32, ActionHash)>` — sequence index + hash
- `warrants: Vec<Warrant>`

**Warrants** — created by validators when they detect invalid ops. Collected at agent's pubkey address. Application layer must use warrants to gate interactions with bad actors (the network doesn't block them automatically — on roadmap but not current behaviour).

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

**Network infrastructure required:**
- Kitsune2 bootstrap/signal server (peer discovery + connection establishment)
- WebRTC STUN servers (NAT traversal)
- All agents in a DNA must use SAME bootstrap/signal servers to find each other
- Configure in `kangaroo.config.ts`: `bootstrapUrl` (https://), `signalUrl` (wss://)

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

## HANDOVER NOTES FOR NEW CHAT

1. Read this file first — it is the complete knowledge base.
2. Read the session summary at top of transcript to understand project context.
3. Check journal.txt at /mnt/transcripts/journal.txt for full session history.
4. Files in /mnt/user-data/uploads contain source documents.
5. ValiChord scaffold latest version: valichord_scaffold_4.rs
6. Pending actions: send Arthur Brock email (drafted), contact Shin Sakamoto (Discord DM drafted), find Cardiff University PI for UKRI grant, follow up with Jamison Day (CTO candidate).
7. The entire Holochain Build Guide has now been read — no more pages to fetch.
