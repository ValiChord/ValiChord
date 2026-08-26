# Coordinator Auto-Updater Sidecar — Plan

**Status:** Phases 1–3 built + tested — 2026-07-23 (end-to-end rehearsal PASS on a real conductor;
`coordinators-rev-1` published). Only the first live Oracle rollout remains — an ops step, not
code, **but it is a container rebuild, not a config flip**: the Oracle clone is 18 commits behind
and has no `coordinator-autoupdate.mjs` and no `AUTOUPDATE` block in its `node-entrypoint.sh`, so
`AUTOUPDATE=on` alone is inert (verified on the box 2026-07-23). Not urgent — rev-1 is a **no-op**
for Oracle, whose live nodes already run that coordinator code via the 2026-07-08 hot-swap.
See PROJECT_STATUS.md → "Coordinator auto-updater" for the rollout options and the `down -v` warning.
**Author:** Ceri John (scoped with Claude Code)
**Source of pattern:** `WeAreFlowsta/flowsta-dht-node` (Eric Doriean) — checksum-verified DNA
auto-updater sidecar. Adapted, not copied: see the "Critical reframe" below for why
ValiChord's updater is fundamentally coordinator-only where Flowsta's installs new DNA
versions.

---

## Problem

Pushing a coordinator-zome fix to the live Oracle demo nodes (researcher + 3 validators on
`132.145.23.78`, since the 2026-08-24 rebuild) is manual today:

```
scp   attestation_coordinator.wasm + hotswap-coordinators.mjs  → host
docker cp <files> <container>:/tmp/          # per container
docker exec … node /tmp/hotswap-coordinators.mjs   # per container, researcher first, verify between
```

Consequences:
- **Error-prone ordering.** Four containers swapped by hand; easy to leave nodes on
  mismatched coordinator revisions (split-brain coordinator behaviour).
- **Single WASM only.** `hotswap-coordinators.mjs` swaps one coordinator (attestation).
  A change touching both attestation and governance is two manual passes.
- **No versioning, no integrity check.** Nothing records which revision a node is on, and
  nothing verifies the WASM bytes before applying them.
- **The happ is baked into the image** (`/app/valichord/workdir/${ROLE}.happ`), so the only
  alternatives to the manual swap are (a) rebuild the image, or (b) `down -v` — which
  **destroys every published HarmonyRecord URL**.

## Critical reframe — why this is NOT Flowsta's updater verbatim

Flowsta's `dht-update.mjs` installs **new DNA versions**. Each new version is a new DNA
hash = a new network. That is acceptable for a Flowsta community node, which only serves
whatever public networks exist and has no stable per-network state to preserve.

**ValiChord cannot do that.** The Oracle nodes hold one live network with published
HarmonyRecord URLs. A new *integrity*-DNA hash = a new network = **every shared URL dies**
(the same hazard as `docker compose down -v`).

Therefore:

- We borrow Flowsta's **delivery mechanism** (poll a manifest → checksum-verify → apply,
  non-fatal, retrying, wait-for-conductor-ready).
- The **apply step is `AdminRequest::UpdateCoordinators`** — zero DNA-hash change,
  identical to what `demo/hotswap-coordinators.mjs` already does.
- **Integrity-zome changes are out of scope by design.** Those require a new network and
  remain a deliberate, manual, breaking migration. The updater must never call
  `InstallApp` and must refuse any manifest that could change a DNA hash.

This is the coordinator-only upgrade path already documented in `CLAUDE.md`
("Coordinator-only upgrade (zero DNA hash change)"), automated.

## What already exists (≈70% of the hard part)

`demo/hotswap-coordinators.mjs` already implements:
- `AdminRequest::UpdateCoordinators` against a running conductor (zero hash change).
- A real read-only zome-call verification (`get_my_claimed_studies`) **before and after**
  the swap.
- A `REHEARSAL=1` throwaway-conductor mode for safe local testing.

The gap is only: manifest/versioning, sha256 verification, multi-zome, multi-node
ordering, and running it on a loop instead of by hand.

---

## Design

### Phase 1 — `coordinators-manifest.json` + published WASMs (no new infra) — ✓ DONE 2026-07-23

Shipped as `demo/pack-coordinators.mjs` (Node built-ins only, no npm deps). Reads the four
built coordinator WASMs, computes a sha256 over each **raw** WASM (the exact bytes
`UpdateCoordinators` consumes — cross-checked against `hotswap-coordinators.mjs`), and emits
`coordinators-manifest.json` + WASM copies into `demo/coordinator-updates/` (self-ignored so
binaries are never committed — they become GitHub release assets). Flags: `--dry-run`,
`--revision N` (default: prior revision + 1), `--holochain X.Y.Z` (default: detected), `--only
<roles>`, `--wasm-dir`, `--out`. Manifest grouped **per cell** (not the flat list sketched
below) because `UpdateCoordinators` is per-cell; each zome entry carries
`{name, integrity, wasm, sha256, bytes}` — everything Phase 2 needs to rebuild the bundle and
verify a download. Default set = **all four** coordinators (attestation, governance,
researcher_repository, validator_workspace); Phase 2 skips any cell a node doesn't run.
Verified: sha256 matches independent `sha256sum`; auto-bump reads the prior revision; never
opens a conductor socket.

A small manifest, committed to / released from `ValiChord/ValiChord` and served as GitHub
release assets over checksummed HTTPS (GitHub is already the source of truth — **zero new
servers**):

```json
{
  "revision": 3,
  "holochain": "0.6.2",
  "zomes": [
    { "role": "attestation", "wasm": "attestation_coordinator.wasm", "sha256": "…" },
    { "role": "governance",  "wasm": "governance_coordinator.wasm",  "sha256": "…" }
  ]
}
```

- `revision` is a monotonic integer — the only thing a node compares against its local
  applied-marker.
- `holochain` pins the conductor version the WASMs were built against (a node on a
  different conductor version refuses to apply — a guard against a toolchain mismatch).
- A helper `demo/pack-coordinators.mjs` packs the coordinator WASMs and emits the manifest
  with authoritative sha256 values, so the checksum is generated, never hand-typed.

> Coordinator WASMs are built with `hc dna pack --coordinator-only` (no integrity bytes),
> per `CLAUDE.md`. This is what keeps the DNA hash identical.

### Phase 2 — the updater loop (`demo/coordinator-autoupdate.mjs`) — ✓ DONE 2026-07-23

Shipped as `demo/coordinator-autoupdate.mjs` (Node 20 built-ins + `@holochain/client`, no new
deps) plus an **opt-in, default-OFF** launch hook in `node-entrypoint.sh`. Reuses the exact
`updateCoordinators` bundle shape proven live in `hotswap-coordinators.mjs` (kept untouched to
avoid regressing the working tool) but is manifest-driven, multi-cell, and looped.

Behaviour per cycle: fetch manifest → compare `revision` to the marker
(`/app/demo/conductor_data/.coordinator-revision`, on the persisted volume) → if newer,
download every WASM and **sha256- + size-verify before applying anything** (any mismatch
aborts the whole update) → guard `manifest.holochain` == running conductor → per cell present
on this node: `updateCoordinators`, then **assert the DNA hash is unchanged** (published URLs
must survive), then a read-only verify zome call where one is configured (attestation →
`get_my_claimed_studies`) → write the marker. Modes: loop (default), `--once`, `--check`
(conductor-free: fetch+verify only). Non-fatal in loop mode.

**Phase 3 rails already folded in here:** coordinator-only by construction (never `InstallApp`),
DNA-hash-unchanged assertion, role-ordering delay (`AUTOUPDATE_ROLE_DELAY_S`), kill-switch
(`AUTOUPDATE=off`, the default), monotonic marker. Still outstanding for Phase 3: an explicit
rollback helper (keep-previous-WASM + pin marker) and the first live Oracle rollout rehearsal.

**Locally tested (conductor-free `--check`):** success path verifies all four WASMs and reports
OK-to-apply; noop when marker ≥ manifest revision; **fail-closed** refusal (exit 1) on a
tampered sha256. Entrypoint guard proven inert when `AUTOUPDATE` is unset/off.

Generalise `hotswap-coordinators.mjs` into a poller. On each interval (default 6 h, matching
Flowsta; configurable via `AUTOUPDATE_INTERVAL_S`):

1. Fetch `coordinators-manifest.json`.
2. Compare `revision` to the local applied-marker file
   (`/app/demo/conductor_data/.coordinator-revision`, on the persisted volume).
3. If newer:
   a. Download each WASM.
   b. **Verify sha256 against the manifest — refuse the whole update on any mismatch.**
   c. Verify `manifest.holochain` matches the running conductor version.
   d. For each zome, `AdminRequest::UpdateCoordinators` (reusing the existing swap logic).
   e. Run the existing read-only verification zome call.
   f. On success, write the new revision to the marker file.
4. All steps non-fatal and retrying — a failed poll never crashes the node; it retries next
   interval, exactly like the Flowsta sidecar.

**Where it runs:** a background loop inside `demo/node-entrypoint.sh`, in the same container
as the conductor. The container already has localhost:4444 admin access, so **no compose
changes and no exposed admin port are needed.** (Alternative considered and rejected for
now: a separate sidecar container per node via `network_mode: service:<node>` — more moving
parts for no benefit at demo scale.)

### Phase 3 — safety rails + rollout tooling — ✓ DONE 2026-07-23

Rails (all shipped; most folded into `coordinator-autoupdate.mjs` during Phase 2):
- **Coordinator-only guard.** ✓ The manifest carries only coordinator WASMs; the updater has
  no `InstallApp` path. After each swap it re-reads `AppInfo` and asserts the cell's DNA hash
  is unchanged (aborts if not) — exercised in the rehearsal below.
- **Ordering.** ✓ `AUTOUPDATE_ROLE_DELAY_S` lets validators wait so the researcher node lands
  first when a fleet updates near-simultaneously.
- **Kill-switch.** ✓ `AUTOUPDATE=off` (the default) — opt-in per deployment.
- **Rollback (pin ceiling).** ✓ `AUTOUPDATE_MAX_REVISION` halts auto-upgrades at a known-good
  revision even if a newer (bad) manifest is published. To revert an already-applied bad
  revision, **roll-forward**: re-pack the previous-good WASMs and publish them as a higher
  revision (releases are immutable), or on a single node run `hotswap-coordinators.mjs` with
  the old WASM + `AUTOUPDATE=off`. No local WASM cache is needed — published releases are the
  durable store.

Rollout tooling (new this phase):
- **`demo/publish-coordinators.sh`** — packs → publishes the manifest + WASMs as an immutable
  GitHub release (tag `coordinators-rev-<N>`) and prints the `AUTOUPDATE_MANIFEST_URL`. Refuses
  to clobber an existing revision. `--dry-run` supported.
- **`demo/rehearse-autoupdate.sh`** — end-to-end rehearsal against a throwaway conductor:
  installs `valichord.happ` (dev bypass), serves the manifest, runs `--once`, asserts the
  marker advanced. Self-cleaning (temp dir, isolated port, full teardown).

### Verification — DONE

- **Conductor-free (`--check`):** success verifies all four WASMs; noop at/below the marker;
  **fail-closed** refusal (exit 1) on a tampered sha256; pin ceiling holds above / allows
  at-or-below the pin.
- **End-to-end rehearsal on a real conductor, 2026-07-23 — PASS:** installed `valichord.happ`,
  applied `UpdateCoordinators` to **all four cells** (attestation, governance,
  researcher_repository, validator_workspace), the **DNA-hash-unchanged assertion held on every
  cell**, the attestation verify call returned OK, the marker advanced 0 → 1, exit 0.
  (Gotcha found + fixed: a throwaway conductor config needs a `relay_url` field even for a
  single no-peer node; and the in-proc lair socket path must stay short — `SUN_LEN` — so the
  rehearsal uses `mktemp -d` under `/tmp`, not a long scratch path.)
- **Still pending (ops, not code) — first live Oracle rollout:** publish a revision matching
  the *currently-applied* coordinators (a no-op the nodes skip), set `AUTOUPDATE=on` +
  `AUTOUPDATE_MANIFEST_URL` on the 4 containers, verify markers, then publish a real bump.

---

## Effort

| Phase | Size | Notes |
|---|---|---|
| 1 — manifest + pack helper | Small | New `pack-coordinators.mjs`; manifest committed/released |
| 2 — updater loop | Moderate | Mostly refactoring `hotswap-coordinators.mjs`; add fetch/verify/marker/loop |
| 3 — safety rails | Small | Guards + env flags |

Low risk overall — the apply-and-verify core is code already proven live (2026-07-08).

---

## Anything else useful (triaged from the 2026-07-23 Flowsta recon)

| Pattern | Verdict | Rationale |
|---|---|---|
| **Community full-replica node template** (`flowsta-dht-node` compose + `conductor-config-example.yaml`) | **Worth it, medium value — do AFTER the auto-updater** | A template for **public governance-DNA redundancy**. Today every HarmonyRecord lives only on the Oracle box; 1–2 always-on community replicas remove that single point of failure. Larger scope (a public-node package). |
| **CGNAT / public-IP preflight** (`flowsta-dht-node/setup.sh`) | **Cheap add-on** | ~15 lines; folds into any bootstrap/relay setup script; chips at the kangaroo bootstrap blocker. Bundle with the node template, not standalone. |
| **Tri-state verify UX** (verified / unsigned / tampered-blocked, `Your-Own-AI/packSigning.ts`) | **Idea only** | Clean model for presenting an attestation check in `valichord-ui`. UI polish, not infra. Park as a UX note. |
| **Encrypted-entry DNA maturity** (`Your-Own-AI` `transcript` DNA, 1 MiB cipher cap) | **Reference, don't build** | Confirms the Phase-2 encrypt-to-self design if Open Audit Mode / mid-round crash recovery ever gets real demand. Already "don't build on spec" (arch doc Known Limitation #4). |

## Recommended order

1. **Auto-updater (Phases 1→3)** — removes a live ops pain, low risk, high reuse.
2. **Community-node redundancy template** (+ CGNAT preflight folded in) — kills the
   governance-DNA single point of failure.
3. Park the two UI/reference items as notes.

## Non-goals / explicit exclusions

- **Integrity-zome / DNA-hash changes.** Never auto-applied. Those are manual, breaking
  network migrations.
- **New networking infra.** No new bootstrap/relay/API server for the auto-updater — it
  polls a GitHub-hosted manifest.
- **Auto-update of the node API JS or the conductor binary.** Out of scope; those go via
  image rebuild.

---

*Pattern lineage: `WeAreFlowsta/flowsta-dht-node` (delivery mechanism) + ValiChord's own
`demo/hotswap-coordinators.mjs` (apply + verify) + `CLAUDE.md` coordinator-only upgrade
constraints. Directionality note: ValiChord borrows from Flowsta here; no evidence of the
reverse (2026-07-23 org code-search).*
