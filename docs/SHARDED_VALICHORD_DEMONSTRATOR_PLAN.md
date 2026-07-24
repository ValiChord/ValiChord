# Sharded ValiChord — Demonstrator Plan

**Status:** Planning only. Nothing here is scheduled or built as of this document.
**Date:** 2026-07-19
**Author:** Ceri John (with AI assistance)
**Related work:** `research/dht-arc-sharding-sim` branch · canonical repo `ValiChord/polite-shrink` · PR `holochain/kitsune2#572` · kitsune2 issue #160

---

## What this document is

A plan for demonstrating a version of ValiChord whose shared DHTs **shard** — each
node holding a *slice* of the data instead of a full replica — using the
**polite-shrink** controller, *before* Holochain ships safe arc-resizing itself.

It defines two tiers of demonstrator, from cheapest/honest to full/blocked, so a
future decision to build can pick the right cut deliberately.

**This is not a commitment to implement.** It is the map.

---

## Scope: what "sharded ValiChord" actually means

Sharding is a **network-layer** property (kitsune2), *not* an application-layer one.
The four ValiChord DNAs and their zome code do **not** change. Two facts bound the
whole exercise:

1. **Only 2 of 4 DNAs are even shardable.**
   - `researcher_repository` (DNA 1) and `validator_workspace` (DNA 2) are **private,
     single-agent** DNAs — no DHT, no peers, nothing to shard.
   - `attestation` (DNA 3, credentialed shared DHT) and `governance` (DNA 4, public
     HarmonyRecords) are the only candidates. The **governance DHT** — permanent,
     immutable HarmonyRecords accumulating without bound — is the natural headline
     target for a scaling story.

2. **Sharding only *means* anything at scale.** With ~5 live nodes and a redundancy
   target R≈3, every node holds nearly everything regardless. The payoff (storage per
   node ≪ full replication) is only *visible* with a large node population — which is
   why the demonstrator lives in a controlled multi-node harness, not on the 5-node
   Oracle demo.

---

## The three tiers at a glance

| | **Tier A — kitsune2-only** | **Tier B — full stack** | **Tier C — clone-cell fan-out** |
|---|---|---|---|
| What runs | Forked kitsune2 + polite-shrink controller, loaded with ValiChord-shaped data | ValiChord `.happ` on a custom-built Holochain conductor using the kitsune2 fork | ValiChord `.happ` on **stock, unforked** Holochain 0.6.x — records partitioned across many small clone-cell DHTs |
| Runs Holochain validation? | **No** (storage/gossip layer only) | Yes | **Yes** (stock `validate()`, nothing special) |
| Touches the hard blocker (validation under partial arcs)? | **No — sidesteps it entirely** | **Yes — blocked on it** | **No — sidesteps it entirely, differently** (no partial arcs at all; full replication within each small clone) |
| How much already exists | ~80% (the arc-sim + Wind-Tunnel campaign) | ~0% | ~0% built, but every primitive it needs (clone cells, `schedule()`) already ships in stock HDK |
| New engineering | The sim→real `AgentInfo` shrink-claim port | Custom conductor build **+** validation-under-sharding (not ours to solve) | Shard-assignment policy, a discovery/routing layer, and a scheduled health-check/re-replicate loop |
| Honest claim it supports | "ValiChord's record DHT shards safely on a real runtime" | "Sharded ValiChord you could put real attestations on" | "ValiChord's record DHT can shard *today*, on stock Holochain, with an explicit redundancy floor — no fork, no wait for 0.7" |
| Recommendation | **The demonstrator to build if/when we build one** | Do not aim here yet | **The cheapest possible cut — but check the DNA 4 fit below before picking it over Tier A** |

---

## Tier A — the kitsune2-only demonstrator (recommended)

### Goal
Run the forked kitsune2 with the polite-shrink controller as a standalone network,
loaded with **governance-DHT-shaped data**, and show: nodes shrink their arcs from
full to a slice, the redundancy floor R is never breached, and **zero records are
lost** under node churn — while **storage per node drops well below full replication**.

### Why this is the smart cut
kitsune2 alone is only the storage + gossip layer; it does **not** run Holochain's
`validate()` callbacks. So this demonstrator **never touches the one genuinely hard,
not-ours-to-solve problem** — validation-safe partial arcs (Blocker 3 below). It
isolates the single novel contribution (a *safe shrink* controller) and shows it on
ValiChord's real data shape. That is the honest, defensible thing to demonstrate.

### What already exists (do not rebuild)
Per the arc-sim / Wind-Tunnel campaign (`research/dht-arc-sharding-sim`,
`ValiChord/polite-shrink`):
- **The polite-shrink controller + safety invariant**, proven in the arc-sim harness
  (V3 polite-shrink 0/1248 failure sweep; data-loss flat to 90% message drop).
- **A TLA+ proof of the gate** (the ~15-line "never shrink below R" decision — note the
  proof covers the *gate*, not the *policy* that picks a target arc).
- **A live run on real kitsune2 transport** under Wind-Tunnel: settle / storm /
  timed-storm all passed, zero orphans, zero op loss across 23k+ ops; the storm brake
  fired for real (9 stale-view intents cancelled); a liveness bug that *only* real
  transport could surface was found and fixed. PR `kitsune2#572` is open upstream.

### The genuinely new piece (the only real engineering)
Drive the shrink claim through kitsune2's **existing `AgentInfo` gossip**, not a
bespoke `Msg::ShrinkIntent` broadcast. This is Paul d'Aoust's critique made concrete:
kitsune2 *already* advertises each agent's storage arc in `AgentInfo`, so a separate
shrink-intent message is overreach and double-counts. The real controller must read
and update the arc claim in `AgentInfo`. (Context: the stock kitsune2 controller in
`storage_arc.rs` exists but is **expand-only**; the shrink direction + safety rule are
the open gap — the word "shrink" appears nowhere in it. kitsune2 also carries **no
policy** — only an empty host-supplied hint slot — which is where polite-shrink slots
in.)

### Concrete steps (when built)
1. **Data shape.** Model the governance DHT: a population of HarmonyRecord-sized,
   immutable, `ExternalHash`-keyed ops spread across the keyspace (target ~10k records).
2. **Network.** 20–50 forked kitsune2 nodes on one bootstrap; redundancy target R = 3–5
   (well below node count, so partial arcs are meaningful). *(Prerequisite to confirm:
   whether the run needs a separate Iroh relay — see the watch item on
   `fix/491-stabilize-the-iroh-relay-hosted-in-bootstrap_srv`, which may fold the relay
   into `kitsune2-bootstrap-srv`.)*
3. **Controller in the loop.** Nodes start full-arc; polite-shrink drives them toward
   target coverage via the `AgentInfo` arc claim, enforcing "no keyspace slice drops
   below R holders."
4. **Measure** (reuse the Wind-Tunnel harness):
   - every record still retrievable network-wide after shrink (**zero loss**);
   - kill/restart nodes (churn) → R holds, data survives;
   - **storage-per-node falls well below full replication** — the headline payoff;
   - the safety invariant is never violated across the whole run.

### Deliverable / the claim it earns
> *"ValiChord's permanent-record DHT, sharded: N nodes, each holding ~1/k of records,
> zero loss under churn, redundancy floor never breached — on a real kitsune2 runtime."*

### Honest caveats (must ship with the demo)
- It runs the **storage/gossip layer with ValiChord's data shape**, not ValiChord's
  zomes or validation. It demonstrates safe sharding of the *data*, not the full app.
- It is a forked stack: these nodes interoperate only with each other, not stock
  Holochain (`HCP2P_PROTO_VER` divergence).

### Rough effort
**Small-to-moderate** — an *increment* on existing work, not a new build. The delta is:
(a) parameterise the existing run with governance-DHT data sizes, (b) add the
storage-per-node measurement, (c) implement + verify the `AgentInfo` shrink claim,
(d) frame and write up. The `AgentInfo` port is the item with real unknowns.

---

## Tier B — the full stack (real, but blocked)

### Goal
ValiChord's actual `.happ` running on a Holochain conductor that shards — the thing you
could put real attestations on.

### What it needs
1. **A custom Holochain conductor built from source**, with the kitsune2 fork
   Cargo-`patch`ed in. kitsune2 is compiled *into* the conductor binary — there is no
   runtime swap or config flag. This is a from-source build of a large Rust workspace,
   kept in sync with our pinned Holochain line, maintained indefinitely.
2. **Validation safe under partial arcs** — see Blocker 3. This is the wall.

### Why not now
When a node holds only a slice, its `validate()` dependencies (`must_get_*`) may sit
*outside* its arc, and authority for each op's basis must stay collectively covered
above R. Making Holochain's **validation + data model** correct under partial arcs is
**platform-level work that Holochain itself is doing in 0.7** — it is precisely why
kitsune2 #160 (the redundancy-target-arc controller) stayed open and why safe
arc-resizing was put on the back burner rather than shipped. It is not ours to
shortcut from the app or the fork alone. Tier B should wait until that platform piece
lands (track it through the 0.7 migration).

---

## Tier C — the clone-cell fan-out demonstrator (Volla Recovery pattern)

### Where this comes from
At Volla Community Days 2026 (Remscheid, 13–14 June), the "Volla Cloud for app
developers" workshop (Davide Garberi, Amirhossein Esmaeilipour) and Dr. Jörg Wurzer's
keynote described how **Volla Recovery** — a Holochain-based distributed-backup hApp —
gets storage-per-node well below full replication *without* kitsune2 arc-resizing.
Asked directly about it, Wurzer said: *"the Holochain Foundation has sharding on its
roadmap, but it's not implemented yet, so we had to find our own solution."* Backups
are split into chunks, each chunk stored on only 2–3 of the user's chosen hosts;
scheduled health checks detect a dropped host and quietly re-replicate that host's
chunks elsewhere. (Reported by Sam Turner, hAppenings newsletter, 2026-07-24; workshop
slide deck: `VCD26_Volla_Messages_Tauri_Workshop.pdf`, volla.online.)

### The mechanism (confirmed against source — `github.com/HelloVolla/VollaRecovery`, `crates/dnas/recovery/`)
Volla's Recovery hApp is public. `crates/dnas/recovery/workdir/dna.yaml` defines **one
DNA** (`volla_recovery`) with three integrity/coordinator zome pairs — `membrane`,
`registry`, `storage` — and the actual mechanism is exactly the clone-cell fan-out
guessed above, now confirmed field-by-field:

- **`registry` zome = your own private circle, one DHT per progenitor.** `RegistryMember`
  entries (your invited friends) plus `MemberStatusEntry` (`Invited`/`Active`) track who
  you trust. A `StorageBundle { network_seed, progenitor, network_pub_key, dna_hash }`
  entry (`registry/src/storage_bundle.rs`, `register_storage_bundle`) is created for
  each backup chunk-group, and its `network_seed` is a literal Holochain **clone-cell**
  network seed — `get_storage_bundle_by_network_seed` looks bundles up by it.
- **`storage` zome = the per-bundle clone.** `invite_agent_to_bundle`
  (`registry/src/bundle_member.rs`) writes a `BundleMember { agent, network_seed, status }`
  entry and fires `send_remote_signal(Signal::InviteAgentToBundle { network_seed, .. })`
  straight at the invited host — the doc comment says it plainly: *"Notify the invited
  agent directly so their device can clone the bundle cell."* The host's own
  `get_my_assigned_bundles()` (`registry/src/sync.rs`) — *"used by host agents to
  discover which bundles they need to clone"* — is how they find out what to join, and
  `mark_bundle_as_cloned` flips their status `Invited → Active` once they've actually
  cloned the `storage` DNA with that network seed. Inside that clone, a `StorageEntry`
  (`storage/src/storage_entry.rs`) holds `chunk_hashes: Vec<EntryHash>` pointing at
  `Chunk(SerializedBytes)` entries (`storage/src/chunk.rs`) — replicated only among that
  bundle's small membership, exactly as Tier C originally guessed.
- **Liveness check exists at the registry level, not (found) at the storage level.**
  `ping_registry_agent` / `is_peer_online` / `get_online_registry_members`
  (`registry/src/registry_member.rs`) do agent-to-agent `call_remote` pings. What was
  **not** found in the zome source: a scheduled re-replication function that reassigns a
  dead host's chunks to a fresh one. It may live client-side (Kotlin,
  `JoinStorageBundlesWorker.kt`, not inspected) or may not exist yet — the repo is
  pre-1.0 (5 open issues, public beta only from June 2026). Treat "health-check-driven
  re-replication" as the article's characterisation of the intended behaviour, not a
  verified zome-level guarantee.
- **The redundancy count (2–3 hosts per chunk) is a client-side policy choice, not an
  integrity-zome invariant.** `invite_agent_to_bundle` will happily invite any number of
  agents to a bundle — nothing in `storage_bundle.rs` or the integrity zome enforces a
  minimum. The "never below R" guarantee, if it exists, is enforced by whoever calls the
  coordinator functions (the Kotlin app), not by `validate()`.

This is architecturally a completely different move from Tier A/B. Tier A and B both
try to make **one shared DHT** sharding-safe (an arc-resizing problem, which is why
they need kitsune2 and eventually Holochain's own 0.7 validation-under-partial-arcs
work). Tier C never has one shared DHT to shard — it has **one small private registry
DHT plus many small, fully-replicated storage-bundle clones**, and gets the
storage-per-node payoff from partition count instead of arc size.

### What ValiChord already has that this reuses
- Clone cells and `schedule()` are both already-documented stock HDK features (see
  `docs/Holochain_complete.md` §26–27) — no new host functions, no fork, no custom
  conductor build.
- The "no per-shard redundancy guarantee" gap this closes was already flagged
  independently in the nondominium recon (`memory/project_nondominium_recon_2026-07-08.md`):
  clone-cell fan-out alone gives no redundancy invariant per shard. A Volla-style
  scheduled health-check loop is exactly the missing piece.

### Concrete steps (when built)
1. Partition the governance-DHT record population (per the Tier A data-shape plan
   above) into buckets; each bucket becomes one clone cell of the `governance` DNA.
2. Assign each clone a small membership (R = 3–5 nodes) drawn from the wider node pool
   — a bucket owner or deterministic hash-of-bucket-id → node assignment, not a live
   arc claim.
3. `check_and_create_harmony_record` (or an index-writer role) targets the correct
   clone for a given record via the discovery layer (see caveat below).
4. A scheduled health-check function per clone detects a dead member and reassigns +
   re-gossips its share of that clone's data to a replacement node.
5. Measure the same things as Tier A: zero loss under churn, redundancy floor held,
   storage-per-node well below full replication.

### Honest caveats (must ship with the demo)
- **This does not fit DNA 4's actual requirement well — now confirmed by Volla's own
  design, not just predicted.** `governance` is deliberately open-read so journals,
  funders, and the public can verify any `HarmonyRecord` without running a node or
  knowing anyone. Volla's `registry` DHT is exactly the "fully replicated index" this
  section predicted — but it's scoped to *your own private circle*, not open to the
  public, and that's precisely why it's a non-problem for them: every reader of the
  registry is already a trusted, invited member. A public verifier of DNA 4 has no
  equivalent standing. This caveat does not exist for Tier A, where all data stays in
  one DHT that anyone can read from.
- **The redundancy floor is a client-side policy choice, not a proven gate — confirmed,
  not just suspected.** Nothing in `storage_bundle.rs` or the integrity zome enforces a
  minimum host count per bundle; `invite_agent_to_bundle` accepts any number of
  invitations. Tier A's polite-shrink comes with a 0/1248-failure sweep and a TLA+ proof
  of its shrink gate. Tier C (both Volla's real version and a ValiChord port) would have
  no equivalent verification unless one were added deliberately.
- **The health-check/re-replication loop does not appear to exist yet, checked on both
  sides.** The registry zome has liveness pings (`ping_registry_agent`,
  `is_peer_online`) but no scheduled reassignment-on-dead-host logic. On the Kotlin
  side, all three background workers were checked: `JoinStorageBundlesWorker` (30 s
  poll; joins bundles you've been invited to but haven't cloned — onboarding, not
  repair), `PeriodicBackupWorker` (weekly, calls `BackupOrchestrator.executeBackup()` —
  decides *what* to back up: apps/photos/docs, not *where*), and `BackupOrchestrator`
  itself (no host-liveness or reassignment logic). None of them detect a dropped host
  and move its chunks. Treat "re-replicates when a host drops" as the article's account
  of *intended* behaviour, not something this repo currently does. A ValiChord port
  would need to build this piece for real, most naturally as a `schedule()`-driven
  coordinator function — Volla not having shipped one yet isn't evidence it's hard, just
  evidence the repo is pre-1.0 and this piece hasn't landed.
- **Requires an always-on health-checker for the piece that *is* built.** Fine for the
  Oracle-style always-on demo nodes; a poor fit for a consumer node that goes offline
  unpredictably (the same constraint Volla accepts for Recovery, where hosts are
  "friends' devices," not guaranteed-online infrastructure).

### Rough effort
**Smallest of the three tiers, and now de-risked by a real precedent.** No fork, no
custom conductor, no sim-to-real port — just zome logic (shard assignment via
`StorageBundle`-style catalog entries, a discovery index, and — the one piece Volla's
own source doesn't appear to have finished — a real health-check/re-replicate schedule)
on top of primitives ValiChord's stack already uses elsewhere (clone cells are
documented but not yet used anywhere in the four DNAs; `schedule()` is unused). The
discovery-layer design is still the piece that determines whether this tier is honestly
claimable for DNA 4 at all — Volla's own answer (a private, non-public index) confirms
it isn't, for that DNA, without further work.

---

## Shared blockers (reference)

Ordered easiest → most fundamental. Tier A clears 1–2 and **deliberately avoids 3**;
Tier B faces all five; Tier C avoids 1–3 entirely (it never touches kitsune2 or a
network-layer controller) but picks up a blocker of its own — see its honest caveats
above, especially the DNA 4 open-read mismatch.

1. **kitsune2 isn't runtime-swappable** — it's compiled into the conductor; Tier B needs
   a from-source custom conductor. *(Tier A runs kitsune2 directly, so N/A. Tier C never
   touches kitsune2, so N/A.)*
2. **Controller lives in a simulator, not the real runtime** — the sim→real port, with
   the `AgentInfo` mechanism question. *(Tier A's one real task. N/A for Tier C — its
   "controller" is an ordinary scheduled zome function, not a kitsune2-level component.)*
3. **Validation under partial arcs** — the deep one; Holochain's 0.7 job. *(Tier A
   sidesteps by not running validation; Tier B is blocked on it; Tier C sidesteps it too,
   but differently — it never creates a partial arc in the first place.)*
4. **Scale needed to demonstrate** — sharding only pays off at many nodes; all three
   tiers need a node population well beyond the 5-node Oracle demo to show the payoff.
5. **Fork isolation** — a forked kitsune2 interoperates only with itself
   (`HCP2P_PROTO_VER`); a permanent maintenance fork until/unless it lands upstream.
   *(N/A for Tier C — nothing is forked.)*
6. **Public verifiability** — Tier C only. A public reader of DNA 4 has no way to know
   which clone holds a given record without either a fully-replicated index (undermining
   the storage saving) or a new indirection layer. Tiers A and B don't have this problem
   because they keep one DHT that anyone can read directly.

---

## Recommendation & open questions

**Recommendation:** if we ever build a demonstrator, build **Tier A**. It is mostly done,
it isolates our actual contribution (safe shrink on ValiChord data), and it makes an
honest claim without pretending the full stack exists. Treat Tier B as gated on
Holochain's 0.7 validation-under-sharding work.

**Tier C is the one to reconsider this recommendation for** — it is cheaper than Tier A
by a wide margin (no fork, no sim-to-real port, ships on the stock conductor we already
run) and makes an honest, present-tense claim ("shards today, no waiting on 0.7"). It
loses to Tier A on exactly one axis: DNA 4 needs open, permissionless verifiability, and
Tier C's small-membership clones don't give a stranger an obvious way to find the right
shard. If a demonstrator's target were a bounded-membership DNA instead of the public
governance ledger — closer to DNA 3's credentialed attestation DHT — Tier C's fit
would be much stronger, since every reader is already a known, credentialed participant.
That reframing (pick the DNA to fit the tier, not the other way round) is worth
deciding explicitly before any build, not defaulting into.

**Open questions to resolve before any build:**
- Does the multi-node kitsune2 run still require a separate Iroh relay, or has the
  bootstrap-hosted relay landed? (Watch `fix/491-…bootstrap_srv`.)
- Exact `AgentInfo` arc-claim read/update path in the fork — is the field already
  writable by the host controller, or does the fork need to expose it?
- Realistic governance-DHT parameters: record size distribution, target population, and
  a defensible R for a "permanent public record" workload.
- Strategic: is the deliverable a **ValiChord demo asset**, an **upstream contribution**
  (extending the #572 line), or **both**? That changes framing and where it's published.
- Tier C's discovery layer: is there a design where a public reader can find the right
  clone without a fully-replicated index? (E.g. a deterministic hash-of-record-id →
  clone-id mapping, so "which clone" is computable rather than looked up — worth
  spiking before ruling Tier C out for DNA 4 entirely. Volla's own answer — a private,
  invite-only registry DHT — doesn't transfer to a public ledger, so this is still open.)
- The health-check/re-replication-on-dead-host piece appears genuinely unbuilt in
  Volla's current repo (checked: registry zome, `JoinStorageBundlesWorker`,
  `PeriodicBackupWorker`, `BackupOrchestrator` — none of them do it). A ValiChord Tier C
  build should plan to write this from scratch rather than port it, and it's worth a
  periodic re-check of the Volla repo in case they ship it first (their production need
  for it is more pressing than ours).
