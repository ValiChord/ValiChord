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
pkill -f holochain; pkill -f lair-keystore; sleep 2

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

`sweettest_integration` is deliberately outside `valichord/Cargo.toml` because it depends on `holochain = "0.6.1"` (native binary), which cannot compile to `wasm32-unknown-unknown`. Merging it into the workspace would break the WASM build.

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
- Before any test run: `pkill -f holochain; pkill -f lair-keystore; sleep 2`
- Private entries in single-agent DNAs: use `query()` not `get()` — `get()` in a test conductor can leak across cell boundaries

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
Run `holochain --version`. Current: 0.6.1.

**If 0.7.0 stable is available:** do NOT auto-upgrade. Report to user with these breaking changes:
- `hdk → 0.7.x`, `hdi → 0.8.x` (Cargo.toml across all zomes)
- Wasmer flags renamed: `wasmer_sys → wasmer-sys-cranelift`, `wasmer_wamr → wasmer-wasmi`
- Conductor DB migrated to `holochain_data` — no migration path, must clear state
- `must_get_agent_activity` response types changed
- `HCP2P_PROTO_VER` bumped 2→3 (wire-incompatible with 0.6.x nodes)
- `get_links_details` renamed from `get_link_details`
- CI: update `BASE=` URL and `key: hc-bin-0.6.1` in **both** jobs in `.github/workflows/tests.yml` (4 edits total)

Ignore `0.7.0-dev.*` and `0.6.1-rc.*` tags — stable only.

### CI binary upgrade (any Holochain version bump)
Update 4 places in `.github/workflows/tests.yml`:
1. `BASE=…/releases/download/holochain-X.Y.Z` — `test` job
2. `key: ${{ runner.os }}-hc-bin-X.Y.Z` — `test` job
3. Same `BASE=` — `sweettest` job
4. Same `key:` — `sweettest` job

Verify binary names (`holochain-x86_64-unknown-linux-gnu`, etc.) exist on the release before pushing.

---

## Ecosystem tool notes

- **Unyt joining-service** — REST membrane-proof onboarding; reference impl for institutional validator onboarding on a live network. See `memory/reference_unyt_tools.md`.
- **Unyt heart** — DigitalOcean + Pulumi conductor provisioning. Use when setting up production nodes.
- **Unyt tauri-plugin-holochain** — lighter Electron alternative (not yet open-source); revisit before building the validator desktop app.
- **kangaroo-electron** (`holochain/kangaroo-electron`, branch `main-0.6`) — cross-platform Electron packaging. Full plan: `docs/KANGAROO_PACKAGING_PLAN.md`. Remaining blockers: dedicated bootstrap/relay servers.
