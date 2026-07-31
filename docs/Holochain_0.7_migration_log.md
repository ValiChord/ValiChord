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

| zome | arm | 0.6 form | 0.7 form | notes |
|---|---|---|---|---|
| _(fill in as ported)_ | | | | |

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
| _(baseline, pre-port)_ | pending | |

---

## Still unverified at end of Phase A

_(to be filled at the end of Phase A — this section is what stops the log from being
promoted into `Holochain_complete.md` as false confidence)_
