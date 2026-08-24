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

### ~~Tryorama integration tests~~ — RETIRED 2026-08-03, do not resurrect

`valichord/tests/` is **deleted**. Upstream `@holochain/tryorama` is unmaintained — a banner landed Jan 2026 saying Holochain 0.7+ support *"should not be expected"*, pointing at sweettest. There is nothing to migrate to, and porting to a dead runner would have been work with a known expiry date.

**It was audited before it was deleted, one test at a time** — ~69 of its 92 were already duplicated in sweettest, and every unique test was ported and run green FIRST. That audit is the reason this was not a silent loss: it found **three guards with no working coverage at all**, each now covered by a test that has been *seen to fail*:

- the **conflict-of-interest** guard — its test ran on one conductor, so the self-claim guard rejected the claim first and the COI comparison was never reached
- **DNA 2's cross-agent privacy** — no test anywhere asked whether a *second* agent could read a sealed private attestation
- **`link_agent_identity`'s two signature checks** — the existing test passes 64 zero bytes and says so in its own body

Deliberately NOT ported: the `FailedReproduction` / `Divergent` badge variants. That arithmetic has 27 unit tests in `shared_types`; an integration test would re-prove it at ~30 min a run.

⚠️ **If you are tempted to re-add a TypeScript integration suite, read `docs/Holochain_complete.md` §44 first.** The lesson of this retirement is not "TypeScript bad" — it is that a suite nobody can run becomes a place where fake tests accumulate unseen. Eleven of them were found across two culls, several inside the long-quoted "97 passing".

### Immutability tripwire tests (REQUIRED before/after any `validate()` refactor)

The only tests that prove the **integrity zomes** reject forbidden updates. They need a special build, because no production coordinator exposes `update_entry`.

```bash
cd valichord
./build-test-dnas.sh                       # builds --features test_utils -> target-test/, packs -> workdir-test/
cd sweettest_integration
VALICHORD_DNA_DIR=../workdir-test cargo test --test immutability_tripwire -- --test-threads=1
# 15 tests (5 update + 10 delete), ~50 min (each scenario JIT-compiles ~30 MB WASM)
#
# ⚠️ HC_BIN is REQUIRED on the v0.7.0 branch: build-test-dnas.sh packs with `hc`
# from PATH, which is deliberately still 0.6.2 here. Pack with the same version
# workdir/ was packed with, or the test bundles differ from production for a
# reason unrelated to the code under test:
#   HC_BIN=/path/to/hc-0.7.0 ./build-test-dnas.sh
#
# ⚠️ Run via ./run-sweettest.sh, NOT a hand-rolled `| grep -v sqlcipher_mlock`.
# ENOMEM spam splices into the MIDDLE of a `test <name> ... ok` line, so an
# exclusive filter deletes the result. Observed 2026-08-01: a real run reported
# "10 passed" with only 4 result lines surviving. run-sweettest.sh cross-checks
# named results against the summary and fails on a mismatch.
```

**Run these before AND after the 0.7 `FlatOp` migration.** They are the only thing standing between a mechanical arm-reflow and silently losing immutability.

**Proven to work — negative control, 2026-07-30.** Moving the `ValidationAttestation` guard behind the generic `OpUpdate::Entry { action, .. }` arm (exactly the accident a `FlatOp` rename can cause) made the forbidden update **succeed** — it returned a real `ActionHash`, because it fell through to the generic arm whose author-check passes for the entry's own author. The tripwire test failed as designed; restoring the guard turned it green. **The hazard is real and the wire is connected.**

**Second negative control, 2026-08-03 — the governance delete guards.** Deleting the `GovernanceDecision` arm from `governance_integrity`'s `FlatOp::Delete` match made the forbidden delete **succeed with a real `ActionHash`** (`uhCkkxGoGL6xkAzvDjE7aNnrA2ajzzZWHaXaX0OV-NoNOZ1yFwcUo`) — it fell through to "only the original author may delete", which the author passes by definition. `governance_decision_delete_is_rejected` failed; restoring the arm turned it green. ⚠️ **These three guards (HarmonyRecord / GovernanceDecision / ReproducibilityBadge) had NO test that could fail until this date.** What looked like coverage were three Tryorama tests asserting only that *"no delete function exists in the coordinator API"* — an API-surface check that passes identically against a DNA with no guards at all, and which was about to be deleted along with that suite. Found by reading every test in Tryorama before retiring it, not by any automated check.

⚠️ **Partial compiler safety net, do not rely on it.** `rustc` *does* emit `warning: unreachable pattern` when a specific arm is moved behind a broader one. But it is a **warning, not an error**, in a build that emits others — and it catches **only** the shadowing case. It will NOT catch an arm that is deleted outright, or one whose pattern stops matching after a variant rename. The tests catch all three.

**Safety design** (these hooks must never ship):
- `#[cfg(feature = "test_utils")]` externs in **all 4** coordinators — absent from every production build
- feature build → `target-test/` (separate target dir, cannot overwrite `target/`)
- packs → `workdir-test/` (never the committed `workdir/`)
- `test-dnas/*/dna.yaml` point their **integrity** zome at the *production* build and only the **coordinator** at `target-test/` — so the integrity zome under test is byte-identical to what ships
- `./check-no-test-hooks.sh` scans the committed production bundles for the **`test_force_` prefix** and fails if found. ✅ **Wired into CI** as the `no-test-hooks` job (dependency-free, ~seconds, fails fast ahead of the 90-minute matrix). Verified in **both** directions: passes on `workdir/`, and `NEEDLE_SCAN_DIR=workdir-test ./check-no-test-hooks.sh` correctly **fails** on **all four** bundles. ⚠️ Until 2026-08-03 governance had no hooks and *passed* that check; it now fails it, which is the negative control proving the guard sees newly-added hooks rather than only the ones it was written for.
  ⚠️ **The needle is a prefix, not a name — do not narrow it back.** It was `test_force_update` until 2026-08-01, when delete hooks were added and it would silently have ignored `test_force_delete_entry`: a guard that only catches the hooks existing when it was written has an expiry date nobody is told about. Matching the naming convention covers future hooks the day they are written. Verified with the needle narrowed to `test_force_delete` alone — fails on `workdir-test/`, passes on `workdir/` — so it demonstrably sees the new hooks, not just the old ones.
  ⚠️ **It must decompress before searching — do not "simplify" it back to `grep`.** The first version grepped the bundle files directly and reported "clean" for *everything*, including bundles that definitely contained the hooks: Holochain bundles are compressed, so the symbol names are never in the raw bytes (`*.dna` = one gzip layer; `*.happ` = gzip → msgpack → nested gzip, so two). It was a guard that could not fail. Re-run the two-direction check above after any edit to that script.
- `target-test/` + `workdir-test/` are gitignored

**Assertion discipline — never weaken this.** Every test asserts on the *specific rejection message the guard emits* (`"ValidationAttestation is immutable"`, `"Private entry updates not supported"`), never a bare `is_err()`. Three earlier "immutability" tests were deleted on 2026-07-30 because they asserted `is_err()` against zome functions that did not exist — they passed on "function not found" and would have stayed green with `validate()` deleted entirely.

**Coverage is shaped by the entry-visibility split** (verified against shipped `hdi 0.8.0`): private entries can never match `OpUpdate::Entry`, only `OpUpdate::PrivateEntry`.
- `attestation` (public) — per-type arms are live, ordering matters → 3 per-type tests
- `validator_workspace` / `researcher_repository` (all private) — per-type arms are dead code; **one blanket `OpUpdate::PrivateEntry` arm is the entire guard** → 1 test each, aimed at that arm

### Unit tests (conductor-free, <1 s) — and the `tail` trap

```bash
cd valichord
cargo test -p valichord_shared_types    # 27 — badge/agreement arithmetic
cargo test -p governance_coordinator    #  3 — validator_attestation_pairs
```

Run by the `unit` CI job. They cover `evaluate_badge`, `derive_agreement_level` and
`derive_majority_outcome` — the arithmetic every HarmonyRecord's badge tier rests on, and a
HarmonyRecord is immutable, so a wrong tier is wrong permanently.

⚠️ **`cargo test … | tail -5` USED TO LIE, and both crates now set `doctest = false` to stop it.**
Cargo prints one result block per test binary and doc-tests come **last**, so with no doc examples
the final block reads `running 0 tests` / `test result: ok. 0 passed` while the real result sits
one block earlier. Observed 2026-08-03: I read the tail and concluded the 27 tests did not exist.
`doctest = false` removes the trailing block, so the last line is now the true one.

**Do not delete those two `doctest = false` lines as tidying** — re-enable them only alongside a
real doc example, and expect the trap to return when you do. If a crate ever legitimately needs
doc-tests, the durable fix is the `run-sweettest.sh` pattern: extract **every** `test result:` line
and cross-check the sum, rather than reading the last one.

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

# 608 tests, 97% line coverage (1114 statements, 33 missed).
# measured 2026-08-22, CI run 32598696410, identical on Python 3.10 and 3.13.
# CI measures coverage on every push touching valichord_attestation/**, so
# re-derive the figure from a run rather than quoting this comment.
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

⚠️ **Before designing ANY connection between `valichord_attestation` (or any outside system) and
the protocol, read `docs/PROTOCOL_INTEGRATION_BOUNDARY.md`.** Four normative preconditions; an
integration that cannot meet all four must not be built. Short version: no new entry/link types or
integrity-zome changes (DNA hash break = separate network = every published record URL dies), no
payload parsing inside an integrity zome (`validate()` runs on every node holding the op, so
attacker-shaped input is a network-wide validation bomb), no payload content on a public DHT
(permanent, unredactable, and `Bundle.meta` is free-form), and every crossing value declared
**asserted** or **observed** with the enforcing layer named — otherwise both layers defer to each
other for the same guarantee and neither provides it.

**Known protocol gaps: `docs/protocol-backlog/`** — the protocol-side counterpart of
`valichord_attestation/spec/format-backlog/`, created 2026-08-22 because the protocol had no place
to record known-missing things and two gaps surfaced in conversation that would otherwise have been
lost. **It is deliberately only for changes that get more expensive with time:** 🟠 anything
needing an entry/link type (free if it rides the Oracle rebuild's DNA-hash change, a second network
break if it lands after) and 🔴 anything determining what an immutable record *says*
(records written before the fix stay wrong forever). 🟢 Cheap-forever items do not belong
there.

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
| `merkle.py` | construction selection by `format_version`; wrappers for `merkle_root`, `merkle_proof`, `root_from_path`, `verify_faithfulness` |
| `merkle_v1.py` | **frozen** v1 construction — bare pair hashing, odd levels padded by duplication. Kept so v1.x bundles stay verifiable. Do not "fix" its known weaknesses here |
| `merkle_v2.py` | current construction — RFC 6962 §2.1 |
| `challenge.py` | Probabilistic challenge generation (HMAC-SHA256 seed, SHA-256 counter-mode PRNG) |
| `response.py` | `build_response`, `verify_response` — Merkle-path selective disclosure |
| `adapters/` | `AdapterBase` ABC; `InspectAILogAdapter` (reads `.eval` files); `InspectEvalsAdapter` |

**Format version: v2** (since 2026-08-18; `build_bundle` writes `"v2"`, package 2.0.0). Bundles have a `bundle_hash` (full content) and `content_hash` (excludes `Bundle.meta` provenance block). v1/v1.1/v1.2 bundles remain valid and are **not** rewritten.

**v2 changed the Merkle construction and nothing else** — RFC 6962 §2.1, adopted whole: `0x00`/`0x01` leaf/node domain separation, odd subtrees promoted rather than duplicated, empty and single-leaf cases defined. Every other part of `spec/attestation_format_v1.md` (fields, JCS encoding, both hashes, challenge-response, threat model) still applies. Spec: `spec/attestation_format_v2.md`.

⚠️ **When verifying, pass the bundle's own `format_version`** — never inherit the library default. A root is 64 hex chars under every version, so checking a v1.2 root under v2 returns *does not verify*, indistinguishable from tampering. `construction_for()` raises `UnknownFormatVersion` rather than guessing. This bit three call sites during the v2 release; assume it will bite again.

**Open format backlog: `spec/format-backlog/`** — seven candidate additions raised by outside
implementers, each naming who raised it and when. Not version-named on purpose: `spec/v2-backlog/`
closed when its items shipped and new findings had nowhere to go. ⚠️ `Bundle.meta` is the obvious
home for judge configuration / rubric versions and the **wrong** one — `meta` is excluded from
`content_hash`, so two runs scored by different judges would compare as equivalent.

Conformance vectors: `tests/vectors/merkle_v1_2.json` (+ `_odd_node`) and `merkle_v2.json`. The v1.2 files are **frozen** — they are the evidence old bundles still verify. A new version adds a file, never edits these.

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

### CI triggers — two ways to silently run nothing (both cost time on 2026-08-22)

- ⚠️ **Never write the skip token in a commit message, not even to say you are NOT using it.**
  GitHub matches the literal string **anywhere** in the message, not just the first line. A merge
  commit whose body read *"pushed deliberately without [skip ci]"* skipped both workflows. The
  explanation performed the thing it denied. Refer to it obliquely — "the skip token" — or not
  at all.
- ⚠️ **An empty commit cannot trigger a path-filtered workflow.** `attestation.yml` runs only on
  changes under `valichord_attestation/**`, so `git commit --allow-empty` fires the unfiltered
  90-minute matrix and **not** the 25-second job you wanted. To run that one without a code change,
  use **Actions → Attestation Format → Run workflow** in a browser. ⚠️ `gh workflow run` returns
  **HTTP 403** from a Codespace — the injected `GITHUB_TOKEN` can read runs but not dispatch them.


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

> 🌿 **PHASE A OF THE 0.7 MIGRATION IS DONE AND CI-GREEN (2026-08-01, `v0.7.0` branch).**
> Everything below was written *before* the port, from indirect sources. The observed record —
> what actually happened when the code was migrated — is now **`docs/Holochain_complete.md`
> §44**, and it **supersedes anything here that contradicts it.** Three claims below were
> already corrected by the port: `attestation` has **9** per-type guard arms not 12; the
> "confirmed ZERO" audit table never grepped the **coordinators**, where three real `Action::`
> sites lived; and the prescribed `sweettest_integration` dep line **would be a regression**
> if applied as written. Keep this section for **Phases B and C**, which have not started.

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
2. **MIGRATION IS BRANCH-ONLY — `main` STAYS ON 0.6.2.** User decision, 2026-07-30: this is a major change and must happen on a dedicated **`v0.7.0` branch**, never directly on `main`. `main` keeps the working, publicly-demoed 0.6.2 stack until the branch is fully green (all sweettest suites + UI e2e + a live demo round — Tryorama was retired 2026-08-03 and is no longer a gate) **and** the user explicitly approves the merge. 0.7.0 being superior does not make a broken intermediate state acceptable. See `user_ceri_working_style` — core is paranoid.

### 🔴 BLOCKER: the JS/tooling ecosystem has NOT shipped — the migration is TWO-PHASE

Checked 2026-07-30, ~15 min after the release:

| Package | latest (stable) | next |
|---|---|---|
| `@holochain/client` | **0.20.8** | `0.21.0-rc.1` |
| `@holochain/tryorama` | **0.19.2** | *no 0.7 line at all* |
| `@holochain/hc-spin` | **0.603.0** | `0.700.0-rc.1` |
| holonix | *no `main-0.7` branch* | only `update-to-0.7.0-rc.0` |
| docs-pages upgrade guide PR #647 | open, last updated **07-28** (pre-release) | — |

**Consequence (as written 2026-07-30): the Tryorama suite and the Svelte UI could not migrate yet.** ✅ Both are resolved: the UI shipped on `@holochain/client` 0.21.0 (2026-08-02), and Tryorama was **retired** rather than migrated (2026-08-03) — see the retirement note above.

⚠️ **Any quoted "97 / 92 Tryorama tests" figure is dead — the suite is gone (2026-08-03).** For the record of why the number kept moving: six declarations were culled in `cc19e8c4` as fakes passing on *"function not found"*, taking 98 → 92, and the "97 passing" quoted for months was never reconciled against the source. Current counts live in `TESTING.md`, derived from the source rather than remembered.

**🟠 AND A THIRD BLOCKER — `wind-tunnel` (found in the 2026-07-30 API audit).** `valichord/wind-tunnel/` depends on **`holochain_wind_tunnel_runner`**, a third-party crate that pulls `holochain = "0.6"`. ⚠️ **PARTLY RESOLVED 2026-08-03 — upstream `main` migrated to 0.7 on 07-31; only the crates.io release is missing. See "Phase C — the upstream migration is FINISHED" below before treating this as blocked.** Independent of both the zomes and the JS side.

**So the migration is THREE phases, two of them blocked on upstream:**

| Phase | Scope | Status |
|---|---|---|
| **A** | 4 DNA zomes + `sweettest_integration` | ✅ **unblocked — can start now** |
| **B** | Svelte UI | ✅ done 2026-08-02 — 6/6 e2e green on a real 0.7 conductor |
| **B** | ~~Tryorama tests~~ | ✅ resolved 2026-08-03 by **retiring** the suite, not migrating it |
| **C** | `wind-tunnel/` | 🟠 **upstream work is DONE, awaiting a crates.io release** — see below |

Re-check the table above before starting Phase B, and crates.io for `holochain_wind_tunnel_runner` before Phase C.

### ✅ Wind-tunnel builds on 0.7 — fixed 2026-08-03 (Phase C is further along than the note below)

⚠️ **The Phase C note below is now partly superseded.** `valichord/wind-tunnel/` **builds and
its unit tests pass on the 0.7 stack**, by pinning the runner to a git **rev** of
`holochain/wind-tunnel` (`e4861457`, their "Update to Holochain 0.7.0" commit) instead of the
crates.io release. Verified: `cargo build` clean in 3m40s, `cargo test -p dht_sync_lag` 4
passed. CI job re-enabled.

🆕 **The merge to 0.7 broke this workspace, and the "blocked upstream" note is why it was
missed.** Phase C was recorded as "not a merge blocker — the load tests were untouched".
Untouched was true; **unaffected was not.** The scenarios depend on `valichord_shared_types`
**by path**, so migrating that crate to `hdi 0.8.0` (→ `holo_hash 0.8`) collided with the
crates.io runner's holochain 0.6 (→ `holo_hash 0.6`):

```
error[E0308]: expected `HoloHash<External>`, found `HoloHash<holo_hash::hash_type::External>`
note: there are multiple different versions of crate `holo_hash` in the dependency graph
```

⚠️ **Rule: before any version bump, check every workspace with a PATH dependency on the crate
being bumped — not just the ones being changed.** A separate Cargo workspace is isolated for
*compilation targets*, not from your own source.

**Four more layers sat behind the first**, each hidden by the one in front:
1. Direct `holo_hash = "0.6"` / `holochain_types = "0.6"` pins in five scenario manifests —
   a 0.7 runner alone would still have dragged the old `holo_hash` back in.
2. `ed25519 = "=3.0.0-rc.4"` / `pkcs8 = "=0.11.0-rc.11"` — held for kitsune2 0.4.x's
   pre-release iroh stack. kitsune2 0.5.0 → iroh 1.0.0 wants final `ed25519 ^3`, so the pins
   became the blocker. ✅ **Their comment named its own expiry condition** ("revisit when the
   iroh stack moves to a non-pre-release ed25519-dalek"), which turned an afternoon into five
   minutes. **Write pins that way.**
3. `YamlProperties::new` takes `yaml_serde::Value` on 0.7, not `serde_yaml::Value` — the same
   swap `sweettest_integration` made in Phase A.
4. `ValidationAttestation` needed `reproduction_bundle_hash` (validator→bundle binding). Set
   to `None` — an unbound verdict, correct for a load test that performs no reproduction.
   ⚠️ Safe only because the scenario uses the dev bypass (`commitment_hash = [0u8; 32]`,
   empty nonce). **With real nonces this field is bound into `commitment_msgpack_bytes()`
   and must be byte-identical at commit and reveal, including `None`.**

### 🟠 Phase C — the upstream migration is FINISHED; only the release is missing (checked 2026-08-03)

**`holochain/wind-tunnel` `main` migrated to Holochain 0.7.0 on 2026-07-31** — the day after 0.7.0
stable, via `feat: Update to Holochain 0.7.0` (preceded by rc.1 on 07-17 and rc.3 on 07-28). `main`
now pins `hdk 0.7.0`, `hdi 0.8.0`, `holochain_types 0.7.0`, `holochain_client 0.9.0`,
`kitsune2 0.5.0` — our exact stack. The repo is active (pushed 2026-08-03).

**But it is NOT published.** Latest on crates.io is `holochain_wind_tunnel_runner` **0.7.1, dated
2026-07-21** — *ten days before* the migration — and it still pins `holochain_types ^0.6.3` and
`kitsune2_api ^0.4.1`.

⚠️ **VERSION-NAME TRAP, AND WE ARE INSIDE IT.** Our scenarios declare
`holochain_wind_tunnel_runner = "0.7"` (all five: `valichord_wt_common`,
`validation_request_throughput`, `phase_observation_latency`, `concurrent_reveal_throughput`,
`dht_sync_lag`; plus `kitsune_wind_tunnel_runner = "0.7"` in `kitsune_dht_propagation`).
**The crate's own 0.7.x has nothing to do with Holochain 0.7 — 0.7.1 is a Holochain *0.6* runner.**
This is the inverse of the trap already recorded above ("never infer *not published* from a crate
version that trails the release name"): here, do not infer *already migrated* from a crate version
that matches it. Reading `= "0.7"` and concluding Phase C is fine would be wrong.

**So Phase C is blocked on a RELEASE, not on development.** Two routes when it is wanted, neither a
merge blocker:
1. Wait for their next crates.io release (they cut them periodically — look for `chore: Prepare
   next release` on `main`).
2. Point the scenarios at the git repo pinned to a **rev** rather than a branch. Unblocks
   immediately; cost is a non-published dependency.

🆕 **Unrelated to the migration but worth a look:** branch `214-mixed-full-arc-and-zero-arc-scenarios`
and **issue #214 *"Mixed full arc and zero arc network scenarios"* (CLOSED, follows on from #161)**.
Its framing is close to the polite-shrink thesis — *"a network with many zero arc conductors,
supported by a smaller number of full arc conductors… what we don't know is how hard the full arc
conductors will have to work to carry the validation load"*. ⚠️ The branch's last commit is
**2025-10-07**, so the scenario work stalled even though the issue closed. Relevant to the #160
outreach, not to this migration — see `project_arc_sim_windtunnel_plan` in memory.


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

### 🗺️ What is actually in 0.7.1 — read from the roadmap board, 2026-08-03

Source: `holochain` org **project 11**, roadmap slice *"Holochain 0.7.1"* — **13 items** (against
117 for 0.7, so a stabilisation release, not a breaking one). Needs the `read:project` scope:
`GITHUB_TOKEN= gh auth refresh -s read:project --hostname github.com`, then
`GITHUB_TOKEN= gh project item-list 11 --owner holochain --limit 2000 --format json`.

**🔴 SOURCE-CHAIN RESTORE IS IN 0.7.1 AND IN PROGRESS.** This supersedes the inference above that
it would land in "a later 0.7.x":
- **#5800** *Source chain restore: end-to-end restore workflow* — **In Progress** (this is PR #5920)
- **#5809** *Source chain restore: per-app orchestrator and conductor wiring* — **Ready**

⚠️ So the `AppStatus::AwaitingRestore` / `RestoreComplete` checklist items recorded above as **DEAD
for 0.7.0 are alive for 0.7.1**, and the private-entry loss stops being hypothetical:
`ValidatorPrivateAttestation` (DNA 2) and `LockedResult` (DNA 1) are **not recovered by a restore**.
A validator who loses their machine mid-round loses their sealed attestation silently.

**🟠 #5288 — `get_agent_activity` returns an empty response when the only known peers are local**
(*Awaiting clarification*). **This is the one that touches our code.** `reject_if_warranted`
(`attestation_coordinator/src/lib.rs:636`) does:

```rust
let activity = get_agent_activity(agent, …, GetOptions::network())?;
if !activity.warrants.is_empty() { return Err(…"outstanding warrants"…) }
```

An empty response therefore reads as **"no warrants" → allowed**: the gate **fails OPEN**, which is
the wrong direction. "Only local peers" describes every sweettest run, the Docker demo stack, and
any freshly-bootstrapped network. Three call sites share the pattern — `attestation:637`,
`governance:188`, `governance:367` (⚠️ the older note in this file said `:322`; that line has moved).
Not confirmed to affect us — the upstream bug is still awaiting clarification — but **do not cite
the warrant gate as a safety property without checking this first.**

**Also in 0.7.1, context only:** **#5781** *[CRITICAL] validation receipts accepted without
receive-side signature verification* (*Awaiting clarification*) — Holochain's own machinery, and we
never read receipts. Eight of the thirteen items sit under one epic, *Data Model Consistency*.

### 🟢 `holochain-0.8.0-dev.0` (2026-08-03) is EMPTY — do not investigate it again

It appeared on the GitHub feed 4 days after 0.7.0 stable and looks alarming. It is not. Verified
against the release, the consolidated CHANGELOG, four per-crate CHANGELOGs and the commit list:

- **Three commits past `holochain-0.7.0`**, in full: `29256467` *Format toml files*, `147019b1`
  *chore: Switch to dev releases for 0.8*, `390835a4` *create a release from branch …*.
- **Every `0.8.0-dev.0` changelog section is blank** — `hdi`, `hdk`, `holochain`,
  `holochain_conductor_api`. Not small: empty.
- `develop` is only **6 ahead** of 0.7.0; the rest is a crates-io source refresh and release-branch
  merges. **Nothing functional has landed since 0.7.0.**

🆕 **`147019b1` is the counterpart of the `d1ec5a72` tell recorded above, and worth knowing as a
pair.** `d1ec5a72` flipped the crates `!pre_minor rc` → `minor`, which is what makes the automation
cut a stable minor — the "stable is imminent" signal. `147019b1` flips them back to
`!pre_minor dev`, opening the next line so later merges cut `0.8.0-dev.N` rather than `0.7.1`.
**A `-dev.0` tag with an empty changelog is routine line-opening, not a preview of anything.**
Judge 0.8 by commits on `develop`, never by the existence of a dev tag.

Version numbers to expect whenever 0.8 does acquire content: **`hdi` 0.8.0 → 0.9.0**, **`hdk`
0.7.0 → 0.8.0**, Rust **`holochain_client` 0.9.0 → 0.10.0**.

⚠️ **Re-checked 2026-08-03: PR #5920 (source-chain restore) is still `OPEN`, `draft`,
`CONFLICTING`, last touched 2026-07-30T17:33Z** — about an hour after 0.7.0 shipped, and untouched
since. It did not slip into 0.8 either. The private-entry-loss risk for validators stays
theoretical for now.

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
