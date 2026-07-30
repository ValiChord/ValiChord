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

### Immutability tripwire tests (REQUIRED before/after any `validate()` refactor)

The only tests that prove the **integrity zomes** reject forbidden updates. They need a special build, because no production coordinator exposes `update_entry`.

```bash
cd valichord
./build-test-dnas.sh                       # builds --features test_utils -> target-test/, packs -> workdir-test/
cd sweettest_integration
VALICHORD_DNA_DIR=../workdir-test cargo test --test immutability_tripwire -- --test-threads=1
# 5 tests, ~14 min (each scenario JIT-compiles ~30 MB WASM)
```

**Run these before AND after the 0.7 `FlatOp` migration.** They are the only thing standing between a mechanical arm-reflow and silently losing immutability.

**Proven to work — negative control, 2026-07-30.** Moving the `ValidationAttestation` guard behind the generic `OpUpdate::Entry { action, .. }` arm (exactly the accident a `FlatOp` rename can cause) made the forbidden update **succeed** — it returned a real `ActionHash`, because it fell through to the generic arm whose author-check passes for the entry's own author. The tripwire test failed as designed; restoring the guard turned it green. **The hazard is real and the wire is connected.**

⚠️ **Partial compiler safety net, do not rely on it.** `rustc` *does* emit `warning: unreachable pattern` when a specific arm is moved behind a broader one. But it is a **warning, not an error**, in a build that emits others — and it catches **only** the shadowing case. It will NOT catch an arm that is deleted outright, or one whose pattern stops matching after a variant rename. The tests catch all three.

**Safety design** (these hooks must never ship):
- `#[cfg(feature = "test_utils")]` externs in 3 coordinators — absent from every production build
- feature build → `target-test/` (separate target dir, cannot overwrite `target/`)
- packs → `workdir-test/` (never the committed `workdir/`)
- `test-dnas/*/dna.yaml` point their **integrity** zome at the *production* build and only the **coordinator** at `target-test/` — so the integrity zome under test is byte-identical to what ships
- `./check-no-test-hooks.sh` greps the committed production bundles for `test_force_update` and fails if found — **run it in CI**
- `target-test/` + `workdir-test/` are gitignored

**Assertion discipline — never weaken this.** Every test asserts on the *specific rejection message the guard emits* (`"ValidationAttestation is immutable"`, `"Private entry updates not supported"`), never a bare `is_err()`. Three earlier "immutability" tests were deleted on 2026-07-30 because they asserted `is_err()` against zome functions that did not exist — they passed on "function not found" and would have stayed green with `validate()` deleted entirely.

**Coverage is shaped by the entry-visibility split** (verified against shipped `hdi 0.8.0`): private entries can never match `OpUpdate::Entry`, only `OpUpdate::PrivateEntry`.
- `attestation` (public) — per-type arms are live, ordering matters → 3 per-type tests
- `validator_workspace` / `researcher_repository` (all private) — per-type arms are dead code; **one blanket `OpUpdate::PrivateEntry` arm is the entire guard** → 1 test each, aimed at that arm

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

**🚨 HOLOCHAIN 0.7.0 STABLE SHIPPED 2026-07-30T16:28:31Z.** Announced by Eric Harris-Braun on a live stream ~15:00 UK; released ~90 min later. Verified on all three surfaces the same hour:

| Surface | Value |
|---|---|
| GitHub release `holochain-0.7.0` | `prerelease=false`, published **2026-07-30T16:28:31Z** |
| git tag `refs/tags/holochain-0.7.0` | exists |
| crates.io `holochain` / `hdk` / `hdi` | **0.7.0** (16:21Z) / **0.7.0** (16:13Z) / **0.8.0** (16:11Z) |

(Trail for the record: `develop` head `d1ec5a72` *"chore: Prepare the 0.7.0 release"* at 14:16:58Z flipped all 35 crate CHANGELOGs from `default_semver_increment_mode: !pre_minor rc` to `semver_increment_mode: minor` — the switch that makes the release automation cut the minor bump instead of rc.6. That commit is the reliable "stable is imminent" tell for future cycles.)

### ⚠️ WE ARE STILL ON 0.6.2 — TWO STANDING RULES

1. **Do NOT auto-upgrade.** Migration is deliberate and planned.
2. **MIGRATION IS BRANCH-ONLY — `main` STAYS ON 0.6.2.** User decision, 2026-07-30: this is a major change and must happen on a dedicated **`v0.7.0` branch**, never directly on `main`. `main` keeps the working, publicly-demoed 0.6.2 stack until the branch is fully green (Tryorama + all 5 sweettest suites + UI e2e + a live demo round) **and** the user explicitly approves the merge. 0.7.0 being superior does not make a broken intermediate state acceptable. See `user_ceri_working_style` — core is paranoid.

### 🔴 BLOCKER: the JS/tooling ecosystem has NOT shipped — the migration is TWO-PHASE

Checked 2026-07-30, ~15 min after the release:

| Package | latest (stable) | next |
|---|---|---|
| `@holochain/client` | **0.20.8** | `0.21.0-rc.1` |
| `@holochain/tryorama` | **0.19.2** | *no 0.7 line at all* |
| `@holochain/hc-spin` | **0.603.0** | `0.700.0-rc.1` |
| holonix | *no `main-0.7` branch* | only `update-to-0.7.0-rc.0` |
| docs-pages upgrade guide PR #647 | open, last updated **07-28** (pre-release) | — |

**Consequence: the 97 Tryorama tests and the Svelte UI CANNOT migrate yet** — there is no stable client or Tryorama to migrate *to*. The Rust zomes + `sweettest_integration` can migrate today.

**🔴 AND A THIRD BLOCKER — `wind-tunnel` (found in the 2026-07-30 API audit, not previously recorded).** `valichord/wind-tunnel/` depends on **`holochain_wind_tunnel_runner`**, a third-party crate that pulls `holochain = "0.6"`. That crate must ship a 0.7 version before the load-test workspace can move. Independent of both the zomes and the JS side.

**So the migration is THREE phases, two of them blocked on upstream:**

| Phase | Scope | Status |
|---|---|---|
| **A** | 4 DNA zomes + `sweettest_integration` | ✅ **unblocked — can start now** |
| **B** | Tryorama tests + Svelte UI | 🔴 blocked: no stable `@holochain/client` 0.21, no 0.7 Tryorama |
| **C** | `wind-tunnel/` | 🔴 blocked: `holochain_wind_tunnel_runner` on 0.6 |

Re-check the table above before starting Phase B, and crates.io for `holochain_wind_tunnel_runner` before Phase C.

### Evidence legend for everything below

The pre-release notes in this file were accumulated from indirect sources (branch-watching, RC changelogs, a draft upgrade guide written against rc.4) and **four of them turned out to be wrong**. A verification pass was run 2026-07-30 against the *shipped* artifacts — the `hdi 0.8.0` / `hdk 0.7.0` crate sources downloaded from crates.io, and the published 0.7.0 CHANGELOGs. Every claim now carries its evidence status:

- ✅ **VERIFIED** — checked against shipped 0.7.0 source or the published CHANGELOG.
- ❌ **CORRECTED** — was wrong; the corrected fact and the old claim are both recorded.
- ⚠️ **UNVERIFIED** — plausible but not yet checked against a shipped artifact. Treat as a hypothesis; verify before acting.

**Rule going forward: do not act on a ⚠️ line without verifying it first.** The four pre-release errors were all in claims derived from indirect sources; none were in claims checked against artifacts.

### ✅ VERIFIED — held up exactly

- ✅ **The `FlatOp` rename table is exactly right.** Shipped `hdi 0.8.0` `FlatOp` has precisely six variants: `CreateRecord(OpRecord)`, `CreateEntry(OpEntry)`, `AgentActivity(OpActivity)`, `Link(OpLink)`, `Update(OpUpdate)`, `Delete(OpDelete)`.
- ✅ **51 match arms, independently recounted 2026-07-30:** 26 `RegisterUpdate` / 12 `StoreEntry` / 8 `RegisterDeleteLink` / 4 `RegisterDelete` / 1 `RegisterAgentActivity` / 0 `StoreRecord`. Per-zome update arms: attestation **12**, governance **5**, validator_workspace **5**, researcher_repository **4**. (Beware: `grep -c RegisterDelete` returns 12 because it substring-matches `RegisterDeleteLink`.)
- ✅ **Both link variants really do fold into one `OpLink`** — `OpLink::CreateLink { link_type, action }` and `OpLink::DeleteLink { original_action, link_type, action }`. Structural, not a rename.
- ✅ **`@holochain/client` 0.21.x is the JS line; `holochain_client` 0.9.0 is the Rust crate.** `holochain_client-0.9.0` shipped *in* the 0.7.0 release, confirming the earlier "0.9.x" conflation fix was right.
- ✅ **The 5 live conductor-config hit sites exist** exactly as listed: `demo/conductor-config-node.yaml:19,21`, `valichord-ui/dev-conductor.yaml:17,19`, `demo/rehearse-autoupdate.sh:56`.
- ✅ **`TypedAction<D>` shape** — `{ header: ActionHeader, data: D }`, with `Deref<Target = D>` and an `author()` accessor. Authoritative rule from the shipped `holochain` CHANGELOG: **`OpUpdate` keeps `original_action_hash()`/`original_entry_hash()` as accessor methods; `OpEntry`/`OpRecord`/`OpActivity`/`OpLink` DROP those fields with no replacement method — read `action.data.<field>` directly.** `agent`/`new_key`/`original_key` remain accessors on `OpEntry`/`OpRecord`/`OpActivity`.

### ❌ CORRECTED — the draft upgrade guide was stale (all in our favour)

- ❌ **`OpActivity::CreateAgent` KEEPS its `agent` field**, and `UpdateAgent` keeps `new_key`/`original_key`. PR #5910 restored what #5903 removed. The guide predates this. *(Old claim: "CreateAgent loses its agent field.")*
- ❌ **Our membrane-proof arm needs ONLY the variant rename — not the rewrite the guide prescribes.** Shipped `OpActivity::AgentValidationPkg { membrane_proof: Option<MembraneProof>, action: TypedAction<AgentValidationPkgData> }` **retains `membrane_proof`**, and our arm at `attestation_integrity/src/lib.rs:957` destructures exactly `{ membrane_proof, .. }`. So `FlatOp::RegisterAgentActivity` → `FlatOp::AgentActivity` and nothing else. *(Old claim, from guide §3: needs `create.agent()` + `action.prev_action()` + matching `ActionData::AgentValidationPkgData`. That recipe applies to `OpActivity::CreateAgent`, which we never match.)*
- ❌ **Source-chain restore did NOT ship in 0.7.0 — now evidence, not inference.** The only trace in the shipped CHANGELOG is #5799, a `get_agent_activity_multi` p2p call *"for use by source-chain restore"* (groundwork only). No `AwaitingRestore`, no `Unrecoverable`, no `restore_chain_quorum` in the `holochain_conductor_api` or `holochain_types` changelogs. **All source-chain-restore checklist items are DEAD for 0.7.0** — no `dev-setup.mjs` or Svelte `AppStatus` work needed. Re-check when it lands in a later 0.7.x.
- ❌ **"rc.5's crate line is not on crates.io" was WRONG** (recorded pre-release). Per-crate versions run **independently of the umbrella release name** — `hdk 0.7.0-rc.4` *was* rc.5's hdk. Never infer "not published" from a crate version that trails the release name.
- ❌ **"PR #5920 source-chain restore is the main brake on the stable tag" was WRONG.** It was a conflicting draft ~8h before the release was prepared; they shipped without it.
- ❌ **"#5898 / #5906 landed after rc.4" was WRONG** — both are in rc.4. They remain real migration items (see below); they were never evidence of post-rc churn.

### 🆕 NEW — found during the verification pass, not in the original plan

- ✅ **`OpUpdate::PrivateEntry` SURVIVES in `hdi 0.8.0`** — `{ app_entry_type: <ET as UnitEnum>::Unit, action }`. Combined with the finding below, this means **the match-ordering hazard is concentrated in the `attestation` DNA** (the only one with public entry types).
- ✅ **Private entry types can NEVER match `OpUpdate::Entry`.** Verified in `hdi` `src/op.rs` (`get_app_entry_type_for_record_authority` returns `UnitEnumEither::Unit` for private entries → `OpUpdate::PrivateEntry`; `Enum` → `OpUpdate::Entry`). Therefore these per-type guard arms are **unreachable dead code**: `validator_workspace_integrity.rs:149` (`ValidatorPrivateAttestation`), `:157` (`DeliberateAbstention`), `researcher_repository_integrity.rs:150` (`PreRegisteredProtocol`). What actually enforces immutability in DNA 1 and DNA 2 is the single blanket `FlatOp::RegisterUpdate(OpUpdate::PrivateEntry { .. }) => Invalid` arm in each (`:210` and `:199` respectively). **Migration risk shifts accordingly: dropping or mis-porting that ONE blanket arm silently loses ALL private-entry immutability at once.**
- ✅ **`OpUpdate::PrivateEntry` LOST its `original_action_hash` field** (0.6.2 had it; now an accessor method). We destructure `{ .. }`, so we are unaffected — recorded because it is exactly the kind of silent change that bites.
- ⚠️ **The guarded-type list in this file is imprecise:** `LockedResult` has **no per-type guard arm at all** — it is private, so it is covered only by the blanket rule.
- ❌ **The three existing "immutability" sweettests are FAKE and prove nothing.** `sweettest_integration/tests/attestation.rs:267,313,334` call `update_attestation_for_test` / `update_commitment_for_test` / `update_phase_marker_for_test` — **none of these zome functions exist anywhere in the codebase.** The call fails with "function not found", `assert!(result.is_err())` passes, test is green. **They would stay green with `validate()` deleted entirely.** They test the coordinator's surface, not the integrity guard. Fix or replace before relying on any immutability signal.

### ⚠️ UNVERIFIED — check before acting

- ✅ **RETIRED 2026-07-30 — conductor-config syntax VERIFIED against the real 0.7.0 binary.** Both our configs were run against `holochain 0.7.0` and now **start cleanly with exactly two changes each**. See "Conductor configs" in the guide section below for the exact diffs and the full allowed-field lists. **Do NOT apply the fixes to `main`** — they would break our running 0.6.2 stack. They belong on the `v0.7.0` branch.
- ✅ **RETIRED 2026-07-30 — the match-ordering hazard is PROVEN REAL, and tripwire tests now exist.** See "Immutability tripwire tests" below. Negative control run: moving the `ValidationAttestation` guard behind the generic arm caused the forbidden update to be **silently ACCEPTED** (it returned a real `ActionHash`), and the tripwire test caught it. Guard restored → green again.

**If 0.7.0 stable is available:** do NOT auto-upgrade. Report to user with these breaking changes (⬤ = CONFIRMED landed in 0.7.0-rc.0, verified from the crate CHANGELOGs 2026-07-19):
- ✅ **`hdk → 0.7.0`, `hdi → 0.8.0` — only THREE version strings, not "across all zomes"** (audited 2026-07-30). Every zome uses `{ workspace = true }`, so the only literals are `valichord/Cargo.toml:18` (`hdi = "=0.7.2"`) and `:19` (`hdk = "=0.6.2"`), plus `sweettest_integration/Cargo.toml:42` (`hdk = "=0.6.2"`). `sweettest_integration` needs 4 more (`holochain`, `holochain_types`, `holochain_keystore`, `holo_hash`, all `=0.6.2`) → **~7 strings total.**
- Wasmer flags renamed: `wasmer_sys → wasmer-sys-cranelift`, `wasmer_wamr → wasmer-wasmi`
- Conductor DB migrated to `holochain_data` — no migration path, must clear state; Oracle demo nodes need `docker compose down -v` before upgrading, not just a binary swap
- ✅ **ZERO IMPACT — `must_get_agent_activity` / `ChainFilter`** (audited 2026-07-30). Response types changed (new variants `UntilTimestampIndeterminate`, `UntilTimestampGreaterThanChainHead`, `IncompleteChain`) and `ChainFilter` is now built via `take(n)` / `until_hash(h)` / `until_timestamp(t)` constructors rather than builder chaining — **but we never call either.** `must_get_agent_activity` appears exactly once in the repo, inside a *comment* (`attestation_integrity/src/lib.rs:324`); `ChainFilter` is a hard zero. No work.
- `HCP2P_PROTO_VER` bumped 2→3 (wire-incompatible with 0.6.x nodes)
- ✅ **ZERO IMPACT — `get_links_details` renamed from `get_link_details`.** Both names are a hard zero in our code (audited 2026-07-30). No work.
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
- ❌ **NOT IN 0.7.0 — CONFIRMED ABSENT, NO WORK NEEDED.** Verified against the shipped 0.7.0 CHANGELOGs 2026-07-30: the only source-chain-restore trace is #5799 (`get_agent_activity_multi` groundwork). Nothing below exists in 0.7.0 — **do not touch `dev-setup.mjs` or the Svelte `AppStatus` handling for it.** Re-check when restore lands in a later 0.7.x. If/when it does ship: new `AppStatus` variants `AwaitingRestore` (restore in progress) and `Unrecoverable(cell_id, reason)` (terminal — chain forked or warrant validated) — `dev-setup.mjs` and Svelte UI currently assume only `Running`/`Disabled`; new `SystemSignal` variants `RestoreComplete { cell_id }`, `AppRestoreComplete { installed_app_id }`, `RestoreFailed { cell_id, reason }`; new conductor config field `restore_chain_quorum: u8` (default 2). (Source: `holochain/holochain` branch `cascade-read-and-cutover`, `docs/design/source_chain_restore.md`)
- **Source-chain restore does NOT recover private entries** — `ValidatorPrivateAttestation` (DNA 2) and `LockedResult` (DNA 1) are private and absent after a restore. Validators who lose their machine mid-round lose their uncommitted private attestations silently. **Moot for 0.7.0 if restore did not ship (above); it becomes live the release restore actually lands in.**
- ✅ **ZERO IMPACT — `ChainIntegrityWarrant::InvalidChainOp` gains a `reason: String` field** (excluded from `PartialEq`/`Hash` — deduplication unaffected). The old note said "check any match arm that destructures this variant in `reject_if_warranted`" — **there is no such arm.** `ChainIntegrityWarrant`, `InvalidChainOp` and `SignedWarrant` are all a hard zero in our code; `reject_if_warranted` only calls `.warrants.is_empty()` (audited 2026-07-30). No work.
- CI: update `BASE=` URL and `key: hc-bin-0.6.2` in **both** jobs in `.github/workflows/tests.yml` (4 edits total)

#### Official upgrade guide — read it first, and this ValiChord audit alongside it

**Source: `holochain/docs-pages` branch `docs/upgrade-guide-holochain-0.7`, file `src/pages/resources/upgrade/upgrade-holochain-0.7.md`** (700 lines, written 2026-07-27). **Now open as [docs-pages PR #647](https://github.com/holochain/docs-pages/pull/647) — *"docs: add Holochain 0.6 → 0.7 upgrade guide"*, NOT a draft (verified 2026-07-30; supersedes the earlier "no PR yet"). Re-read it from the PR head at migration time — it will likely gain fixes as 0.7.0 ships.** It is written against **rc.4** and states plainly that *"further breaking changes are still possible"* — another reason the migration waits for stable. **Caveat added 2026-07-30: the guide therefore predates rc.5, and so predates #5910's HDI `TypedAction` changes** — treat its validate-callback sections as one release behind and reconcile against the HDI CHANGELOG at migration time. It names `holochain/dino-adventure`'s integrity zome as the reference port to adapt our `validate` dispatcher from, and notes **no 0.7 scaffolding release exists yet**.

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

**2. ⚠️ IMMUTABILITY-GUARD ORDERING IS THE REAL HAZARD — ValiChord-specific. RESCOPED 2026-07-30 by the verification pass.** Per `docs/7_ValiChord_4-DNA_architecture_technical.md:325`, **Rust match ordering IS the enforcement mechanism** — guarded arms must precede the generic update arm. A mechanical rename-and-reflow that reorders them **silently disables immutability: no compile error, and no test failure unless a test explicitly attempts a forbidden update.** Treat "preserve arm ordering, then prove it with a forbidden-update test" as its own migration step, not part of the rename.

**But the hazard is NOT spread evenly across the 26 arms** — verified against shipped `hdi 0.8.0`:
- **`attestation` DNA (public entries) — THE REAL ORDERING RISK.** Its 12 per-type `OpUpdate::Entry` guard arms (`ValidationAttestation`, `CommitmentAnchor`, `PhaseMarker`, `StudyClaim`, `StudyClaimRelease`, `ResearcherResultCommitment`, `ResearcherReveal`, `AgentIdentityAttestation`, `ValidationRequest`, …) are live and **must** stay ahead of the generic `OpUpdate::Entry { action, .. }` arm (`:490`) and the catch-all `RegisterUpdate(_)` (`:508`). This is where a reflow does real damage.
- **`validator_workspace` + `researcher_repository` (all entries private) — DIFFERENT RISK.** Their per-type `OpUpdate::Entry` arms are **dead code** (private entries only ever surface as `OpUpdate::PrivateEntry`). Immutability there rests on a **single blanket `OpUpdate::PrivateEntry { .. } => Invalid`** arm each. Ordering is irrelevant; **losing that one arm is catastrophic.** Guard it with one tripwire test per DNA, not six.
- ⚠️ `LockedResult` has no per-type arm at all — blanket-covered only.

**3. Membrane proof — ❌ THE GUIDE IS STALE HERE; OUR WORK IS SMALLER.** `attestation_integrity/src/lib.rs:957` matches `AgentValidationPkg` inside the agent-activity arm (our `validate_agent_joining` credential path). **Verified against shipped `hdi 0.8.0` 2026-07-30: `OpActivity::AgentValidationPkg { membrane_proof: Option<MembraneProof>, action: TypedAction<AgentValidationPkgData> }` RETAINS `membrane_proof`**, and our arm destructures exactly `{ membrane_proof, .. }` — so this arm needs **only** the `FlatOp::RegisterAgentActivity` → `FlatOp::AgentActivity` rename. The guide's `create.agent()` + `prev_action()` + `ActionData::AgentValidationPkgData` recipe applies to `OpActivity::CreateAgent` (which keeps its `agent` field anyway, per #5910) — **we never match that variant.** Ignore the guide's before/after diff for this arm.

**4. Conductor configs FAIL TO START, they are not ignored.** `NetworkConfig` now rejects unknown fields. Live hits to fix at migration:
- `demo/conductor-config-node.yaml:19` (`signal_url`), `:21` (`db_sync_strategy: Fast`)
- `valichord-ui/dev-conductor.yaml:17` (`signal_url`), `:19` (`db_sync_strategy: Resilient`)
- `demo/rehearse-autoupdate.sh:56` (`signal_url`)

✅ **VERIFIED EMPIRICALLY 2026-07-30 against the real `holochain 0.7.0` binary** (downloaded to scratchpad; the 0.6.2 on `PATH` was left untouched). Both configs were run to a live conductor. **Exactly TWO changes are needed per file, and nothing else:**

```diff
  network:
    bootstrap_url: <unchanged>
-   signal_url: <anything>          # ← REMOVE THIS LINE
    relay_url: <unchanged>
- db_sync_strategy: Fast            # demo/conductor-config-node.yaml
+ db_sync_level: Off
- db_sync_strategy: Resilient       # valichord-ui/dev-conductor.yaml
+ db_sync_level: Normal
```

With those two edits, **both configs start a 0.7.0 conductor and open their admin port.** Everything else we use survives unchanged: `data_root_path`, `keystore.type: lair_server_in_proc`, `lair_root`, `admin_interfaces`, `network.bootstrap_url`, `network.relay_url`, `db_max_readers`. Same fix applies to the embedded config in `demo/rehearse-autoupdate.sh:56` (`signal_url` only — it has no `db_sync_strategy`).

⚠️ **Do NOT apply these to `main`** — they break 0.6.2, which rejects `db_sync_level`. They go on the `v0.7.0` branch.

**Exact allowed field lists, read out of the 0.7.0 parser's own error messages:**

- **Top level:** `tracing_override`, `wasm_backend`, `data_root_path`, `keystore`, `admin_interfaces`, `network`, `db_sync_level`, `db_max_readers`, `incoming_request_concurrency_limit`, `restore_chain_quorum`, `tuning_params`, `tracing_scope`
- **`network`:** `base64_auth_material_bootstrap`, `base64_auth_material_relay`, `bootstrap_url`, `relay_url`, `request_timeout_s`, `target_arc_factor`, `report`, `advanced`
- **`db_sync_level` values:** `Full`, `Normal`, `Off`

Three things fall out of those lists:

1. ❌ **CORRECTION to our own 2026-07-30 finding: `restore_chain_quorum` IS a valid 0.7.0 config field**, even though the source-chain-restore *workflow* (PR #5920) did not ship. The config surface landed ahead of the feature. This does **not** revive the `AppStatus::AwaitingRestore` / `RestoreComplete` items — those remain unverified-and-likely-absent — but "restore_chain_quorum is absent from 0.7.0" was wrong.
2. 🆕 **`base64_auth_material_bootstrap` / `base64_auth_material_relay` are real network fields** — this is the kitsune2 v0.5.0 authenticated-relay work (bearer token on the relay WebSocket upgrade) surfacing in conductor config. Directly relevant to the relay blocker-remover note and to kangaroo packaging.
3. 🆕 **`target_arc_factor` is a `network` config field in 0.7.0** — relevant to the polite-shrink / kitsune2 #160 work (Unyt HEART hardcodes `target_arc_factor: 1`).

✅ Confirmed removed as claimed: `signal_url`, `chc_url`, `webrtc_config`. ✅ Confirmed moved: `request_timeout_s` is now under `network`. ✅ `db_max_readers` survives (we use it). ⚠️ The `Fast`→`Off` / `Resilient`→`Normal` *semantic* mapping is the guide's claim — the three valid values are verified, the mapping itself is plausible (it matches SQLite `synchronous` levels) but not independently confirmed. **A local iroh relay additionally needs `advanced: { irohTransport: { relayAllowPlainText: true } }`.**

**Gotcha hit during verification, worth remembering:** a long `data_root_path` makes the in-process lair keystore fail with `path must be shorter than SUN_LEN` — the same trap already documented for `rehearse-autoupdate.sh`. It looks like a config error but is not; keep test conductor paths short (`mktemp -d /tmp/hc7XXXX`).

**5. `AgentActivity` → `AgentActivityStatus` — ❌ LISTED AS WORK, ACTUALLY ZERO.** The rename is real (it resolves the collision with the `AgentActivity` op variant) and our three call sites are real — `governance_coordinator/src/lib.rs:188,322`, `attestation_coordinator/src/lib.rs:637`. **But none of them need changing** (verified against shipped `hdk 0.7.0` + `holochain_zome_types 0.7.0`, 2026-07-30):

```rust
// hdk 0.7.0 — IDENTICAL signature to 0.6.2, only the return type's NAME changed
pub fn get_agent_activity(
    agent: AgentPubKey, query: ChainQueryFilter,
    request: ActivityRequest, options: GetOptions,
) -> ExternResult<AgentActivityStatus>
```

Same four arguments, same argument types (`ChainQueryFilter`, `ActivityRequest`, `GetOptions`, `GetStrategy` all still exist). **We never name the return type** — two sites chain `.map(|a| a.warrants.is_empty())`, the third does `let activity = …`, so it is inferred. And `AgentActivityStatus.warrants: Vec<SignedWarrant>` survives, which is the only field we read. **All three compile unchanged.**

**6. JS side.** `SignedActionHashed` is no longer generic and the per-variant types (`Create`, `Update`, `Delete`, `CreateLink`, `DeleteLink`) are no longer exported; common action fields move under `.header`. **`valichord-ui/src/lib/types.ts:331`** does `record.signed_action.hashed.content.author` → needs `.header.author`. Also `signalingServerUrl` → `relayServerUrl`; `dumpNetworkStats` returns `ApiTransportStats` (nested under `transport_stats`, `is_webrtc` → `is_direct`).

**7. Sweettest dep line** for `sweettest_integration`: `holochain = { version = "0.7.0", default-features = false, features = ["encryption", "wasmer-sys-cranelift"] }` — `sqlite-encrypted`→`encryption`, `wasmer_sys`→`wasmer-sys-cranelift`, drop `transport-iroh`. ✅ **Import surface is tiny** (audited 2026-07-30): only 3 `use` lines across `src/` + `tests/` — `holochain_types::prelude::YamlProperties`, `pub use holochain::prelude::*`, `pub use holochain::sweettest::*`. ⚠️ **But two are globs**, so #5898's re-layering of conductor state types out of the `holochain` crate will surface as *unresolved names at use sites*, not as import errors — expect the breakage to appear scattered through the tests rather than at the top of the file. The guide also carries a table of removed implicit Cargo features (`holo_hash` `serde`→`serialization`, `hdi` `tracing`→`trace`, `holochain_zome_types` `serde_yaml`→`properties`, …) — check our zome + `shared_types` manifests against it.

**8. Toolchain:** `hc-spin` → `0.700.0-rc.1`; holonix `main-0.7` **still does not exist** (re-verified 2026-07-30 — the only 0.7 branch is `update-to-0.7.0-rc.0`; branches are `main-0.2`…`main-0.6` + `main`, so use `ref=main` and expect `main-0.7` to appear around the stable tag); nodejs 22 → 24; Sweettest builds may need `perl` on `PATH`.

**9. ✅ FULL API AUDIT — confirmed ZERO in our code** (grep across all four zomes + `shared_types` + `sweettest_integration`, 2026-07-30, post-release). Every one of these is a hard zero, so none of the listed migration work applies:

| Symbol | Why it was listed | Our hits |
|---|---|---|
| `ChainFilter` | new constructors | **0** |
| `must_get_agent_activity` | response variants changed | **0 calls** (1 comment only) |
| `get_link_details` / `get_links_details` | renamed | **0** |
| `Record::new` | now takes `RecordEntry` | **0** |
| `block_agent` / `unblock_agent` | removed | **0** |
| `EntryCreationAction` / `NewEntryAction` | removed (v2 action model) | **0** |
| `ActionBuilder` | removed | **0** |
| `RateWeight` / `EntryRateWeight` | `rate_limit` module removed | **0** |
| link `base_address` / `target_address` / `tag` destructuring | fields dropped, no replacement | **0** |
| `ChainIntegrityWarrant` / `InvalidChainOp` / `SignedWarrant` | `reason` field added | **0** |

**Net effect of the audit: the migration reduces to (a) the 51 `FlatOp` match arms, (b) 3 conductor-config files, (c) ~7 version strings + sweettest feature flags.** Everything else previously listed is confirmed zero or zero-work.

**10. Every published HarmonyRecord URL dies at migration.** Zome-definition serialization changed, so an otherwise-identical DNA has a different `DnaHash`, and 0.7 agents form a network separate from 0.6. This is the same fact as "clear state / `down -v`", but stated in the form that matters for the Oracle demo's public links.

**✅ WATCH COMPLETE — `holochain-0.7.0` stable landed 2026-07-30T16:28:31Z.** The rc.0 signal fired 2026-07-15 and the stable tag followed on 07-30. Nothing further to watch on the release itself.

**New watch items replacing it:**
1. **`@holochain/client` 0.21.x stable** on npm dist-tag `latest` (currently `0.20.8`) and **`@holochain/tryorama` on a 0.7 line** (currently `0.19.2`, no 0.7 line) — these gate **Phase B** of the migration. Check both before starting any JS work.
2. **holonix `main-0.7`** branch (does not exist yet; use `ref=main`).
3. **Source-chain restore** (PR #5920) landing in a later 0.7.x — reactivates the `AppStatus`/`RestoreComplete` checklist items and makes the private-entry-loss risk real for validators.

**Blocker-remover — ✅ LANDED on kitsune2 `main` 2026-07-27 and ✅ NOW PUBLISHED in kitsune2 `v0.5.0` (2026-07-28), which holochain `0.7.0-rc.5` pins.** What was tracked as branch `fix/491-stabilize-the-iroh-relay-hosted-in-bootstrap_srv` merged as **`3746be1` *"feat: stabilize authenticated iroh relay hosted in the bootstrap server"*** (refs #492; 16 files, ~+1160/−490). Relay access is gated by a bearer token on the relay WebSocket upgrade (`RelayConfig::with_auth_token`), validated in `AccessControl::on_connect`; bootstrap client gains `blocking_fetch_relay_token`; a client-side registration heartbeat (`relayReRegistrationIntervalS`, default 120 s) + token-rotating watchdog work around iroh 1.0.0 capturing the relay token once per connection actor; legacy `PUT /relay/register` allowlist retained for 0.4.x clients. Covered by unit, server-side auth-flow, and an end-to-end bootstrap-restart recovery test. **This removes the "need a separate Iroh relay" blocker for both the deferred wind-tunnel kitsune live run and kangaroo desktop packaging — as a 0.7-migration item, not something available on 0.6.2.** The re-check condition recorded here on 2026-07-27 ("does the picked-up kitsune2 actually carry `3746be1`?") **is now answered: YES.** Verified 2026-07-30: `v0.5.0` is 7 ahead / 0 behind `3746be1`, and the commit appears in the `v0.5.0-dev.6...v0.5.0` list (24 commits) along with two relay follow-ups on top of it — **`03d21103`** *"negotiate relay protocol version, enabling V2"* and **`768b01b1`** *"add TLS security headers to relay HTTP responses"*. holochain `0.7.0-rc.5` pins `kitsune2_* 0.5.0` (PR #5913). Our 0.6.2 stays on `0.4.1`, so **none of this is reachable until we migrate** — plan the relay work as part of the 0.7 migration, not before. **Note the holochain side's own backport branch has NOT consumed it:** `holochain/holochain`'s own `fix/491-…` branch is stale — last commit 2026-04-22, 114 behind `develop`, 1 commit ahead containing only `build: kitsune #491`.

**`holochain/holochain` branch watch — re-verified 2026-07-30 against `develop` (default branch is `develop`, not `main`).** Only two things are live; everything else previously listed here is stale or has merged:
- **LIVE, but MISSED THE 0.7.0 RELEASE** `feat/5800-source-chain-restore-workflow` → **PR #5920** *"Add source chain restore workflow"* (opened 2026-07-29). Branch **20 ahead / 4 behind**, **+2516/−33 across 15 files**. Still `draft = true`, `mergeable = CONFLICTING`, review outstanding as of **2026-07-30T06:25Z — ~8 hours before `d1ec5a72` prepared the 0.7.0 release**. ❌ **It was recorded here as "the main brake on the stable tag" — that read was WRONG; they cut the release without it.** Expect it in a later 0.7.x. Recent commits include *"add unit test for ignoring forgery during a restore"*. Still does NOT recover private entries → `ValidatorPrivateAttestation`/`LockedResult` lost on restore (see architecture doc, Phase 0 limitation 4). **Keep watching: this is the release that makes the private-entry loss real for validators.**
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
