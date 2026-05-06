# ValiChord — Current Project Status

**Last updated:** 2026-05-06
**Phase:** Full protocol running end-to-end on Oracle. Svelte/TS frontend wired to live conductor, end-to-end tested. v0.5.0. `valichord_attestation` now includes probabilistic challenge-response (v1.1 additive).

---

## What ValiChord does (one paragraph)

ValiChord is a scientific reproducibility verification system built on Holochain. A researcher deposits a hash of their data and result claim. Independent validators each reproduce the analysis blindly, seal their verdict using a commit-reveal protocol, then reveal simultaneously — removing any last-mover advantage. Outcomes are aggregated into a tamper-evident **HarmonyRecord** on a public DHT. No central party can alter it after the fact.

**valichord_at_home** (separate tool, live on Render) runs 100+ automated deposit-quality checks and Claude semantic analysis to help researchers prepare a clean, reproducible deposit before the protocol begins. It does not produce the validation verdict — validators do.

---

## What is live right now

| Component | Status | Detail |
|---|---|---|
| Flask REST API | **Live** | `POST /validate`, `GET /result/<job_id>`, `GET /download/<job_id>`, `GET /health` |
| Analysis pipeline | **Live** | 100+ detectors + Claude semantic analysis |
| `validator_outcome` / `validator_notes` | **Live** | Validators submit real replication verdicts; `validator_attested: true` in result |
| API key authentication | **Live** | `VALICHORD_API_KEYS` env var; `X-ValiChord-Key` header on write endpoints |
| Webhook callbacks | **Live** | `callback_url` form field; fires once on completion with one retry |
| OpenAPI 3.0 spec | **Live** | `GET /openapi.yaml` — machine-readable spec for any HTTP client |
| Swagger UI | **Live** | `GET /docs` — interactive API explorer |
| Decentralised demo | **Working end-to-end** | 4 isolated Docker conductors (researcher + 3 validators) communicating only via DHT — `docker compose up` + `python3 demo/ai_validator.py --mode decentralised` |
| Node.js bridges | **Working** | `researcher-node.mjs` (port 3001) + `validator-node.mjs` (ports 3002–3004) — HTTP APIs over each conductor |
| HarmonyRecord URL | **Working** | `GET /record?hash=<hash>` on researcher node — no auth, returns clean JSON |
| Feynman skill (was PR #13) | **Historical** | Feynman is no longer operational (April 2026). Superseded by `demo/ai_validator.py` (direct Claude API). |
| valichord-ui (Svelte/TS frontend) | **Working end-to-end** | Full UI for all three roles (researcher, validator, governance). Wired to a live local conductor: `bash dev.sh` starts conductor + installs app + writes auth token; `npm run dev` serves at `:5173`. `submit_validation_request` → DHT → `get_validation_request_for_data_hash` verified. See `valichord-ui/README.md` and `FRONTEND.md`. |

---

## How the demo runs end-to-end

Five Docker containers — researcher + 3 validators + kitsune2 bootstrap server — each with their own Holochain conductor, keystore, and SQLite database. The only communication between containers is the DHT.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
docker compose -f demo/docker-compose.yml up --build -d
until [ "$(docker compose -f demo/docker-compose.yml logs 2>/dev/null | grep -c 'node API →')" -ge 4 ]; do sleep 3; done && echo "Ready"
python3 demo/ai_validator.py --mode decentralised
```

**Demo output (step 7):**
```
[7/7] Permanent record.
────────────────────────────────────────────────────────────
  Outcome:           Reproduced (3/3 validators)
  Agreement level:   ExactMatch
  Discipline:        ComputationalBiology
  HarmonyRecord:     uhC8k…
  Researcher reveal: uhCkk…

  Validator 1: Reproduced (High) — …
  Validator 2: Reproduced (High) — …
  Validator 3: Reproduced (High) — …

  Shareable URL:
  http://localhost:3001/record?hash=uhC8k…

  Verifying record is readable…
  Record confirmed. Outcome: Reproduced  Agreement: ExactMatch  Validators: 3

════════════════════════════════════════════════════════════
  Demo complete. The full ValiChord protocol ran end-to-end.
  Researcher and 3 validators all commit-revealed simultaneously.
════════════════════════════════════════════════════════════
```

Full architecture, retry design, and commit-reveal table: **`demo/DECENTRALISED_DEMO.md`**

---

## Recently completed

### Wind-Tunnel performance scenarios — 2026-05-06 ✓

Three load-testing scenarios under `valichord/wind-tunnel/` (commit `fcf8ced`).
Separate Cargo workspace — intentionally outside `valichord/Cargo.toml` (same isolation pattern as `sweettest_integration`; native `holochain` deps can't compile to `wasm32`).
All three compile clean (`cargo check --workspace`).

| Scenario | What it measures | Default invocation |
|---|---|---|
| `validation_request_throughput` | Concurrent CommitmentAnchor write throughput — N agents loop `submit_validation_request` + `notify_commitment_sealed`; reports `commits_sent` counter | `--agents 4 --duration 60` |
| `phase_observation_latency` | Time from `notify_commitment_sealed` returning to first `RevealOpen` observation via polling — uses `num_validators_required=1`; reports `phase_observation_ms`, `poll_count`, `phase_timeout_count` | `--agents 2 --duration 60` |
| `concurrent_reveal_throughput` | Full commit-reveal cycle under N-agent concurrent load; tests `ChainTopOrdering::Relaxed` under 3 sequential source-chain writes; reports `round_total_ms`, `reveal_count`, `reveal_timeout_count` | `--agents 4 --duration 90` |

Pre-requisite: pack `valichord.happ` first. Override path with `VALICHORD_HAPP_PATH` env var.

```bash
cd valichord/wind-tunnel
cargo run -p validation_request_throughput -- --agents 4 --duration 60
cargo run -p phase_observation_latency    -- --agents 2 --duration 60
cargo run -p concurrent_reveal_throughput -- --agents 4 --duration 90
```

---

### `valichord_attestation` real-data example — 2026-05-06 ✓

Real-data demo of the v1.1 protocol under `valichord_attestation/examples/mistral_7b_gsm8k_demo/`:

- **`run_eval.sh`** — lm-evaluation-harness v0.5.0, Mistral-7B-Instruct-v0.3, GSM8K 100-sample subset, fully pinned; ~10 min on a 4090, ~£1.50
- **`build_bundle.py`** — parses lm-eval output (glob-based, robust to directory structure) OR `--fixture` for no-GPU demo. `samples_total=100` passed explicitly (exercises threat-model §10(d) sample-omission defence). Merkle round-trip validated on every run.
- **`challenge_response_demo.py`** — loads `bundle.json`, k=20 challenge with documented fixed nonce, verifies all 20 Merkle paths, demonstrates tamper detection
- **`bundle.json`** — committed bundle (simulated fixture, `random.Random(42)`, 35% accuracy); replace with real eval output by running the two scripts on a GPU
- **`examples/README.md`** — new index pointing at both synthetic and real-data examples

No library code changed. All 142 tests pass.

---

### `valichord_attestation` explicit `samples_total` — 2026-05-05 ✓

Closes sample-omission gap (threat model §10 attack surface (d)). `build_bundle` now accepts `samples_total: Optional[int]`; when provided and larger than `len(samples)`, `bundle.samples_total > bundle.samples_completed` is directly visible in the bundle without out-of-band context. Raises `ValueError` if `samples_total < len(samples)`. 4 new tests (boundary: omitted, equal, larger, smaller); 142 tests total, 100% line coverage. Spec §2 field descriptions tightened; §10 (d) updated to note that explicit declaration shifts detection in-bundle, and that federation remains the backstop against a lying adapter.

---

### `valichord_attestation` probabilistic challenge-response — 2026-05-05 ✓

Additive extension on top of v1 Merkle structure. Verifier-controlled randomness: challenged indices derived deterministically from `HMAC-SHA256(nonce, bundle_hash)` + SHA-256 counter-mode PRNG, so the holder cannot predict which samples will be challenged.

**New modules:**
- `challenge.py` — `Challenge` dataclass, `derive_seed`, `generate_indices`, `compute_challenge_hash`
- `response.py` — `ResponseSample`, `ChallengeResponse`, `build_response`, `verify_response`

**Protocol properties:**
- Seed: `HMAC-SHA256(key=verifier_nonce, msg=bundle_hash_ascii)`
- Indices: SHA-256 counter-mode (`SHA256(seed || counter_u64_be)` mod `total_samples`, rejection-sampled for distinctness)
- Response contains only hashes + proof paths — no raw sample content
- `challenge_hash` = `SHA-256(JCS({"bundle_hash", "k", "verifier_nonce_hex"}))` binds response to challenge
- `merkle_path` reuses existing `list[{"position","sibling"}]` format from `merkle_proof`
- `_leaf_hash` promoted to public `leaf_hash` (protocol-defining)

**Test coverage:** 57 new tests (38 challenge + 35 response, 4 pre-existing overlap removed). 138 tests at this point; 142 total after subsequent `samples_total` additions. 100% line coverage maintained.

**Fixed test vector:** `bundle_hash='a'*64`, `nonce=bytes(range(16))`, `k=5`, `total=100` → indices `[9, 69, 33, 74, 38]`

**No breaking changes** — v1 bundle format unchanged. No new dependencies.

---

### `valichord_attestation` v0.1.0 — 2026-05-05 ✓

Python library for canonical, cryptographically verifiable attestation bundles for AI evaluation runs. Applies ValiChord's commit-hash-reveal principle to AI benchmarks: a published accuracy score becomes traceable to the run that produced it.

**Key properties:**
- **Deterministic hash** — RFC 8785 (JCS) encoding; `SHA-256(JCS(bundle))` is stable across implementations
- **Merkle root** — SHA-256 tree over per-sample outputs; selective disclosure without the full log
- **Harness-agnostic** — `AdapterBase` ABC; Inspect AI stub included

**What's in the package:**
- `builder.py` — `build_bundle(...)`, `MalformedBundleError` on NaN/missing fields
- `canonical.py` — JCS encoding + `hash_bundle()`
- `merkle.py` — `merkle_root`, `merkle_proof`, `verify_faithfulness`
- `spec/attestation_format_v1.md` — canonical spec
- 81 tests, 100% line coverage

**Not in v1:** cryptographic signing (v2), ZK proofs, Holochain DHT integration (post-format-stabilisation).

**Motivation:** Scott Simmons's review of `UKGovernmentBEIS/inspect_evals#1610` — canonical attestation spec belongs in ValiChord, not in each harness.

---

### UI bug fixes + backend signal hardening — 2026-05-04 ✓

**UI fixes (both are live-demo killers):**
- **Signal handler leak** (`App.svelte`) — `onSignal` return value was never captured. Each component remount stacked another handler; validators received duplicate `RevealOpen` notifications. Fixed with `onDestroy` + captured unsubscribe.
- **`checkPendingReveals` race** (`ValidatorView.svelte`) — the reactive `$:` fired `checkPendingReveals()` unawaited; multiple concurrent invocations could race to set `revealTaskHash`/`revealPrivateAttestation`/`screen`. Fixed with a `checkingReveals` boolean guard.
- **Signal format mismatch** (`types.ts`, `App.svelte`) — `Signal` enum uses adjacent-tag serde (`#[serde(tag = "type", content = "content")]`), delivering `{ type: "RevealOpen", content: { ... } }` over the WebSocket. `types.ts` and the previous `"RevealOpen" in payload` check assumed external-tag format and never fired. Fixed throughout.

**Backend fixes (attestation + governance coordinators):**
- **`FinalizationFailed` signal** — `call_governance_fire_and_forget` now returns `bool`. When the cross-DNA call to `check_and_create_harmony_record` fails after a successful `submit_attestation`, the attestation coordinator emits `Signal::FinalizationFailed { request_ref }` locally. The UI displays an actionable error pointing to `force_finalize_round`.
- **Warrant-check asymmetry comment** — `unwrap_or(true)` in the HarmonyRecord warrant filter is intentionally asymmetric with `reject_if_warranted()` (claim time). At finalisation time there is no automatic retry trigger, so excluding a legitimate validator on a transient network error would permanently strand a completed round. Comment updated to explain this explicitly.
- **TOCTOU comment** — updated to note that `write_harmony_record` already sorts `participating_validators` by key bytes, making the same-set race benign via content-addressing. Only the N vs N+1 case remains as documented Phase 1 work.

**Docs updated:** `FRONTEND.md` (signal format, handler cleanup pattern), `docs/7_ValiChord_4-DNA_architecture_technical.md` (signals table, commit-reveal flow).

---

### valichord-ui wired to live conductor — 2026-04-27 ✓
Full browser UI connected to a real Holochain conductor for the first time.

**What was built:**
- `dev.sh` — start script: launches conductor via `dev-conductor.yaml` (in-process lair, admin `:4444`), then runs `dev-setup.mjs`
- `dev-setup.mjs` — Node.js bootstrap: installs hApp with membrane-proof bypass (`0x42×64` + `authorized_joining_certificate_issuer: ''`), enables app, attaches app interface on `:8888`, issues no-expiry auth token, calls `admin.authorizeSigningCredentials()` for all 4 cells, writes `VITE_HC_TOKEN` + `VITE_HC_SIGNING_CREDENTIALS` to `.env.local`
- `holochain.ts` — reads `VITE_HC_TOKEN` (base64 → `number[]`) and `VITE_HC_SIGNING_CREDENTIALS` (base64 JSON) from Vite env; calls `setSigningCredentials` before `AppWebsocket.connect` (required by `@holochain/client` 0.20.x)
- `types.ts` → `entryFromRecord` — now msgpack-decodes the raw entry bytes returned by `@holochain/client` 0.20.x (entry is not auto-decoded; must call `decode()` from `@msgpack/msgpack`)
- Fixed two TypeScript narrowing errors in `GovernanceView.svelte` (Discipline union cast)

**Verified:** `submit_validation_request` writes to attestation DHT; `get_validation_request_for_data_hash` reads back with all fields correctly decoded. Idempotency guard (duplicate data_hash rejection) working.

**Not yet tested in a real browser:** the Node.js verification script uses the same code path as the UI. A human clicking through the form is the remaining manual step.

---

### Reputation/certification system — 2026-04-24 ✓
**4-tier `CertificationTier`**: `Provisional` → `Standard` (≥5 rounds) → `Advanced` (≥20 + rate ≥60%) → `Certified` (≥50 + rate ≥80%).
**Badge thresholds**: use raw validator count (7/5/3/3) — tier-weighted thresholds were attempted but reverted (too complex for now; revisit post-Phase 1 when real validator tiers exist).
**Production implication**: all validators stay `Provisional` until Phase 1 oracle is wired — Gold and Silver cannot be issued in production yet. Bronze remains fully functional.
**DNA hash changed**: `CertificationTier` is in `ValidatorReputation` (governance integrity) and `ValidatorProfile` (attestation integrity). Dev-only — no live network impact.
**Tests**: sweettest tests 12 + 13 in `governance.rs` verify Provisional→Standard promotion boundary.

---

## What is NOT done yet

### 1. `ANTHROPIC_API_KEY` persistent on Oracle — HIGH, 2 min fix
Currently must be manually exported each SSH session. Blocks unattended demo runs.
```bash
# SSH into Oracle and add to ~/.bashrc:
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.bashrc
```

### 2. ~~Feynman PR #23~~ — CLOSED
Feynman is no longer operational (April 2026). AI validator functionality has been rebuilt
directly against the Claude API (`demo/ai_validator.py`). No further Feynman integration work.

### 3. Rate limiting — LOW
API keys are in. No per-key rate limiting yet.

---

## Installed tools and skills (2026-04-24)

### holochain/ai-tools — `holochain-dev` Claude Code skill
Installed at `~/.claude/skills/holochain-dev/` (12 files). Activates automatically on any Holochain task.
- DNA-hash tripwire: refuses/warns on integrity changes that break the DNA hash
- Verifies every HDK/HDI API call against docs.rs at the project-pinned version (never training data)
- Serialization-boundary inversion: check stale WASM before msgpack version pins
- Sweettest-only test generation; lazy-load reference files in `references/`

Source: https://github.com/holochain/ai-tools (branch: main)

### holochain/kangaroo-electron — future desktop packaging path
Template for packaging ValiChord as a cross-platform Electron app. **Not started yet.**
Pre-requisites before we can use it: (1) ~~browser UI for ValiChord~~ **done** (`valichord-ui/` wired end-to-end), (2) Holochain 0.6.1 upgrade, (3) dedicated bootstrap/signal/relay servers (`holochain/network-services` Pulumi repo).
Branch to use: `main-0.6` (Holochain 0.6.x). Enables: validators install desktop app and run their own conductor.

Source: https://github.com/holochain/kangaroo-electron (branch: main-0.6)

### Other tools noted but not installed
- **hc-spin** (https://github.com/holochain/hc-spin) — run `.happ` files locally with multiple agents, single CLI. Potential replacement for Docker demo once 0.6.1 lands.
- **chisel** (https://github.com/holochain/chisel) — demux interleaved multi-conductor logs: `cat logs.txt | chisel tryorama demux`
- **network-services** (https://github.com/holochain/network-services) — Pulumi IaC for self-hosted Holochain bootstrap + relay servers on DigitalOcean. Needed before production kangaroo packaging.
- **hc-cooperative-content** (https://github.com/holochain/hc-cooperative-content) — multi-agent governance zomes, applicable to DNA 4.

### Unyt ecosystem tools — evaluated 2026-04-24
Three tools from https://github.com/orgs/unytco/repositories worth knowing for ValiChord's operational roadmap:
- **joining-service** — REST API for issuing membrane proofs + hApp bundles on join (`GET /.well-known/holo-joining` → `POST /v1/join`). Reference impl of ValiChord's `authorized_joining_certificate_issuer` pattern, done properly as a service. **Use when designing institutional validator onboarding for a live network.**
- **heart** — DigitalOcean + Pulumi conductor provisioning with Telegraf/InfluxDB monitoring. Goes further than network-services (bootstrap/relay only) — provisions the conductor itself. **Use when setting up production conductor nodes.**
- **tauri-plugin-holochain** — Lighter/faster Electron alternative for the desktop validator installer (Rust-based, not Chromium). Not fully open source yet (Open Collective fundraise in progress). **Revisit before building the installer; for now, kangaroo-electron remains safer.** See `memory/reference_unyt_tools.md` for full detail on each + not-relevant tools.

---

## Key technical facts for the next session

### tx5 / kitsune2 bootstrap
Holochain 0.6.0 uses tx5/WebRTC transport. Oracle uses a local `kitsune2-bootstrap-srv`
(pre-compiled binary in `demo/bin/`) on port 9000 — avoids dependency on the external
`dev-test-bootstrap2.holochain.org` relay which caused intermittent peer-discovery timeouts.
`serve.mjs` wraps `claim_study` in `_retryOnTx5()` (10 retries × 6s).

### Per-run UUID salt
`ai_validator.py` salts the data hash: `SHA-256(data_bytes + run_id)` where `run_id` is
16 random bytes. Ensures each run presents a fresh `ExternalHash` and avoids DHT
"already claimed" capacity errors on repeated runs against the same conductor.
Use `docker compose -f demo/docker-compose.yml down -v` between runs to clear conductor state if needed.

### hc-http-gw URL format (verified from source)
```
http://<host>:8090/<dna_hash>/<app_id>/<zome_name>/<fn_name>?payload=<base64url-padded>
```
- Payload = BASE64_URL_SAFE **with** `=` padding of JSON-encoded input
- For `get_harmony_record`: payload = base64url(JSON.stringify(externalHashB64))
- Response is msgpack-decoded — HoloHash fields are byte arrays, not strings

### Multi-app conductor setup
Five apps on one conductor:

| App | Network seed | `minimum_validators` | Role |
|---|---|---|---|
| `valichord-demo` | `valichord-demo` | 1 | Legacy single-validator |
| `valichord-researcher` | `valichord-demo-multi` | 3 | Researcher identity |
| `valichord-validator-1/2/3` | `valichord-demo-multi` | 3 | Validators |

Separate network seeds are required — multi-validator integrity zome rejects
`num_validators_required=1` ValidationRequest entries.

### Validator reveal — production-grade (as of 2026-04-14)
After `seal_private_attestation`, `serve.mjs` calls `get_private_attestation_for_task`
on DNA 2 to retrieve the real 32-byte nonce. This is passed to `submit_attestation`,
which verifies `SHA-256(msgpack(attestation) || nonce) == CommitmentAnchor.commitment_hash`
on DNA 3. Both sides of the commit-reveal are now fully hash-verified.

---

## Key files to read for context

| File | What it contains |
|---|---|
| `PROJECT_STATUS.md` | **This file** — current status, open work, technical facts |
| `docs/Holochain_complete.md` | Complete Holochain build guide + tx5 timing, hc-http-gw URL format, ExternalHash JS, NetworkConfig |
| `demo/DECENTRALISED_DEMO.md` | Full technical guide for the decentralised demo — architecture, retry design, commit-reveal table |
| `demo/ai_validator.py` | Python orchestrator — `--mode decentralised` calls the five node APIs |
| `demo/docker-compose.yml` | 5-container stack definition |
| `demo/researcher-node.mjs` | Node.js HTTP API for researcher conductor |
| `demo/validator-node.mjs` | Node.js HTTP API for each validator conductor |
| `demo/node-lib.mjs` | Shared helpers: `withSession`, `retryOnTx5`, `loadHcClient`, `externalHashFromB64` |
| `backend/app.py` | Flask REST API |
| `docs/INTEGRATION_GUIDE.md` | REST API integration guide |
| `valichord-ui/FRONTEND.md` | Screen-by-screen UI walkthrough — all three roles |
| `valichord-ui/src/lib/` | Svelte components: ResearcherView, ValidatorView, GovernanceView, types.ts, holochain.ts |
| `docs/7_ValiChord_4-DNA_architecture_technical.md` | Four-DNA architecture |
| `valichord/wind-tunnel/` | Wind-Tunnel load-test workspace — 3 performance scenarios (write throughput, phase latency, reveal throughput) |

---

*This file is the single catch-up document for new Claude sessions. Read it before responding to any questions about project status, Feynman integration, or what to demo.*
