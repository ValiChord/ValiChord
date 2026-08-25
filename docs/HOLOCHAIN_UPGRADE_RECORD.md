# Holochain upgrade record — the 0.6.2 → 0.7.0 migration

**Moved out of `CLAUDE.md` on 2026-08-25.** It was 48,985 bytes — **64.1%** of a file that is
re-sent to the model on every single turn — and the section itself said *"Sections below this line
predate the 0.7.0 merge."* Keeping a completed migration's working notes in the always-loaded file
cost roughly 12,000 tokens per turn for material that was, by its own admission, superseded.

⚠️ **It was also actively misleading.** One heading in here read **"WE ARE STILL ON 0.6.2"** for
three weeks after `main` merged 0.7.0 on 2026-08-03 — in the file every session reads first. That
is the concrete argument for this move: an always-loaded file should carry what is *true now*, and
a record should carry what happened.

**Nothing has been deleted.** Everything below is verbatim as it stood in `CLAUDE.md`. The live
items — the Oracle divergence, the `get_agent_activity` warrant-gate caution, the source-chain
restore watch, and the standing upgrade rules — stayed behind in `CLAUDE.md`.

**Read this when:** planning the next major version bump, or when something in the current code
looks inexplicable and the reason might be a migration decision. `docs/Holochain_complete.md` §44
remains the observed record of what actually happened during the port and supersedes anything here
that disagrees.

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

### ✅ `main` IS ON 0.7.0 — THE STANDING RULES BELOW ARE SPENT (corrected 2026-08-24)

> 🟢 **`main` merged Holochain 0.7.0 on 2026-08-03 (`38ea2123`, verified an ancestor of
> `main`).** This heading read **"WE ARE STILL ON 0.6.2 — TWO STANDING RULES"** for three weeks
> after that merge, in the file every session reads first. Any session trusting it would have
> concluded the upgrade had not happened and that `main` must be protected from it. `PROJECT_STATUS.md`
> had it right the whole time; this file did not.
>
> **What is still true:** the **Oracle demo host** runs 0.6.2. So `main` and the live public demo
> describe different stacks until Oracle is rebuilt — a full rebuild with state loss, not an
> upgrade. See `docs/ORACLE_0.7.0_UPGRADE.md`, which also records that the host currently has **no
> reachable shell** (SSH key lost at creation; Compute Instance Run Command accepts commands and
> never executes them).

**The original rules, kept because their reasoning still applies to the next major version:**

1. **Do NOT auto-upgrade.** Migration is deliberate and planned.
2. **MIGRATION IS BRANCH-ONLY.** User decision, 2026-07-30: a major change happens on a dedicated branch, never directly on `main`, and `main` keeps the working publicly-demoed stack until that branch is fully green (all sweettest suites + UI e2e + a live demo round — Tryorama was retired 2026-08-03 and is no longer a gate) **and** the user explicitly approves the merge. Superiority does not make a broken intermediate state acceptable. See `user_ceri_working_style` — core is paranoid.

⚠️ **Sections below this line predate the 0.7.0 merge.** Several are written in the future
tense about work that is now done. Read `docs/Holochain_complete.md` §44 — the observed record of
the port — before acting on any of it; §44 supersedes anything here that disagrees.

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
