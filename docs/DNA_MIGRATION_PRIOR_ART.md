# DNA migration across a hash change — prior art, read properly

**Read before the Holochain 0.7 migration.** Source: `unytco/migration-service` @ `740889a` (2026-07-22), read in full 2026-07-27 — both Rust services, the TypeScript router, the state machines and the error contract.

> ⚠️ **Licence: Cryptographic Autonomy License v1.0 (CAL-1.0), not Apache-2.0.** Strong copyleft with a user-data provision. This document is a **design reading**. Do not copy code into Apache-2.0 ValiChord.

## Why this matters to us

Holochain 0.7 changes the `DnaHash` of an otherwise-identical DNA (zome-definition serialization changed) and renames the databases with no migration path. Agents on 0.7 form a network separate from 0.6. The official upgrade guide's instruction is simply to clear state.

Unyt built a migration path anyway, on the `close_chain`/`open_chain` HDK primitives documented in `Holochain_complete.md` §29. It works. Whether we should copy it is a separate question, answered at the end — **the short version is no, and the reasons are worth knowing before someone proposes it.**

---

## 1. The shape of the thing

Three components, none of which hold the security property:

| Component | Language | Role |
|---|---|---|
| `migration-router/` | TS, Cloudflare Worker | Public HTTP entry. Validates `(from_dna_hash, to_dna_hash)` against an `upgrades_from` version chain, tries that DNA's notary daemons in per-request random order, returns the package **verbatim**. Holds no keys, never interprets the payload. |
| `notary-daemon/` | Rust, axum + `ham` | Runs beside a conductor still serving the **old** network. `/healthz` + `/v1/fetch-close` behind bearer auth. Calls `read_predecessor_close` — a pure read. **No signing capability of any kind.** |
| `headless-migrator/` | Rust, clap + `ham` | Two supervised systemd services: **close** on the old server, **open** on the new. Probe-first, idempotent, exit 0 only on success so `Restart=on-failure` drives the loop. |

The registry the router validates against is bundled or KV-loaded, and pins each notary to a daemon API version; an unsupported version is a **startup** error, never a request-time one. Each `DnaEntry` carries `upgrades_from` (predecessor) and `upgrade_targets` (permitted forward destinations, mirroring the on-chain global definition).

**The security is not in any of this.** It is in the DNA's own validators, which the next section makes explicit. The three services are transport and orchestration.

## 2. Close side

The old chain is quiesced, then `close_agent_chain` commits a `ClosingStateSummary` and issues `close_chain`. Before that, M-of-N notary signatures are gathered **on-chain**, and it is those signatures — not any service — that carry the trust forward.

The collection policy (`headless-migrator/src/policy.rs`) is the part worth stealing conceptually:

- Ask only **M** of the N notaries, chosen **at random** — never all N.
- Per-request timeout (default 120 s) counts as failure → substitute a random not-yet-tried notary.
- `UnableToVerify` → transient → substitute.
- `StateMismatch` → retry the **same** notary with backoff (2 s → 30 s cap, 5 consecutive) before substituting — its DHT view is catching up, not faulty.
- A merely-slow signer is **never** substituted; slowness surfaces only as `TimedOut`, and one that eventually returns `Signed` is honoured.
- Exhausted below M → the whole attempt fails, nothing committed, retry later. **No overall deadline.**
- `Warranted` → hard stop for the entire migration.

Written pure over an injected signer + RNG, so it is exhaustively unit-testable with no conductor.

**Note the discrepancy they document honestly.** `probe.rs` models three close states — `Open` → `PrepareCollectClose`, `PartialClose` → `FinishCloseOnly`, `Closed` → `AlreadyClosed` — but `close.rs` records that the alliance transactor **exposes no bare `close_chain` extern**, so `FinishCloseOnly` is not executable: it re-runs the full prepare → collect → close. They justify it (the orphaned first summary is harmless because the author-time validator only checks the summary directly preceding the `CloseChain`, and the quiesced workload means the chain top cannot move between prepare and close) and flag it for the DNA owner. The modelled state machine and the executable action differ, deliberately and in writing. Good practice to copy.

## 3. Open side

Two-phase by necessity: connect **admin-only** first (the app cell does not exist yet, so `ham` cannot attach) to probe and install, then reconnect with `ham` to drive `init` and verify.

1. Wait out gossip until the package is fetchable from the router.
2. Fetch a **fresh membrane proof** from the target release's joining service, for the carried key.
3. Install the app **for the carried key**, with the package as the migrating role's **`init_properties`**.
4. The DNA's `init` reads those properties and **opens the chain at genesis**. `init` is driven by the first zome call (`verify_if_migrated`). Explicitly: *no post-install `migration_init` call, and no first-zome-call ordering window to guard.*
5. Verify, then persist `safe_to_teardown`.

Two traps documented there apply to **any** programmatic install, migration or not:

- **DNA modifiers must be overridden completely.** `network_seed` *and* `properties` are both hashed into the `DnaHash`. Overriding only the seed lands the cell on a different DNA than the network — *"its own empty DHT, no peers, no gossip, and an `init` that can never resolve the GD."* Silent and fatal. Our installers already override both (`dev-setup.mjs`, `node-setup.mjs`, `conductor-manager.ts`, `valichord_wt_common`); keep it that way.
- **Idempotency must survive teardown.** `safe_to_teardown` is written authoritatively at verify success so a restart *after the old side is gone* short-circuits from persisted state with no router fetch — otherwise the idempotent restart hard-requires a fetch that can never succeed, and spins forever.

## 4. Where the trust actually lives

`headless-migrator/src/dna_errors.rs` exposes the on-chain validation contract, and it is the most transferable thing in the repo after `policy.rs`.

`rave_engine`'s `MigrationError` renders a machine-extractable **`[MIGERR:<CODE>]` prefix** on every DNA-side verdict, and `from_rendered` recovers the variant from a conductor-wrapped string. Every classifier matches **the code, not the English text**, so rewording a validator message can never silently reclassify an error. Substring matching survives only as a fallback for surfaces that carry no tag, and those are enumerated in one place.

The variants show what `init` enforces on the opening side: `KeyDoesNotMatchNotarizedAgent`, `SignatureDoesNotVerify`, `NotaryThresholdNotMet`, `DuplicateNotarySigner`, `SelfNotarizedClose`, `NotaryNotConfigured`, `TargetDnaMismatch`, `SourceNotAcceptedPredecessor`, `CarryForwardMalformed`, `MigrationDisabled`, `OpeningSummaryUpdateForbidden` — plus `AlreadyMigrated` (double-migration guard) and `NonFreshChain`. Close-side codes surfacing from an `init` are treated as an anomaly and a **hard stop**, never a retry.

The service-side classification is a four-way split: `HardFailure` (terminal), `AlreadyMigrated` (success-adjacent, re-verify), `NonFreshChain` (anomalous once the chain opens at genesis, so hard stop), and `TooEarly` (successor global definition not yet gossiped or not yet effective — recoverable, but under a **bounded** deadline, since the classifier cannot distinguish "not yet" from "never").

Verification is a genuine two-source cross-check, not a self-comparison: the router-fetched package on one side, and what the new chain actually committed read back through `get_opened_agreement_state` on the other. Their own comment records that a count taken from the fetched package alone "compared a value against itself and was deliberately absent until the extern existed."

## 5. What ValiChord would have to build to do the same

Not a tooling job. To migrate a ValiChord DNA this way we would need, on **both** the old and new DNA:

- Integrity-zome validators for the closing summary and the opening summary, plus an `init` that opens the chain from `init_properties`.
- Externs the coordinators do not have: `close_agent_chain`, `read_predecessor_close`, `get_migration_close_state`, `verify_if_migrated`, and a state read-back for verification.
- A notary set defined in DNA properties with a threshold — and notaries are **nodes that keep serving the old network after cutover**.
- A version registry with `upgrades_from` / `upgrade_targets`, and a router deployment.
- An application-defined "state summary" worth carrying. Unyt's is a ledger (balance, carry-forward units). **We have no equivalent.**

That last point is the one that decides it.

## 6. Verdict for our 0.7 migration

**Do not build this. Accept the reset and republish.** Reasons, in order:

1. **It carries an agent's own source chain, not the DHT.** ValiChord's valuable artifacts are `HarmonyRecord`s — DNA 4 entries authored by *participating validators*, read by third parties at published URLs. A chain migration does not republish other-authored entries, so **no amount of this machinery saves a single published record URL.** That is the thing we actually care about losing.
2. **It cannot touch DNA 1 or DNA 2.** Both are single-agent private DNAs: no peers, therefore no notaries and no gossip. This is the same boundary that limits 0.7's source-chain restore, and for the same reason. `LockedResult` and `ValidatorPrivateAttestation` are unreachable either way.
3. **We have no carried state to summarise.** The mechanism's whole point is moving application state (a ledger balance) across the boundary under notary signature. ValiChord's per-agent chain state is claims and commitments whose meaning is public and already spent by the time a round finalises. There is no balance to preserve.
4. **The cost is integrity-zome work on four DNAs plus a notary fleet**, to buy identity continuity we can get more cheaply by other means if we decide we need it.

**What to do instead**, when 0.7 stable lands: treat it as a network reset. Clear state (`docker compose down -v` on Oracle, per the existing checklist), reinstall, and **re-mint the demonstrator records**. The published-URL problem is a *communications* problem, not a protocol one — if URL permanence ever becomes a real requirement, the answer is an archival/notarised-snapshot service over DNA 4, not agent-chain migration.

## 7. What we should actually take

1. **`policy.rs` → `select_validators()`.** The M-of-N random-selection policy with its failure taxonomy is the algorithm our Phase-1 validator assignment engine needs, including the distinction that a *slow* participant and a *dead* one need opposite handling. Already cross-referenced from the Known Gaps table in `docs/7_ValiChord_4-DNA_architecture_technical.md`. Design source only (CAL-1.0).
2. **Typed error codes over substring matching.** The `[MIGERR:<CODE>]` prefix + `from_rendered` pattern, with every fragile untagged match confined to one module. Our coordinators currently return bare `wasm_error!(Guest(...))` strings, and anything matching on them is matching English. Worth adopting the next time we touch a coordinator error surface.
3. **The complete-modifiers install trap**, recorded above — it costs nothing to know and is silent when you get it wrong.
4. **Probe-first idempotent supervised services**, with the modelled state machine and the executable action allowed to differ *in writing* when a DNA surface can't support the ideal.
5. **`ham`'s lair signing with no committed capability grant** — cleaner than our Node bridges, which commit signing credentials.
