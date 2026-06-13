# ValiChord Wind-Tunnel scenarios

Performance / load-testing scenarios for ValiChord, built on
[holochain/wind-tunnel](https://github.com/holochain/wind-tunnel)
(`holochain_wind_tunnel_runner` **0.7.0**, targeting Holochain 0.6.1 / Kitsune2 0.4.1).

A scenario applies user-defined load with N agents and reports metrics. Each
agent is one thread of execution that repeatedly runs a *behaviour*. Wind-Tunnel
auto-captures per-`call_zome` latency; scenarios add their own custom metrics on
top.

> **This is a separate Cargo workspace** — intentionally *not* a member of
> `valichord/Cargo.toml`. The runner pulls in `holochain` (the native
> conductor), which cannot compile to `wasm32-unknown-unknown` and would break
> the main WASM build. Same isolation pattern as `sweettest_integration/`.

---

## Prerequisites

**All Holochain scenarios** need the packed hApp. Build the WASMs and pack first:

```bash
cd /workspaces/ValiChord/valichord
cargo build --target wasm32-unknown-unknown --release
hc dna pack dnas/attestation           -o workdir/attestation.dna
hc dna pack dnas/researcher_repository -o workdir/researcher_repository.dna
hc dna pack dnas/validator_workspace   -o workdir/validator_workspace.dna
hc dna pack dnas/governance            -o workdir/governance.dna
hc app pack . -o workdir/valichord.happ
```

Override the hApp path with `VALICHORD_HAPP_PATH=/path/to/valichord.happ`.

Always kill stale conductors before a run:

```bash
pkill -f holochain; pkill -f lair-keystore; sleep 2
```

**The Kitsune scenario** (`kitsune_dht_propagation`) does **not** use the hApp.
It needs a running Kitsune2 **bootstrap server** *and* an **Iroh relay server**
instead (see its section below).

---

## Running — required environment (runner 0.7.0)

Two things the scenario args alone don't cover:

- **`WT_METRICS_DIR` must be set** (a writable dir for conductor telemetry) or
  every agent panics at startup — this is new in runner 0.7.0.
- **Custom scenario metrics** (`sync_lag`, `sent_count`, `recv_count`, …) are
  only written when you pass **`--reporter=influx-file`**. They land in
  `$WT_METRICS_DIR/<scenario>-<timestamp>.influx`, each prefixed
  `wt.custom.<name>` (e.g. `wt.custom.sync_lag`). Without the flag you still get
  the printed "Summary of operations" (per-call latencies) but not the custom
  metrics.

```bash
export WT_METRICS_DIR=/tmp/wt_metrics && mkdir -p "$WT_METRICS_DIR"
# …then any command below, adding --reporter=influx-file to capture wt.custom.* metrics
```

The credential-gated attestation DNA is installed with a **dev-mode
membrane-proof bypass** automatically — the shared `valichord_wt_common` crate
ports the bypass from valichord-ui's `dev-setup.mjs` (empty issuer + 64×0x42
proof) and installs against the `attestation` role. No manual step.

### CI vs local

CI (`.github/workflows/wind-tunnel-smoke.yml`) **builds all scenarios + runs the
unit tests** — a deterministic check that catches compile / dependency /
install-path regressions. It does **not** run a live scenario: a live
multi-conductor run was tried in CI twice and both failed for environment (not
code) reasons on a standard 2-core/7 GB GitHub runner — the per-agent conductors
either couldn't peer (the 0.7.0 runner uses the default public bootstrap, no
local-bootstrap knob) or couldn't all start before a setup timeout. **Live runs
are a local / well-resourced-machine activity** (they work — see the dht_sync_lag
result below); CI gates on build + unit tests only.

---

## Scenarios

There are five scenarios. The first three measure **protocol throughput /
latency**; the last two form a propagation-latency ladder, from the raw network
substrate up to a real ValiChord entry crossing between agents.

### Protocol throughput & latency

| Scenario | Measures | Default run | Key metrics |
|---|---|---|---|
| `validation_request_throughput` | Concurrent commit-phase write throughput — each agent loops `submit_validation_request` + `notify_commitment_sealed` | `--agents 4 --duration 60` | `commits_sent` |
| `phase_observation_latency` | Time from a `CommitmentAnchor` write to the `PhaseMarker(RevealOpen)` becoming observable (single agent; `num_validators_required=1`) | `--agents 2 --duration 60` | `phase_observation_ms`, `poll_count`, `phase_timeout_count` |
| `concurrent_reveal_throughput` | Full commit→reveal round under N-agent concurrent load (exercises `ChainTopOrdering::Relaxed` over 3 back-to-back source-chain writes) | `--agents 4 --duration 90` | `round_total_ms`, `reveal_count`, `reveal_timeout_count` |

```bash
cargo run -p validation_request_throughput -- --agents 4 --duration 60
cargo run -p phase_observation_latency     -- --agents 2 --duration 60
cargo run -p concurrent_reveal_throughput  -- --agents 4 --duration 90
```

### Propagation-latency ladder

These answer the question the `DepMissingFromDht` "transient gossip lag" noise
raises: *how fast is propagation, and is the cost in the network or in our DNA
logic?* Reading down the ladder isolates each layer.

#### `dht_sync_lag` — ValiChord cross-agent entry propagation

How long after a `write` agent authors a `ValidationRequest` does it become
visible to `record_lag` reader agents. Readers discover requests with no prior
knowledge via the global pending anchor (`get_pending_request_refs`) and emit
`sync_lag = observed_time − the record's Action timestamp`.

**Zero DNA changes** — reuses existing zome functions and takes the send-time
from each record's built-in Action timestamp (no `created_at` field, no
integrity change, no DNA-hash change). Runs against the existing `valichord.happ`.

Run with one writer and N readers:

```bash
cargo run -p dht_sync_lag -- --agents 3 --duration 60 \
  --behaviour=write:1 --behaviour=record_lag:2 --reporter=influx-file
```

Key metrics: `sync_lag` (per request, seconds), `sent_count`, `recv_count`.
Single-host assumption: all agents share a wall clock, so `now − authored_at`
needs no clock-skew correction.

**Verified live (2026-06-12, 3 agents, 45s):** the writer submitted 288
requests; two readers on **separate conductors** observed them propagate
(287/288 and 232/288), recording 525 `sync_lag` samples — **median ≈ 185 ms**,
p90 ≈ 8.7 s (the gossip-under-load tail). This was the first live run of any
ValiChord wind-tunnel scenario; it's what surfaced the membrane-proof install
fix now shared across all four Holochain scenarios.

#### `kitsune_dht_propagation` — raw Kitsune2 substrate (prototype)

Benchmarks peer-to-peer message propagation at the Kitsune2 networking layer,
*beneath* ValiChord's DHT/DNA. Agents create an instrumented "chatter" instance,
join a shared network, and broadcast timestamped messages. Runs **no ValiChord
code** — it's the network baseline you subtract from `dht_sync_lag`.

Needs a Kitsune2 bootstrap server **and** an Iroh relay (the iroh/QUIC transport
uses the relay for NAT traversal / peer discovery). Confirm flags with `--help`:

```bash
cargo run -p kitsune_dht_propagation -- \
  --bootstrap-server-url http://127.0.0.1:30000 \
  --relay-url <iroh-relay-url> \
  --agents 2 --duration 30
```

`NUM_MESSAGES` (env, default 3) sets messages per interval.

> **Dependency pin — do not remove.** This scenario's transitive iroh stack
> pulls `ed25519-dalek 3.0.0-pre.1`, which only builds against the
> release-*candidate* `pkcs8`/`ed25519` crates (the final 0.11.0 / 3.0.0
> releases changed `pkcs8::Error::KeyMalformed` to a tuple variant and break the
> build). The exact RC versions are pinned in `kitsune_dht_propagation/Cargo.toml`
> (matching upstream's own lockfile). An unconstrained `cargo update` will try to
> undo this — if the Kitsune build breaks after a dep update, re-check those pins
> first. The Holochain scenarios are unaffected (they use `ed25519-dalek 2.x`).

---

## Reporters

Default output is human-readable. For machine-readable metrics, append a
reporter, e.g.:

```bash
cargo run -p concurrent_reveal_throughput -- --agents 8 --duration 120 --reporter=influx-file
```

---

## Adding a scenario

1. Create `scenarios/<name>/{Cargo.toml,src/main.rs}` (copy the closest existing
   scenario — `validation_request_throughput` for a Holochain write scenario,
   `dht_sync_lag` for a writer/reader split, `kitsune_dht_propagation` for a
   Kitsune substrate test).
2. Register it under `members` in `wind-tunnel/Cargo.toml`.
3. `cargo build -p <name>` to verify. Pure-logic helpers can have inline
   `#[cfg(test)]` unit tests (no conductor needed); live runs need the packed
   hApp + a conductor and are best left to CI / a beefy machine.
