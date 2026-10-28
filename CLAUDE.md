# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Always read at session start
- `PROJECT_STATUS.md` — current project phase, what's live, open work, **and installed tools/skills**
- `docs/Holochain_complete.md` — complete Holochain Build Guide knowledge base
- `docs/7_ValiChord_4-DNA_architecture_technical.md` — four-DNA architecture

## Installed Claude Code skills
- `~/.claude/skills/holochain-dev/` — official Holochain skill (installed 2026-04-24 from https://github.com/holochain/ai-tools) **in the Codespace**. ⚠️ **Not present on the Windows machine** (checked 2026-10-17) — do not assume it is loaded there. A separate `upgrade-holochain-0.7` skill was added to the same repo 2026-08-06. Activates on any Holochain task. Provides: DNA-hash tripwire, docs.rs API verification, serialization-boundary inversion, sweettest-only tests. Lazy-load topic files from `references/` inside the skill. See `PROJECT_STATUS.md` → "Installed tools and skills" for full tool inventory.

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

# Pack DNAs and hApp for local runs (repack after any source change)
hc dna pack dnas/attestation            -o workdir/attestation.dna
hc dna pack dnas/researcher_repository  -o workdir/researcher_repository.dna
hc dna pack dnas/validator_workspace    -o workdir/validator_workspace.dna
hc dna pack dnas/governance             -o workdir/governance.dna
hc app pack .                           -o workdir/valichord.happ
# The demo nodes (Docker stack and Oracle) load these two, not valichord.happ:
hc app pack researcher                  -o workdir/researcher.happ
hc app pack validator                   -o workdir/validator.happ
```

**`pack_dna.py` was deleted on 2026-10-27** — it was broken (it embedded the same DNA bytes for all four roles). Do not restore it from git history; always pack with `hc`.

All three `.happ` files in `workdir/` are committed, and **only the Repack bundles workflow**
(`.github/workflows/repack-bundles.yml`) may refresh them — a local pack has a different DNA hash
(see Hard constraints). The commands above overwrite them in your working tree, which is fine for
sweettest, the UI and a local Docker demo; run `git checkout -- workdir/*.happ` before committing.

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

Four **forgery** tests share that build and ride the same CI `tripwire` job, 1 test each:
`harmony_record_forgery.rs` (#11 — peers refuse a HarmonyRecord its signed attestations do not back)
and `validator_tier_forgery.rs` (#8 — peers refuse a self-assigned `certification_tier`), both since
#47 (2026-10-18); `reveal_phase_forgery.rs` (#51/#53 — peers refuse a RevealOpen marker that does not
list the whole cohort, and a researcher reveal that does not name its own request and commitment;
#55) and `supersession_forgery.rs` (backlog 01 — peers refuse a supersession link made in a role its
author does not hold; #57), both since 2026-10-19.

```bash
cd valichord
./build-test-dnas.sh                       # builds --features test_utils -> target-test/, packs -> workdir-test/
cd sweettest_integration
VALICHORD_DNA_DIR=../workdir-test cargo test --test immutability_tripwire --test harmony_record_forgery --test validator_tier_forgery --test reveal_phase_forgery --test supersession_forgery -- --test-threads=1
# 15 tripwires (5 update + 10 delete) + 4 forgery — the same five binaries the CI job runs.
# Over an hour: CI took ~90 min on 2026-10-19 even before supersession_forgery was added, and its
# job timeout is 150 min (each scenario JIT-compiles ~30 MB WASM)
#
# ⚠️ Pack with the same `hc` version workdir/ was packed with (0.7.1 since 2026-10-17), or the
# test bundles differ from production for a reason unrelated to the code under test.
# build-test-dnas.sh uses `hc` from PATH; override with HC_BIN=/path/to/hc ./build-test-dnas.sh.
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
cargo test -p valichord_shared_types    # 35 — 27 badge/agreement arithmetic, 4 certificate tier grants, 3 commitment encoding, 1 hardware digest
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
cargo test --test membrane_proof     # the only suite NOT on the dev bypass

# Single test by name
cargo test --test governance silver_badge_issued_with_five_validators -- --test-threads=1
```

Prefer `../run-sweettest.sh <suite>` for any run whose result you will report (see the `tail`/`grep -v` traps above). Counts (2026-10-27, from source): attestation 30, governance 22, researcher_repository 17, validator_workspace 13, security 12, membrane_proof 6 — plus the 19 tripwire/forgery tests.

`sweettest_integration` is deliberately outside `valichord/Cargo.toml` because it depends on `holochain = "=0.7.1"` (native binary), which cannot compile to `wasm32-unknown-unknown`. Merging it into the workspace would break the WASM build.

### valichord_attestation: moved out

The Python attestation library now lives in its own repository,
**[ValiChord/valichord-attestation](https://github.com/ValiChord/valichord-attestation)** (moved
2026-10-19 with its history). Build and test it there. Only redirect stubs remain in
`valichord_attestation/` here.

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

**Since 2026-10-19 it is a separate repository: [ValiChord/valichord-attestation](https://github.com/ValiChord/valichord-attestation)** (moved partly so that no reviewer, human or AI, mistakes it for the product). `valichord_attestation` is a standalone Python library for generating cryptographic attestation bundles from AI evaluation runs (inspect_ai logs, lm-eval outputs, etc.). It is **not** an equivalent or alternative to ValiChord proper — it is currently independent, and is intended to become the *client-side on-ramp* once wired to ValiChord proper's DHT: a researcher generates a bundle, submits it to the Holochain protocol, and the commit-reveal verification applies to AI benchmark results.

Rules:
- When describing ValiChord's architecture → talk about the 4 DNAs, commit-reveal, Holochain. Do NOT describe attestation bundle formats.
- When asked what ValiChord does → answer from `valichord/`. `valichord_attestation` is a future plug-in, not the product.
- `valichord_attestation` can be discussed on its own terms, but never as a replacement or stand-in for the protocol.

| Component | Path | What it is |
|---|---|---|
| **ValiChord protocol** | `valichord/` | **The main project.** Holochain commit-reveal — 4 DNAs, blind attestation, HarmonyRecord on DHT |
| **valichord-attestation** | separate repo (stubs only in `valichord_attestation/`) | Python library — future client on-ramp to the protocol; currently standalone |
| **valichord-ui** | `valichord-ui/` | Svelte 5 browser UI for the three protocol roles (Researcher, Validator, Governance) |

`app_protocol.py` (archived to `docs/archive/backend/` on 2026-10-27; it could not start) was an integration layer — not a definition of either project.

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
`spec/format-backlog/` in the valichord-attestation repo, created 2026-08-22 because the protocol had no place
to record known-missing things and two gaps surfaced in conversation that would otherwise have been
lost. **It is deliberately only for changes that get more expensive with time:** 🟠 anything
needing an entry/link type and 🔴 anything determining what an immutable record *says*
(records written before the fix stay wrong forever). 🟢 Cheap-forever items do not belong
there.

⚠️ **The 🟠 discount has expired.** Those items were cheap only while they could ride the Oracle
rebuild's DNA-hash change, which was already being paid for. **That rebuild happened on
2026-08-24**, so each one now costs a network break of its own — a second one. Anything in the
backlog that was deferred on the reasoning that the window was still open needs re-deciding on its
own merits, not on a discount that no longer exists.
✅ **Update 2026-10-27 — the second break has been paid, and the discount has expired again.**
Holochain 0.7.1 (#45) plus the integrity changes in #47, #55 and #57 reached Oracle with the fresh
install of 2026-10-19. Ceri decided that 01 (supersession) and 02 (hardware provenance) should ride
it, and they did, in #57, together with #23 (hash-algorithm labels) and #24 (the network name). No
break is scheduled now, so any further 🟠 item costs a network break of its own.

### Four-DNA architecture (valichord/)

| DNA | Membrane | Purpose |
|---|---|---|
| `attestation` | Public DHT + Ed25519 credential | Shared protocol state: requests, commitments, profiles, phase markers |
| `researcher_repository` | Private, single-agent | GDPR-protected data; never enters DHT |
| `validator_workspace` | Private, single-agent | Private attestations before reveal; commit-reveal state |
| `governance` | Public DHT, open join | HarmonyRecords, badges, reputation, governance decisions |

Cross-DNA calls use `CallTargetCell::OtherRole("role_name")` with the author grant (same-agent only). Helper: `call_attestation_zome_opt<I, O>` in governance coordinator — returns `Ok(None)` on any cross-DNA failure rather than propagating.

The `sweettest_integration/` and `wind-tunnel/` directories are each their own Cargo workspaces isolated from `valichord/Cargo.toml`.

### The attestation library is a separate repository

Its modules, format notes, backlog and conformance vectors moved to
**[ValiChord/valichord-attestation](https://github.com/ValiChord/valichord-attestation)** on
2026-10-19, with that repository's own `CLAUDE.md`. Nothing about it belongs in this file beyond
the separation rules above.

### Svelte UI architecture (valichord-ui/)

`holochain.ts` — AppWebsocket singleton; reads auth token + signing credentials from `.env.local` (written by `dev-setup.mjs`); sets `SigningCredentials` before connecting (required since `@holochain/client 0.20.x`; the UI is on **0.21.1**, the 0.7.1 line).

`types.ts` — TypeScript mirrors of all Rust types; `entryFromRecord` msgpack-decodes the raw entry bytes (since client 0.20.x entries are not auto-decoded — must call `decode()` from `@msgpack/msgpack`; still the case in the code on 0.21.1).

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
- ⚠️ **An empty commit cannot trigger a path-filtered workflow.** `demo.yml` runs only on
  changes under its own paths, so `git commit --allow-empty` fires the unfiltered 90-minute matrix
  and **not** the short job you wanted. To run that one without a code change, use
  **Actions → Demo → Run workflow** in a browser. (The example was `attestation.yml` until that
  workflow moved to the valichord-attestation repo on 2026-10-19.) ⚠️ `gh workflow run` returns
  **HTTP 403** from a Codespace — the injected `GITHUB_TOKEN` can read runs but not dispatch them.


- Never restore `pack_dna.py` (deleted 2026-10-27; it embedded the same DNA bytes for all four roles)
- Always use `hc dna pack` + `hc app pack`
- Never commit bundles packed outside the **Repack bundles** workflow. Every integrity WASM in the
  committed bundles embeds the CI runner's absolute build paths (`/home/runner/…`,
  `.cargo/registry/src/…`, checked 2026-10-27), so a build on any other machine produces different
  integrity bytes — **a different DNA hash, so a different network** — with no error anywhere.
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

- ✅ **`main` is on Holochain 0.7.1** (PR #45 merged 2026-10-17, `1b5e7c8`; 0.7.0 was merged
  2026-08-03, `38ea2123`). `hdk =0.7.1` / `hdi =0.8.1`, 0.7.1 binaries, and the demo stack's own
  pins (`demo/Dockerfile.node`: 0.7.1 / kitsune2-bootstrap-srv **0.5.1**). ⚠️ **This is a network
  break, not a patch bump.** `hdk 0.7.1` pins
  `hdi =0.8.1`, which changes the serialised shape of capability grants, so the DNA hash changes:
  a separate network, and every HarmonyRecord published on the 0.7.0 Oracle since 2026-08-24 dies.
  ⚠️ **Existing installs cannot be upgraded in place either** — 0.7.1 cannot read capability grants
  written by 0.7.0 (#5820), and `init` does not re-run, so the public-read grant would be missing.
  **Fresh install only.**
- ✅ **#47 merged 2026-10-18; latest release `v0.6.6`** (0.7.1 + #47; v0.6.5 was the 0.7.0 one).
  Peers now enforce, in `validate()`: joining credentials (`attestation_integrity::check_joining_certificate`,
  also run at genesis and `init()` — #37); a HarmonyRecord's `attestation_evidence` (signatures,
  request, outcome, agreement level, `validators_requested`; a short record only after
  `round_timeout_secs` — #11); a ValidatorProfile's `certification_tier` = what its certificate
  grants (#8). ⚠️ So "validate() cannot check HarmonyRecord content" / "the membrane is only checked
  in init()" are **wrong now**, and "`verify_signature` is unavailable in integrity zomes" was
  **always** wrong. Still undecided (Ceri): who writes `ValidatorReputation` in production, and
  whether a timed-out short record may earn a badge.
- ✅ **Oracle runs 0.7.1** — the fresh install was run on 2026-10-19 (`docs/ORACLE_0.7.1_UPGRADE.md`,
  which records the new DNA hashes and what the run turned up). It carries #47, #55 and #57, and
  #60's coordinator since the hot-swap of 2026-10-28 (`docs/ORACLE_HOTSWAP_60.md`). On those nodes
  `get_linked_agents_for` is outside `public-read`, because `init()` does not re-run. A real round
  passed (Reproduced 3/3). Every 0.7.0 record is dead, as planned. ⚠️ The server's `python3` is
  **3.9**: demo scripts run there must not evaluate 3.10+ syntax.
- ⚠️ **The committed `.happ` bundles are what Oracle and the Docker demo run** — nothing compiles
  on the server. They go stale on every Holochain bump **and on every zome change, coordinator-only
  ones included**. Repack with the **Repack bundles** workflow
  (`.github/workflows/repack-bundles.yml`), not by hand on Windows (no `hc` there). The UI e2e job
  builds from source and so cannot detect a stale committed bundle — only this can.
  ✅ **Current as of 2026-10-27:** repacked after #60 (run `40602164694`, from `d90f98a`). Only the
  attestation coordinator changed. All four integrity WASMs and every DNA manifest are
  byte-identical to the bundles Oracle installed on 2026-10-19, so the DNA hashes are unchanged.
  Oracle runs the same attestation coordinator since the 2026-10-28 hot-swap. Check any function
  with `NEEDLE=<fn_name> ./check-no-test-hooks.sh` (exit 1 = present in a bundle, 0 = absent).
- ⚠️ **Oracle changed address.** It is **`132.145.23.78`**, not `152.67.153.149`. The old instance
  was never reached: its SSH key was lost at creation, and Oracle's Compute Instance Run Command
  accepts commands without ever executing them. A new instance was built with a key that is held.
  Runbook and full evidence: `docs/ORACLE_0.7.0_UPGRADE.md`.
- ✅ **The old host was switched off on 2026-10-28** (Ceri, Oracle Cloud console). Until then
  `152.67.153.149:3001/health` answered `{"status":"ok","role":"researcher"}`, on **0.6.2**, a
  different DNA hash and therefore a different network: anything pointed at it got a run that
  looked completely successful and wrote a record onto a network nothing reads. The lesson stands
  for any retired host: **an HTTP 200 from the wrong network is worse than a connection error**,
  because only one of the two is legible. Check the address before believing any demo result.
- **Every HarmonyRecord URL published before 2026-08-24 is dead.** Accepted at the merge, and
  inherent to the DNA-hash change — not a bug to fix.
- 🔴 **Oracle froze from about 2026-10-21 to 2026-10-28, and nothing noticed.** Memory climbed
  until the server stopped answering, while the console still showed it *Running*. A console reboot
  fixed it, but at that rate it freezes again within a few days of each restart until the memory
  is dealt with (`PROJECT_STATUS.md`, "What is left", item 5). Check
  `http://132.145.23.78:3001/health` before believing the demo is up.
  ⚠️ **More memory is not a free fix:** Ceri's Oracle free allowance is **1 OCPU / 6 GB**, and this
  instance already uses all of it. Several Claude sessions have wrongly said 4 OCPU / 24 GB, so do
  not repeat that.
- ⚠️ **`database is locked` on Oracle is expected, not a failure.** 1 OCPU means SQLite contention:
  76 of them during a verified round, zero crashes, every assertion held. Do not treat them as the
  cause of an unrelated problem.
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
**Still OPEN and NOT fixed in 0.7.1** (re-checked 2026-10-17; last comment 2026-02-24). **This one
touches our code.** `reject_if_warranted` reads an empty response as *"no warrants"*, so the gate
**fails OPEN** — the wrong direction. "Only local peers" describes every sweettest run, the Docker
demo stack, and any freshly-bootstrapped network. Three call sites share the pattern:
`attestation_coordinator::reject_if_warranted`, and the warrant checks inside
`governance_coordinator::check_and_create_harmony_record` and
`governance_coordinator::force_finalize_round` (at `:716`, `:195` and `:401` on 2026-10-27 — line
numbers drift with every zome change, so cite them by function name).
⚠️ **Do not cite the warrant gate as a safety property without checking this first.**

**2. Source-chain restore — SHIPPED in 0.7.1** (`#5800`/PR `#5920` closed 2026-08-10, `#5802`
2026-09-02; install with `restore_from_dht: true`). ⚠️ **Restore does NOT recover private entries.**
`ValidatorPrivateAttestation` (DNA 2) and `LockedResult` (DNA 1) are private, so a validator who
loses their machine mid-round loses their sealed attestation **silently**. This is **no longer
theoretical** on 0.7.1. Upstream's own design doc says *"Restore covers public chain state only"*,
and **capability-grant bodies are lost too** — so a restored node would also lose our `public-read`
grant. ⚠️ Correction to an older note: `AppStatus::AwaitingRestore`/`Unrecoverable` already existed
at the 0.7.0 tag; only the workflow is new. `valichord-ui/dev-setup.mjs:106` calls `enableApp` for
any non-`enabled` status and would error on them — harmless until we adopt restore.

**3. 0.7.1 shipped 2026-10-14** (`holochain-0.7.1`). Also fixed in it: `#5781` (receipt signatures
now verified on receive), `#5949`, `#5950`, `#5946`. Still open: `#3313` (we only use
`try_from_raw_39`, so unaffected) and `#4345`. **Tooling:** use `@holochain/client` **0.21.x**
(0.21.1 is the 0.7.1 line) — **not 0.22**, which is a separate breaking line. The wind-tunnel
crates.io runner still targets Holochain 0.6, so keep the git-rev pin.

### 🟢 Do not investigate `holochain-0.8.0-dev.0` again

It appeared 4 days after 0.7.0 and looks alarming. It is **empty** — three commits past the 0.7.0
tag, every per-crate changelog section blank. `147019b1` *"Switch to dev releases for 0.8"* simply
reopens the next line so later merges cut `0.8.0-dev.N` rather than `0.7.1`. **A `-dev.N` tag with
an empty changelog is routine line-opening.** Judge 0.8 by commits on `develop`, never by a dev tag.

### CI binary upgrade (any Holochain version bump)

Update **6** places in `.github/workflows/tests.yml` — 3 jobs (`ui-e2e`, `sweettest`, `tripwire`) ×
(`BASE=…/releases/download/holochain-X.Y.Z` + `key: …-hc-bin-X.Y.Z`) — plus `HOLOCHAIN_VERSION` in
`.github/workflows/repack-bundles.yml`. (The `test` job named here until 2026-10-18 was the
Tryorama job, deleted 2026-08-03.) Verify the binary names exist on the release before pushing.


## Ecosystem tool notes

- **Unyt joining-service** — REST membrane-proof onboarding; reference impl for institutional validator onboarding on a live network. See `memory/reference_unyt_tools.md`.
- **Unyt heart** — Go/Pulumi **fleet** deployer (one stack per release; `progenitor` + `notary` node types). Use when setting up production nodes. Note `cloudinit/cloud-config.yaml` hardcodes **`target_arc_factor: 1`** (every node full-arc) — the concrete "kitsune2 #160 in production" artifact.
- **Unyt migration-service** — working `close_chain`/`open_chain` DNA-migration pipeline. **Read in full 2026-07-27 → `docs/DNA_MIGRATION_PRIOR_ART.md`, which is the answer to "can we carry data across the 0.7 DNA-hash change?"** Verdict: **no — accept the reset and republish.** It carries an agent's own source chain, not the DHT, so it saves no published HarmonyRecord URL; it cannot touch DNA 1/DNA 2 (single-agent, no notaries); and we have no carried state to summarise. **CAL-1.0 — design source, don't copy code.** Read it for `policy.rs` (the algorithm `select_validators()` needs) and the `[MIGERR:<CODE>]` typed-error pattern.
- **tauri-plugin-holochain** — lighter-than-Electron desktop packaging. **Public**, contrary to the old "not yet open-source" note here: the canonical repo is `darksoil-studio/tauri-plugin-holochain`, and Unyt's copy is a fork (per `memory/reference_unyt_tools.md`, reviewed 2026-06-13). Evaluate it against kangaroo-electron before building the validator desktop app.
- **kangaroo-electron** (`holochain/kangaroo-electron`, branch **`main-0.7`** — `main-0.6` was current when the plan was written) — cross-platform Electron packaging. Full plan: `docs/KANGAROO_PACKAGING_PLAN.md`. Remaining blockers: dedicated bootstrap/relay servers.
