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

## Upgrade status and standing rules

> **Full history of the 0.6.2 → 0.7.0 migration — the pre-release research, the verified/corrected
> claim tables, the FlatOp rename detail, the conductor-config diffs, the API audit and the branch
> watch — moved to [`docs/HOLOCHAIN_UPGRADE_RECORD.md`](docs/HOLOCHAIN_UPGRADE_RECORD.md) on
> 2026-08-25.** It was 64% of this file, describing a migration that is done. Read it when planning
> the next major bump. `docs/Holochain_complete.md` §44 is the observed record of the port itself
> and supersedes anything there that disagrees.

### Where things actually are

- ✅ **`main` is on Holochain 0.7.0** (merged 2026-08-03, `38ea2123`).
- 🔴 **The Oracle demo host still runs 0.6.2.** `main` and the live public demo therefore
  describe **different stacks** until Oracle is rebuilt — a full rebuild with state loss, not an
  upgrade. Every previously published HarmonyRecord URL is already dead (accepted). See
  `docs/ORACLE_0.7.0_UPGRADE.md`, which also records that the host has **no reachable shell**
  (SSH key lost at creation).
- ⚠️ **Be careful about public claims until Oracle is rebuilt** — the README describes what
  `main` is, which is not what the demo runs.
- **Wind-tunnel builds on 0.7** by pinning the runner to a git **rev** of `holochain/wind-tunnel`
  (`e4861457`), not the crates.io release. CI job is enabled.

### Two standing rules for any future major version

1. **Do NOT auto-upgrade.** Migration is deliberate and planned.
2. **MIGRATION IS BRANCH-ONLY.** A major change happens on a dedicated branch, never directly on
   `main`, and `main` keeps the working publicly-demoed stack until that branch is fully green
   **and** the user explicitly approves the merge. Superiority does not make a broken intermediate
   state acceptable. Core is paranoid — see `user_role` in memory.

### 🔴 Three live watch items

**1. `#5288` — `get_agent_activity` returns an empty response when the only known peers are local.**
Still *Awaiting clarification* upstream (re-checked from the roadmap board 2026-08-24). **This one
touches our code.** `reject_if_warranted` reads an empty response as *"no warrants"*, so the gate
**fails OPEN** — the wrong direction. "Only local peers" describes every sweettest run, the Docker
demo stack, and any freshly-bootstrapped network. Three call sites share the pattern:
`attestation_coordinator:637`, `governance_coordinator:188`, `governance_coordinator:367`.
⚠️ **Do not cite the warrant gate as a safety property without checking this first.**

**2. Source-chain restore — in 0.7.1, and moving.** `#5800` (end-to-end workflow) and `#5802`
(integration test suite) are both **In Progress**. ⚠️ **Restore does NOT recover private entries.**
`ValidatorPrivateAttestation` (DNA 2) and `LockedResult` (DNA 1) are private, so a validator who
loses their machine mid-round loses their sealed attestation **silently**. This stops being
theoretical the release restore actually ships in. The `AppStatus::AwaitingRestore` /
`RestoreComplete` UI work in the record file reactivates at that point.

**3. 0.7.1 itself is not close.** Both release tickets (`#5932` rc.0, `#5933`) were still only
*Ready for refinement* on 2026-08-24.

### 🟢 Do not investigate `holochain-0.8.0-dev.0` again

It appeared 4 days after 0.7.0 and looks alarming. It is **empty** — three commits past the 0.7.0
tag, every per-crate changelog section blank. `147019b1` *"Switch to dev releases for 0.8"* simply
reopens the next line so later merges cut `0.8.0-dev.N` rather than `0.7.1`. **A `-dev.N` tag with
an empty changelog is routine line-opening.** Judge 0.8 by commits on `develop`, never by a dev tag.

### CI binary upgrade (any Holochain version bump)

Update **6** places in `.github/workflows/tests.yml` — 3 jobs (`test`, `sweettest`, `ui-e2e`) ×
(`BASE=…/releases/download/holochain-X.Y.Z` + `key: …-hc-bin-X.Y.Z`). Verify the binary names exist
on the release before pushing.


## Ecosystem tool notes

- **Unyt joining-service** — REST membrane-proof onboarding; reference impl for institutional validator onboarding on a live network. See `memory/reference_unyt_tools.md`.
- **Unyt heart** — Go/Pulumi **fleet** deployer (one stack per release; `progenitor` + `notary` node types). Use when setting up production nodes. Note `cloudinit/cloud-config.yaml` hardcodes **`target_arc_factor: 1`** (every node full-arc) — the concrete "kitsune2 #160 in production" artifact.
- **Unyt migration-service** — working `close_chain`/`open_chain` DNA-migration pipeline. **Read in full 2026-07-27 → `docs/DNA_MIGRATION_PRIOR_ART.md`, which is the answer to "can we carry data across the 0.7 DNA-hash change?"** Verdict: **no — accept the reset and republish.** It carries an agent's own source chain, not the DHT, so it saves no published HarmonyRecord URL; it cannot touch DNA 1/DNA 2 (single-agent, no notaries); and we have no carried state to summarise. **CAL-1.0 — design source, don't copy code.** Read it for `policy.rs` (the algorithm `select_validators()` needs) and the `[MIGERR:<CODE>]` typed-error pattern.
- **Unyt tauri-plugin-holochain** — lighter Electron alternative (not yet open-source); revisit before building the validator desktop app.
- **kangaroo-electron** (`holochain/kangaroo-electron`, branch `main-0.6`) — cross-platform Electron packaging. Full plan: `docs/KANGAROO_PACKAGING_PLAN.md`. Remaining blockers: dedicated bootstrap/relay servers.
