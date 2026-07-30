# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Always read at session start
- `PROJECT_STATUS.md` — current project phase, what's live, open work, **and installed tools/skills**
- `docs/Holochain_complete.md` — complete Holochain Build Guide knowledge base
- `docs/7_ValiChord_4-DNA_architecture_technical.md` — four-DNA architecture

## Installed Claude Code skills
- `~/.claude/skills/holochain-dev/` — official Holochain skill (installed 2026-04-24 from https://github.com/holochain/ai-tools). Activates on any Holochain task. Provides: DNA-hash tripwire, docs.rs API verification, serialization-boundary inversion, sweettest-only tests. Lazy-load topic files from `references/` inside the skill. See `PROJECT_STATUS.md` → "Installed tools and skills" for full tool inventory.

---

## Build and test commands

### PATH requirement (Codespaces)
```bash
export PATH="/home/codespace/.cargo/bin:$PATH"
```

### Holochain (valichord/)

```bash
# Kill stale conductors first — always
# (-x = exact process-name match. -f would match this very shell's own
#  command line and SIGTERM it — exit code 144, compound command dies.)
pkill -x holochain; pkill -x lair-keystore; sleep 2

# Build all WASM zomes (~5–10 min clean, ~1 min incremental)
cd valichord
cargo build --target wasm32-unknown-unknown --release

# Pack DNAs and hApp (always repack after any source change)
hc dna pack dnas/attestation            -o workdir/attestation.dna
hc dna pack dnas/researcher_repository  -o workdir/researcher_repository.dna
hc dna pack dnas/validator_workspace    -o workdir/validator_workspace.dna
hc dna pack dnas/governance             -o workdir/governance.dna
hc app pack .                           -o workdir/valichord.happ
```

**Never use `pack_dna.py`** — it is broken and embeds the same DNA bytes for all four roles.

### Tryorama integration tests (96 pass, 1 skipped)

```bash
cd valichord/tests && npm test

# Single test file
npx vitest run src/attestation.test.ts
```

All per-test timeouts are 900 000 ms — each `runScenario` JIT-compiles ~30 MB of WASM. Timeouts are slow conductor startup, not logic errors. `DepMissingFromDht` in logs is transient gossip lag, also not a root cause.

The one skipped test (`GoldReproducible badge — 7 validators`) exhausts WebSocket connections in Codespaces. It is covered by sweettest 15 instead.

### Sweettest (in-process conductors, separate workspace)

```bash
# From valichord/sweettest_integration/ — separate Cargo workspace, never add to valichord/Cargo.toml
cargo test --test attestation
cargo test --test governance
cargo test --test researcher_repository
cargo test --test validator_workspace
cargo test --test security

# Single test by name
cargo test --test governance silver_badge_issued_with_five_validators -- --test-threads=1
```

`sweettest_integration` is deliberately outside `valichord/Cargo.toml` because it depends on `holochain = "0.6.2"` (native binary), which cannot compile to `wasm32-unknown-unknown`. Merging it into the workspace would break the WASM build.

### valichord_attestation (Python)

```bash
cd valichord_attestation

# Install (first time)
pip install -e ".[dev]"

# Run all 259 tests with coverage
pytest --cov

# Single test file
pytest tests/test_merkle.py
```

For `InspectAILogAdapter` tests: `pip install -e ".[inspect-ai]"` first.

### Svelte UI (valichord-ui/)

```bash
# Terminal 1 — conductor (wait for "Token + signing credentials written to…")
cd valichord-ui && npm install && bash dev.sh

# Terminal 2 — UI server (--host required in Codespace)
cd valichord-ui && npm run dev -- --host
# Opens at http://localhost:5173

# Type-check only
npm run check

# E2E (Playwright + real conductor on :4445/:8889 — no clash with dev.sh; needs packed happ)
npm run test:e2e
```

`dev.sh` starts a fresh conductor (admin `:4444`), installs the hApp with dev-mode bypass (no real credential check), attaches app interface on `:8888`, and writes `VITE_HC_TOKEN` + `VITE_HC_SIGNING_CREDENTIALS` to `.env.local`. Conductor state lives in `/tmp/valichord-dev-data` — wiped on each `dev.sh` run.

### Decentralised demo

```bash
export ANTHROPIC_API_KEY=sk-ant-...
docker compose -f demo/docker-compose.yml up --build -d
until [ "$(docker compose -f demo/docker-compose.yml logs 2>/dev/null | grep -c 'node API →')" -ge 4 ]; do sleep 3; done && echo "Ready"
python3 demo/ai_validator.py --mode decentralised
```

Use `docker compose -f demo/docker-compose.yml down -v` between runs to clear conductor state.

### Wind-Tunnel load tests

```bash
# Pack valichord.happ first (see above), then:
cd valichord/wind-tunnel
cargo run -p validation_request_throughput -- --agents 4 --duration 60
cargo run -p phase_observation_latency    -- --agents 2 --duration 60
cargo run -p concurrent_reveal_throughput -- --agents 4 --duration 90
```

`valichord/wind-tunnel/` is also a separate Cargo workspace (same reason as sweettest: native conductor deps).

---

## Architecture

### Primary project

**`valichord/` is the main project.** Everything else in this repo is either tooling that supports it or a future integration point.

### Hard separation — valichord/ vs valichord_attestation

`valichord_attestation` is a standalone Python library for generating cryptographic attestation bundles from AI evaluation runs (inspect_ai logs, lm-eval outputs, etc.). It is **not** an equivalent or alternative to ValiChord proper — it is currently independent, and is intended to become the *client-side on-ramp* once wired to ValiChord proper's DHT: a researcher generates a bundle, submits it to the Holochain protocol, and the commit-reveal verification applies to AI benchmark results.

Rules:
- When describing ValiChord's architecture → talk about the 4 DNAs, commit-reveal, Holochain. Do NOT describe attestation bundle formats.
- When asked what ValiChord does → answer from `valichord/`. `valichord_attestation` is a future plug-in, not the product.
- `valichord_attestation` can be discussed on its own terms, but never as a replacement or stand-in for the protocol.

| Component | Path | What it is |
|---|---|---|
| **ValiChord protocol** | `valichord/` | **The main project.** Holochain commit-reveal — 4 DNAs, blind attestation, HarmonyRecord on DHT |
| **valichord_attestation** | `valichord_attestation/` | Python library — future client on-ramp to the protocol; currently standalone |
| **valichord-ui** | `valichord-ui/` | Svelte 5 browser UI for the three protocol roles (Researcher, Validator, Governance) |

`backend/app_protocol.py` is an integration layer — not a definition of either project.

### Four-DNA architecture (valichord/)

| DNA | Membrane | Purpose |
|---|---|---|
| `attestation` | Public DHT + Ed25519 credential | Shared protocol state: requests, commitments, profiles, phase markers |
| `researcher_repository` | Private, single-agent | GDPR-protected data; never enters DHT |
| `validator_workspace` | Private, single-agent | Private attestations before reveal; commit-reveal state |
| `governance` | Public DHT, open join | HarmonyRecords, badges, reputation, governance decisions |

Cross-DNA calls use `CallTargetCell::OtherRole("role_name")` with the author grant (same-agent only). Helper: `call_attestation_zome_opt<I, O>` in governance coordinator — returns `Ok(None)` on any cross-DNA failure rather than propagating.

The `sweettest_integration/` and `wind-tunnel/` directories are each their own Cargo workspaces isolated from `valichord/Cargo.toml`.

### valichord_attestation modules

| Module | Purpose |
|---|---|
| `builder.py` | `build_bundle(...)` — assembles a `Bundle` from typed fields |
| `canonical.py` | JCS (RFC 8785) encoding + `hash_bundle()` + `content_hash()` |
| `merkle.py` | `merkle_root`, `merkle_proof`, `verify_faithfulness` |
| `challenge.py` | Probabilistic challenge generation (HMAC-SHA256 seed, SHA-256 counter-mode PRNG) |
| `response.py` | `build_response`, `verify_response` — Merkle-path selective disclosure |
| `adapters/` | `AdapterBase` ABC; `InspectAILogAdapter` (reads `.eval` files); `InspectEvalsAdapter` |

Format version: v1.2. Bundles have a `bundle_hash` (full content) and `content_hash` (excludes `Bundle.meta` provenance block). v1/v1.1 bundles remain valid.

### Svelte UI architecture (valichord-ui/)

`holochain.ts` — AppWebsocket singleton; reads auth token + signing credentials from `.env.local` (written by `dev-setup.mjs`); sets `SigningCredentials` before connecting (required by `@holochain/client 0.20.x`).

`types.ts` — TypeScript mirrors of all Rust types; `entryFromRecord` msgpack-decodes the raw entry bytes (client 0.20.x does not auto-decode entries — must call `decode()` from `@msgpack/msgpack`).

`App.svelte` → role-based tab nav → `ResearcherView`, `ValidatorView`, `GovernanceView`. Signal subscription is set up in `App.svelte` and cleaned up in `onDestroy` (one handler per mount, no stacking).

The Vite `vite.config.ts` proxies `/hc-ws` → `ws://localhost:8888` — the browser never opens a plain `ws://` connection directly, which matters in Codespace/Docker environments.

---

## What Holochain is — read before writing anything about ValiChord

**Holochain is NOT a blockchain.** Never use the words blockchain, distributed ledger, on-chain, or any crypto-currency framing. The user is actively de-cryptoing this project.

Holochain is **agent-centric distributed computing**: every agent maintains their own **source chain** (personal append-only log, cryptographically signed); shared state lives in a **DHT** (peer-to-peer, each node validates what it holds). No global ledger, no miners, no tokens, no consensus across all nodes. Scales with users rather than bottlenecked by global consensus.

**ValiChord's core meaning — do not corrupt:**
- ValiChord asks: *can an independent party arrive at the same result as the researcher?*
- "Reproduced" = the validator got the **same result as the researcher** — NOT that the result is correct
- The commit-reveal protocol means no party can change their claim after seeing others'

---

## Serde encoding rules — critical for JS/TS integration

### Adjacent tag `#[serde(tag = "type", content = "content")]`
Used by: `Discipline`, `AttestationOutcome`, `DeviationType`

```
// Unit variant — content key ABSENT
{ type: "ComputationalBiology" }
{ type: "Reproduced" }

// Struct variant — content key present
{ type: "PartiallyReproduced", content: { details: "..." } }
```

### External tag (default — no attribute)
Used by: `ValidationTier`, `AttestationConfidence`, `ValidationPhase`, `AgreementLevel`, `CertificationTier`

```
// Unit variants → plain strings
"Basic"  "High"  "RevealOpen"  "ExactMatch"  "Provisional"
```

### Other rules
- `Option<T>`: `Some(x)` → unwrapped `x`; `None` → nil
- `ExternalHash` in JS: use `hashFrom32AndType(core32, HoloHashType.External)` — never `new Uint8Array(39).fill(byte)` (DHT location bytes must be a valid blake2b checksum)
- DNA properties with HoloHash fields: use `String`, not `AgentPubKey` — conductor passes YAML as msgpack strings

---

## Hard constraints

- Never use `pack_dna.py` — broken (embeds same DNA bytes for all four roles)
- Always use `hc dna pack` + `hc app pack`
- Before any test run: `pkill -x holochain; pkill -x lair-keystore; sleep 2` (never `-f` — it matches the invoking shell itself)
- Private entries in single-agent DNAs: use `query()` not `get()` — `get()` in a test conductor can leak across cell boundaries
- **Read-strategy rule (coordinators):** lookups whose results are entirely self-authored (my links, my entries) use `GetStrategy::Local` / `GetOptions::local()` — the source chain is complete by construction, and a Network walk on a fresh/cold cell can hang past the read budget without finding anything new. Anything that can include *other agents'* writes (quorum counts, phase markers, releases by reclaimers, protocol guards) stays `Network`. When one function mixes both, comment each read. (Pattern source: flowsta-signing-dna v1.4 "self-authored lookups read locally".)

## Coordinator-only upgrade (zero DNA hash change)

```
AdminRequest::UpdateCoordinators { dna_hash, coordinator_bundle }
```

Pack only the coordinator: `hc dna pack --coordinator-only` (no integrity bytes). All running cells switch immediately; DNA hash stays identical.

Use for: bug fixes, new read functions, `schedule()` additions, warrant-gate changes.  
**Do NOT use** for: integrity zome changes, new entry/link types, `cache_at_agent_activity` toggles.

---

## Pending upgrade checks (run at every session start)

### Holochain version
Run `holochain --version`. Current stable in use: 0.6.2. (0.6.3 shipped 2026-07-15 — trivial `reqwest`/native-tls build-feature patch in `holochain_metrics`, nothing for us; no reason to bump.)

**⚠️ 0.7.0 IS NOW IN RELEASE-CANDIDATE (RC iterating; rechecked 2026-07-30):** `0.7.0-rc.0` tagged 2026-07-15, `0.7.0-rc.1` 2026-07-16, then rc.2, rc.3, rc.4, and **`0.7.0-rc.5` (2026-07-29 — latest release as of 2026-07-30)**. This is the "watch for rc.0" trigger firing. Still NO plain `holochain-0.7.0` stable tag. **ETA: still early-to-mid August 2026, but the churn read behind it has softened** — of the three signals recorded on 2026-07-27 as arguing against an imminent stable tag, one was a misread and two have since weakened:

- ❌ **CORRECTED — "two `!` breaking changes landed *after* rc.4 (#5898, #5906)" is WRONG. Both are IN rc.4** (verified 2026-07-30 by comparing each merge commit against the rc.4 tag: `behind_by = 0` for both; their 07-23/07-24 merge dates precede rc.4's 07-27 tag). They remain real *migration* items — see the bullets below — but they are not evidence of post-rc churn.
- ⚠️ **weakened — the HDI validate-callback surface has settled.** rc.5 absorbed **#5910**, the follow-up that had been sitting on `develop`. The surface is now inside a release rather than moving under us, for the first time in three weeks. rc.4→rc.5 introduced **no new `!` breaking commits** (9 commits / 80 files).
- ⚠️ **weakened but still the main brake — the marquee feature now has a PR, and it is a draft with conflicts.** `feat/5800-source-chain-restore-workflow` is now **PR #5920** *"Add source chain restore workflow"* (opened 2026-07-29, +2516/−33 across 15 files, branch 20 ahead / 4 behind, last commit 2026-07-30). But `draft = true`, `mergeable = CONFLICTING`, review required. Closer than "no open PR", nowhere near days-away.

Treat this as a read of the churn rate, not a published schedule. Crate lines: `hdk 0.7.0-rc.x`, `hdi 0.8.0-rc.x`, `@holochain/client 0.21.x` (see below). **Note crates.io still shows `hdk 0.7.0-rc.4` / `hdi 0.8.0-rc.4` as newest — rc.5's crate line is not published there yet**, so an rc.5 trial migration could not even resolve deps today. Kitsune2 line confirmed from `Cargo.lock`: **rc.5 pins `kitsune2_* 0.5.0` (stable — bumped from rc.4's `0.5.0-dev.6` by PR #5913); our 0.6.2 pins `0.4.1`** — so anything landing on kitsune2's 0.5 line reaches us only at the 0.7 migration. (Oddity, low significance: rc.5's lock leaves `kitsune2_dht` at `0.5.0-dev.6` while every sibling crate moved to `0.5.0` — looks like release sequencing.) Still HOLD on 0.6.2 until *stable*; then a deliberate planned migration, never auto.

**If 0.7.0 stable is available:** do NOT auto-upgrade. Report to user with these breaking changes (⬤ = CONFIRMED landed in 0.7.0-rc.0, verified from the crate CHANGELOGs 2026-07-19):
- `hdk → 0.7.x`, `hdi → 0.8.x` (Cargo.toml across all zomes)
- Wasmer flags renamed: `wasmer_sys → wasmer-sys-cranelift`, `wasmer_wamr → wasmer-wasmi`
- Conductor DB migrated to `holochain_data` — no migration path, must clear state; Oracle demo nodes need `docker compose down -v` before upgrading, not just a binary swap
- `must_get_agent_activity` response types changed — new variants: `UntilTimestampIndeterminate`, `UntilTimestampGreaterThanChainHead`, `IncompleteChain`; `ChainFilter` now constructed via `take(n)` / `until_hash(h)` / `until_timestamp(t)` constructors, not builder chaining
- `HCP2P_PROTO_VER` bumped 2→3 (wire-incompatible with 0.6.x nodes)
- `get_links_details` renamed from `get_link_details`
- ⬤ **v2 Action model is now canonical (rc.0)** — the legacy per-variant action structs (`Create`, `Update`, `Delete`, `Dna`, `CreateLink`, `DeleteLink`, `OpenChain`, `CloseChain`, `AgentValidationPkg`, `InitZomesComplete`), the `ActionBuilder`/`ActionBuilderCommon`, and the `EntryCreationAction`/`NewEntryAction`/`NewEntryActionRef` wrapper enums are all **removed** (PR #5860). This is the FlatOp-v2 migration below, now landed. Audit any code that names those types.
- **`validate()` migration to `FlatOp v2` — BIGGER THAN "v1→v2", AND STILL MOVING (verified on `develop` 2026-07-27).** `flat_op_v2` module added to HDI; v2 `FlatOp` is built over new `dht_v2::Action`/`Op` types with validating constructors. All four ValiChord integrity zomes use `op.flattened::<EntryTypes, LinkTypes>()`, so all four are affected. **The FlatOp variants have since been reshaped twice, both after rc.0:**
  - **PR #5903** (merged 2026-07-21, 14 files, +1084/−670) — *"give validate-callback FlatOp types precise per-variant action data"*. Adds `TypedAction<D>`, pairing an action's header with the exact payload its FlatOp variant already implies instead of a generic `Action`. **Fields that duplicated `action.data` became accessor methods** — `original_action_hash`, `original_entry_hash`, link `base_address`/`target_address`/`tag`, and the agent-key fields. `EntryCreationData` / `TypedAction<EntryCreationData>` restores the Create-or-Update narrowing that the removed `EntryCreationAction` used to provide.
  - **PR #5910** (merged 2026-07-27, **shipped in rc.5**, +550/−121) — follow-up adding conversions *"found missing while porting a real app (dino-adventure) to 0.7.0-rc.3"*: `IntoEntryCreationData`, `Deref`, single-variant `TryFrom<Action>` narrowing with `try_from_action` siblings. **Partly reverts #5903**, restoring the `agent`/`new_key`/`original_key` fields on `CreateAgent`/`UpdateAgent`. Adds a doc note that narrowing failures should propagate as errors, not `ValidateCallbackResult::Invalid`.
  - **What this means for us:** our destructuring arms (e.g. `OpUpdate::Entry { app_entry, .. }`, anything reading a link's base/target/tag out of a variant) are exactly what moved to accessors. **Do not start this migration before the stable tag** — a real-app port was still shaking out missing conversions on rc.3, and the first refactor was partly walked back six days later. That said, **both refactors are now inside rc.5**, so the surface has stopped moving. Re-read the HDI CHANGELOG at migration time rather than trusting this bullet.
- **`refactor!: re-layer conductor state types out of the holochain crate` (PR #5898, 2026-07-23, in rc.4)** — matters because `sweettest_integration` depends on the `holochain` crate directly. Expect import churn there at migration.
- **`feat(api)!: add paginated state dumps` (PR #5906, 2026-07-24, in rc.4)** — breaking admin-API change. Only matters if we read state dumps.
- **`feat(admin_api): expose DHT op timings via DumpOpTimings` (PR #5917, in rc.5)** — additive admin-API call, not breaking. No impact for us (we don't read op timings); noted so the rc.5 delta is complete.
- ⬤ **`rate_limit` module REMOVED (rc.0)** — `RateWeight`/`EntryRateWeight` and the action-weight machinery are gone (PR #5860). No code impact (we don't use them) but Holochain knowledge-base §43 is now stale for 0.7.
- ⬤ **`holochain_sqlite` crate REMOVED (rc.0)** — persistence moved to `holochain_data`; databases renamed; legacy DBs unused (reinforces the must-clear-state / `down -v` note above). New `encryption` feature replaces the old `sqlite-encrypted` (which now has no effect).
- ⬤ **`transport-iroh` feature flag REMOVED (rc.0)** — iroh/QUIC is the sole transport, compiled in unconditionally. Downstream crates that built `default-features = false` + explicitly listed `transport-iroh` must drop it. No impact for us (we don't gate on it).
- ⬤ **`DnaStorageInfo` (StorageInfo admin call) fields changed (rc.0)** — drops `authored_data_size`/`_on_disk` and `cache_data_size`/`_on_disk`; source-chain data now counts under `dht_data_size`/`_on_disk` (PR #5844). Only matters if we read storage metrics.
- **`@holochain/client` bumps to the `0.21.x` line** (`0.21.0-rc.1` on npm dist-tag `next`; `0.20.8` is current stable on our line). ⚠️ **A previous version of this file said "0.9.x" — that was wrong and conflated two packages:** `0.9.0-rc.4` is the **Rust `holochain_client` crate**, not the JS one. Verified on npm + crates.io 2026-07-27. Three pins to update: `valichord-ui/package.json` (`^0.20.5`), `valichord/tests/package.json` (`^0.20.4`), `demo/package.json` (`0.20.2`).
- **New `AppStatus` variants from source-chain restore** — `AppStatus::AwaitingRestore` (restore in progress) and `AppStatus::Unrecoverable(cell_id, reason)` (terminal — chain forked or warrant validated). `dev-setup.mjs` and Svelte UI currently assume only `Running`/`Disabled`; both need updating. New `SystemSignal` variants: `RestoreComplete { cell_id }`, `AppRestoreComplete { installed_app_id }`, `RestoreFailed { cell_id, reason }`. New conductor config field: `restore_chain_quorum: u8` (default 2). (Source: `holochain/holochain` branch `cascade-read-and-cutover`, `docs/design/source_chain_restore.md`)
- **Source-chain restore does NOT recover private entries** — `ValidatorPrivateAttestation` (DNA 2) and `LockedResult` (DNA 1) are private and absent after a restore. Validators who lose their machine mid-round lose their uncommitted private attestations silently.
- `ChainIntegrityWarrant::InvalidChainOp` gains a `reason: String` field (excluded from `PartialEq`/`Hash` — deduplication unaffected). Check any match arm that destructures this variant in `reject_if_warranted`.
- CI: update `BASE=` URL and `key: hc-bin-0.6.2` in **both** jobs in `.github/workflows/tests.yml` (4 edits total)

#### Official upgrade guide — read it first, and this ValiChord audit alongside it

**Source: `holochain/docs-pages` branch `docs/upgrade-guide-holochain-0.7`, file `src/pages/resources/upgrade/upgrade-holochain-0.7.md`** (700 lines, written 2026-07-27, no PR yet). It is written against **rc.4** and states plainly that *"further breaking changes are still possible"* — another reason the migration waits for stable. **Caveat added 2026-07-30: the guide therefore predates rc.5, and so predates #5910's HDI `TypedAction` changes** — treat its validate-callback sections as one release behind and reconcile against the HDI CHANGELOG at migration time. It names `holochain/dino-adventure`'s integrity zome as the reference port to adapt our `validate` dispatcher from, and notes **no 0.7 scaffolding release exists yet**.

**1. `FlatOp` variants are RENAMED — and we have 51 match arms.** Counted across the four integrity zomes 2026-07-27:

| 0.6 | 0.7 | Our arms |
|---|---|---|
| `FlatOp::RegisterUpdate` | `FlatOp::Update` | **26** |
| `FlatOp::StoreEntry` | `FlatOp::CreateEntry` | **12** |
| `FlatOp::RegisterDeleteLink` | `FlatOp::Link(OpLink::DeleteLink { link_type, action, original_action })` | **8** |
| `FlatOp::RegisterDelete` | `FlatOp::Delete(OpDelete { action })` | **4** |
| `FlatOp::RegisterAgentActivity` | `FlatOp::AgentActivity` | **1** |
| `FlatOp::StoreRecord` | `FlatOp::CreateRecord` | 0 |

The 8 `RegisterDeleteLink` arms are not a rename — **both link variants fold into a single `FlatOp::Link`** wrapping an `OpLink`. That one is structural.

**2. ⚠️ IMMUTABILITY-GUARD ORDERING IS THE REAL HAZARD — ValiChord-specific.** Those 26 `RegisterUpdate` arms *are* our immutability guards (`ValidationAttestation`, `CommitmentAnchor`, `PhaseMarker`, `StudyClaim`, `ValidatorPrivateAttestation`, `LockedResult`). Per `docs/7_ValiChord_4-DNA_architecture_technical.md`, **Rust match ordering IS the enforcement mechanism** — guarded arms must precede the generic update arm. A mechanical rename-and-reflow that reorders them **silently disables immutability: no compile error, and no test failure unless a test explicitly attempts a forbidden update.** Treat "preserve arm ordering, then prove it with a forbidden-update test per guarded type" as its own migration step, not part of the rename.

**3. Membrane proof — the guide has our exact arm.** `attestation_integrity/src/lib.rs:957` matches `AgentValidationPkg` inside the agent-activity arm (our `validate_agent_joining` credential path). `OpActivity::CreateAgent` loses its `agent` field → use the `create.agent()` accessor + `action.prev_action()` + match `ActionData::AgentValidationPkgData`. The guide gives the full before/after diff for this.

**4. Conductor configs FAIL TO START, they are not ignored.** `NetworkConfig` now rejects unknown fields. Live hits to fix at migration:
- `demo/conductor-config-node.yaml:19` (`signal_url`), `:21` (`db_sync_strategy: Fast`)
- `valichord-ui/dev-conductor.yaml:17` (`signal_url`), `:19` (`db_sync_strategy: Resilient`)
- `demo/rehearse-autoupdate.sh:56` (`signal_url`)

Field changes: `signal_url` + `webrtc_config` removed; `request_timeout_s` moves from top level **into `network`**; `db_sync_strategy` → **`db_sync_level`** with values `Fast`→`Off`, `Resilient`→`Normal`; `chc_url` removed; new optional `wasm_backend` (`"cranelift"`/`"LLVM"`/`"wasmi"`) and `restore_chain_quorum`. **A local iroh relay additionally needs `advanced: { irohTransport: { relayAllowPlainText: true } }`** — relevant to the wind-tunnel/relay work. (Guide's example shows `restore_chain_quorum: 3`; the default is recorded above as 2 — confirm which at migration.)

**5. `AgentActivity` → `AgentActivityStatus`** (renamed to resolve the collision with the `AgentActivity` op variant). Three call sites: `governance_coordinator/src/lib.rs:188,322`, `attestation_coordinator/src/lib.rs:637`. The 4th `GetOptions` arg we already pass.

**6. JS side.** `SignedActionHashed` is no longer generic and the per-variant types (`Create`, `Update`, `Delete`, `CreateLink`, `DeleteLink`) are no longer exported; common action fields move under `.header`. **`valichord-ui/src/lib/types.ts:331`** does `record.signed_action.hashed.content.author` → needs `.header.author`. Also `signalingServerUrl` → `relayServerUrl`; `dumpNetworkStats` returns `ApiTransportStats` (nested under `transport_stats`, `is_webrtc` → `is_direct`).

**7. Sweettest dep line** for `sweettest_integration`: `holochain = { version = "0.7.0-rc.x", default-features = false, features = ["encryption", "wasmer-sys-cranelift"] }` — `sqlite-encrypted`→`encryption`, `wasmer_sys`→`wasmer-sys-cranelift`, drop `transport-iroh`. The guide also carries a table of removed implicit Cargo features (`holo_hash` `serde`→`serialization`, `hdi` `tracing`→`trace`, `holochain_zome_types` `serde_yaml`→`properties`, …) — check our zome + `shared_types` manifests against it.

**8. Toolchain:** `hc-spin` → `0.700.0-rc.1`; holonix `main-0.7` **does not exist yet** (use `ref=main`); nodejs 22 → 24; Sweettest builds may need `perl` on `PATH`.

**9. Confirmed NOT applicable to us** (checked): no `Record::new` calls (now takes `RecordEntry`), no `block_agent`/`unblock_agent` (removed), no link `base_address`/`target_address`/`tag` destructuring in the integrity zomes.

**10. Every published HarmonyRecord URL dies at migration.** Zome-definition serialization changed, so an otherwise-identical DNA has a different `DnaHash`, and 0.7 agents form a network separate from 0.6. This is the same fact as "clear state / `down -v`", but stated in the form that matters for the Oracle demo's public links.

Ignore `0.7.0-dev.*` and `0.6.x-rc.*` tags. **`0.7.0-rc.*` is NOT ignored** — rc.0 was the watch signal and it has now fired (see the ⚠️ note above). Next tell: the plain `holochain-0.7.0` stable tag — report to user the moment it appears.

**Blocker-remover — ✅ LANDED on kitsune2 `main` 2026-07-27 and ✅ NOW PUBLISHED in kitsune2 `v0.5.0` (2026-07-28), which holochain `0.7.0-rc.5` pins.** What was tracked as branch `fix/491-stabilize-the-iroh-relay-hosted-in-bootstrap_srv` merged as **`3746be1` *"feat: stabilize authenticated iroh relay hosted in the bootstrap server"*** (refs #492; 16 files, ~+1160/−490). Relay access is gated by a bearer token on the relay WebSocket upgrade (`RelayConfig::with_auth_token`), validated in `AccessControl::on_connect`; bootstrap client gains `blocking_fetch_relay_token`; a client-side registration heartbeat (`relayReRegistrationIntervalS`, default 120 s) + token-rotating watchdog work around iroh 1.0.0 capturing the relay token once per connection actor; legacy `PUT /relay/register` allowlist retained for 0.4.x clients. Covered by unit, server-side auth-flow, and an end-to-end bootstrap-restart recovery test. **This removes the "need a separate Iroh relay" blocker for both the deferred wind-tunnel kitsune live run and kangaroo desktop packaging — as a 0.7-migration item, not something available on 0.6.2.** The re-check condition recorded here on 2026-07-27 ("does the picked-up kitsune2 actually carry `3746be1`?") **is now answered: YES.** Verified 2026-07-30: `v0.5.0` is 7 ahead / 0 behind `3746be1`, and the commit appears in the `v0.5.0-dev.6...v0.5.0` list (24 commits) along with two relay follow-ups on top of it — **`03d21103`** *"negotiate relay protocol version, enabling V2"* and **`768b01b1`** *"add TLS security headers to relay HTTP responses"*. holochain `0.7.0-rc.5` pins `kitsune2_* 0.5.0` (PR #5913). Our 0.6.2 stays on `0.4.1`, so **none of this is reachable until we migrate** — plan the relay work as part of the 0.7 migration, not before. **Note the holochain side's own backport branch has NOT consumed it:** `holochain/holochain`'s own `fix/491-…` branch is stale — last commit 2026-04-22, 114 behind `develop`, 1 commit ahead containing only `build: kitsune #491`.

**`holochain/holochain` branch watch — re-verified 2026-07-30 against `develop` (default branch is `develop`, not `main`).** Only two things are live; everything else previously listed here is stale or has merged:
- **LIVE — now a PR** `feat/5800-source-chain-restore-workflow` → **PR #5920** *"Add source chain restore workflow"* (opened 2026-07-29; the "no open PR" note recorded 2026-07-27 is superseded). Branch **20 ahead / 4 behind**, last commit 2026-07-30, **+2516/−33 across 15 files**. But `draft = true`, `mergeable = CONFLICTING`, review required — so this is the main brake on the stable tag, not a sign it's imminent. Recent commits include *"add unit test for ignoring forgery during a restore"*. Still does NOT recover private entries → `ValidatorPrivateAttestation`/`LockedResult` lost on restore (see architecture doc, Phase 0 limitation 4).
- **MERGED, no longer a watch item** `private-entry-sync-tests` → **PR #5912 merged and shipped in rc.5**. Test-only (2 files), so nothing to act on, and the new coverage surfaced no defect that reached the release notes. Private-entry gossip semantics are what DNA 1 and DNA 2 rest on, so this is a mild positive signal rather than nothing.
- **LIVE** `develop` itself.
- ⚠️ **`feat/generate-ts-types-ts-rs` is DEAD, not active** — last commit 2025-12-11, message `wip`, **257 behind**. The hand-maintained `valichord-ui/types.ts` mirror has no replacement coming; don't wait for one.
- **STALE** (all verified, none worth watching): `feat/per-space-bootstrap-override` (2026-03-17, 144 behind), `feat/space-network-override-conductor-config` (2026-05-11, 92 behind), `use-k2-with-iroh-0.97` (2026-04-01, 292 behind), `feat/network-readiness-events` (2026-03-18, 140 behind), `direct-signals-cap` (2026-06-25), `reduce-wasm-bloat` (2026-07-06), `fix/bound-sys-validation-dep-fetch` (2026-04-14), `feat/restore-validation-receipts-behavior-for-published-ops` (2026-06-25), `docs/coordinator-upgrades` (2026-07-14).

### CI binary upgrade (any Holochain version bump)
Update 6 places in `.github/workflows/tests.yml` (3 jobs × BASE + cache key):
1. `BASE=…/releases/download/holochain-X.Y.Z` — `test` job
2. `key: ${{ runner.os }}-hc-bin-X.Y.Z` — `test` job
3. Same `BASE=` — `sweettest` job
4. Same `key:` — `sweettest` job
5. Same `BASE=` — `ui-e2e` job
6. Same `key:` — `ui-e2e` job

Verify binary names (`holochain-x86_64-unknown-linux-gnu`, etc.) exist on the release before pushing.

---

## Ecosystem tool notes

- **Unyt joining-service** — REST membrane-proof onboarding; reference impl for institutional validator onboarding on a live network. See `memory/reference_unyt_tools.md`.
- **Unyt heart** — Go/Pulumi **fleet** deployer (one stack per release; `progenitor` + `notary` node types). Use when setting up production nodes. Note `cloudinit/cloud-config.yaml` hardcodes **`target_arc_factor: 1`** (every node full-arc) — the concrete "kitsune2 #160 in production" artifact.
- **Unyt migration-service** — working `close_chain`/`open_chain` DNA-migration pipeline. **Read in full 2026-07-27 → `docs/DNA_MIGRATION_PRIOR_ART.md`, which is the answer to "can we carry data across the 0.7 DNA-hash change?"** Verdict: **no — accept the reset and republish.** It carries an agent's own source chain, not the DHT, so it saves no published HarmonyRecord URL; it cannot touch DNA 1/DNA 2 (single-agent, no notaries); and we have no carried state to summarise. **CAL-1.0 — design source, don't copy code.** Read it for `policy.rs` (the algorithm `select_validators()` needs) and the `[MIGERR:<CODE>]` typed-error pattern.
- **Unyt tauri-plugin-holochain** — lighter Electron alternative (not yet open-source); revisit before building the validator desktop app.
- **kangaroo-electron** (`holochain/kangaroo-electron`, branch `main-0.6`) — cross-platform Electron packaging. Full plan: `docs/KANGAROO_PACKAGING_PLAN.md`. Remaining blockers: dedicated bootstrap/relay servers.
