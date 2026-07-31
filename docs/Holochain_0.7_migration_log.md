# Holochain 0.7 migration log — evidence captured during the port

**Branch:** `v0.7.0` · **Started:** 2026-07-31 · **From:** Holochain 0.6.2 (`hdi 0.7.2` / `hdk 0.6.2`) · **To:** Holochain 0.7.0 (`hdi 0.8.0` / `hdk 0.7.0`)

**Every entry here was hit for real during the migration. Nothing inferred.**

That rule is the whole point of this file. The pre-migration checklist in `CLAUDE.md`
was assembled from indirect sources and **four of its claims turned out to be wrong** —
all four in items derived from branch-watching and a draft upgrade guide, none in items
checked against a shipped artifact. So: if it is not written down here, it was not
observed. Anything still believed-but-unobserved stays in `CLAUDE.md` under its
⚠️ UNVERIFIED tag until the port actually touches it.

**Promotion plan.** At the end of Phase A this log gets folded into
`docs/Holochain_complete.md`, and that file's version banner is re-scoped to 0.7.
Sections nobody touched during the port stay explicitly marked unverified — which tells
the next reader exactly where the gaps are, instead of dressing 0.6 knowledge in a 0.7 label.

---

## Scope

| Phase | Scope | Status |
|---|---|---|
| **A** | 4 DNA integrity+coordinator zomes, `shared_types`, `sweettest_integration`, conductor configs | in progress |
| **B** | 97 Tryorama tests + Svelte UI | 🔴 blocked upstream — no stable `@holochain/client` 0.21, no 0.7 Tryorama line |
| **C** | `valichord/wind-tunnel/` | 🔴 blocked upstream — `holochain_wind_tunnel_runner` still on `holochain = "0.6"` |

---

## FlatOp arms — what actually changed

Expected: **51 arms** across four integrity zomes (26 `RegisterUpdate` / 12 `StoreEntry` /
8 `RegisterDeleteLink` / 4 `RegisterDelete` / 1 `RegisterAgentActivity` / 0 `StoreRecord`).

⚠️ **Ordering is the enforcement mechanism for immutability**, concentrated in `attestation`
(12 live per-type guard arms that must stay ahead of the generic `OpUpdate::Entry { action, .. }`
arm). `validator_workspace` and `researcher_repository` are all-private, so their per-type arms
are dead code and immutability rests on **one blanket `OpUpdate::PrivateEntry` arm each** —
different risk, same severity.

### Arm inventory — recounted on the branch, 2026-07-31 ✅ checklist held

| variant | attestation | governance | validator_workspace | researcher_repository | total |
|---|---|---|---|---|---|
| `RegisterUpdate` → `Update` | 12 | 5 | 5 | 4 | **26** |
| `StoreEntry` → `CreateEntry` | 8 | 4 | 0 | 0 | **12** |
| `RegisterDeleteLink` → `Link(OpLink::DeleteLink)` | 5 | 3 | 0 | 0 | **8** |
| `RegisterDelete` → `Delete` | 1 | 1 | 1 | 1 | **4** |
| `RegisterAgentActivity` → `AgentActivity` | 1 | 0 | 0 | 0 | **1** |
| `StoreRecord` → `CreateRecord` | 0 | 0 | 0 | 0 | **0** |
| `RegisterCreateLink` | 0 | 0 | 0 | 0 | **0** |
| | | | | | **51** |

Matches the pre-branch count exactly, including the per-zome update split.

❌ **CORRECTION to `CLAUDE.md`: `attestation` has NINE per-type immutability guard arms, not twelve.**
The checklist says *"its 12 per-type `OpUpdate::Entry` guard arms"*. Twelve is the total
`RegisterUpdate` arm count. The actual breakdown (`attestation_integrity/src/lib.rs:430–508`) is:

- **9 per-type guards** — `ValidationAttestation` (:430), `CommitmentAnchor` (:436),
  `PhaseMarker` (:442), `ResearcherResultCommitment` (:448), `ResearcherReveal` (:454),
  `AgentIdentityAttestation` (:460), `ValidationRequest` (:468), `StudyClaimRelease` (:474),
  `StudyClaim` (:483)
- **3 fall-through arms** — generic `OpUpdate::Entry { action, .. }` (:490, author check),
  `OpUpdate::PrivateEntry` (:501, Invalid — this DNA has no private entries),
  catch-all `RegisterUpdate(_)` (:508, Valid)

**The ordering invariant is precise: all 9 guards must stay above :490.** The checklist's
list of guarded types was also incomplete — it named six; there are nine.

### The ordering invariant, stated exactly — per DNA

Read off the source on the branch, before any edit. **These are the three things a reflow
must not break.** Each is compile-clean if broken, so only the tripwires catch them.

**`attestation`** (`attestation_integrity/src/lib.rs`) — public entries, ordering is everything:
> all **9** per-type guards (`:430`–`:487`) must stay **above** the generic
> `OpUpdate::Entry { action, .. }` author-check at `:490`.

This is the case that was reproduced by negative control on 2026-07-30: moving the
`ValidationAttestation` guard below `:490` made the forbidden update **succeed**, because the
generic arm's author-check passes for the entry's own author.

**`validator_workspace`** (`:149`–`:217`) and **`researcher_repository`** (`:150`–`:206`) —
all entries private, so the shape is different and the checklist's framing needs one refinement:
> the blanket `OpUpdate::PrivateEntry { .. } => Invalid` arm (`:210` / `:199`) must stay
> **above** the catch-all `RegisterUpdate(_) => Valid` (`:217` / `:206`).

⚠️ Note what is *not* the invariant here. The per-type guards at `validator_workspace:149,157`
and `researcher_repository:150`, **and the generic `OpUpdate::Entry` arm at `:200`/`:189`, are
all dead code** — private entries can only ever surface as `OpUpdate::PrivateEntry`. So the
relative order of `:200` and `:210` is irrelevant; only `:210` vs `:217` matters. One arm is
the entire immutability guard for each of these two DNAs.

| zome | arm | 0.6 form | 0.7 form | notes |
|---|---|---|---|---|
| attestation | ×12 | `FlatOp::RegisterUpdate(…)` | `FlatOp::Update(…)` | pure rename |
| attestation | ×8 | `FlatOp::StoreEntry(OpEntry::CreateEntry{…})` | `FlatOp::CreateEntry(OpEntry::CreateEntry{…})` | pure rename; inner `OpEntry::CreateEntry` keeps its name |
| attestation | ×5 | `FlatOp::RegisterDeleteLink{ link_type, .. }` | `FlatOp::Link(OpLink::DeleteLink{ link_type, .. })` | **structural** — note the extra closing paren |
| attestation | ×1 | `FlatOp::RegisterDelete(OpDelete{action})` | `FlatOp::Delete(OpDelete{action})` | pure rename |
| attestation | ×1 | `FlatOp::RegisterAgentActivity(OpActivity::AgentValidationPkg{membrane_proof, ..})` | `FlatOp::AgentActivity(…)` | rename only, as predicted |

| governance | ×5 | `FlatOp::RegisterUpdate(…)` | `FlatOp::Update(…)` | pure rename |
| governance | ×4 | `FlatOp::StoreEntry(…)` | `FlatOp::CreateEntry(…)` | pure rename |
| governance | ×3 | `FlatOp::RegisterDeleteLink{…}` | `FlatOp::Link(OpLink::DeleteLink{…})` | structural |
| governance | ×1 | `FlatOp::RegisterDelete(…)` | `FlatOp::Delete(…)` | pure rename |

**attestation ported 2026-07-31 — compiled clean on the first build, zero warnings.**
27 renames, all counts matched expectation. Ordering verified mechanically: all **29**
top-level arms (27 `FlatOp` + 2 `_` catch-alls) are in identical positions with identical
selectors, guards at 0–8 and the generic arm at 9.

⚠️ **Sequencing constraint discovered: the tripwires cannot run per-zome.** They need all four
DNAs packed, `sweettest_integration` on 0.7, *and* a 0.7 `hc` binary. So the handoff's
"run after each batch of arms" cadence is not achievable mid-port. The achievable per-zome
checks are `cargo build -p <zome> --target wasm32-unknown-unknown --release` plus the two
below; the tripwires run once the whole of Phase A compiles.

### Two negative controls, both run before trusting the result

Compile-clean is exactly what broken ordering looks like, so neither check was trusted until
it was shown to fail.

1. **The arm-ordering checker.** Reproduced the 2026-07-30 accident on a copy — moved the
   `ValidationAttestation` guard below the generic `Update` arm — and the checker reported
   **10 mismatches**. It fires on the real hazard.
2. **rustc still helps, partially, on 0.7.** The same broken copy produced
   `warning: unreachable pattern`. Useful because our *correct* build produces **zero**
   warnings, so any warning during the remaining three zomes is signal rather than noise.
   Unchanged caveat: it is a warning not an error, and it catches **only** shadowing — not a
   deleted arm, nor one whose pattern stops matching after a rename.

The checker is now a reusable script rather than a one-off:
`scratchpad/check_arm_order.py <old.rs> <new.rs>` (exit 1 on mismatch). It carries the
rename table, so it compares a 0.6 original against its 0.7 port directly.

**governance ported 2026-07-31 — 13 arms, clean first build, zero warnings, 15/15 arms in
identical order.** Its ordering hazard is *not* the same shape as attestation's, and was
negative-controlled separately: governance has no generic `OpUpdate::Entry` arm, but its
**`ValidatorReputation` update arm carries the `system_coordinator_key` authorisation
check**. Dropped below the `Update(_)` catch-all it becomes dead code and *any agent may
rewrite any reputation record* — a privilege-escalation, not just a lost immutability guard.
Reproducing exactly that break made the checker report 2 mismatches and rustc warn. Restore
verified byte-identical afterwards.

⚠️ **Generalisation worth carrying into the last two zomes:** the hazard is not "guards above
the generic arm". It is **"any arm carrying logic must stay above any broader arm that would
swallow it"** — which in governance is an authorisation check, and in
`validator_workspace`/`researcher_repository` will be the single blanket `PrivateEntry` arm
vs the `Update(_)` catch-all.

**validator_workspace (6 arms) + researcher_repository (5 arms) ported 2026-07-31** — clean
build, zero warnings, 7/7 and 6/6 arms in identical order. Both are pure renames
(`RegisterUpdate`→`Update`, `RegisterDelete`→`Delete`); neither has link or create arms.

Negative-controlled on **their** hazard, which is the most severe of the three shapes: moving
the single blanket `OpUpdate::PrivateEntry` arm below `Update(_)` makes it dead code, and
**every private entry in the DNA becomes mutable at once** — `ValidatorPrivateAttestation`
(the sealed commit-reveal verdict), `LockedResult` (the researcher's nonce + result),
`PreRegisteredProtocol`. One arm, whole-DNA blast radius. Both the order checker and rustc
fired on it, in both zomes; restores verified byte-identical.

### ✅ All four integrity zomes + all four coordinators build on 0.7

Verified with a genuine from-scratch rebuild (WASM artifacts and fingerprints deleted first —
an incremental "Finished in 0.08s" is not evidence). All 8 zomes compiled, **zero errors and
zero warnings**. Total 51/51 arms ported; 57/57 top-level match arms confirmed in identical
order and selectors across the four zomes.

### 🆕 `[workspace.dev-dependencies]` is not a real Cargo key — `fixt` was never applied

`cargo` reports `unused manifest key: workspace.dev-dependencies` (`valichord/Cargo.toml:34`).
There is no such table in the manifest format (`[workspace.dependencies]` exists;
dev-dependencies are not inheritable this way). So the `fixt` pin there has **always** been
inert, on 0.6.2 as much as 0.7. Bumped `0.6` → `0.7` for correctness, but nothing consumes it.
Pre-existing, not caused by the migration; recorded so it is not mistaken for migration fallout.

---

## API surprises (things the checklist did NOT predict)

### The `action.author` field access breaks everywhere — but the compiler catches all of it

Verified against shipped `hdi 0.8.0` + `holochain_integrity_types 0.7.0` (crate sources
pulled from crates.io, 2026-07-31). `TypedAction<D>` is `{ header: ActionHeader, data: D }`
with `Deref<Target = D>`. So a field access on `action` resolves against **`D`**, not the header.

`ActionHeader` owns `author` / `timestamp` / `action_seq` / `prev_action`. The per-variant
`D` structs (`CreateData`, `UpdateData`, `DeleteData`, `CreateLinkData`, `DeleteLinkData`)
own **none** of them. Consequences, split by whether the compiler will tell us:

| 0.6 expression | 0.7 | why | sites |
|---|---|---|---|
| `action.original_action_address` | ✅ **unchanged** | `UpdateData.original_action_address` — same field, same name, reached via `Deref` | 4 |
| `action.deletes_address` | ✅ **unchanged** | `DeleteData.deletes_address` — ditto | 4 |
| `action.author` | 🔴 **compile error** → `action.author()` | no `author` field on any `D`; it is an accessor on `TypedAction` | **~20** |

**This is the good case.** Every broken site is a hard compile error (`no field 'author' on
type 'UpdateData'`), so none can slip through silently — unlike the arm-ordering hazard,
which compiles clean. Note the type change too: `author()` returns `&AgentPubKey`, so
comparisons against an owned `AgentPubKey` need a deref (`anchor.validator != *action.author()`)
and `.to_string()` sites just chain (`action.author().to_string()`).

⚠️ **The two "unchanged" rows are the ones to watch.** They compile silently. They were
checked field-by-field against the 0.7.0 struct definitions and the names and meanings are
identical — but this is exactly the class of thing that would otherwise be assumed.

### 🔴 THE ONE THE AUDIT MISSED — `Action::<Variant>(..)` pattern matching in **coordinators**

The v2 Action model was on the checklist (*"legacy per-variant action structs … removed"*),
but the mechanical audit that declared everything zero **only covered the four integrity
zomes, `shared_types` and `sweettest_integration`** — it never grepped the *coordinator*
zomes for `Action::` patterns. Three real sites, found only when the full workspace build
failed:

| file | 0.6 | 0.7 |
|---|---|---|
| `validator_workspace_coordinator/src/lib.rs:290` | `if let Action::Create(create) = signed.action()` | `if let ActionData::Create(create) = &signed.action().data` |
| `attestation_coordinator/src/lib.rs:90` | `if let Action::AgentValidationPkg(avp) = record.action()` | `if let ActionData::AgentValidationPkg(avp) = &record.action().data` |
| `attestation_coordinator/src/lib.rs:1938` | `if let Action::Create(_) = signed_action.action()` | `if let ActionData::Create(_) = &signed_action.action().data` |

`Action` in 0.7 is a **struct** `{ header: ActionHeader, data: ActionData }`, not an enum —
hence `no associated item named 'Create' found for struct 'Action'`. The per-variant payload
field names all survive (`CreateData.entry_hash`, `AgentValidationPkgData.membrane_proof`),
so only the match shape changes.

⚠️ **Lesson for Phase B/C: treat the audit's "confirmed ZERO" table as scoped to the files it
actually grepped.** Two of those three sites are in `post_commit` — the commit-reveal
notification path — so this would have been a runtime break in the protocol's critical path,
not a cosmetic one. It was caught only because the compiler is strict here.

### ❌ `sweettest_integration` broke in a completely different place than predicted

The checklist predicted PR #5898's re-layering of conductor state types would surface as
*"unresolved names scattered through the tests"*, because two of the three imports are globs.
**That did not happen at all.** Not one name moved out from under the globs. What actually
broke was three unrelated things:

**1. `pkcs8` pin — the dependency graph would not even resolve.** `sweettest_integration`
pinned `pkcs8 = "=0.11.0-rc.11"` as a 0.6.x workaround (0.6 pulled `ed25519-dalek 3.0.0-pre.1`,
which broke against `pkcs8 0.11.0` stable). 0.7.0 pulls `ed25519-dalek 3.0.0-rc.0` via
`iroh 1.0.0` ← `kitsune2_transport_iroh 0.5.0`, and that **requires `pkcs8 ^0.11` stable**.
The pin made the graph unresolvable. Its own comment said to drop it on upgrade — past-us
left the right instruction, and it was correct.

**2. `serde_yaml` → `yaml_serde`.** `YamlProperties::new` now takes a `yaml_serde::Value`.
Holochain 0.7 moved off the deprecated `serde_yaml 0.9.34+deprecated` to `yaml_serde 0.10.4`,
which is an API-compatible rename (same `from_str`, `Value`, `Mapping`, `as_mapping_mut`).
13 use sites across `src/lib.rs` and `tests/security.rs`, plus the `Cargo.toml` dep. The
error is friendly — rustc says *"have similar names, but are actually distinct types"*.

**3. ⚠️ `SweetConductor::from_standard_config()` is REMOVED, and `standard()` is NOT its rename.**
This is the one to be careful with, because the obvious substitution silently changes behaviour:

| 0.6.2 | body | 0.7.0 | body |
|---|---|---|---|
| `from_standard_config()` | `from_config(SweetConductorConfig::standard())` — **no rendezvous** | `standard()` | `from_config_rendezvous(SweetConductorConfig::rendezvous(true), SweetLocalRendezvous::new())` — **spawns a local rendezvous server, bootstrap enabled** |

Porting `from_standard_config()` → `standard()` would silently add a rendezvous server to
every single-conductor test. Ported faithfully instead as
`create_with_defaults(SweetConductorConfig::standard(), None, None::<DynSweetRendezvous>)`.
Verified equivalent: 0.6.2's `from_config` did `create_with_defaults(config, None, config.get_rendezvous())`,
and `SweetConductorConfig::standard()` never set a rendezvous, so `get_rendezvous()` was `None`.
(`get_rendezvous()` does not exist in 0.7.0 at all.)

`SweetConductorBatch::from_standard_config_rendezvous(n)` → `from_config_rendezvous(n,
SweetConductorConfig::rendezvous(true))` **is** an exact equivalent — that is literally the
old function's body. 5 sites in `tests/`, 1 in `src/lib.rs`.

Result: all 6 test binaries compile. One warning remains
(`unused import: UpdateValidatorProfileInput`, `tests/attestation.rs:34` — the symbol is used
at `:680` via its fully-qualified path). **Pre-existing and identical on `main`**, not
migration fallout; left alone rather than widening scope.

### `OpEntry::CreateEntry` carries `TypedAction<CreateData>`

Not `EntryCreationData`. `EntryCreationData` (the `Create`-or-`Update` narrowing enum that
replaces the removed `EntryCreationAction`) exists in `hdi 0.8.0` but is used by
`OpRecord`/`OpActivity`, not by the `OpEntry::CreateEntry` arm we match. Our 12 `StoreEntry`
arms therefore need the variant rename plus the `action.author` fix, nothing more.

### `OpLink` accessors exist, and we need none of them

`OpLink::base_address()` / `target_address()` / `tag()` are provided because those fields
moved into the per-variant data. **Zero impact for us** — all 8 of our link arms are
`RegisterDeleteLink` arms that match on `link_type` and discard the rest with `..`
(confirmed: no integrity zome reads a link base/target/tag). The port is the structural
fold into `FlatOp::Link(OpLink::DeleteLink { link_type, .. })` and nothing else.

### ❌ The sweettest "feature flag" migration is ZERO work — the checklist's dep line is wrong for us

`CLAUDE.md` prescribes this line for `sweettest_integration`:

```toml
holochain = { version = "0.7.0", default-features = false, features = ["encryption", "wasmer-sys-cranelift"] }
```

with the note *"`sqlite-encrypted`→`encryption`, `wasmer_sys`→`wasmer-sys-cranelift`, drop `transport-iroh`"*.

**That recipe is for a manifest that named the old features explicitly. Ours does not.**
Our actual line is `holochain = { version = "=0.6.2", features = ["test_utils"] }` — plain
defaults plus `test_utils`. And shipped `holochain 0.7.0`'s own defaults are:

```toml
default = ["encryption", "schema", "wasmer-sys-cranelift"]
```

— i.e. the renamed features are *already* the defaults. So the correct edit is the version
bump alone (`"=0.6.2"` → `"=0.7.0"`), and **applying the prescribed line as written would be
a regression**: `default-features = false` would silently drop `schema`, which we currently get.

Same logic for `sqlite-encrypted` / `wasmer_sys` / `transport-iroh` — all three are a hard
zero in our manifests, so there is nothing to rename or drop.

### Version strings — 7 confirmed, exactly as counted

`valichord/Cargo.toml:18` (`hdi = "=0.7.2"` → `=0.8.0`), `:19` (`hdk = "=0.6.2"` → `=0.7.0`);
`sweettest_integration/Cargo.toml:39–43` (`holochain`, `holochain_types`, `holochain_keystore`,
`hdk`, `holo_hash`, all `=0.6.2` → `=0.7.0`). Every zome uses `{ workspace = true }`, so there
are no other literals. ⚠️ `valichord/Cargo.toml:21` pins `holochain_serialized_bytes = "=0.0.57"`
— **not yet checked** against what `hdi 0.8.0` expects.

### `AgentValidationPkg` — confirmed, rename only

Shipped `OpActivity::AgentValidationPkg { membrane_proof: Option<MembraneProof>, action:
TypedAction<AgentValidationPkgData> }` **retains `membrane_proof`**, and our single arm
(`attestation_integrity/src/lib.rs:957`) destructures exactly `{ membrane_proof, .. }`.
So: `FlatOp::RegisterAgentActivity` → `FlatOp::AgentActivity` and nothing else. The official
upgrade guide's rewrite recipe applies to `OpActivity::CreateAgent`, a variant we never match.
This confirms the checklist's ❌ correction against the guide.

---

## Compiler errors worth remembering

_(nothing yet)_

---

## Conductor / config

Predicted (verified empirically against the real 0.7.0 binary on 2026-07-30, before the
branch existed): two lines per file — remove `signal_url` from `network:`, rename
`db_sync_strategy` → `db_sync_level` (`Fast`→`Off`, `Resilient`→`Normal`). Files:
`demo/conductor-config-node.yaml`, `valichord-ui/dev-conductor.yaml`,
`demo/rehearse-autoupdate.sh` (`signal_url` only).

Record here what happened when the edits were actually applied in anger.

_(nothing yet)_

---

## Tripwire runs

The immutability tripwires (`sweettest_integration/tests/immutability_tripwire.rs`, 5 tests)
are the safety net for the arm port. Run before starting and after each batch of arms:

```bash
cd valichord && ./build-test-dnas.sh
cd sweettest_integration && VALICHORD_DNA_DIR=../workdir-test cargo test --test immutability_tripwire -- --test-threads=1
```

| when | result | notes |
|---|---|---|
| 2026-07-31, baseline on unmodified 0.6.2 | ✅ **5 passed, 0 failed** (833.80 s) | Run before touching any zome code. Safety net confirmed live before the port began. |
| after Phase A compiles end-to-end | pending | cannot run sooner — see the sequencing constraint above |

---

## Still unverified at end of Phase A

_(to be filled at the end of Phase A — this section is what stops the log from being
promoted into `Holochain_complete.md` as false confidence)_
