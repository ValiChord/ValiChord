# ValiChord — Current Project Status

**Last updated:** 2026-08-01
**Phase:** Full protocol running end-to-end on Oracle. Public web demo live at valichord-demo.onrender.com/demo. Svelte/TS frontend wired to live conductor, end-to-end tested. **v0.6.1** (GitHub release, 2026-07-23) — coordinator auto-updater (checksum-verified, zero DNA-hash-change hot-swap; opt-in/default-OFF; end-to-end rehearsal PASS) + live-ops hardening (first Oracle hot-swap, local-read perf, Oracle ARM rebuild, UI Playwright e2e); still Holochain 0.6.2, no protocol change. Prior release **v0.6.0** (GitHub release, 2026-07-06) — core hardening: commit-reveal hash verification enforced on-chain for real nonces (tampered reveals rejected, sweettest-proven), StudyClaim immutability (attestation DNA hash bump), Holochain 0.6.2 toolchain, badge-sweettest flake hardening. **Versioning note:** GitHub tags jump v0.5.4 → v0.6.0; the v0.5.5–v0.5.7 labels below were internal milestones, never git-tagged. Demo stack (from that untagged line): Your Hypothesis demo (CMA validators, user's own key, user-triggered reveal) is the primary hero section; five accordion explainers; Holochain logo in header; discipline classification via Claude. `valichord_attestation` at v1.2 (Metric.filter, Bundle.meta, dual content_hash) with **five adapters** (InspectAI, InspectEvals, PiSession, LmEval, AILuminate) and a `ValiChordLogger` PR in flight for lm-evaluation-harness. 537 valichord_attestation tests, 97% line coverage.

---

# 🚦 START HERE — next session (updated 2026-08-02)

**✅ PHASE A IS COMPLETE AND CI-GREEN.** All 51 `FlatOp` arms ported, all 8 zomes on
`hdi 0.8.0` / `hdk 0.7.0`, conductor configs fixed, bundles repacked on 0.7, and **run
`30659873225` (commit `719c62ce`) was fully green — all 5 immutability tripwires, all 5
sweettest suites, and the hook guard.** The sweettest sweep is the one that matters most: it
covers commit-reveal, phase transitions, quorum counting, cross-DNA calls and badge issuance,
so the protocol is proven to still *work* on 0.7, not merely to still reject forbidden updates.

**✅ AND THE UI HALF OF PHASE B IS NOW DONE TOO** (`10c92fe5`, 2026-08-02). `valichord-ui` runs
**6/6 Playwright e2e green against a real `holochain 0.7.0` conductor**, locally *and* in CI —
the `ui-e2e` job is unskipped on the branch and passed on a clean runner. Getting there needed a
**sixth conductor-config site that no audit had found**, because it is *generated* in TypeScript
rather than committed as YAML. Details below and in §44.11.

**✅ AND THE DEMO STACK RUNS A FULL COMMIT-REVEAL ROUND ON 0.7** (`316abb7b`, same day) — five
containers, five conductors, real cross-container gossip, HarmonyRecord read back as
**Reproduced / ExactMatch / 3 validators**. Starting it found **four more breakages** the blind
config edit had missed. §44.12.

**✅ AND THE LIVE AI DEMO ROUND PASSED ON 0.7** — three independent Claude validators, blind
commit, phase gate, on-chain-verified reveal, HarmonyRecord **Reproduced (3/3) / ExactMatch**.
That was the merge-gating "live demo round".

**✅ AND THE COORDINATOR AUTO-UPDATER REHEARSES GREEN ON 0.7** — hot-swap applied to all four
cells, DNA hash unchanged on each.

**👉 Everything that gated the 0.7 merge is green.** What is left is merge prep — reverting the
branch-only CI changes and the merge decision itself, which is the user's. See THE NEXT STEP.

---

## 🔴 READ THIS FIRST IF THE SESSION RESTARTED — state as of 2026-08-02, late

**You are probably on the wrong branch.** Three branches are live:

| Branch | What is on it | Trust level |
|---|---|---|
| `main` | Holochain 0.6.2, the publicly-demoed stack | untouched, stays 0.6.2 |
| `v0.7.0` | the whole 0.7 migration, up to `af4ba3e5` | ✅ CI-green, merge-ready |
| `investigate/harmony-record-undercount` | branched off `v0.7.0`; badge-flake diagnosis + fix, plus test work | 🟠 **mixed — see below** |

### ⚠️ The investigation branch mixes VERIFIED work with an UNVERIFIED experiment

`e1b701f3` is a bad commit boundary — my error, flagged so it gets fixed rather than inherited.
It bundles four separate things:

| In that commit | Status |
|---|---|
| `tests/membrane_proof.rs` (5 tests) | ✅ **VERIFIED — 5/5 green.** Belongs on `v0.7.0`. |
| 8 bare `is_err()` assertions strengthened + `assert_rejected_with()` in `src/lib.rs` | ✅ **VERIFIED** — security suite 12/12. Belongs on `v0.7.0`. |
| 2 new attestation tests (self-claim, capacity) | 🟠 compiles, **never run** |
| `governance_yaml_props` `round_timeout_secs` 0 → 86400 | 🟠 **the experiment** — being verified when the session ended |

**Recommended first action:** cherry-pick the two verified items onto `v0.7.0` so the migration
branch carries them, and leave the experiment here. They are independent of the flake fix.

### ✅ RESULT OF THAT RUN (completed 2026-08-02): the flake fix WORKS

`18 passed, 1 failed`. **Gold, silver and bronze all passed** — the badge flake is fixed — and
the new `sweep_cannot_finalize_a_round_still_in_progress` regression test passed too.

⚠️ **The one failure was caused by the fix, and was legitimate.**
`get_pending_request_refs_includes_other_discipline_studies` force-finalises a round in its part
(c), so it genuinely needed `round_timeout_secs: 0`. With a real timeout the round has not aged
out and `force_finalize_round` correctly declines — which is precisely the behaviour the change
exists to produce. Fixed by moving that test to `setup_two_agents_instant_timeout()`, alongside
`force_finalize_round_with_partial_quorum`. **Not yet re-run.**

All four `force_finalize_round` call sites are now deliberately configured:
`force_finalize_round_with_partial_quorum` and `get_pending_request_refs_…` use the instant
timeout (they assert finalisation *succeeds*); `sweep_cannot_finalize_a_round_still_in_progress`
uses the safe default (it asserts a decline); `live_claim_blocks_force_finalize` /
`released_claim_allows_force_finalize` use instant so the claim gate is the only deciding factor.

⚠️ `run-sweettest.sh`'s cross-check fired again (4 result lines vs 19) — the ENOMEM splice, not
lost data. It will fire on every memory-pressured run; see the note about teaching its extractor
the spliced form.

### ✅ The liveness gate IS built, packed and under test (updated 2026-08-02, late)

Superseding the earlier "committed but NEVER RUN" note:

- WASM rebuilt and `workdir/governance.dna` + `workdir/valichord.happ` repacked with 0.7 `hc`.
- **Verified the packed DNA really contains the gate** — sha256 of the coordinator WASM inside
  `governance.dna` matches the freshly built one (`40ec846f408c478a`). Worth doing: a stale pack
  would have produced a green run that proved nothing.
- **DNA hash byte-identical before and after** (`uhC0kRrX19H1PP-lfWYhBc6vRUIDAG1CkI7zMWVOD9AZ15xoGwZSC`),
  so "coordinator-only, hot-swappable, zero hash change" is now measured, not asserted. It can
  reach the live Oracle nodes without touching any published record URL.
- `./run-sweettest.sh governance` was **in flight** against that build when the session ended.
  It contains `live_claim_blocks_force_finalize` + `released_claim_allows_force_finalize`.

**If that run's result is not recorded below, it did not finish — re-run it.** The two liveness
tests are a matched pair and must both pass: one proves the gate blocks, the other that it opens.
If only the first passes, the gate may be refusing unconditionally and the sweep is dead.

### ✅✅ THE LIVENESS GATE IS VERIFIED (governance run, 2026-08-02 late)

**21 passed, 0 failed** against the rebuilt DNA. Both halves of the matched pair passed:

| Test | Result |
|---|---|
| `live_claim_blocks_force_finalize` | ✅ the gate **blocks** a round with a live claim |
| `released_claim_allows_force_finalize` | ✅ the gate **opens** once the slot is released |
| `sweep_cannot_finalize_a_round_still_in_progress` | ✅ |
| gold / silver / bronze | ✅ badge-flake fix confirmed a second time |

Both directions matter: the blocking test alone would be satisfied by a gate that refuses
everything, which would leave the sweep unable to close genuinely stuck rounds.

⚠️ **21 = 18 pre-existing + 3 new.** `governance_decisions_round_trip_and_accumulate` was added
*after* that run started, so it is **not** in this result. ✅ **It has since been run on its own
(2026-08-03) and passed** — 1 passed, 0 failed, cross-check clean. So the governance suite stands
at 22 known-green, though never all in one sweep.

⚠️ `run-sweettest.sh`'s cross-check fired again (3 lines vs 21). Reconciled by hand: 3 intact
result lines + 18 standalone `ok` continuations = 21, with 0 FAILED and 0 panics. It is the ENOMEM
splice, not lost data — but it will keep firing on this box, and a guard that cries wolf gets
ignored. Teaching its extractor the spliced form is worth doing.

### ⚠️ `workdir/*.dna` IS GITIGNORED — a fresh Codespace has no DNAs

`valichord/.gitignore` ignores `workdir/*.dna`; only `workdir/valichord.happ` is tracked. So after
a rebuild the four `.dna` files are **absent**, and every sweettest fails with "…dna not found".
Rebuild before running anything:

```bash
export PATH="/home/codespace/.cargo/bin:$PATH"
cd valichord && cargo build --target wasm32-unknown-unknown --release
for d in attestation researcher_repository validator_workspace governance; do
  <0.7-hc> dna pack dnas/$d -o workdir/$d.dna
done
<0.7-hc> app pack . -o workdir/valichord.happ
```

### ✅ The ported Tryorama tests are RUN AND GREEN — and two of them were fake (2026-08-03)

`e6b27849` + `ad593e1c`, executed after the Codespace restart. Full attestation suite:
**27 passed, 2 failed** (4171 s); governance `governance_decisions_round_trip_and_accumulate`:
**1 passed** (97 s, cross-check clean). **Both failures were test bugs, not protocol bugs — and
both tests were passing against the wrong guard entirely.** Fixed, re-run as the `claim_*` subset:
**7 passed, 0 failed** (1347 s).

| Failure | What it actually proved |
|---|---|
| `claim_study_coi_same_institution_rejected` | **The COI rule had NO coverage at all.** The test ran on a *single* conductor, so researcher and validator were the same agent — and the self-claim guard (`attestation_integrity/src/lib.rs:665`) sits **ahead** of the COI comparison (`:677`), so the claim was rejected before the institution check was reached. The error text said so verbatim. Fixed with `setup_two_agents()`: Alice submits, Bob declares the same institution. |
| `claim_rejected_when_study_is_at_capacity` | **Never reached the capacity guard.** It set `num_validators_required = 1`, but the test DNA properties set `minimum_validators: 2` and `validate()` rejects below that floor (`:614`) — the *first* call failed and the request was never written. |

⚠️ **The first one is the finding worth keeping.** It looked green only because its assertion was
a bare `is_err()`; the 2026-08-02 audit's `assert_rejected_with()` strengthening (`e1b701f3`) is
what exposed it, on the first run after. **That audit paid for itself.** Same shape as
`link_agent_identity_self_link_rejected`. Both now assert the guard's own wording, so they are
provably reaching the guard they name.

⚠️ **Lowering the DNA floor would have been the wrong fix for the second** — that floor is what
stops a single colluding validator satisfying the commitment gate alone. It is now capacity 2 with
a **fourth** agent, which also makes it assert **both** directions: the second claim must *succeed*,
so a guard that refused everything after the first would fail it. At capacity 1 it would not have.

The other 22 attestation tests were not re-run after the fix — the edits touch two test bodies
only, no shared helper — so the clean 29/29 sweep is not on the record.

**Tryorama can now be retired**: this was the gate on it.

Deliberately NOT ported: the badge-outcome variants (`FailedReproduction`, `Divergent`). Their
logic already has 27 unit tests in `shared_types` covering every agreement level and threshold, so
an integration test would re-prove arithmetic at ~30 min a run while exercising round wiring the
bronze test already covers.

### The 0.7 binaries are in a scratchpad that does NOT survive a restart

`holochain` and `hc` on `PATH` are **0.6.2**, deliberately. Everything 0.7 used a scratchpad copy.
Re-fetch with `gh release download holochain-0.7.0 --repo holochain/holochain -p '<name>-x86_64-unknown-linux-gnu'`
(`holochain`, `hc`, `kitsune2-bootstrap-srv`, `lair-keystore` all exist there), then
`HOLOCHAIN_BIN=/path/to/holochain` — `dev.sh`, the e2e harness and `rehearse-autoupdate.sh` all
honour that override.

### The demo stack is stopped, not destroyed

`docker compose -f demo/docker-compose.yml start` brings it back with volumes intact (it was
`stop`, not `down -v`). `ANTHROPIC_API_KEY` was appended to `~/.bashrc` — note bash's
non-interactive guard means it is NOT inherited by tool shells; read it out of the file instead.

---

The full evidence log is **`docs/Holochain_complete.md` §44** (folded in from the standalone
migration log, which is deleted). **§44.8 is the honest list of what is *not* verified — read it
before assuming anything works.** §44.11 covers the UI half.

**`main` remains on 0.6.2**, at `03fc16f4`. Branch head is `10c92fe5` (+ this docs commit).

### The state of the three phases

| Phase | Scope | Status |
|---|---|---|
| **A** | 4 DNA zomes, `sweettest_integration`, configs, bundles | ✅ **complete, CI-green** |
| **B** | Svelte UI | ✅ **done 2026-08-02 — 6/6 e2e green on a real 0.7 conductor** |
| **B** | Tryorama suite (92 tests, was 98 — see below) | 🔴 blocked upstream, re-checked 2026-08-02 |
| **C** | `valichord/wind-tunnel/` | 🔴 blocked upstream |

**Upstream re-checked 2026-08-02 — no change.** `@holochain/tryorama` latest is still `0.19.2`,
pinning `@holochain/client ^0.20.4`; there is no 0.7 line, so there is nothing to migrate the
suite *to*. (Its `beta: 0.3.0-rc.4` dist-tag is from 2019 — noise, not a 0.7 preview.) **Phase C
unchanged:** `holochain_wind_tunnel_runner` last published 2026-07-21, still on
`holochain = "0.6"`. What unblocked the UI half on 2026-08-01 was `@holochain/client` **0.21.0**
and `@holochain/hc-spin` **0.700.0** going stable on npm `latest`; that half is now **done**
(see below).

### Riding along with the 0.7 hash break — decided 2026-08-01

**Decision (user):** take the **validator→bundle binding** now; do **Open Audit Mode** later,
when it can be done properly. Both were explained before the call was made.

✅ **Validator→bundle binding is BUILT** — see `docs/VALIDATOR_BUNDLE_BINDING_PLAN.md` for the
full record. One optional field on `ValidationAttestation` (`reproduction_bundle_hash`), bound
into the commitment automatically because `commitment_msgpack_bytes()` was already the shared
seam between commit and reveal. No new hashing path, no new protocol message. Closes the gap
documented publicly against ValiChord in falsify-cookbook Pattern 13: a validator's verdict is
now a claim about *a specific set of per-sample outputs* rather than the bare word "Reproduced".
Tests S9/S10/S11 in `security.rs`, and **the negative control fired** — deliberately unbinding
the field made a substituted-bundle reveal succeed with a real `ActionHash` while every other
test stayed green.

🕐 **Open Audit Mode is still mostly outstanding — but its integrity-level groundwork was taken
on the same reasoning** (`171b7042`). `DataLocalityMode` (`Gdpr` | `OpenAudit`, defaulting to
`Gdpr`) now exists in `shared_types` and rides on `LockedResult`, and the DNA 1 delete guard
follows it: erasure stays **allowed** under `Gdpr` (guarding it would remove the erasure right
the mode exists to protect, and buys nothing — the binding commitment is on DNA 3, public and
immutable) and is **refused** under `OpenAudit` (a mode that *is* a permanent commitment to
post-reveal public access cannot let the sealed material be erased afterwards). That field is
integrity-level, so taking it later would have cost a second hash break by itself.

⚠️ **Everything in production today is `Gdpr`; the `OpenAudit` branch is unreachable groundwork.**
What remains: `EncryptedDataset`, per-study X25519 key generation, the decryption-key field on
`ResearcherReveal`, and the submission-time mode selector. **Only the first two are
hash-breaking** — key generation, the selector and the UI are coordinator/frontend work, which
hot-swaps onto live nodes with **zero** hash change. So the second break is now smaller still,
and stays cheap if the remaining entry shapes are settled before it is paid.

**It also closed a real hole, not just groundwork.** `LockedResult` — the researcher's sealed
metrics *and nonce* — was update-guarded by the blanket `PrivateEntry` arm but had **no delete
guard at all**; deletes fell through to "only the original author may delete", which the
researcher passes by definition. Because the *update* test passed, deletes looked covered.

### What landed after the Phase A checkpoint — 2026-08-01 afternoon

Mostly the product of auditing the test suites rather than of the port itself — but one of them
(`60a5609c`) is a **protocol correctness bug with permanent consequences**, so read that row.

| Commit | What it fixed, and why it matters |
|---|---|
| `0030a9cf` | **`run-sweettest.sh`** — the `grep -v sqlcipher_mlock` filter that ate a test's result line on 07-30 did it *again* on 08-01, to the same test, because the "mitigation" was a note asking a human to remember. The script keeps the raw log unfiltered and **cross-checks named results against cargo's own summary**, failing on a mismatch. Negative-controlled three ways via a `SWEETTEST_REPLAY_LOG` hook. **Use it; do not hand-roll a filter.** |
| `710f2b6b` | Instruments the badge flake so the next occurrence produces a **verdict** rather than a third inference — asks *every* conductor on the failure path, and is written so it can say the standing theory is wrong. |
| `cc19e8c4` | **The delete guards had no coverage that could fail.** Sixteen "cannot be deleted" guards, and not one test that would have failed if they were removed — the 0.7 port reflowed four `RegisterDelete` arms with no runtime net behind them. Eight tests called zome functions that were **never written** and passed on *"function not found"*; six of them were in the Tryorama suite, inside the quoted 97. Deleted rather than repaired (Tryorama structurally cannot issue a forbidden delete — no coordinator exposes `delete_entry`), and replaced with **five delete tripwires** mirroring the update ones, each asserting the guard's own message. ⚠️ Tryorama declarations went **98 → 92** (1 `test.skip`), so drop the "97 tests" figure; it cannot be re-confirmed by running until Phase B unblocks. |
| `60a5609c` | **HarmonyRecord undercount — the most serious of these.** `write_harmony_record` silently `filter_map`ped away any attestation whose entry would not decode or arrived as `NotStored`, *after* the quorum gate had already counted it. Both consequences are permanent, because a HarmonyRecord is immutable: participation understated forever, and the count feeds `evaluate_badge`, so a genuine 7/7 `ExactMatch` round would issue **Silver instead of Gold**. Found by CI (`left: 6, right: 7`). Now errors and retries later; logic split into `validator_attestation_pairs()` so it unit-tests in 0.00 s instead of needing a 2-hour 7-conductor run. |
| `171b7042` | `DataLocalityMode` + the `LockedResult` delete guard (above). |
| `99a72a69` | **The badge flake's actual mechanism** — see below. |

**CI on the head commit** (`99a72a69`, run `30710181336`): tripwires, the `no-test-hooks` guard,
and the security / researcher_repository / validator_workspace sweettests all green; **attestation
and governance still in flight at the time of writing — check them before treating the head as
verified.** `60a5609c` — the commit carrying the undercount fix — was **fully green** on its own
run, so that fix itself is verified independently of how the head run lands.

⚠️ **Sequencing rule that was followed and should be followed again:** Phase A was green
*before* the binding went on top, as separate commits. A failure can therefore be attributed
between the port and the feature, and the migration stays independently verifiable.

### Phase B — UI half is DONE (`10c92fe5`, 2026-08-02)

`valichord-ui` is on `@holochain/client` **0.21.0**, and it is now **proven, not just
type-checked: 6/6 Playwright e2e tests pass against a real `holochain 0.7.0` binary**, and the
`ui-e2e` CI job is **unskipped on this branch** so the result is repeatable rather than
remembered. Full record: `docs/Holochain_complete.md` §44.11.

🆕 **A sixth conductor-config site existed that no audit had found.** The checklist lists five,
all found by grepping YAML for `signal_url` / `db_sync_strategy`.
`valichord-ui/tests/e2e/setup/conductor-manager.ts` doesn't *read* a config — it **generates**
one as a TypeScript string array, and still emitted both 0.6-only fields. On 0.7 that is fatal
(exit 42, hard parse error), so the e2e suite could not have started at all, regardless of the
UI code. ⚠️ **The lesson: a grep for a config field cannot find a config that doesn't exist
until runtime — audit generators, not just committed files.** Same shape as the
`check-no-test-hooks.sh` bug: a search that couldn't see its target and so reported clean.

**Two claims were kept separate on purpose, and the config bug is why it mattered.** *Did the
UI port correctly?* — `npm run check` answered that on 08-01. *Does it actually talk to a 0.7
conductor?* — nothing answered that until this run, and a type-check never could: the broken
config type-checked perfectly and would have died on the first byte of a real run.

**Evidence the run was genuine** (a bare "6 passed" is exactly what this branch has learned to
distrust): the same config run against the 0.6.2 still on `PATH` fails with ``missing field
`signal_url` ``, so the conductor cannot have been 0.6.2; and the tests are falsifiable — one
reads a form-submitted request back through a *different role view*, another pushes a typed
payload through a direct zome call and asserts the UI renders it, both of which break on serde
drift at the msgpack boundary.

`HOLOCHAIN_BIN` now overrides the conductor binary in `dev.sh` and the e2e harness (defaults to
`holochain` on `PATH`, so CI and `main` are unaffected). It is needed because the Codespace
`PATH` is deliberately still 0.6.2 while `dev-conductor.yaml` is 0.7-only — without it
`bash dev.sh` cannot start a conductor on this branch at all.

⚠️ **What this does NOT prove:** the suite is single-agent, single-conductor, and covers
UI↔conductor wiring only. **No commit-reveal round, no quorum, no reveal.** The demo stack on
0.7 is still the outstanding risk, and it is what gates the merge.

Two corrections to what the old handoff said here, both found by reading the shipped package
instead of trusting the note:

- The line number was stale (`types.ts:339`, not `:331`).
- **"`SignedActionHashed` is no longer generic" was WRONG** — it is still
  `SignedActionHashed<H extends Action = Action>` in 0.21.0. The real change is that **`Action`
  is now `{ header, data }`**, with `author`/`timestamp`/`action_seq`/`prev_action` on `header`.
- Also new, not in the note: `AppWebsocket.client` is now typed as the `AppClientTransport`
  interface (because the App API can route over Tauri IPC, which has no socket), so it **no
  longer exposes `close()`**. Two e2e teardown sites narrow it back to `WsClient`.
  `AdminWebsocket.client` is unaffected. `signalingServerUrl`/`dumpNetworkStats` are zero hits
  for us.

**Only one of the three pins was bumped, deliberately.** `valichord/tests/package.json` must
stay on 0.20.x — Tryorama 0.19.2 pins `^0.20.4` and there is no 0.7 line. `demo/package.json`
waits until the demo stack is actually exercised on 0.7.

🆕 **The bump also surfaced a real bug from `ef795736`,** unrelated to 0.21: the binding added
`reproduction_bundle_hash` to `ValidationAttestation` and to the TS mirror but never to the
Svelte view that constructs one, and `ValidatorPrivateAttestation`'s mirror was missing the
field entirely. The UI had had no type-check since Phase A began. ⚠️ **The two construction
sites are not the same fix:** the commit path passes `null` (the UI has no bundle — a
legitimate permanent state), but the reveal path **must** read it from the private record,
because the field was bound into `commitment_hash` at seal time and substituting anything
there — *including `null`* — makes the reveal fail with "Hash mismatch".

### ✅ The demo stack runs a full round on 0.7 (`316abb7b`, 2026-08-02)

**A complete commit-reveal round now runs on the 0.7 Docker stack** — five containers, five
conductors, real cross-container gossip. Full record: `docs/Holochain_complete.md` §44.12.

The config had been edited blind on 07-30; starting it found **four more breakages** the edit had
not touched: the Dockerfile still pinned Holochain **0.6.2**; the bundled-binary check was
`--version >/dev/null` (*"does it execute?"*) and the committed `kitsune2-bootstrap-srv` is
**0.4.1**, which execs fine and would have been silently preferred over 0.5.0 — across a p2p wire
protocol bump 2→3; `--sbd-disable-rate-limiting` no longer exists in kitsune2 0.5.0; and
`relay_url` still carried the old `ws://` signal URL.

⚠️ **That last one failed twice, in opposite directions, and it is the lesson worth keeping.**
`ws://` → iroh rejects the scheme but **the conductor starts and the happ installs**, so it only
degrades relay connectivity behind a warning that repeats a few times a second. `http://` →
kitsune2 **crashes the conductor** outright (`Disallowed plaintext relay URL`). **The crash is the
better outcome**, and the fix was already sitting in `CLAUDE.md` from the 07-30 verification:
`http://` plus `advanced.irohTransport.relayAllowPlainText: true`.

**What the round proved:** DNA 1 private lock (incl. the new `data_locality_mode`) →
`submit_validation_request` → **three validators on three separate conductors reading that request
across container boundaries** and sealing private attestations → quorum → `PhaseMarker` gossiped,
phase `null` → `RevealOpen` → researcher reveal **passing on-chain SHA-256 verification** → three
validator reveals → HarmonyRecord read back as **Reproduced / ExactMatch / `validator_count: 3`**.

⚠️ **That count is evidence by itself:** it is the `60a5609c` undercount fix holding under real
gossip — the exact scenario that produced `left: 6, right: 7` in CI, and one no in-process test
can reproduce. Stack health: 5 up, **0 restarts, 0 crashes**.

### ✅ The live AI demo round passed on 0.7 (2026-08-02)

**`demo/ai_validator.py --mode decentralised` ran for real against the 0.7 stack** with a live
`ANTHROPIC_API_KEY`. **This was the "live demo round" gating the merge.** Three independent
Claude validators formed verdicts blind, committed to three separate conductors, the phase gate
opened, the researcher reveal passed on-chain SHA-256 verification, and all three broke their
seals: **Reproduced (High) ×3** → HarmonyRecord **Reproduced (3/3) / ExactMatch**.

⚠️ **The one warning it prints is an environment artifact, not a defect.**
`WARNING: Could not reach viewer: <urlopen error timed out>` — the script rewrites `localhost`
to a **detected public IP** so the URL is shareable (right on Oracle), then fetches its own URL
to self-verify. A Codespace has no inbound route to that address. The record itself reads back
completely from `localhost:3001`. **It will not reproduce on Oracle; don't chase it.**

⚠️ **Observed, not diagnosed:** recurring `database is locked` errors from
`integrate_dht_ops_consumer` in both rounds. Nothing failed and every assertion held. Five
conductors on a 2-core box is the likely cause, but **that is a hypothesis** — it was not
compared against a 0.6.2 run on the same hardware, which is what would settle it. Worth watching
on Oracle (1 OCPU).

### ✅ The coordinator auto-updater rehearses green on 0.7 (2026-08-02)

`./demo/rehearse-autoupdate.sh` **PASSES**: four WASMs sha256-verified before anything was
applied, `UpdateCoordinators` applied to all four cells, **DNA hash unchanged on each**, verify
call OK, marker 0 → 2. The zero-hash-change hot-swap path works on 0.7 — the mechanism that
lets coordinator fixes reach live nodes without breaking published record URLs. Full record:
§44.13. To reproduce: `node demo/pack-coordinators.mjs --holochain 0.7.0` then
`HOLOCHAIN_BIN=<0.7 binary> ./demo/rehearse-autoupdate.sh`.

🆕 **It found a latent bug on the way, worth knowing about.** `runningHolochainVersion()` in
`coordinator-autoupdate.mjs` shells out to `holochain --version` **from `PATH`** — it never asks
the conductor it is updating, despite the guard's stated job being *"must match the running
conductor version"*. It is correct on Oracle only because the poller runs inside the node
container beside its own conductor. The admin API has **no conductor-version call** (checked
against client 0.21), so a binary check is the only available proxy; it is now explicit,
`HOLOCHAIN_BIN`-overridable, and documented for what it actually establishes. ✅ **It failed
CLOSED** — it refused a correct update rather than applying a mismatched one.

### 🆕 The badge flake is SOLVED — it was the scheduled sweep, not gossip lag (2026-08-02)

Three sessions guessed at this area. It is now established from code, with each link checked:

1. `init()` schedules `sweep_timed_out_rounds` on cron `"0 0 * * * * *"` — **hourly, on the wall
   clock**, on every conductor — which calls `force_finalize_round` for every pending study.
2. That function finalises when **both** `attestation_records.len() >= min_required` (where
   `min_attestations_for_finalization: 0` **silently coerces to 1**) and
   `elapsed_secs >= round_timeout_secs` (`0` → always true). The test properties had **both at
   zero**, so both gates were open.
3. So any multi-validator test still mid-round when the clock crossed the top of an hour had its
   round force-finalised with a partial set — permanently, since a HarmonyRecord is immutable.
4. **Proof by elimination:** `check_and_create_harmony_record` *cannot* write a short record. Its
   gate requires `len() >= num_validators_required`, the warrant filter re-checks the same bound,
   and `validator_attestation_pairs` is 1:1 with an explicit length check that errors.
   `force_finalize_round` is the only lower-threshold path, and the sweep is its only caller here.
5. **Timing corroborates:** gold ran 16:31→17:02, straddling 17:00:00 → failed `left: 5,
   right: 7`. Silver ran 17:09→17:31, straddled nothing → passed.

This explains everything "gossip lag" never did: why the failure **moved between tests**, why
**docs-only commits flipped it** (they shift start times), why **widening retries never helped**
(the record already existed and is immutable), and why it presented as a **count** error.

⚠️ **The test-config fix does NOT fix the underlying design.** See Phase 0 limitation 6 in
`docs/7_ValiChord_4-DNA_architecture_technical.md`: age is not evidence of abandonment, and a
slow-but-healthy round is indistinguishable from an abandoned one. `fd56cc41` implements the real
fix (gate on live claims) but **has not been run**.

🆕 **An idle timeout does NOT work** — recorded because it looks obviously right. A validator
claims a slot then does the reproduction work for days, emitting **no DHT activity at all**; the
silence *is* the work. An idle clock reads a room of working validators as empty. Do not build it.

### 🆕 Test-suite audit — 2026-08-02

Two mechanical sweeps, both reproducible:

- **Integrity guards vs assertions.** 83 distinct `Invalid()` messages across the four integrity
  zomes. **12** are asserted by any test — **10 of those are the immutability tripwires**. 71 have
  no test at all. Many are unreachable through any coordinator call by design (which is why the
  tripwires need test-only externs), but the real safety net is those 10 tests, not the 92-test
  Tryorama suite anyone would assume covered it.
- **Assertion quality.** 8 sweettests used bare `is_err()` — same class as the fakes culled on
  07-30 and 08-01. Now fixed via `assert_rejected_with()`, which checks the expected fragment
  *first* so guards legitimately containing "not found" do not false-positive.
  ⚠️ One finding: `link_agent_identity_self_link_rejected` is rejected by the **coordinator**, so
  `validate()` is never reached — the integrity guard behind it remains unproven and unreachable.

### 🆕 Tryorama: retire it, don't migrate it — scoped 2026-08-02

**Upstream `@holochain/tryorama` is dead**: an unmaintained banner landed Jan 2026 saying
*"support for Holochain 0.7+ should not be expected"* and pointing at **sweettest**. A community
fork (`@holochain-open-dev/tryorama` 0.20.0, MIT, targets 0.7 + client 0.21) does exist — so the
long-standing "no 0.7 line, blocked upstream" note was checking the wrong package.

Scoping says **retire rather than port**: of 92 tests, **~69 are already duplicated in sweettest**
(`researcher_repository` 13/13 and `validator_workspace` 7/7 are 100% redundant) and ~23 unique.
✅ The 5 membrane-proof tests — the only coverage of DNA 3's credentialed membrane anywhere, since
sweettest runs entirely in dev-bypass — **are ported and green**. ~15 unique tests remain, mostly
edge cases; 3 are `"no delete fn exists"` assertions superseded by the delete tripwires.

⚠️ **Trap for the port:** `verify_signature(key, sig, data)` does **not** verify over `data` as
given — `VerifySignature::new` stores `holochain_serialized_bytes::encode(&data)`, so a `Vec<u8>`
is verified as a msgpack *array of integers*, not raw bytes. Sign via `Sign::new`, which routes
through the same `encode()`. Signing raw bytes fails in a way indistinguishable from "the guard
works".

### 👉 THE NEXT STEP — merge prep

Everything that gated the merge is now green. What remains is process, not verification:

Ordered. Items 1–3 are the investigation branch; 4–6 are the migration itself.

1. **Cherry-pick the verified test work onto `v0.7.0`** — `membrane_proof.rs` and the 8
   strengthened assertions. Both are verified and independent of the experiment.
2. **Rebuild + repack, then run the governance suite** to test the liveness gate (`fd56cc41`).
   Confirm `live_claim_blocks_force_finalize` **fails** against the old DNA first, or the test is
   not exercising the gate.
3. **Decide on the honest-record change** — `HarmonyRecord` carrying *both* the requested cohort
   size and the number who reported, so an early close is visibly incomplete rather than quietly
   false. Integrity-level, so it wants to ride the 0.7 hash break rather than buy its own — but
   the branch is otherwise merge-ready, so this is a scope call: take it now and delay, or accept
   a second break later. `OpenAudit` groundwork was banked for exactly this reason.
4. **Revert the branch-only CI changes** — see Non-negotiables. ⚠️ **`ui-e2e` must stay
   unskipped**; only the `test` skip, the `sweettest` gating change and the branch-only
   `tripwire` job are the ones to reconsider.
5. **Take the merge decision explicitly with the user** — it is theirs, and it has never been
   given. Accepted cost, already decided: every published HarmonyRecord URL dies at the hash
   break.
6. **Oracle is a separate, later job** — a full rebuild with state loss, **not** an upgrade, and
   not to be touched until after the merge.

⚠️ **The finalisation hazard is PRE-EXISTING on `main`** — it is not something the 0.7 migration
introduced, and shipping 0.7 does not worsen it. It need not block the merge unless the user
wants it to.

Tryorama and `wind-tunnel` stay blocked upstream and are **not** merge blockers — they were
already skipped/untouched before this branch existed.

⚠️ **The Oracle box is a separate question and is NOT part of this.** It runs the live 0.6.2
demo. Do not touch it until the branch merges — and when it happens it is a full rebuild with
state loss, not an upgrade (accepted: see the record-URL note in Non-negotiables).

### The badge flake — "gossip lag" was the wrong diagnosis, twice

`silver_badge_issued_with_five_validators` fails intermittently. Still **not a 0.7 regression**
(it passed on `719c62ce` and failed on `70cd07dc`, a **docs-only** commit). But it was recorded
here twice as gossip lag, and **that never fitted the code**:

- `issue_badge_if_missing` did `let Some(record) = get(hash, GetOptions::network())? else {
  return Ok(()) }` — on a miss it issued no badge, logged nothing, and **reported success**.
- That fetch is genuinely **remote** (the HarmonyRecord is authored by whichever validator's
  reveal met quorum; the repair runs on a different agent), so a miss is ordinary, not exotic.
- **The retry loop only re-READ badges — it never re-triggered issuance.** One missed fetch made
  all five rounds futile *by construction*. That is why widening the retry windows never helped.
  No amount of re-reading conjures a badge that was never issued.

`99a72a69` fixes it either way the underlying race goes: the silent-skip and decode-to-`None`
paths now return `Err` (safe — the sole caller warns and continues, so finalisation still
succeeds), and each retry iteration calls `check_and_create_harmony_record` first: a no-op when
the badge is there, a repair when it is not.

⚠️ **Causation is still not formally proven** — the diagnostic from `710f2b6b` will settle it on
the next failure. `1152fd38`'s earlier fix (a retry loop that `unwrap()`ed inside itself and
panicked on its own first iteration) was real but addressed the wrong layer.

### What was learned during the port — read before the next migration

- **The pre-migration audit's "confirmed ZERO" table was scoped to the files it actually grepped.**
  It declared the v2 Action model zero-impact, having never grepped the **coordinators** — where
  three real `Action::` sites lived, two of them in `post_commit`, the commit-reveal critical path.
- **Compile-clean is what broken match-ordering looks like.** Ordering was proven mechanically, and
  the checker was negative-controlled on all three distinct hazard shapes before being trusted.
- **An equivalence argument across a version bump must check every moving part.** `SweetConductor`'s
  constructors were compared while `SweetConductorConfig::standard()` was *assumed* unchanged — it
  had changed, and that cost a red tripwire run. See `docs/Holochain_complete.md` §44.3.
- **`attestation` has 9 per-type guard arms, not 12** — the checklist conflated guards with total
  `RegisterUpdate` arms.
- 🆕 **A green safety net proves only what it tests.** The tripwires covered the *update* guards,
  so the 0.7 reflow of four `RegisterDelete` arms went across with **no runtime net at all** —
  and the eight tests that appeared to cover deletes passed on *"function not found"*. Before
  trusting a net across a version bump, check it can fail for the thing you are about to change.
- 🆕 **A cull is only as wide as the suite you looked at.** The 07-30 cull of fake immutability
  tests never looked at the Tryorama suite, where five more of them lived — inside the
  97-passing figure.

### Non-negotiables (unchanged)

- **`main` stays on 0.6.2** until the branch is fully green *and* the user explicitly approves the
  merge.
- 🆕 **Losing the published HarmonyRecord URLs at merge is ACCEPTED — decided by the user
  2026-08-01.** The 0.7 hash break means 0.7 agents form a separate network from 0.6, so every
  existing record URL dies. *"That's not important. We move forward and create new Harmony
  records."* **So do not treat URL preservation as a merge blocker, or price it into future
  decisions** — including Open Audit Mode's second hash break. What still gates the merge is a
  green branch and a working live demo round, not record continuity. Re-check any grant or
  outreach material that cites a record URL after the merge, though: that is a
  correctness-of-public-claims issue, not a preservation one.
- **`.github/workflows/tests.yml` on this branch is marked REVERT BEFORE MERGE.** It skips
  `test`, adds a branch-only `tripwire` job, and lets `sweettest` run when `test` is skipped.
  None of that should reach `main` as-is. ⚠️ **`ui-e2e` came OFF that list on 2026-08-02** — it
  is unskipped and must stay unskipped; it is the only CI signal covering the UI on 0.7.
- **Never weaken a test to a bare `is_err()`.**

### The lesson that keeps recurring

**An assertion that cannot fail is worse than none — and so is a mitigation that cannot mitigate.**
2026-07-30: three "immutability" tests passing on *"function not found"*; a CI guard grepping
*compressed* bundles. 2026-07-31: a badge-flake retry loop that panicked on the first retry; a
public doc advertising a HarmonyRecord URL that had been dead for seven weeks; and my own log
filter that ate a test's result line while I was checking that very test. 2026-08-01: **eight
more** tests passing on "function not found", this time in Tryorama; a badge retry loop that
could only re-read a badge that had never been issued; and **that same log filter eating that
same test's result line a second time**, because its "fix" had been a note asking a human to
remember. Every fix was the same —
**run the negative control: prove the check can fail before trusting that it passed.**

🆕 **And its corollary, learned on 2026-08-01: a remembered mitigation is not a mitigation.** The
log filter recurred because the control lived in a document. It stopped recurring when it became
`run-sweettest.sh`, which fails on a count mismatch whether or not anyone remembers why.

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
| Decentralised demo | **Live on Oracle (rebuilt 2026-07-07)** | 5 isolated Docker containers (bootstrap + researcher + 3 validators) on Oracle server **152.67.153.149** (Ampere A1 ARM, PAYG account, Always Free shape); `restart: unless-stopped` survives reboots. Run locally: `docker compose up` + `python3 demo/ai_validator.py --mode decentralised`. **Previous server 132.145.34.27 was reclaimed by Oracle when the free trial ended 2026-06-11 — its DHT state and every HarmonyRecord URL on that IP are gone.** |
| Public web demo | **Live on Render** | Flask app at `valichord-demo.onrender.com/demo`. **One demo: *Your Hypothesis*** — user enters any claim + their own sealed answer + their own Anthropic key; 3 CMA validators research it blind in parallel; user clicks a pulsing green Reveal button once all 3 commit; adjudicator Claude call compares answers; HarmonyRecord written to DHT. (The server-funded *Free Demo* was **removed June 2026** — every visitor run drew on the server's own Anthropic key, causing rate-limit/cost problems; the site now runs **exclusively on the visitor's `sk-ant-` key**, no server key. The `/demo/run` + `/demo/result` routes are gone from `app.py`. Full detail in `demo/DEMO_WEBSITE.md`.) Linear scroll layout with five expandable accordion explainers (how it works, why remarkable, why Holochain not blockchain, why not central server, why disagreement is fine). Holochain logo in header. |
| Node.js bridges | **Working** | `researcher-node.mjs` (port 3001) + `validator-node.mjs` (ports 3002–3004) — HTTP APIs over each conductor |
| HarmonyRecord URL | **Working** | `GET /record?hash=<hash>` on researcher node — no auth, returns clean JSON. On Oracle: `http://152.67.153.149:3001/record?hash=<hash>` (port 3001 must be open in Oracle Security List). |
| Feynman skill (was PR #13) | **Historical** | Feynman is no longer operational (April 2026). Superseded by `demo/ai_validator.py` (direct Claude API). |
| valichord-ui (Svelte/TS frontend) | **Working end-to-end** | Full UI for all three roles (researcher, validator, governance). Wired to a live local conductor: `bash dev.sh` starts conductor + installs app + writes auth token; `npm run dev` serves at `:5173`. `submit_validation_request` → DHT → `get_validation_request_for_data_hash` verified. See `valichord-ui/README.md` and `FRONTEND.md`. |

---

## How the demo runs end-to-end

Five Docker containers — researcher + 3 validators + kitsune2 bootstrap server — each with their own Holochain conductor, keystore, and SQLite database. The only communication between containers is the DHT. **Neither the researcher nor any validator can see each other's results before committing.** Validators do not know what other validators concluded. The researcher cannot know what validators will say. The commit-reveal protocol enforces this structurally — not by policy.

**Run locally:**
```bash
export ANTHROPIC_API_KEY=sk-ant-...
docker compose -f demo/docker-compose.yml up --build -d
until [ "$(docker compose -f demo/docker-compose.yml logs 2>/dev/null | grep -c 'node API →')" -ge 4 ]; do sleep 3; done && echo "Ready"
python3 demo/ai_validator.py --mode decentralised
```

**Run against Oracle (already running — no Docker setup needed):**
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export VALICHORD_RESEARCHER_URL=http://152.67.153.149:3001
export VALICHORD_VALIDATOR_1_URL=http://152.67.153.149:3002
export VALICHORD_VALIDATOR_2_URL=http://152.67.153.149:3003
export VALICHORD_VALIDATOR_3_URL=http://152.67.153.149:3004
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
  http://152.67.153.149:3001/record?hash=uhC8k…

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

### v0.6.1 release — coordinator auto-updater + live-ops hardening — 2026-07-23 ✓

GitHub release **[v0.6.1](https://github.com/ValiChord/ValiChord/releases/tag/v0.6.1)** (2026-07-23), covering the 24 commits since v0.6.0. **Still on the Holochain 0.6.2 toolchain — no DNA-hash or protocol change.**

**Coordinator auto-updater (new; opt-in, default-OFF).** A checksum-verified way to roll coordinator-zome fixes onto the live Oracle nodes with **zero DNA-hash change**, so published HarmonyRecord URLs survive. Built in three phases; full plan + status in `docs/AUTO_UPDATER_SIDECAR_PLAN.md`.
- **`demo/pack-coordinators.mjs`** — packs the four coordinator WASMs and emits `coordinators-manifest.json` (monotonic revision, pinned conductor version, sha256 over each raw WASM). Output self-ignored (`demo/coordinator-updates/`) — WASMs become GitHub release assets, never committed.
- **`demo/coordinator-autoupdate.mjs`** — poller: on a newer revision, downloads each WASM and **sha256+size-verifies before applying anything** (any mismatch aborts the whole update), guards the manifest's Holochain version against the running conductor, applies `UpdateCoordinators` per cell present on the node, **asserts the DNA hash is unchanged**, runs a read-only verify call (attestation → `get_my_claimed_studies`), and writes the applied-revision marker on the persisted volume. Modes: loop / `--once` / `--check`; non-fatal in loop mode. Rollback valve: `AUTOUPDATE_MAX_REVISION` pin ceiling. Launched by an **opt-in, default-OFF** hook in `node-entrypoint.sh` — demo behaviour is unchanged unless `AUTOUPDATE=on` + `AUTOUPDATE_MANIFEST_URL` are set.
- **`demo/publish-coordinators.sh`** — publishes the manifest + WASMs as an immutable GitHub release (`coordinators-rev-<N>`) and prints `AUTOUPDATE_MANIFEST_URL`; refuses to clobber an existing revision.
- **`demo/rehearse-autoupdate.sh`** — self-cleaning end-to-end rehearsal against a throwaway conductor. **Ran green 2026-07-23:** installs `valichord.happ`, applies `UpdateCoordinators` to all four cells, DNA-hash assertion holds on each, attestation verify OK, marker 0 → 1. (Gotchas found + fixed: throwaway config needs a `relay_url` field even single-node; lair socket path kept short for `SUN_LEN` via `mktemp` under `/tmp`.) The live-proven `demo/hotswap-coordinators.mjs` was left untouched.
- Verified conductor-free (`--check`): success, noop, **fail-closed** refusal on tampered sha256, pin ceiling holds/allows.
- **`coordinators-rev-1` published 2026-07-23** (GitHub release, all 5 assets; manifest sha256s verified against the on-disk WASMs, published copy byte-matches local). Manifest URL: `https://github.com/ValiChord/ValiChord/releases/download/coordinators-rev-1/coordinators-manifest.json`.
- **Remaining step is a CONTAINER REBUILD, not a config flip — verified on the box 2026-07-23.** The Oracle clone is at `5b1b465`, **18 commits behind**: `coordinator-autoupdate.mjs` and `pack-coordinators.mjs` are absent and `node-entrypoint.sh` there contains **no `AUTOUPDATE` block**. Setting `AUTOUPDATE=on` today would do nothing — there is no poller in the image to switch on. Enabling it requires `git pull` on Oracle + an **ARM image rebuild** (1-OCPU box) + recreating all 4 containers. **Never `down -v`** — named volumes hold the DHT state and every published HarmonyRecord URL.
- **No urgency: rev-1 is a genuine no-op for Oracle.** The only protocol commit the Oracle clone lacks is `7e8b2e6` (attestation local-read perf), and that was already hot-swapped onto the live nodes 2026-07-08 — so the live conductors are already running rev-1's coordinator code. The updater's value is for the *next* fix, not this one.
- **Lower-risk alternative to the rebuild:** `docker cp` the updater into one running container and run it `--once` against rev-1 (a no-op) — proves the real Oracle apply path with no rebuild, no restart, no downtime. Mirrors how `hotswap-coordinators.mjs` was delivered.

**Also folded into v0.6.1** (landed just after the v0.6.0 tag): first live coordinator hot-swap on Oracle + local-read perf (self-authored lookups read `GetStrategy::Local`); the Oracle demo rebuilt on a new Ampere A1 / ARM server; the UI Playwright e2e suite against a real conductor + the data-hash `pattern` form-blocking fix; GitHub Pages refresh; a forward-looking sharding design note; and the Holochain 0.7.0 RC watch note.

### 🚨 Holochain 0.7.0 STABLE SHIPPED — 2026-07-30 (report-only, still on 0.6.2)

**Eric Harris-Braun announced on a live stream (~15:00 UK) that 0.7.0 was ready; it released ~90 minutes later.** Verified on all three surfaces:

| Surface | Value |
|---|---|
| GitHub release `holochain-0.7.0` | `prerelease=false`, **2026-07-30T16:28:31Z** |
| git tag `refs/tags/holochain-0.7.0` | exists |
| crates.io `holochain` / `hdk` / `hdi` | **0.7.0** / **0.7.0** / **0.8.0** |

⚠️ **We remain on 0.6.2. When we upgrade, it happens on a dedicated `v0.7.0` branch — `main` stays on 0.6.2.** User decision, 2026-07-30. `main` keeps the working, publicly-demoed stack until the branch is fully green (Tryorama + all 5 sweettest suites + UI e2e + a live demo round) **and** the user explicitly approves the merge.

#### 🔴 The migration is THREE-PHASE — two phases blocked on upstream

| Phase | Scope | Status |
|---|---|---|
| **A** | 4 DNA zomes + `sweettest_integration` | ✅ **unblocked — can start now** |
| **B** | 97 Tryorama tests + Svelte UI | 🔴 blocked on upstream |
| **C** | `valichord/wind-tunnel/` | 🔴 blocked on upstream |

**Phase B** — checked ~15 min after release: `@holochain/client` latest **0.20.8** (0.21 only as `rc.1`), `@holochain/tryorama` latest **0.19.2** (*no 0.7 line at all*), `@holochain/hc-spin` latest **0.603.0**, holonix has **no `main-0.7`** branch, and upgrade-guide PR #647 was last updated *before* the release. There is nothing to migrate *to* yet.

**Phase C** — found in the API audit, not previously recorded: `wind-tunnel/` depends on **`holochain_wind_tunnel_runner`**, a third-party crate pulling `holochain = "0.6"`. It must ship a 0.7 version first.

#### Verification pass — the plan was re-checked against shipped 0.7.0

The pre-release notes were built from indirect sources (branch-watching, RC changelogs, a draft guide written against rc.4) and **four proved wrong**. A verification pass was run against the *shipped* `hdi 0.8.0` / `hdk 0.7.0` crate sources and the published CHANGELOGs. Full evidence-tagged checklist (✅ verified / ❌ corrected / ⚠️ unverified) is in `CLAUDE.md` → "Pending upgrade checks". Headlines:

- ✅ **Held up exactly:** the `FlatOp` rename table (6 shipped variants, all as recorded); the **51 match arms** and their 26/12/8/4/1/0 breakdown (independently recounted); both link variants folding into one `OpLink`; the `@holochain/client` 0.21.x vs Rust `holochain_client` 0.9.0 distinction (0.9.0 shipped in this release); the 5 live conductor-config hit sites.
- ❌ **Guide was stale, in our favour:** `OpActivity::CreateAgent` **keeps** its `agent` field (#5910 restored it), and **our membrane-proof arm needs only the variant rename** — shipped `AgentValidationPkg` retains `membrane_proof` and our arm destructures exactly that. The guide's rewrite recipe applies to a variant we never match.
- ❌ **Source-chain restore confirmed ABSENT from 0.7.0** (only #5799 groundwork shipped). All `AppStatus::AwaitingRestore` / `RestoreComplete` / `restore_chain_quorum` checklist items are **dead** — no `dev-setup.mjs` or Svelte work needed.
- 🆕 **Ordering hazard rescoped.** `OpUpdate::PrivateEntry` survives in 0.8.0, and private entry types can never match `OpUpdate::Entry`. So the per-type guard arms in `validator_workspace_integrity.rs:149,157` and `researcher_repository_integrity.rs:150` are **unreachable dead code** — immutability in DNA 1 / DNA 2 rests on a **single blanket `OpUpdate::PrivateEntry` arm each**. The real match-ordering risk is concentrated in the **attestation** DNA (the only one with public entries).
- ❌ **The three existing "immutability" sweettests are fake.** `sweettest_integration/tests/attestation.rs:267,313,334` call zome functions (`update_attestation_for_test`, `update_commitment_for_test`, `update_phase_marker_for_test`) that **exist nowhere in the codebase**; they pass on "function not found" and would stay green with `validate()` deleted. Fix or replace before trusting any immutability signal.
- ✅ **RETIRED — conductor-config syntax verified empirically** (see below). Was the last ⚠️ on the critical path.

#### Conductor-config verification against the real 0.7.0 binary — 2026-07-30 ✓

Downloaded `holochain 0.7.0` to scratchpad (**the 0.6.2 on `PATH` untouched**) and ran both our configs against it. Confirmed the "fails to start, does not degrade" prediction — exit code 42, hard parse error. **Then found the fix is tiny: two lines per file.**

- Remove `signal_url` from `network:`; rename `db_sync_strategy` → **`db_sync_level`** (`Fast`→`Off` in `demo/conductor-config-node.yaml`, `Resilient`→`Normal` in `valichord-ui/dev-conductor.yaml`). `demo/rehearse-autoupdate.sh:56` needs the `signal_url` removal only.
- **With those edits both configs start a 0.7.0 conductor and open their admin port.** Everything else we use survives: `data_root_path`, `keystore`, `lair_root`, `admin_interfaces`, `bootstrap_url`, `relay_url`, `db_max_readers`.
- ⚠️ **Not applied to `main`** — `db_sync_level` breaks 0.6.2. These go on the `v0.7.0` branch.

The parser's error messages also yielded the full allowed-field lists (recorded in `CLAUDE.md`), which produced three findings:

1. ❌ **Correcting our own earlier finding: `restore_chain_quorum` IS a valid 0.7.0 config field**, despite the source-chain-restore workflow not shipping — the config surface landed ahead of the feature. (The `AppStatus`/signal items remain likely-absent; only this one was wrong.)
2. 🆕 **`base64_auth_material_bootstrap` / `base64_auth_material_relay` are real `network` fields** — the kitsune2 v0.5.0 authenticated-relay work surfacing in conductor config. Relevant to the relay blocker and kangaroo packaging.
3. 🆕 **`target_arc_factor` is a `network` config field in 0.7.0** — relevant to the polite-shrink / kitsune2 #160 work.

#### Immutability tripwire tests — 2026-07-30 ✓ (the pre-migration safety net)

**5 new sweettests that actually prove the integrity zomes reject forbidden updates** — the first tests in the repo to do so. `valichord/sweettest_integration/tests/immutability_tripwire.rs`. All 5 pass (825 s).

They need a special build, because no production coordinator exposes `update_entry`: three coordinators carry `#[cfg(feature = "test_utils")]` externs that issue one. `./build-test-dnas.sh` then `VALICHORD_DNA_DIR=../workdir-test cargo test --test immutability_tripwire`.

**Proven to work by negative control — the part that matters.** Moving the `ValidationAttestation` guard behind the generic update arm (exactly the accident the 0.7 `FlatOp` rename can cause) made the forbidden update **silently succeed**, returning a real `ActionHash`; it fell through to the generic arm, whose author-check passes for the entry's own author. **The tripwire failed as designed.** Guard restored → green again. So the match-ordering hazard is real, and the test genuinely detects it — unlike the three fake tests deleted the same day.

⚠️ `rustc` does emit `warning: unreachable pattern` for the shadowing case, but it is a warning among others, and it catches **only** shadowing — not a deleted arm, nor one whose pattern stops matching after a rename.

**Safety:** hooks are absent from production builds; the feature build goes to `target-test/` and packs to `workdir-test/` (both gitignored), never the committed `workdir/`; the test manifests point their **integrity** zome at the *production* build so what's under test is byte-identical to what ships; and `./check-no-test-hooks.sh` fails if any committed bundle contains the hooks — now wired into CI as the dependency-free `no-test-hooks` job that fails in seconds ahead of the 90-minute matrix.

⚠️ **That guard was itself broken on first write, and the fix is worth remembering.** It grepped the bundles directly and reported "clean" for *everything* — including bundles that definitely contained the hooks — because Holochain bundles are compressed (`*.dna` = one gzip layer; `*.happ` = gzip → msgpack → nested gzip). It was a guard that could not fail: the same false-confidence class as the fake immutability tests deleted the same day. Now decompresses recursively, and is verified in **both** directions (passes on `workdir/`, fails on `workdir-test/` — while still correctly passing `governance.dna`, which carries no hooks).

**Coverage follows the verified entry-visibility split:** 3 per-type tests on `attestation` (public, ordering matters), 1 blanket-arm test each on `validator_workspace` and `researcher_repository` (all-private, where one `OpUpdate::PrivateEntry` arm is the entire guard).

#### Mechanical API audit — 2026-07-30 ✓ (grep across 4 zomes + shared_types + sweettest_integration)

Ran to size the migration precisely. **Result: almost everything on the breaking-change list is a hard zero in our code.**

- ✅ **Confirmed ZERO:** `ChainFilter`, `get_link_details`/`get_links_details`, `Record::new`, `block_agent`/`unblock_agent`, `EntryCreationAction`, `NewEntryAction`, `ActionBuilder`, `RateWeight`/`EntryRateWeight`, link `base_address`/`target_address`/`tag` destructuring, and `ChainIntegrityWarrant`/`InvalidChainOp`/`SignedWarrant`. `must_get_agent_activity` appears once — **inside a comment**, not a call.
- ❌ **Listed as work, actually zero:** the three `AgentActivity` → `AgentActivityStatus` call sites (`governance_coordinator:188,322`, `attestation_coordinator:637`) **need no changes.** Verified against shipped `hdk 0.7.0`: the `get_agent_activity` signature is identical to 0.6.2 (same 4 args), only the return type's *name* changed — and we never name it, we only read `.warrants`, which survives on `AgentActivityStatus`.
- ✅ **Smaller than recorded:** the `hdk`/`hdi` bump is **~7 version strings**, not "Cargo.toml across all zomes" — every zome uses `{ workspace = true }`; the only literals are `valichord/Cargo.toml:18-19`, `sweettest_integration/Cargo.toml:42`, plus 4 holochain pins in sweettest.
- ⚠️ **`sweettest_integration` import surface is 3 lines, but 2 are globs** (`holochain::prelude::*`, `holochain::sweettest::*`) — so PR #5898's re-layering will surface as unresolved names scattered through the tests, not as import errors.

**Net: the migration reduces to (a) the 51 `FlatOp` match arms, (b) 3 conductor-config files, (c) ~7 version strings + sweettest feature flags.** Everything else is confirmed zero or zero-work.

**RC history:** `0.7.0-rc.0` (2026-07-15), rc.1 (07-16), rc.2, rc.3, rc.4, rc.5 (07-29) — the "watch for rc.0" trigger from the 2026-06-13 estimate firing. One further correction from the 2026-07-27 notes: #5898 (re-layers conductor state types out of the `holochain` crate, which `sweettest_integration` depends on directly) and #5906 (paginated state dumps) were recorded as landing *after* rc.4; they are **in rc.4**. Both remain real migration items. rc.5 absorbed #5910, settling the HDI validate-callback surface our four integrity zomes depend on.

RC changelogs confirmed several breaking changes have now actually landed (previously anticipated): the **v2 Action model is canonical** (legacy per-variant action structs + `ActionBuilder` + `EntryCreationAction`/`NewEntryAction` enums removed — the FlatOp-v2 migration our four integrity zomes need); **`holochain_sqlite` removed**, persistence in `holochain_data`, DBs renamed → **must clear state / `docker compose down -v`** on the Oracle demo, not a binary swap; **`rate_limit` module removed** (`RateWeight`/`EntryRateWeight` — no code impact, but Holochain KB §43 now stale for 0.7); `transport-iroh` feature flag removed; `DnaStorageInfo` size fields changed. Full, verified checklist lives in `CLAUDE.md` → "Pending upgrade checks" (⬤ = confirmed-in-rc.0).

**An official 0.6 → 0.7 upgrade guide now exists — 2026-07-27.** `holochain/docs-pages` branch `docs/upgrade-guide-holochain-0.7` adds a 700-line guide (`src/pages/resources/upgrade/upgrade-holochain-0.7.md`) plus a 0.7 compatibility table. No PR yet; written against rc.4 and explicitly warning that *"further breaking changes are still possible"*. It names three big changes: the rewritten action model (`header` + `data`), tx5/WebRTC fully gone, and **no data migration path**. It points at `holochain/dino-adventure`'s integrity zome as the reference port to adapt our `validate` dispatcher from, and notes **no 0.7 scaffolding release exists yet**.

Read against our own code, it produced one correction and several new items — full audit in `CLAUDE.md` → "Pending upgrade checks" → "Official upgrade guide". The headlines:
- **`FlatOp` variants are all renamed**, and we have **51 match arms** across the four integrity zomes (26 `RegisterUpdate` → `Update`, 12 `StoreEntry` → `CreateEntry`, 8 `RegisterDeleteLink` → folded into `FlatOp::Link`, 4 `RegisterDelete`, 1 `RegisterAgentActivity`).
- ⚠️ **The 26 `RegisterUpdate` arms are our immutability guards** (`ValidationAttestation`, `CommitmentAnchor`, `PhaseMarker`, `StudyClaim`, `ValidatorPrivateAttestation`, `LockedResult`), and per the architecture doc **Rust match ordering is the enforcement**. A mechanical rename that reorders them disables immutability silently — no compile error, no test failure unless a forbidden update is explicitly attempted. Its own migration step, with a forbidden-update test per guarded type.
- **Conductor configs will fail to start, not degrade** — `NetworkConfig` now rejects unknown fields. Five live hits: `demo/conductor-config-node.yaml:19,21`, `valichord-ui/dev-conductor.yaml:17,19`, `demo/rehearse-autoupdate.sh:56`.
- Client-version error corrected (`@holochain/client` → 0.21.x, not 0.9.x — three `package.json` pins), `AgentActivity` → `AgentActivityStatus` (3 call sites), `valichord-ui/src/lib/types.ts:331` needs `.header.author`. `docs/Holochain_complete.md` §40 gained a 0.7 warning — it had documented `signal_url` as current with no caveat.
- Confirmed **not** applicable to us: `Record::new`, `block_agent`/`unblock_agent`, link base/target/tag destructuring.

**0.6.3** also shipped (2026-07-15) on our stable line — a one-line `reqwest`/native-tls build patch in `holochain_metrics`; nothing for us, no bump.

**Blocker-remover — ✅ LANDED 2026-07-27, ✅ NOW PUBLISHED in kitsune2 `v0.5.0` (2026-07-28), reachable at the 0.7 migration.** What was tracked as branch `fix/491-stabilize-the-iroh-relay-hosted-in-bootstrap_srv` merged to kitsune2 `main` as **`3746be1` — *"feat: stabilize authenticated iroh relay hosted in the bootstrap server"*** (refs #492; 16 files, ~+1160/−490). It puts an authenticated iroh relay *inside* `kitsune2-bootstrap-srv`: relay access gated by a bearer token on the relay WebSocket upgrade (`RelayConfig::with_auth_token`), validated in `AccessControl::on_connect`; bootstrap client gains `blocking_fetch_relay_token`; a client-side registration heartbeat (`relayReRegistrationIntervalS`, default 120 s) plus a token-rotating watchdog work around iroh 1.0.0 capturing the relay token once per connection actor; the legacy `PUT /relay/register` allowlist stays for 0.4.x clients. Unit + server-side auth-flow + end-to-end bootstrap-restart recovery tests. **This clears the "separate Iroh relay" prerequisite for both the deferred wind-tunnel kitsune live run and kangaroo desktop packaging — as a 0.7-migration item, not something we can use on 0.6.2.** The 2026-07-27 re-check condition ("does the picked-up kitsune2 actually carry `3746be1`?") **is answered: yes.** Verified 2026-07-30: kitsune2 **`v0.5.0` stable shipped 2026-07-28** and contains `3746be1` (`v0.5.0` is 7 ahead / 0 behind it; it appears in the 24-commit `v0.5.0-dev.6...v0.5.0` list), with two relay follow-ups on top — `03d21103` *"negotiate relay protocol version, enabling V2"* and `768b01b1` *"add TLS security headers to relay HTTP responses"*. **holochain `0.7.0-rc.5` pins `kitsune2_* 0.5.0`** (PR #5913, bumped from rc.4's `0.5.0-dev.6`). Our 0.6.2 stays on `0.4.1`, so plan the relay work as part of the 0.7 migration rather than before it. Note the **holochain side's own backport branch has not consumed it** — that repo's `fix/491-…` branch is stale (last commit 2026-04-22, 114 behind `develop`).

**Branch watch re-verified 2026-07-30** against `holochain/holochain`'s `develop` (which is the default branch). Two changes since 2026-07-27: `feat/5800-source-chain-restore-workflow` **now has an open PR (#5920)** — draft, conflicting, 20 ahead / 4 behind. **It missed the 0.7.0 release** (still a conflicting draft ~8 h before `d1ec5a72` prepared it), so expect it in a later 0.7.x; it still does not recover private entries → `ValidatorPrivateAttestation`/`LockedResult` lost on restore; and PR **#5912** *"test: add DHT sync coverage for private entries"* **merged and shipped in rc.5**, so it drops off the watch list (test-only, no defect surfaced — a mild positive for the DNA 1/DNA 2 private-entry gossip semantics we depend on). ⚠️ **`feat/generate-ts-types-ts-rs` is dead, not active** — last commit 2025-12-11, message `wip`, 257 behind; the hand-maintained `valichord-ui/types.ts` mirror has no replacement coming. Nine other previously-watched branches confirmed stale.

### First live coordinator hot-swap on Oracle (local-read change) — 2026-07-08 ✓

The flowsta "local reads for self-authored lookups" pattern (commit `7e8b2e6`) was rolled onto all
four live Oracle demo nodes via `AdminRequest::UpdateCoordinators` — **zero downtime, zero DNA-hash
change, no container restarts, all HarmonyRecord URLs preserved.** First production use of the
coordinator hot-swap mechanism.

- **Code:** `release_claim`, `get_my_claimed_studies`, and the duplicate-commitment guard in
  `notify_commitment_sealed` now use `GetStrategy::Local` for self-authored lookups (quorum counts and
  reclaimer-release checks stay `Network`). Read-strategy rule added to CLAUDE.md hard constraints.
- **Test evidence:** all four sweettests covering the changed functions pass serially; CI ran the full
  matrix on the push (Tryorama 97 + UI e2e + 5 sweettest suites). Local full-suite serial runs were
  twice killed by an unexplained external SIGTERM ~1.5 h in (8/8 passing at kill both times; 2-core
  Codespace) — the "only run the tests that matter, let CI do the matrix" approach is the documented
  workaround.
- **Tooling:** `demo/hotswap-coordinators.mjs` — rehearse locally with `REHEARSAL=1` against a
  throwaway conductor, then `docker exec` per container (researcher first, verify between nodes).
  Runbook in the script header.
- **Live verification:** post-swap `get_my_claimed_studies` returned 2 real claimed-study records on
  each validator through the new Local-read path; all four `/health` endpoints green; public record
  URL (`uhC8kCnUE…`) still serving `Reproduced`/`ExactMatch`.

### Oracle demo outage + full rebuild on new server — 2026-07-07 ✓

**Outage:** the original Oracle VM (132.145.34.27) was reclaimed when the account's free trial ended **2026-06-11** — discovered only 2026-07-07 when grant-application demo links failed. All DHT state on that box (including every published HarmonyRecord URL) is unrecoverable. The Render web demo itself never went down; it just couldn't reach the nodes.

**Rebuild (same day):** account upgraded to **Pay-As-You-Go** (required for A1 capacity; a £1 budget alert is set — the instance itself is an Always Free shape, £0/month). New instance `instance-20260707-1610` = **152.67.153.149**, Oracle Linux 9, **Ampere A1 ARM, 1 OCPU / 6 GB** (+4 GB swap; free-tier capacity capped the shape — resize to 4/24 pending an A1 service-limit increase). SSH: key `oracle_valichord` (user `opc`). Stack deployed from a repo clone + two ARM-patched files; all four node APIs verified healthy from the public internet.

**ARM compatibility changes (committed `2ff064d`, pushed to main):**
- `demo/Dockerfile.node` — arch-detects via `uname -m`, exec-tests bundled binaries, downloads `holochain` + `kitsune2-bootstrap-srv` for the right target from the Holochain 0.6.2 release (conductor bumped 0.6.1 → 0.6.2)
- `demo/docker-compose.yml` — bootstrap service now runs from the shared node image instead of bind-mounting the committed x86-only `demo/bin/kitsune2-bootstrap-srv`
- IP sweep 132.145.34.27 → 152.67.153.149 across `render.yaml`, `demo/ai_validator_cma.py`, README + demo docs

**Verified live end-to-end:** full commit-reveal round runs on the new box (Reproduced 3/3, ExactMatch); the public Render site (`valichord-demo.onrender.com/demo`) proxies to the new nodes and returns the signed record. Fresh shareable HarmonyRecord for grant applications: `http://152.67.153.149:3001/record?hash=uhC8kCnUE040sim58_Ae84Y_QIoOEPBZ3XQLNEqii_mG-IpddkA-n` (also via the site at `/demo/record/<hash>`).

**Ops facts for next time:**
- Oracle Linux 9 default user is `opc` (not `ubuntu`).
- Demo ports need opening in BOTH the VCN Security List (console) AND host firewalld (`firewall-cmd --permanent --add-port=3001-3004/tcp`).
- OCI ephemeral public IPs survive stop/start but die with the instance. Reserving `152.67.153.149` is **deferred housekeeping** — the console wouldn't convert ephemeral→reserved in place (would change the IP), and the ephemeral address is stable unless the instance is terminated. Do it calmly later (accept the new IP + re-sweep) before the next round of published links.
- **The Render `valichord-demo` service reads env vars from the DASHBOARD, not `render.yaml`** — the blueprint file is inert for it. The four `VALICHORD_*_URL` vars had to be set/edited in Render → service → Environment tab (dashboard values always win). `render.yaml` was updated too for correctness/future blueprint use, but editing it alone does nothing to the live site. Symptom of a missing var: the app falls back to `localhost:3001` and the record proxy returns "Connection refused" (errno 111); a wrong-but-set IP gives "Connection timed out" (errno 110).
- **Never keep work on a fork's main — "Sync fork" force-pushes it away** (bit us twice today: lm-eval ValiChordLogger rescued to branch `valichord-logger`).

### Future AGI public issue — verifiable eval-run exports — 2026-07-07 ✓

Filed [future-agi/future-agi#1368](https://github.com/future-agi/future-agi/issues/1368) — *"feat(evals): verifiable eval-run exports — canonical JSON + content hash so shared results can be independently checked"*. Follows their CONTRIBUTING issue-first rule; complements the 2026-07-06 email to Nikhil Pareek (context: `memory/reference_futureagi_nikhil.md`). Proposes an RFC 8785 canonical export + SHA-256 content hash + per-datapoint Merkle root (selective disclosure), names `valichord_attestation` as prior art (adapters: lm-eval-harness, Inspect AI, AILuminate), offers adapter or endpoint PR. Their self-run benchmark claims (AgentCompass/TRAIL) addressed gain-framed: "first eval platform whose headline numbers are independently checkable" — deliberately no deficit-framing (see `memory/feedback_outreach_tone.md`). Repo evidence behind the issue: `Evaluation` results = mutable JSONFields (`futureagi/model_hub/models/evaluation.py`), only export surface = annotation-queue CSV, SDK `BatchRunResult` has no canonical serialization. Filed via gh CLI so the form's auto-labels weren't applied (cosmetic; we lack triage permission). Their CONTRIBUTING promises maintainer response in ~3 business days. **Adapter still not to be built on spec** — wait for engagement.

### UI e2e suite + form-blocking bug fix + CI job — 2026-07-06 ✓ (same day as v0.6.0; folded into the v0.6.0 release notes, no new release)

Ported the real-conductor Playwright e2e pattern from `happenings-community/requests-and-offers` (`feat/e2e-real-conductor-infrastructure`) to `valichord-ui` — the UI's first automated browser coverage. Commits `f550ba1` (bug fix), `1cf6b5d` (harness), `bf17555` (CI job).

**The harness** (`valichord-ui/tests/e2e/`): Playwright globalSetup starts one throwaway conductor per run (admin `:4445`, app `:8889`, `/tmp/valichord-e2e-data` — never clashes with dev.sh), installs the hApp with the dev-mode membrane-proof bypass (mirrors dev-setup.mjs — **update both files if DNA properties change**), issues auth token + per-cell signing credentials, and hands them to the browser via URL hash params `#APP_PORT=&TOKEN=&CREDS=` (the Launcher channel App.svelte already read; `holochain.ts` gained the `CREDS` fallback). Six tests as one serial story: connect → validator profile via UI → researcher request via form → validator browse list → zome-seeded request renders → governance view. Hybrid seeding via a Node-side AppWebsocket client. `npm run test:e2e`; ~1.3 min locally.

**Production bug caught on the suite's first run:** `ResearcherView.svelte` had `pattern="[0-9a-f]{64}"` on the data-hash input — Svelte parses `{64}` in a quoted attribute as a template expression, so the DOM got `pattern="[0-9a-f]64"` and native form validation silently rejected every real 64-char hash: **the Submit button did nothing for every user of the form** (no toast, no error). Fixed with `pattern={"[0-9a-f]{64}"}`. Diagnosis path worth remembering: zome-call failures surface as 4-second toasts that failure screenshots miss — `gotoApp` now pipes browser console errors into test output, and durable assertions (screen transitions) are preferred over toast text.

**CI:** new `ui-e2e` job in `tests.yml` — independent fast-signal job using the **committed** `workdir/valichord.happ` (no Rust toolchain), shared `hc-bin-0.6.2` cache, Node 22, Playwright chromium. **Passed first CI run in 1 m 19 s.** Traces/screenshots uploaded on failure; one CI-only retry. CLAUDE.md CI-upgrade checklist now lists 6 edit sites (3 jobs).

**README refresh (same session):** repo links `topeuph-ai/ValiChord` → `ValiChord/ValiChord` (49 links; Pages + valichord_at_home untouched); stale free-demo description replaced with the current Your Hypothesis demo (visitor's own key); test counts corrected to 183 across three suites (97 Tryorama / 80 sweettest / 6 Playwright); wind-tunnel 3 → 5 scenarios; quickstart 0.6.1 → 0.6.2; valichord_attestation 259/100% → 537/97% + five adapters; broken Funding & Research table fixed.

---

### v0.6.0 release — core hardening merged (PR #26) — 2026-07-06 ✓

Branch `core-hardening-0.6.2` merged to main (`c934497`) after its first fully green CI run, and published as **GitHub release v0.6.0** — the first tag since v0.5.4 (2026-05-24), covering 194 commits.

**What the branch shipped** (commit `a757441`):
- **Commit-reveal verification enforced for real nonces** — `submit_attestation`'s hash-verification bypass narrowed from "issuer empty" to "issuer empty AND nonce empty", mirroring `reveal_researcher_result`. Real-nonce reveals (demo bridges, UI dev) are now verified on-chain even on dev-mode networks; empty-nonce test flows unaffected. Coordinator-only for that file. New sweettests S7 (real-nonce reveal passes verification) and S8 (tampered reveal rejected with "Hash mismatch") — the first tests to exercise both paths, running the genuine workspace seal flow.
- **StudyClaim immutability** — integrity-zome update/delete guards; claims vacate via `StudyClaimRelease` as the architecture doc states. Integrity change → **attestation DNA hash bumped** (dev-only impact; existing dev conductors need reinstall).
- **Holochain 0.6.2 toolchain** — hdk 0.6.2, hdi 0.7.2, holochain/holochain_types/holochain_keystore/holo_hash 0.6.2; CI BASE + cache keys updated; hApp repacked.

**CI flake diagnosis + fix** (commit `136ae8f`): run 28753458422 failed `silver_badge_issued_with_five_validators` and `get_badges_by_type_bronze_with_three_validators` — diagnosed as the documented badge-index gossip-lag flake (same class as the gold-test flake fixed 2026-06-13), not a regression: the branch touched no governance code and the already-hardened gold test passed. Fix (test-only): ported the gold test's 5-iteration re-sync + re-query loop to silver and bronze; widened bronze's `await_consistency_s` windows 20 s → 60 s (3-conductor test was using the 2-agent standard). Next run: all 6 CI jobs green.

**Also this session:** Future AGI outreach — Nikhil Pareek (founder, future-agi/future-agi eval platform) cold-emailed; replied with a repo-specific gap analysis (eval-result verifiability) + two-page integration brief. See `memory/reference_futureagi_nikhil.md`. Do not build their adapter on spec.

---

### Security/efficiency audit + spring-cleaning fixes — 2026-07-05 ✓

Full read-only audit of all workspaces (4 DNA zomes, Flask demo, Node bridges, attestation library, UI, CI), then targeted fixes. **No DNA or protocol changes; nothing repacked.**

**Fixed:**
- **`ws` high-severity vulns** — `npm audit fix` in `valichord-ui` (now 0 vulns) and `valichord/tests` (ws fixed; remaining 4 vulns are the esbuild→vite→vitest dev-tooling chain, fix requires breaking vitest 3→4 — deliberately deferred, dev-only exposure)
- **GovernanceView badge display bug** — `inferBadge`/`badgeEmoji`/`badgeClass` compared against stale short names ("Gold"/"Silver"/"Bronze"/"Failed"); every badge rendered "—". Now uses canonical `BadgeType` literals. Same class of bug as the v0.5.4 types.ts fix, missed in the view. `npm run check` now 0 errors (was 14; also added required `keyType: "ed25519"` in holochain.ts dev credentials)
- **Demo API-key hygiene (`demo/app.py`)** — `_custom_jobs` entries scrub `_api_key`/`_claim`/`_user_answer` on terminal state and evict after 1 h TTL; watchdog sweep is now exception-guarded (dict-mutation race could previously kill the thread → demo stuck "busy" until redeploy); `_custom_running` cleared under lock
- **`custom_runner.py` agent-env cache** — now keyed by SHA-256 of the API key (raw visitor keys no longer persist in memory) and size-capped at 32
- **CI supply chain** — `jlumbroso/free-disk-space@main` pinned to SHA `54081f1` (= v1.3.1, same commit; zero behaviour change)
- **`backend/app_protocol.py`** — API key check now constant-time (`hmac.compare_digest`)

**Verified:** UI `npm run check` 0 errors; demo suite 52 tests pass; scrub/eviction/cache-cap logic unit-tested inline.

**Demo follow-up round (same day, after user approval):**
- **Website copy corrected** (`demo/app.py` accordion) — no longer claims on-chain reveal verification; now says commitments are public and immutable before reveal (true on the demo network) and that production networks enforce the hash match at reveal time (true). Root cause: Oracle installs with empty issuer (`demo/node-setup.mjs:78`) and `submit_attestation` skips SHA-256 verification in that mode. **The coordinator fix was investigated and deliberately NOT made:** the empty-nonce bypass is load-bearing for both test suites (`sweettest attestation.rs:55`, `governance.test.ts:238` — tests fabricate commitments and reveal with empty nonces). Making verification unconditional breaks ~165 tests. Proper fix = decouple verification from the issuer key via a dedicated test-mode flag + migrate tests to the full seal→nonce→reveal flow — needs its own session.
- **Node API write auth shipped (off by default)** — `checkNodeKey` in `node-lib.mjs`: when `NODE_API_KEY` is set in the container env, all POST endpoints on researcher/validator nodes require a matching `X-ValiChord-Node-Key` header (timing-safe compare). Reads (`/health`, `/phase`, `/record`) stay open — public record URLs are the point. All three Python callers (`ai_validator.py`, `ai_validator_cma.py`, `demo_runner.py`) send the header when `VALICHORD_NODE_KEY` is set. **Enabling it is an ops step:** set `NODE_API_KEY` on the 4 Oracle containers AND `VALICHORD_NODE_KEY` on Render + any local runner — rolling out one side only breaks the demo.
- **In-memory Map caps** — `capMap` (200 entries, oldest-evicted) on `lockedResults` (researcher) and `tasks` (validator); unauthenticated spam can no longer grow node memory without bound.
- **`Dockerfile.node` root user — investigated, WON'T FIX:** conductor keystores live in named volumes that are root-owned on Oracle today. Adding `USER` would crash-loop all 4 nodes on any future image rebuild that doesn't `down -v` — and `down -v` destroys the publicly shared HarmonyRecord URLs. Container-root in an isolated bridge network is the lesser risk.

**Still deferred (core, batch with future work):**
1. Commit-reveal verification decoupled from issuer bypass (coordinator + test migration — dedicated session; see above).
2. StudyClaim update/delete guards (integrity change → DNA hash bump — batch with next integrity work).
3. Merkle leaf/node domain separation (RFC 6962 prefixes) — attestation format v2 consideration.

### DeliberateAbstention entry type (validator_workspace DNA) — 2026-06-27 ✓ (pushed to main)

New private entry type that distinguishes a validator who consciously stepped back from one who simply never showed up — the equivalent of a reasoned recusal in scientific peer review.

**Changes (all in `valichord/dnas/validator_workspace/`):**
- **`validator_workspace_integrity`** — `DeliberateAbstention { request_ref: ExternalHash, reason: Option<String> }` added as a private entry type. `RequestToAbstention` link type added. `validate()` blocks updates and deletes on `DeliberateAbstention` (immutable by design, same pattern as `ValidatorPrivateAttestation`).
- **`validator_workspace_coordinator`** — `record_deliberate_abstention(input: DeliberateAbstention) -> ActionHash`: guards against duplicates by checking `RequestToAbstention` links before writing; creates the entry and link. `get_abstention_for_request(request_ref: ExternalHash) -> Option<Record>`: follows the link and queries the local source chain for the target.

**Sweettest:** 3 new tests in `sweettest_integration/tests/validator_workspace.rs` — `get_abstention_returns_none_before_recording`, `record_and_retrieve_deliberate_abstention`, `duplicate_abstention_is_rejected`. All 12 validator_workspace tests pass (9 pre-existing + 3 new).

**Note:** This is an integrity zome change — `DeliberateAbstention` is a new entry type and `RequestToAbstention` is a new link type, so the validator_workspace DNA hash has changed. Dev-only; no live network impact.

---

### Governance / IP files — 2026-06-24 ✓ (pushed to main)

Three root-level files establishing the open-core IP structure:

- **`CONTRIBUTING.md`** — contributor guide + lightweight CLA. Point 3 grants the maintainer a perpetual right to re-license contributions, preserving the commercial/dual-licence option without requiring future contributor contact.
- **`NOTICE`** — standard Apache 2.0 copyright notice; scopes the licence to source code only and cross-references `TRADEMARK.md`.
- **`TRADEMARK.md`** — trademark policy, independence commitment, governance statement, and commercial-licensing terms. Includes a "Maintainer's note on IP structure" confirming the deliberate open-core design; binding pieces to be finalized with counsel before anything is signed.

Contact email (`topeuph@gmail.com`) wired into both `CONTRIBUTING.md` and `TRADEMARK.md`.

---

### Meeting with Cazandra Aporbo (LOOPCHii) — 2026-06-24

Meeting went well. Transcript being prepared. See `memory/reference_loopchii_cazandra.md` for contact and thread details.

---

### Two new valichord_attestation adapters — 2026-06-23 ✓ (pushed to main)

**`LmEvalAdapter`** (`valichord_attestation/adapters/lm_eval_adapter.py`) — reads lm-evaluation-harness `results_*.json` (v0.4+) and optional `samples_*.json` (from `--log_samples`) and converts them into a canonical Bundle. Field mapping: `pretty_model_name` / `model_source` / `pretrained=` parse / `config.model` (priority chain) → `model_id`; task name(s) `"|"`-joined when multi-task → `task_id`; per-metric values with `,none` suffix stripped and `_stderr` keys excluded → metrics; multi-task keys prefixed with task name (`hellaswag/acc`). Without `--log_samples`, one summary leaf per task is synthesised as a fallback. `task_names=`, `metric_keys=`, `task_id_override=` for caller control. 51 tests.

**`AiluminateAdapter`** (`valichord_attestation/adapters/ailuminate_adapter.py`) — reads the `benchmark_run_*.json` report produced by MLCommons modelbench (AILuminate v1.0+) and optional per-item annotation dicts from `compile_annotations()`. Field mapping: `scores[i].sut.uid` → `model_id`; `benchmark.uid` → `task_id`; per-hazard `score.estimate` → `{code}_safe_rate` metrics (e.g. `cse_safe_rate`, `dfm_safe_rate`); `numeric_grade` 1-5 → `{code}_numeric_grade` (optional, on by default); top-level `score` → `overall_safe_rate`; `end_time` → `generated_at`; `_metadata.code.source.code_version` → `repo_commit`. When annotations are provided each `{hazard, prompt, response, is_safe, is_valid}` dict is used as a Merkle leaf, committing to the model response AND the grader ensemble verdict together. Multi-SUT reports require `sut_uid=` to select one model. Hazard short-code extraction strips version prefix (`safe_hazard-1_0-cse` → `cse`). 42 tests.

**Why these two matter:** `LmEvalAdapter` covers the de-facto industry standard for LLM benchmarking (HuggingFace Open LLM Leaderboard, NVIDIA, Cohere etc.) — highest-value target for the "user is already running this" scenario. `AiluminateAdapter` covers the strongest ValiChord *value story*: AILuminate uses LLM-as-judge grading where honest validators can legitimately differ, so blind independent verification proves more than anti-fabrication — it proves independent judgment convergence. Natural fit for Justin (AISI/Arcadia AI-safety world).

**Adapter priority tracking (from eval-landscape survey):** lm-eval-harness ✓ done → AILuminate ✓ done → HELM methodology (reference only, maintenance mode, no adapter planned) → everything else: skip.

---

### OETP bridge — 2026-06-22 ✓ (pushed to main)

`demo/oetp_bridge.py` — three pure functions for embedding a ValiChord HarmonyRecord into an [Open Ethics Transparency Protocol](https://github.com/OpenEthicsAI/OETP) disclosure (an IETF Internet-Draft JSON standard for AI transparency).

**Integration point:** `snapshot.processing.source[]` — an existing OETP array of `{type, url, comments}` pointers. ValiChord adds a `"ValiChord Reproducibility Attestation"` entry whose `url` is the live DHT record and whose `comments` state outcome, agreement level, and validator count. Verified against the vNext schema before building.

**API:**
- `valichord_source_entry(round_result)` — builds the single source entry
- `inject_into_disclosure(disclosure, round_result)` — non-mutating deepcopy injection into any existing OETP JSON
- `minimal_disclosure(product_url, round_result)` — standalone valid OETP disclosure from a round result alone

**`--emit-oetp` flag** added to `ai_validator.py`. Set `VALICHORD_PRODUCT_URL` to control the product URL; falls back to `RESEARCHER_URL`.

28 tests, all pass. Works with both `demo_runner` result dicts (key `outcome`) and `ai_validator` result dicts (key `outcome_type`).

**Usage context:** This is a general reusable capability — ValiChord emits attestations compatible with an IETF-track transparency standard. Whether a given partner uses OETP is a question to ask, not an assumption to build a pitch on. Surface only if they confirm they use it.

---

### LOOPCHii outreach — 2026-06-18 ✓

Cazandra Aporbo (CEO | Principal Architect, LOOPCHii Technologies LLC — www.loopchii.com) replied warmly to a cold outreach the same day. She independently articulated the governance/verification distinction ("related problems, but not the same problem") and called out the commit-reveal mechanism by name. She's asked to see the demo and connect next week.

Reply sent pointing to `valichord-demo.onrender.com/demo` (Anthropic key required) with the LinkedIn video as a fallback; noted the demo now completes in ~90 seconds vs the sped-up 5-minute video. Call to be scheduled for w/c 2026-06-22.

**Why relevant:** LOOPCHii's PriorAuth Sovereign is exactly the high-stakes decision context where unverified accuracy claims matter. The two layers (Loopchii = rules/governance, ValiChord = independent verification of claimed results) are natural complements. Contact: cazandra@loopchii.com. Gmail thread ID: 19edaddbd8601fb4.

---

### Maintenance + ecosystem triage — 2026-06-13 ✓ (pushed to main)

A round of small, durable fixes plus a wide sweep of the Holochain ecosystem for patterns and current tooling. All code/doc changes are on `main`.

**Code & config changes (pushed):**
- **Governance gold-badge sweettest hardened** (`9627699`) — `gold_badge_issued_with_seven_validators` was an intermittent CI failure (the only failing `Sweettest (governance)` test). Diagnosed as a **flake, not a regression**: identical governance bytes passed and failed across runs whose commits touched no governance code. Root cause = the global `badge.gold` type-index lagging the study-specific index by a gossip round under CI load (7 in-process conductors on a 2-core runner). Fix (test-only, no DNA/production change): assert the HarmonyRecord is `ExactMatch` + 7 validators *before* the badge checks (so a real wrong-tier is diagnostic, not a bare "Gold empty"), and wrap both badge queries in a 5-iteration `await_consistency` + re-query loop. Compile-verified before push.
- **`valichord-ui/dev.sh` conductor auto-reap** (`4955771`) — the dev conductor is now spawned under `setpriv --pdeathsig TERM` (+ `EXIT/INT/TERM` trap), so if `dev.sh` dies for any reason (Ctrl-C, crash, SIGKILL, OOM, closed terminal) the kernel SIGTERMs the conductor — no orphan holding `:4444`/`:8888`. Pattern borrowed from `topeuph-ai/flowsta-vault-app`. The `pkill` at the top of the script is now a fallback, not load-bearing.
- **`@holochain/client` bump** (`077ecb3`) — `valichord-ui` floor moved `^0.20.4-rc.0` → `^0.20.5` (current stable; lockfile regenerated). Stays on the 0.20.x line for our Holochain 0.6.1 stack; 0.21 remains dev-only.
- **`memory/reference_unyt_tools.md` created** (`baa4770`, `e67f953`) — resolved a dangling `CLAUDE.md` reference and documented the Unyt/desktop tooling (see "Ecosystem findings" below).

**Upgrade-check result (CLAUDE.md mandate):** **Holochain 0.7.0 is still not stable** — the line is at `0.7.0-dev.28`; **0.6.1 remains current stable → hold, no upgrade action.** Estimated 0.7.0 stable ≈ **Q3 2026 (most likely ~September; range Aug–Oct)** based on the 0.6 dev-cycle base rate (~31 weeks, 33 dev releases) and an in-flight major feature ("Source chain restore") still landing on `develop`. **Tell to watch: the first `0.7.0-rc.0` tag** — in the 0.6 cycle rc.0→stable was just ~2 weeks. lair (0.6.3) and kitsune2 (0.4.1 stable) unchanged for our stack.

**Ecosystem findings (research → memory, no code change):**
- **Validator desktop app front-runner identified: `darksoil-studio/tauri-plugin-holochain`.** Now public (supersedes the CLAUDE.md "not yet open-source" note), on **Holochain 0.6.1 stable**, full runtime (bundles lair + conductor). Decisively, its `install_app`/`install_web_app` take `roles_settings` (membrane_proof + DNA `modifiers.properties`) + `membrane_proofs` + `network_seed`, so it reproduces our dev membrane-proof bypass directly **and** supports real joining-service proofs into the existing `authorized_joining_certificate_issuer` gate — the thing `hc-spin` could not. Evaluate it **first** vs kangaroo-electron. Full detail in `memory/reference_unyt_tools.md`.
- **Production onboarding blueprint mapped** — `Holo-Host/joining-service` (membrane-proof issuer + `joining-cli`) + HWC `@holo-host/web-conductor-client` (drop-in `@holochain/client` → browser users as real zero-arc agents) + `h2hc-linker`; the operational layer for our already-built credential gate, demonstrated end-to-end by `GeekGene/mewsfeed`. All alpha → forward-looking, for the production-onboarding/desktop phase.
- **`Tryorama` is officially deprecated** (as of Holochain 0.6; moved to `holochain-open-dev/tryorama`, now `@holochain/tryorama` v0.19.2). Sweettest is the recommended harness — we already use it. Implication: don't invest new coverage in our 96-test Tryorama suite; factor the community-fork lineage into the 0.7 upgrade.
- **Deferred-work leads:** the **kitsune2 bootstrap-srv also provides relay fallback** (may remove the separate-Iroh-relay blocker for the deferred wind-tunnel kitsune live run and halve the kangaroo bootstrap/relay deployment); `holochain/network-services` is the Pulumi bootstrap-srv + sbd deploy recipe. **Tooling to remember:** `zits` (auto-generate `types.ts` from Rust zomes — handles our serde tag conventions, but pinned a HC-minor behind, needs a 0.6.x compat check); `hc-spin` (dev runner, needs a pre-baked empty-issuer dev happ to handle our bypass).
- Noise filtered out: a trojanized "holochain-agent-skill" repo (anonymous account, README pushes `iwr … | sh` on a binary zip — **do not install**) and a star-farm spam repo were flagged and discarded.

### Wind-Tunnel 0.7.0 bump + two propagation scenarios — 2026-06-12 ✓ (pushed to main)

Bumped `holochain_wind_tunnel_runner` 0.6.0 → **0.7.0** (still targets our Holochain 0.6.1 / Kitsune2 0.4.1 stack; runner Rust API is source-compatible, so the three existing scenarios only needed the pin bump). Added **two new scenarios** and a wind-tunnel `README.md` documenting all five. Commits `3c88605` (bump + Kitsune), `bd38b48` (dht_sync_lag), `a355444` (README).

The wind-tunnel suite now has a **propagation-latency ladder** — raw network substrate → real ValiChord entry → app-logic — alongside the original throughput/latency scenarios:

| Scenario | Layer | Measures |
|---|---|---|
| `kitsune_dht_propagation` *(new, prototype)* | Kitsune2 substrate (no ValiChord code) | Raw peer-to-peer message gossip latency — the network baseline |
| `dht_sync_lag` *(new)* | ValiChord entry, cross-agent | `sync_lag` = how long a `ValidationRequest` authored by a `write` agent takes to become visible to `record_lag` readers |
| `phase_observation_latency` *(existing)* | ValiChord app logic, single agent | `CommitmentAnchor` → observable `PhaseMarker(RevealOpen)` |

- **`dht_sync_lag`** has **zero DNA changes** — it reuses existing zome fns (`submit_validation_request`, `get_pending_request_refs`, `get_validation_request_for_data_hash`) and derives send-time from each record's **Action timestamp** (no `created_at` field, no integrity change, no DNA-hash change). Run: `--agents 3 --behaviour=write:1 --behaviour=record_lag:2`. Verified: compiles + 4 pure-logic unit tests pass + binary runs.
- **`kitsune_dht_propagation`** uses the new Kitsune2 bindings (`kitsune_wind_tunnel_runner`); needs a bootstrap server **and** an Iroh relay (not the hApp). **Pin gotcha:** its iroh stack pulls `ed25519-dalek 3.0.0-pre.1`, which only builds against RC `pkcs8`/`ed25519` — those RC versions are pinned in its `Cargo.toml`; an unconstrained `cargo update` will try to undo this. See `memory/project_wind_tunnel_07.md`.
- **First live run done (2026-06-12).** `dht_sync_lag` ran end-to-end on 3 conductors (1 writer + 2 readers, 45s): writer submitted 288 ValidationRequests; the two readers observed them propagate cross-DHT (287/288 and 232/288) and recorded 525 `sync_lag` samples — **median ≈ 185 ms**, p90 ≈ 8.7 s (gossip-under-load tail). `validation_request_throughput` also verified live (128 `commits_sent`). This first live run surfaced a **latent bug in all 4 Holochain scenarios**: they installed with role name `"valichord"` (no such role — it's `"attestation"`) and no membrane proof, so the credentialed attestation DNA never enabled. Fixed by a shared `scenarios/valichord_wt_common` crate that ports valichord-ui's dev-mode bypass (empty issuer + 64×0x42 proof) via `install_app_custom`; all 4 Holochain scenarios now call `install_valichord_app`. Also note: runner 0.7.0 requires `WT_METRICS_DIR` set, and custom metrics need `--reporter=influx-file` (land under `wt.custom.*`). Full run commands + result in `valichord/wind-tunnel/README.md`. **Still deferred:** the Kitsune scenario live run (needs an Iroh relay) and the complex behaviours (phase/reveal) aren't behaviour-verified live yet — only their install path is.
- **CI (`.github/workflows/wind-tunnel-smoke.yml`) = build + unit tests, path-filtered + manual.** A live multi-conductor run was attempted in CI twice and both failed for *environment* (not code) reasons on a standard 2-core/7 GB GitHub runner: (1) the per-agent conductors couldn't peer (the 0.7.0 runner uses the default public bootstrap, no local-bootstrap knob), and (2) the runner couldn't bring up three 4-DNA conductors before a startup timeout cancelled setup. Conclusion: a live wind-tunnel run isn't viable on a stock GitHub runner, so CI gates on the deterministic signal (compile all scenarios + the 4 dht_sync_lag unit tests) and the **live run stays a local / well-resourced-machine activity** (where it works — median ≈185 ms). Full rationale in `valichord/wind-tunnel/README.md`.

### CORE-Bench attestation bundle-emit (`--emit-bundles`) — 2026-06-02 ✓ (merged to main + pushed)

Opt-in flag on the CORE-Bench runner that, after a successful commit-reveal round, emits **one `valichord_attestation` bundle per validator**. Each bundle is a `model × task` record: `raw_metrics` from that validator's reproduced report (via `build_numeric_panel`, so they equal the on-chain panel by construction), `samples` parsed from the validator's `.eval` log through **EveryEvalEver's `InspectAIAdapter`** (so "built on EEE" is real + visible), and `meta.attestation_uri` pointing at the one shared HarmonyRecord — i.e. several independent cross-model reproductions of the same capsule, each provably blind, all anchored to one tamper-evident record. Emission is isolated: a bundle failure sets `result["bundles_error"]` and never invalidates the committed round. New module `demo/core_bench_bundle.py`; `run_validator_eval` now returns `(report, eval_log_path)`. Built TDD via subagent-driven-development (implementer + spec + code-quality review per task, plus a final whole-feature review). Full demo suite **77 passed**. Spec/plan: `docs/superpowers/{specs,plans}/2026-06-02-core-bench-bundle-emit*.md`; usage in `demo/CORE_BENCH_DEMO.md` → "Attestation bundles". **Strategic purpose:** these bundles are the artifact for the EveryEvalEver convergence — submit a CORE-Bench reproduction to EEE as a record carrying a ValiChord `attestation_uri` (shared contact: MattFisher, maintainer of both inspect_evals and EEE). **Next (deferred):** (1) generate real bundles from a live run + eyeball; (2) draft the EEE issue around the worked example; (3) wire EEE submission.

### CORE-Bench demo review-hardening — 2026-06-01 ✓

Three review-hardening units merged to `main` (fast-forward; **local — not yet pushed at the time of writing**). Built TDD via subagent-driven-development (fresh implementer + spec-compliance + code-quality review per task) in an isolated worktree. **No integrity-zome or DNA-hash change.** All green: Python 44 / JS 5 / Rust 27 (incl. a cross-language agreement golden test). Full detail in `demo/CORE_BENCH_DEMO.md` → "Review-hardening"; spec/plan under `docs/superpowers/`.

1. **Capsule blinding gate** (`demo/capsule_blinding_gate.py`) — after the researcher seals the claim and before any validator runs, scans every *retained* (hard-mode-surviving, prefix-aware) capsule file for the committed answer (rounded-form on all files; interval-membership on doc files only). Hard-aborts the round with `CapsuleLeakError` if the answer leaks, so "independent execution" can't reduce to "read the number". Wired into `core_bench_runner`; spike prints a non-fatal leak report.
2. **`/record` numeric-convergence panel** — `GET /record` now returns a per-validator value-vs-committed-interval panel with explicit degradation states (full / `"pending"` / base-only; never 500s). Pure JS helpers in `node-lib.mjs` (`numericMatch` is a faithful port of Python `match_value`, inclusive bounds, empty/whitespace → non-match); base fields stay back-compatible with `ai_validator.py`.
3. **Agreement parity** — `derive_agreement_level`/`derive_majority_outcome` pinned to a shared `valichord/shared_types/tests/agreement_golden.json` asserted by **both** Python and a new Rust `#[test]` (cross-language drift guard). The runner echoes the **authoritative on-chain `outcome`/`agreement_level`** read gossip-free on the authoring node (`/create-harmony-record` returns them), with a labelled recompute fallback (`agreement_recomputed`).

Two review-caught bugs fixed during the run: `numericMatch('')` returned `true` in JS (diverged from Python) → guarded; the echoed adjacent-tagged `outcome` printed as `{'type': 'Reproduced'}` → normalized to a bare string. Known follow-up: `researcher-node.mjs` `/record` still returns the raw `{type:…}` outcome dict in its base fields — worth normalizing in the JS layer if a UI consumes it.

### CORE-Bench integration strategy — 2026-05-29 ✓

Strategic analysis and integration doc for combining ValiChord with CORE-Bench (the inspect_evals benchmark for AI computational reproducibility). Full doc at `docs/CORE_BENCH_INTEGRATION.md`.

**Key insights:**

- **The capsule is the input layer.** A CodeOcean capsule already contains everything ValiChord needs as structured input: code + data (the claim, operationally defined), `README.md` / `REPRODUCING.md` (instructions any independent party can follow), and specific numerical outputs (the pre-defined metrics validators check against). A researcher with an existing capsule has already done ValiChord's hardest UX work without knowing it.

- **Automatic metric extraction closes the loop.** CORE-Bench's agent can be run once by the researcher to extract key numerical outputs. Those outputs become the committed metrics. The researcher didn't manually define metrics — their code defined them.

- **Validator count is a parameter, not a constant.** The current demo uses three validators for illustration; the protocol places no architectural limit. The optimal number for any given claim (routine benchmark vs regulatory submission) is an open empirical question — analogous to statistical power analysis in clinical trial design.

- **What N independent computational runs actually prove.** For deterministic code, commit-reveal protects against result copying (validator B copying validator A's `report.json` instead of running the code), not opinion anchoring. This is a real and defensible guarantee — stated precisely it is hard to poke. N runs prove: (a) the capsule executes from scratch without hints, (b) the result is robust to independent environments, (c) no agent fabricated or copied a result.

- **Design constraint: ground-truth vs committed claim.** Validators commit their raw `report.json` before the researcher reveals. ValiChord agreement is researcher-claim-relative. CORE-Bench ground truth (the official benchmark answers) is a separate optional overlay and must not be available at commit time — doing so would defeat blinding.

- **`FailedToReproduce` not `NotReproduced`.** The valid `AttestationOutcome` enum values are `Reproduced | PartiallyReproduced | FailedToReproduce | UnableToAssess`.

- **Tolerance function must be pinned.** Numeric tolerance (e.g. "within 0.5% counts as a match") is currently client-side in the Python adapter before becoming an outcome enum. For "no trust required at any layer" to hold, the tolerance configuration should be committed alongside the researcher's metrics.

**Demo spec:** three validators (illustrative), hard difficulty, Python capsule, no GPU, <5 min, numeric outputs. Build estimate ~6–8 days with capsule selection on the critical path. See `docs/CORE_BENCH_INTEGRATION.md` for full architecture, demo output, and infrastructure requirements.

**inspect_evals outreach context:** `docs/inspect_evals_issue_and_pr.md` contains a draft issue (target: 2026-06-02) and PR proposing two optional YAML fields (`valichord_attestation_uri`, `valichord_harmony_record_uri`) in the register schema. CORE-Bench is named in the issue as the most direct example. The integration doc and demo are held for follow-up once the issue gets a positive response.

---

### Release v0.5.7 — Demo reliability hardening — 2026-05-29 ✓

10-commit reliability overhaul of the public demo, driven by user reports of "validator 1/2/3 ended without giving a verdict." Root cause: the custom demo path (`custom_runner.py`) had never received the hardening applied to the free path (`ai_validator_cma.py`) in v0.5.5/v0.5.6.

**Fixes shipped (custom_runner.py):**
- **Hardened system prompt** — ported the "REQUIRED FINAL ACTION — YOU MUST DO THIS" block and "Do not put your verdict in a text response" instruction to `VALIDATOR_CLAIM_SYSTEM`
- **Fresh-session retry** — replaced the weak in-session reminder with a `_MAX_ATTEMPTS = 2` loop that creates a fully fresh CMA session on retry (mirrors `_run_cma_session` in the free path); `json.JSONDecodeError` also triggers a retry
- **`compare_answers` fallback** — wrapped JSON parse in try/except; a malformed Claude reply no longer marks the job as error after the HarmonyRecord is already on-chain
- **Reveal retry** — `_reveal_with_retry` helper retries each validator `/reveal` call up to 3 times with 5 s back-off
- **Tolerant error collection** — parallel validator futures are now all awaited before raising; a single failure produces a descriptive error naming which validators failed rather than aborting silently

**Fixes shipped (ai_validator_cma.py):**
- **Commit DHT retry** — ported the 6-attempt "No ValidationRequest found" retry from the custom path to the free path's `_run_cma_session`
- **Reveal retry** — same `_reveal_with_retry` helper applied to `_finish_protocol`
- **Tolerant error collection** — same tolerant `as_completed` loop applied to `form_verdicts_cma`

**Fixes shipped (app.py):**
- **Watchdog expanded** — background watchdog now releases `_custom_running` for any non-terminal phase (starting, committing, awaiting_reveal), not only `awaiting_reveal`; prevents permanent lock if the commit thread crashes mid-run
- **Rate limit on success only** — `_ip_last_free[ip]` and `_free_run_count` now recorded only after a successful free run, not on failure; failed runs no longer burn the user's daily quota or the monthly budget
- **Client-side poll timeout** — 8-minute `MAX_POLL_MS` hard stop added to both `doPoll` and `pollCustom`; `customPollStart` is reset in `triggerReveal()` so the reveal phase gets its own 8-minute window

Verified by Opus 4.8 code review; one regression (false timeout on reveal) caught and fixed before deploy.

---

### Three minor correctness fixes — 2026-05-28 ✓

Identified by an independent code review (Claude Opus 4.8).

- **Researcher msgpack call site** (`researcher_repository_coordinator/src/lib.rs`): `lock_researcher_result` now hashes metrics via the shared `metric_results_msgpack_bytes()` helper, matching the reveal-side verification path exactly. Previously used an inline `rmps::to_vec_named` call — identical bytes today, but a latent drift risk if the encoding ever changed. Unused `rmp_serde` import removed.
- **Python agreement level bug** (`demo/ai_validator.py`): `ExactMatch` threshold now uses `full_rate` (Reproduced-only count / total), matching `shared_types::derive_agreement_level`. Previously used the combined reproduced+partial rate for all tiers, which would display `ExactMatch` for an all-`PartiallyReproduced` round where the chain record correctly holds `WithinTolerance`. Display-only (the on-chain `HarmonyRecord` is authoritative), but now accurate.
- **Model ID** (`demo/ai_validator.py`): non-CMA validator path updated from `claude-opus-4-6` to `claude-opus-4-7`.

Also posted the wandb GitHub issue ([Feature]: Independent run attestation) — no responses yet as of 2026-05-28.

---

### Release v0.5.6 — Demo website redesign + discipline classification — 2026-05-26 ✓

**Discipline classification:** `classify_discipline(claim, api_key)` added to `demo/custom_runner.py`. A short Haiku call at the start of `start_commit_phase` classifies the hypothesis into an academic discipline (e.g. "Social Psychology", "Exercise Science") and returns `{"type": "Other", "content": "<name>"}` for the DHT. Replaces the hardcoded `{"type": "ComputationalBiology"}` that appeared on every HarmonyRecord regardless of subject matter.

**Demo website redesign (`demo/app.py`):**
- **No tabs** — linear scroll layout replaces the Free/Your Hypothesis tab bar
- **Your Hypothesis is the primary hero section** — full-width card with gradient border at the top of the page
- **Five expandable accordions** (`<details>`/`<summary>`) between the two demos explain the protocol, why it's remarkable, why Holochain and not a blockchain, why a central server lacks the trust layer, and why validator disagreement is a feature not a failure
- **Free demo** demoted to a secondary section below a visual `— Free demo — no API key needed —` divider
- **Holochain logo** (`demo/static/holochain-logo.png`) added to the header as a "Built on / [logo]" badge linking to holochain.org
- **Google Fonts** — DM Sans + Newsreader loaded from fonts.googleapis.com
- **Copy** — hero tagline, accordion text, and the blockchain explainer all give Holochain explicit credit and explain the agent-centric DHT architecture

**`demo/DEMO_WEBSITE.md`** fully rewritten: covers both demos, CMA 5-step system prompt, two-phase protocol, `classify_discipline`, `compare_answers`, request flow, result schema, rate limiting, UI design, updated files table, and Holochain credit.

---

### Release v0.5.5 — CMA validator upgrade — 2026-05-26 ✓

AI validators upgraded from one-shot Claude calls to **Claude Managed Agents** (CMA). Each validator now runs as a proper agent that searches the web, reasons step-by-step, and writes its verdict to a file — all before committing to the DHT.

**New file: `demo/ai_validator_cma.py`** — replaces `ai_validator.py` as the orchestrator for CMA and simple (non-Anthropic) modes. Key features:
- 3 validator agents run **in parallel**, each in their own CMA environment + session
- Each agent uses `web_search`, `web_fetch`, `write` tools to do real research before verdicting
- Verdict written to `/mnt/session/verdict.json`; Python reads from event log after `session.status_idle`
- **User API key support**: user can provide any provider key — `sk-ant-` → CMA mode; `sk-proj-`/`sk-` → OpenAI via litellm; `AIzaSy` → Google; `gsk_` → Groq
- **Rate limiting** on server key: 1 run/hour per IP, $20/month cap
- **`AttestationOutcome` serde fix** in `validator-node.mjs`: struct variants (`PartiallyReproduced`, `FailedToReproduce`, `UnableToAssess`) now correctly serialised with `content: { details }` field — previously caused 502 crashes

**`demo/app.py`** updated: accepts `user_api_key` + `user_model` in POST body; routes to CMA/simple/original mode based on key type.

**Run against Oracle:**
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export VALICHORD_RESEARCHER_URL=http://152.67.153.149:3001
export VALICHORD_VALIDATOR_1_URL=http://152.67.153.149:3002
export VALICHORD_VALIDATOR_2_URL=http://152.67.153.149:3003
export VALICHORD_VALIDATOR_3_URL=http://152.67.153.149:3004
python3 demo/ai_validator_cma.py --mode decentralised
```

Verified end-to-end: 3 validators (36s/6 calls, 88s/17 calls, 123s/32 calls), all Reproduced (High), HarmonyRecord written to Oracle DHT.

---

### Release v0.5.4 — security hardening sweep — 2026-05-24 ✓

**Warrant gate coverage (attestation_coordinator):** Four coordinator entry points that previously let warranted (banned) agents write state are now closed — `submit_validation_request`, `publish_validator_profile`, `assess_difficulty`, `link_agent_identity`. All call `reject_if_warranted(&agent)?` at the start of the handler, matching the existing pattern on `notify_commitment_sealed`, `submit_attestation`, and `claim_study`.

**Integrity validation gaps (attestation_integrity + governance_integrity):** Two entry types had no `validate()` coverage:
- `ResearcherResultCommitment` — `result_commitment_hash` must be exactly 32 bytes (SHA-256). A malformed hash would permanently block the researcher's reveal with no visible error.
- `HarmonyRecord` — `validator_types` (position-parallel to `participating_validators`) must be empty or the same length. A length mismatch causes out-of-bounds panics in UI lookups. The field is `#[serde(default)]` for backwards-compat with pre-existing records.

**TypeScript serde fix (valichord-ui/src/lib/types.ts):** `BadgeType` used wrong string names (`"Gold"`, `"Silver"`, `"Bronze"`, `"Failed"`). Rust serialises to `"GoldReproducible"`, `"SilverReproducible"`, `"BronzeReproducible"`, `"FailedReproduction"`. `get_badges_by_type` calls from the UI now match DHT records.

**Earlier fixes (also in this release):** claim release authorisation (only original claimant or study submitter may release); warrant filter in `get_all_validators`; cross-DNA error handling in `call_attestation_zome_opt`; timeout cast safety in `reclaim_abandoned_claim`; atomic badge issuance hardening in governance.

**New sweettest tests:**

| File | # | Test | What it covers |
|---|---|---|---|
| `attestation.rs` | 16 | `update_validator_profile_merges_fields` | `Some` fields overwrite, `None` fields preserved |
| `attestation.rs` | 17 | `check_all_commitments_sealed_lifecycle` | false before quorum, true after both validators commit |
| `attestation.rs` | 18 | `get_researcher_reveal_none_then_some` | `None` before reveal, `Some(Record)` after |
| `attestation.rs` | 19 | `revoke_agent_identity_link_removes_from_linked_agents` | deleted entry filtered from `get_linked_agents` |
| `attestation.rs` | 20 | `get_my_claimed_studies_filtered_by_release` | released claim excluded from `Vec<Record>` result |
| `governance.rs` | 17 | `get_pending_request_refs_includes_other_discipline_studies` | `Discipline::Other("custom")` study appears in refs; `force_finalize_round` works end-to-end |

Total sweettest coverage: **20 attestation + 17 governance** tests.

---

### Public web demo live on Render — 2026-05-22 ✓

**[valichord-demo.onrender.com/demo](https://valichord-demo.onrender.com/demo)** — one-click browser interface to the full commit-reveal protocol. Runs against the permanently live Oracle nodes (no local setup).

**What it does:** Click Run Protocol → 7-step progress bar shows the full protocol in ~2 minutes (real network time). At the end: outcome, per-validator verdicts, a permanent shareable HarmonyRecord URL, and a `curl` command to fetch the raw record directly from the Oracle DHT — proving the result was not generated by the page itself.

**Architecture:** Flask app (`demo/app.py`) deployed on Render from `demo/Dockerfile`. Background job per run (`threading.Thread`); job state in process-level dict; `threading.Lock()` + `_demo_running` bool enforces one run at a time. `gunicorn --workers 1 --threads 4` so all threads share the same process. Three Claude Haiku agents form independent verdicts. Each run salted with a UUID so the data hash is unique and HarmonyRecord hashes can't be pre-computed.

**Docs:** `demo/DEMO_WEBSITE.md` — full technical guide (request flow, protocol steps table, concurrency design, local run instructions, Render deployment, skeptic-proof verification section).

**ValiChordLogger fixes shipped alongside:** `log_eval_result()` made an explicit no-op (was silently calling `build_bundle(samples=[])` → always raised `MalformedBundleError`); `finish()` added to `run.py`; 28 tests updated. Pushed to `topeuph-ai/lm-evaluation-harness` fork.

---

### `PiSessionAdapter` + `ValiChordLogger` for lm-evaluation-harness — 2026-05-20 ✓

**PiSessionAdapter** (`valichord_attestation/adapters/pi_session_adapter.py`) — reads pi coding agent session v3 JSONL files and converts them to canonical Valichord bundles. Resolves the active branch via parentId walk (mirrors `_buildIndex()`), applies compaction filtering (`firstKeptEntryId`), extracts 8 metrics (turns, tool calls, error rate, tokens, cost, compaction count, stop reason), and builds a full Merkle tree over all branch entries. 67 tests, 99% coverage.

**ValiChordLogger** (`topeuph-ai/lm-evaluation-harness`, fork) — optional logger for lm-evaluation-harness following the `wandb`/`trackio` pattern. Hooks into `post_init` → `log_eval_result` → `log_eval_samples`, builds a `valichord_attestation` bundle (Merkle tree over per-sample `filtered_resps`, stable SHA-256 commitment via RFC 8785), and saves it alongside the `results_*.json` artifact. Wired via `--valichord_args output_path=./results` CLI flag and `pip install lm_eval[valichord]` optional extra. 28 tests, all mocked (no GPU/network required in CI).

**Engagement:** comment posted on [EleutherAI/lm-evaluation-harness#3752](https://github.com/EleutherAI/lm-evaluation-harness/pull/3752) asking if a companion PR is welcome. FazeelUsmani (PR author) previously engaged positively on that thread when v1.2 shipped.

---

### falsify-cookbook Pattern 13 merged — 2026-05-20 ✓

ValiChord is now officially referenced in the [falsify-cookbook](https://github.com/studio-11-co/falsify-cookbook) as Pattern 13 — co-authored with Cüneyt Öztürk (Studio 11).

**PR:** [studio-11-co/falsify-cookbook#3](https://github.com/studio-11-co/falsify-cookbook/pull/3) — merged, reviewed and approved by sk8ordie84 (Cüneyt).

**What the pattern covers:**

Three-layer stack for AI evaluation independence attestation:

| Layer | Tool | What it commits |
|---|---|---|
| Pre-registration | PRML / falsify | metric, comparator, threshold, dataset hash, seed |
| Eval attestation | valichord_attestation | Merkle root over per-sample outputs |
| Independence attestation | ValiChord | blind multi-party verdicts; HarmonyRecord on public DHT |

Pattern 13 fills the gap Pattern 11 (Sigstore) leaves open: Sigstore proves *who* ran the eval and *when*; ValiChord proves validators couldn't coordinate post-hoc. The pattern explicitly cross-references Pattern 10's auditor-layer gap (v0.3 roadmap: centralised consortium registry) as the structural problem ValiChord's DHT solves.

**Honest about limits (documented in the pattern):**
- Validator withdrawal: commitment is visible on DHT but protocol can't compel reveal
- Validators don't yet commit to their own reproduction bundle hash (planned extension)
- Integration is manual today — no single command wires all three layers

**Strategic significance:** ValiChord is now a named, documented component of the falsify/PRML ecosystem. The `attestation_uri` field (P-02) pointing to a HarmonyRecord URL is the concrete integration hook. Future: automate the handoff between `valichord_attestation` and the Holochain protocol.

---

### Holochain 0.6.1 upgrade — 2026-05-13 ✓

Full upgrade of the Holochain toolchain from 0.6.0 to 0.6.1. Transport switches from tx5/WebRTC to iroh/QUIC.

**Binary stack upgraded:**
- `holochain 0.6.1` — `cargo install holochain --version 0.6.1 --locked --force`
- `hc 0.6.1` (holochain_cli) — `cargo install holochain_cli --version 0.6.1 --locked --force`
- `kitsune2-bootstrap-srv 0.4.1` — required for iroh/QUIC peer discovery (0.3.x is protocol-incompatible)
- `@holochain/tryorama 0.19.1` — iroh/QUIC transport; `dhtSync` signature: `(players, dnaHash, intervalMs?, timeoutMs?)`

**Cargo.toml workspace pins bumped:**
- `hdk = "=0.6.1"` (was `"=0.6.0"`)
- `hdi = "=0.7.1"` (was `"=0.7.0"`)
- `holochain_serialized_bytes = "=0.0.57"` (was `"=0.0.56"`)
- `attestation_integrity/Cargo.toml` migrated from local pin to `{ workspace = true }`

**Zome code changes:**
- `reject_if_warranted` (attestation_coordinator): `get_agent_activity` now requires a 4th `GetOptions` parameter — added `GetOptions::network()`
- Governance coordinator warrant filter: same `GetOptions::network()` 4th arg added
- `recv_remote_signal` (attestation_coordinator): 0.6.1 conductor delivers remote signal payload directly as a msgpack map (no outer bin8 wrapper); removed the double-decode workaround; now decodes directly as `RevealOpenWire` in one step
- `Warrant` → `SignedWarrant` type rename in `AgentActivityResponse`: handled automatically by HDK version bump (code only uses `.warrants.is_empty()`)

**Kangaroo-electron prerequisite:** Holochain 0.6.1 upgrade is now ✓ done. Remaining pre-requisites: browser UI ✓, dedicated bootstrap/signal/relay servers.

---

### Release v0.5.21 — 2026-05-17 ✓

Committed and tagged. GitHub release at `v0.5.21`. Covers `InspectAILogAdapter`, `eval_yaml_metadata` enrichment, `generate-attestation-bundle` skill, and package export plumbing. 259 valichord_attestation tests. README updated (version blurb, stale "New:" labels removed, adapters section updated).

---

### `valichord_attestation` InspectAILogAdapter + eval_yaml_metadata — 2026-05-15 ✓

Three additions driven by analysis of the Generality-Labs/inspect-evals-template:

**`InspectAILogAdapter`** — new adapter that reads inspect_ai `.eval` / `.json` log files
directly using the inspect_ai Python API, requiring no pre-parsing step.

Field mapping: `EvalSpec.model` → `model_id`, `EvalSpec.task` → `task_id`,
`EvalSpec.created` → `generated_at`, `EvalSpec.revision.commit` → `repo_commit`
(auto-extracted), `EvalResults.scores` → `metrics` (all scorers combined; scorer-name
prefix on key collision), `EvalLog.samples` → `outputs_merkle_root` (per-sample dicts
`{id, epoch, output, scores}`).

Per-sample dict captures `ModelOutput.completion` + all `Score.value/answer` entries.
`score_name=` restricts to a single scorer. `meta_extras=` merges extra provenance.
`inspect_ai` is an optional dependency; passing a pre-loaded duck-type works without it.

**`InspectEvalsAdapter.to_bundle(..., eval_yaml_metadata=)`** — optional enrichment from
the top-level `eval.yaml` metadata block (not the `evaluation_report` block).
Folds into `Bundle.meta`: `arxiv` → `paper_arxiv`, `group` → `eval_group`,
`version` → `task_version`, `tasks[*].human_baseline` → `human_baseline`,
`state: floating` external assets → `dataset_reproducibility_warning`,
`metadata.requires_internet` → `requires_internet`.

**`generate-attestation-bundle` Claude Code skill** — at `.claude/skills/generate-attestation-bundle/SKILL.md`.
Step-by-step workflow for adding attestation as the final step after an inspect_evals
eval report. Covers both `InspectAILogAdapter` (file path) and `InspectEvalsAdapter`
(eval.yaml evaluation_report) paths, plus challenge-response verification.

Tests: 183 → 259 (+76). 100% line coverage maintained. `inspect-ai` added as an
optional dependency group in `pyproject.toml`.

---

### `valichord_attestation` format v1.2 — 2026-05-09 ✓

Two additive, backward-compatible changes to the attestation bundle format, informed by FazeelUsmani's lm-evaluation-harness PR #3752.

**`Metric.filter` (optional str):** disambiguates metrics sharing the same key produced by different filter passes (e.g. strict-match vs flexible-extract). `None`/absent → omitted from canonical encoding entirely; existing bundles unaffected.

**`Bundle.meta` + `content_hash`:** `meta: Optional[dict]` is a free-form provenance block (harness version, commit, command, timestamp, n_shot, etc.). It is included in `bundle_hash` (byte identity) but excluded from `content_hash` (scientific equivalence). v1.1 bundles with no `meta` have `content_hash == bundle_hash`. `content_hash()` added to `canonical.py` and exported from `__init__.py`.

`build_bundle()` default `format_version` bumped to `"v1.2"`. All v1/v1.1 bundles remain valid — no existing hash values change.

Tests: 142 → 183 (+41 new). 100% line coverage maintained. Spec updated with §2a (meta block), dual-hash §4, filter in Metric schema, and changelog entry referencing the upstream PR.

---

### Governance badge idempotency fix — 2026-05-09 ✓

The auto-call chain `submit_attestation` (DNA 3) → `check_and_create_harmony_record` (DNA 4) → `get_validation_request_for_data_hash` (DNA 3) silently fails: Holochain blocks the re-entrant call back into DNA 3 while `submit_attestation` is still executing. `call_attestation_zome_opt` returns `Ok(None)`, `maybe_researcher` is `None`, and badge issuance is skipped without error.

When a subsequent explicit `check_and_create_harmony_record` call hit the idempotency guard, it returned the existing `HarmonyRecord` hash without retrying badge issuance — leaving the badge permanently absent. The silver badge sweettest exposed this: on a loaded CI runner governance gossip propagated the `RequestToHarmonyRecord` link before the explicit call, so the idempotency path fired every time.

**Fix:** `issue_badge_if_missing()` is now called from the idempotency return path. It network-queries for existing badge links, reads the `HarmonyRecord` for `agreement_level` and `validator_count`, then calls `try_issue_badge()` — the same logic extracted from `write_harmony_record`. The retry runs from a direct governance call where DNA 3 is free, so `get_validation_request_for_data_hash` succeeds.

Silver badge sweettest (`silver_badge_issued_with_five_validators`) updated to sync governance cells before the explicit call, deterministically exercising the idempotency+retry path.

---

### `valichord_attestation` inspect_ai popularity demo — 2026-05-07 ✓

Second real-data example under `valichord_attestation/examples/inspect_ai_popularity_demo/`. Parses an inspect_ai `.eval` log (popularity task, GPT-4o-mini, match scorer) via EveryEvalEver's `InspectAIAdapter`, then builds and challenge-response-verifies a v1.1 bundle.

- **`download_eval.sh`** — fetches the 21 KB real log from inspect_ai's test suite
- **`build_bundle.py`** — EEE-based parsing path + `--fixture` mode (committed `bundle.json`)
- **`challenge_response_demo.py`** — k=20 challenge-response with tamper detection

Strategic context: demonstrates ValiChord format compatibility with the EvalEval Coalition aggregate schema (inspect_evals#910).

---

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

### ~~1. `ANTHROPIC_API_KEY` persistent on Oracle~~ — DONE (2026-05-21)
Added to `~/.bashrc` on Oracle. Survives reboots.

### ~~2. Port 3001 in Oracle Security List~~ — DONE
Port 3001 is open and responding (`{"status":"ok","role":"researcher"}` confirmed from outside Oracle). Shareable HarmonyRecord URLs work.

### 3. ~~Feynman PR #23~~ — CLOSED
Feynman is no longer operational (April 2026). AI validator functionality has been rebuilt
directly against the Claude API (`demo/ai_validator.py`). No further Feynman integration work.

### 4. Rate limiting — LOW
API keys are in. No per-key rate limiting yet.

### 5. CORE-Bench + ValiChord demo — ✓ FULL RUN DONE (2026-05-31); ✓ REVIEW-HARDENING LANDED (2026-06-01)
Live CLI demo combining ValiChord's commit-reveal protocol with the inspect_evals CORE-Bench task — AI agents that actually run research-paper code in isolated Docker sandboxes. On `main` (demo + 3-unit review-hardening); see `demo/CORE_BENCH_DEMO.md`. Hardening detail in "Recently completed" above.

**Full commit-reveal run complete (2026-05-31, 128 GB Codespace):** end-to-end all-Sonnet run (researcher + 3 validators all `claude-sonnet-4-6`, `--researcher-runs 1`) produced a clean **`Reproduced` / `ExactMatch`** HarmonyRecord — all 3 validators independently got `0.9157952669235003`. Was public + recomputable on the old Oracle DHT (`curl "http://132.145.34.27:3001/record?hash=uhC8k4j2xO83gyCFCBMTAtx2Nyy_i_Yr4oDk-X1XJlbOZsI0-bYNT"`) — **that record was lost with the 2026-06-11 Oracle reclamation**; re-run the demo to mint a fresh record on 152.67.153.149. Both Opus 4.8 and Sonnet 4.6 reproduce the capsule exactly. **31 tests pass.**

**Four bugs fixed live (each only surfaces with 3 real validators):** (1) validators ran in a `ThreadPoolExecutor` but inspect_ai forbids concurrent `eval_async` → made sequential; (2) `google-genai` missing from `requirements.txt` → added; (3) `gemini-1.5-pro` retired by Google → `gemini-2.5-pro`; (4) infra failure (rate-limit/quota/auth/interrupt → empty `EvalLog` → `None` report) was minting a bogus `FailedToReproduce` HarmonyRecord → `run_validator_eval` now raises on non-`success` status so the round aborts with the real error. (Earlier: `filter_out_gpu` empties the dataset; `anthropic>=0.105.0`.)

**Gotcha:** the commit-reveal half defaults to the **Oracle** nodes (`demo_runner` `RESEARCHER_URL`/`VALIDATOR_URLS`) unless `VALICHORD_*_URL` is exported to localhost — so the inspect sandboxes run locally but the DHT half hits the live Oracle. **Keys:** mixed-model needs paid keys (OpenAI free = `insufficient_quota`, Gemini free = `limit:0` for 2.5-pro); all-Sonnet is the cheap working default.

**Trigger CORRECTED:** the earlier "hold until the inspect_evals issue responds" gating is **reversed** (per `docs/CORE_BENCH_INTEGRATION.md` 2026-05-30, "lead with the demo"). There is no inspect_evals issue — outreach to Scott Simmons was a **direct LinkedIn message** (no response required). The demo is the gift you lead with, not a follow-up.

---

## New Codespace setup (2026-05-26)

Run this from the terminal — installs everything in one go (~25 min):
```bash
cd /workspaces/ValiChord && bash setup_holochain.sh
```
Installs: Claude Code, Rust, Holochain 0.6.1, hc CLI, kitsune2-bootstrap-srv, holochain-dev skill, compiles all 4 DNA zomes and packs the hApp.

Then inside Claude Code chat: `/plugin install superpowers`

Skill files are committed to `skills/holochain-dev/` in the repo — the setup script copies them to `~/.claude/skills/holochain-dev/`.

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

### iroh/QUIC bootstrap (Holochain 0.6.1+)
Holochain 0.6.1 replaced tx5/WebRTC with iroh/QUIC transport. The bootstrap server binary
must be `kitsune2-bootstrap-srv 0.4.1` (version 0.3.x is protocol-incompatible with 0.6.1
conductors). Tryorama 0.19.1 spawns `kitsune2-bootstrap-srv` automatically for tests.
`_retryOnTx5()` / `retryOnTx5` renamed to `_retryOnNetworkError` / `retryOnNetworkError`
in `serve.mjs`, `node-lib.mjs`, `validator-node.mjs` — tx5-specific error strings removed,
now catches generic timeout/channel-drop errors. `advanced.tx5Transport` removed from all
three conductor YAMLs (dead config under iroh). Oracle demo bootstrap binary in `demo/bin/`
should be updated to 0.4.1 before the next Oracle demo run.

### Per-run UUID salt
`ai_validator.py` salts the data hash: `SHA-256(data_bytes + run_id)` where `run_id` is
16 random bytes. Ensures each run presents a fresh `ExternalHash` and avoids DHT
"already claimed" capacity errors on repeated runs against the same conductor.
Use `docker compose -f demo/docker-compose.yml down -v` between runs to clear conductor state if needed.

### hc-http-gw URL format (verified from source; re-verified 2026-07-27)
```
http://<host>:8090/<dna_hash>/<app_id>/<zome_name>/<fn_name>?payload=<base64url-padded>
```
- Payload = BASE64_URL_SAFE **with** `=` padding of JSON-encoded input
- For `get_harmony_record`: payload = base64url(JSON.stringify(externalHashB64))
- Response is msgpack-decoded — HoloHash fields are byte arrays, not strings

**Version:** this format was verified against **0.3.1**; the 0.6 line has since reached **v0.3.4**. **The format is unchanged** — `v0.3.1...v0.3.4` touches exactly one source file (`src/test/data.rs`, +2/−0); v0.3.3 (2026-07-02) and v0.3.4 (2026-07-20) are pure Holochain version bumps to 0.6.2 and 0.6.3 respectively. **`v0.3.3` is the release matching our 0.6.2 conductor.** (Note `v0.3.3`/`v0.3.4` are git tags with no GitHub Release, so they don't appear in the releases API — check tags.) It also survives 0.7: `v0.3.2...v0.4.0-rc.1` touches 12 source files but `src/routes/zome_call.rs` is +1/−1 and the route shape and payload encoding are untouched, so this block stays valid across the 0.7 migration.

**Not currently deployed.** `demo/start-gateway.sh` was **removed** in `9738fe1` during the Oracle migration; `hc-http-gw` is not installed in this Codespace. The live demo serves records through the Node bridges (`/record?hash=…`) instead. Docs 3 and 13 still describe the March-2026 gateway deployment — read them as historical.

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
| `docs/Holochain_complete.md` | Complete Holochain build guide — iroh/QUIC NetworkConfig, hc-http-gw URL format, ExternalHash JS |
| `demo/DECENTRALISED_DEMO.md` | Full technical guide for the decentralised demo — architecture, retry design, commit-reveal table |
| `demo/DEMO_WEBSITE.md` | Technical guide for the public Render web demo — Flask architecture, request flow, concurrency design, Render deployment |
| `demo/ai_validator.py` | Python orchestrator — `--mode decentralised` calls the five node APIs |
| `demo/docker-compose.yml` | 5-container stack definition |
| `demo/researcher-node.mjs` | Node.js HTTP API for researcher conductor |
| `demo/validator-node.mjs` | Node.js HTTP API for each validator conductor |
| `demo/node-lib.mjs` | Shared helpers: `withSession`, `retryOnNetworkError`, `loadHcClient`, `externalHashFromB64` |
| `backend/app_protocol.py` | Flask REST API integration layer (its `holochain_bridge` import lives in the deployment repo, not here) |
| `docs/INTEGRATION_GUIDE.md` | REST API integration guide |
| `valichord-ui/FRONTEND.md` | Screen-by-screen UI walkthrough — all three roles |
| `valichord-ui/src/lib/` | Svelte components: ResearcherView, ValidatorView, GovernanceView, types.ts, holochain.ts |
| `docs/7_ValiChord_4-DNA_architecture_technical.md` | Four-DNA architecture |
| `valichord/wind-tunnel/` | Wind-Tunnel load-test workspace — 3 performance scenarios (write throughput, phase latency, reveal throughput) |

---

*This file is the single catch-up document for new Claude sessions. Read it before responding to any questions about project status, Feynman integration, or what to demo.*
