# Testing ValiChord

ValiChord is tested at four layers. Every layer runs against real Holochain conductors — there are no mocked network or DHT interactions anywhere in the test stack.

| Layer | Suite | Tool | Count | What it proves |
| :--- | :--- | :--- | :--- | :--- |
| Unit | `valichord/shared_types` | `cargo test` | < 1 s, conductor-free | Pure outcome functions (`derive_majority_outcome`, `derive_agreement_level`) |
| Integration | `valichord/tests/` | Tryorama (TypeScript) | 97 (1 skipped) | Multi-conductor protocol flows over a real peer-to-peer network |
| Integration | `valichord/sweettest_integration/` | Sweettest (Rust, native conductor) | 80 | Zome logic, validation rules, cross-DNA calls, badge issuance |
| Browser E2E | `valichord-ui/tests/e2e/` | Playwright + real conductor | 6 | The real Svelte UI driving real zome calls in a real browser |
| Performance | `valichord/wind-tunnel/` | Wind-Tunnel (Rust) | 5 scenarios | Throughput, DHT propagation latency, load behaviour |

**Totals: 183 automated tests (182 passing, 1 Tryorama test skipped for Codespace RAM — its sweettest equivalent passes). All suites run in CI on every push and PR.**

> **ValiChord has been demonstrated running as a real multi-node network.** Integration tests launch up to 7 independent Holochain conductors — each with its own agent identity, source chain, and DHT participation — executing the full blind commit-reveal protocol and producing a Harmony Record on a shared live DHT. This is not a simulation: each conductor is an independent process with separate state, communicating over a real peer-to-peer network. The constraint is infrastructure RAM, not architecture.

---

## Running the suites

Build and pack the hApp first (see the [README Quickstart](README.md#-quickstart--clone-to-passing-tests)), then:

```bash
# Unit — pure outcome functions, < 1 s
cargo test -p valichord_shared_types                  # from valichord/

# Tryorama integration (97 tests)
cd valichord/tests && npm install && npm test

# Sweettest (80 tests; separate Cargo workspace — native conductor deps)
cd valichord/sweettest_integration
cargo test --test attestation
cargo test --test governance
cargo test --test researcher_repository
cargo test --test validator_workspace
cargo test --test security

# Browser e2e (6 tests, ~1.5 min; needs the packed hApp + chromium)
cd valichord-ui && npm install
npx playwright install --with-deps chromium           # one-time
npm run test:e2e

# Wind-Tunnel performance scenarios
cd valichord/wind-tunnel
cargo run -p validation_request_throughput -- --agents 4 --duration 60
```

Before any conductor-based run, kill stale conductors: `pkill -f holochain; pkill -f lair-keystore; sleep 2`.

In CI (`.github/workflows/tests.yml`): the Tryorama suite and the browser e2e job run on every push/PR, and the sweettest suite runs as five parallel matrix jobs (one per test binary). The e2e job needs no Rust toolchain — it uses the committed `valichord/workdir/valichord.happ` — and reports in ~2 minutes.

---

## Coverage inventory

### Commit-reveal protocol

- Full blind commit-reveal protocol end-to-end across all four DNAs
- Cross-DNA post_commit chain: DNA 2 seal (generates nonce + SHA-256 commitment_hash) → DNA 3 notify (CommitmentAnchor carries hash) → phase open
- Full symmetric commit-reveal: researcher `lock_researcher_result` (DNA 1) → `publish_researcher_commitment` (DNA 3 hash only) → `reveal_researcher_result` (DNA 3, hash-verified) → `ResearcherReveal` on DHT for comparison against validator outputs
- On-chain enforcement proven by test: a real-nonce reveal passes hash verification, and a verdict altered between sealing and reveal is rejected with a hash mismatch (security sweettests S7/S8, added v0.6.0)
- DHT-poll-driven phase transitions (CommitmentAnchor → PhaseMarker)
- Commit phase state detection — `check_all_commitments_sealed` verified at partial and full threshold
- Mixed outcome HarmonyRecord assembly — Divergent agreement level from split validator results

### Identity, membrane, and privacy

- Real Ed25519 membrane proof verification — issuer-signed proofs accepted, forged signatures rejected at coordinator init
- Privacy across agents — private attestations are not readable by peers
- Author key enforcement on GovernanceDecision (HarmonyRecord/Badge/Reputation open to any participant — fully decentralised)

### Immutability

- Immutability enforcement on ValidationAttestation, CommitmentAnchor, PhaseMarker, ResearcherResultCommitment, ResearcherReveal, PreRegisteredProtocol, and StudyClaim (v0.6.0)
- Delete-immutability at API level — no delete functions exposed for HarmonyRecord, GovernanceDecision, or ReproducibilityBadge

### Study lifecycle

- Validator self-assignment (`StudyClaim`) — validators claim studies from the queue via `claim_study(request_ref)`; coordinator enforces capacity and duplicate checks; integrity zome's `validate()` enforces conflict-of-interest (same institution as researcher → rejected); `release_claim` frees the slot while preserving the audit record
- Dropout recovery — `reclaim_abandoned_claim` frees a slot held by a validator who has gone dark (any participant, after configurable timeout); `force_finalize_round` closes a stuck round after 7 days subject to `min_attestations_for_finalization` (governance DNA property — set equal to panel size for ≤4-validator panels, one lower for larger panels), producing a normal HarmonyRecord identifiable as reduced-quorum by validator count
- Deliberate abstention (v0.6.0) — a validator can record a reasoned recusal as a first-class immutable private entry, distinct from simply never showing up
- Reproducibility badge issuance (Gold/Silver/Bronze/Failed thresholds), including the 7-validator GoldReproducible round

### Indexes and discovery

- Validator discovery by discipline via real path index
- `InstitutionPath` index — validators indexed by institution for conflict-of-interest detection (`get_validators_for_institution`)
- `DisciplinePath` attestation index — attestations indexed by discipline for cross-study analytics (`get_attestations_for_discipline`)
- BadgePath cross-study analytics index — written at badge issuance, queryable by type via `get_badges_by_type`
- Difficulty assessment storage and retrieval via DifficultyPath link index
- `get_validation_request_for_data_hash` — resolves ValidationRequest from study path anchor by data hash
- Source-chain list queries (`get_all_studies`, `get_all_tasks`, `get_all_private_attestations`) using type-safe deserialization filter — no hardcoded ZomeIndex
- Governance decision creation, multi-record listing, and author enforcement

### Security guards

- Duplicate attestation rejection, duplicate commitment rejection, researcher commitment idempotency
- Reclaim timeout floor enforcement; `force_finalize_round` conservative abort
- Self-claim prevention (researcher cannot validate own study — no dev bypass)
- Researcher reveal authorisation
- PhaseMarker write idempotency (TOCTOU-safe)
- Deterministic link resolution (all `links.last()` → `max_by_key(timestamp)`)
- O(N) DHT round-trip elimination in claim functions

### Browser E2E (valichord-ui)

- Playwright drives the real Svelte UI against a live conductor (no mocks): connection bootstrap via URL-hash injection (the Holochain Launcher channel), validator profile creation through the UI form, validation request submission through the researcher form, pending-request rendering, zome-seeded data rendering, governance view
- One throwaway conductor per run (`tests/e2e/setup/conductor-manager.ts`), installed with the dev-mode membrane-proof bypass; hybrid seeding via a Node-side AppWebsocket client
- Caught a real production bug on its first run: a Svelte-mangled `pattern` attribute silently blocked every form submission

### Performance (Wind-Tunnel)

- `validation_request_throughput` — CommitmentAnchor write throughput
- `phase_observation_latency` — commit → RevealOpen DHT lag
- `concurrent_reveal_throughput` — full round under N-agent load
- `dht_sync_lag` — cross-agent entry propagation (live 3-conductor run: median ≈ 185 ms)
- `kitsune_dht_propagation` — raw Kitsune2 substrate baseline (prototype)
- Separate Cargo workspace (same isolation pattern as sweettest); live multi-conductor runs are a local/well-resourced-machine activity — CI gates on compile + unit tests (see `valichord/wind-tunnel/README.md`)
