# Coordinator Auto-Updater Sidecar — Plan

**Status:** Scoped, not built — 2026-07-23
**Author:** Ceri John (scoped with Claude Code)
**Source of pattern:** `WeAreFlowsta/flowsta-dht-node` (Eric Doriean) — checksum-verified DNA
auto-updater sidecar. Adapted, not copied: see the "Critical reframe" below for why
ValiChord's updater is fundamentally coordinator-only where Flowsta's installs new DNA
versions.

---

## Problem

Pushing a coordinator-zome fix to the live Oracle demo nodes (researcher + 3 validators on
`152.67.153.149`) is manual today:

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

### Phase 1 — `coordinators-manifest.json` + published WASMs (no new infra)

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

### Phase 2 — the updater loop (`demo/coordinator-autoupdate.mjs`)

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

### Phase 3 — safety rails

- **Coordinator-only guard.** The manifest carries only coordinator WASMs; the updater has
  no `InstallApp` path. Assert that applying the manifest leaves the DNA hash unchanged
  (compare `AppInfo` DNA hashes before/after; abort + alert if any changed).
- **Ordering.** Researcher first, then validators — mirroring the manual runbook. For the
  in-container loop this is naturally per-node; a `AUTOUPDATE_ROLE_DELAY_S` lets validators
  wait a beat so the researcher lands first when a fleet updates near-simultaneously.
- **Rollback.** Keep the previous WASM + previous revision; a bad revision is reverted by
  pinning the marker to the old revision and re-running (or `AUTOUPDATE=off` + manual swap).
- **Kill-switch.** `AUTOUPDATE=off` (default `on` for Oracle, `off` for local dev) — opt-in
  per deployment.

### Verification / test plan

- Reuse `REHEARSAL=1` throwaway-conductor mode for local end-to-end: publish a fake manifest
  at revision N+1 pointing at a rebuilt coordinator WASM, confirm the loop applies it and
  the marker advances, confirm a corrupted WASM is rejected on sha256, confirm a manifest
  with a changed DNA hash is refused.
- Dry-run against a local `docker compose up` stack before any Oracle rollout.
- First Oracle rollout: set the manifest to the *currently applied* revision (a no-op the
  nodes should recognise and skip), verify markers appear correctly, then publish a real
  bump.

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
