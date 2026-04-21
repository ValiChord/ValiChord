# ValiChord Decentralised Demo — 4 Isolated Conductors
### Technical guide for developers

---

## What this demo is

A fully automated, end-to-end run of the ValiChord commit-reveal protocol across **four completely isolated Holochain conductors** — one researcher and three validators — plus a separate kitsune2 bootstrap/DHT server, all running in separate Docker containers with no shared memory and no shared filesystem.

**This is the closest a single-machine setup can get to a real multi-party deployment.** Each container generates its own keypair at startup, writes to its own SQLite conductor database, and communicates with the others exclusively through the DHT — exactly as researcher and validators would on separate machines in production.

What happens when you run it:

- A **real piece of mathematics** is computed: ordinary least-squares linear regression on 20 data points, implemented from scratch in pure Python. The results are deterministic — any independent party running the same script on the same data gets the same numbers to 4 decimal places.
- The **researcher seals a cryptographic commitment** to those results before any validator has seen them. Only the hash leaves their private DNA. They cannot change their claimed values from this point forward.
- **Three independent Claude AI agents** each read the study README and the actual execution output and form their own reproducibility verdict — without seeing each other's. Three separate API calls; three separate judgements.
- All three validators **commit their verdicts blind** to the shared Holochain DHT. The content stays hidden; only the commitment hash is visible.
- A **phase gate** on the Holochain network opens automatically when all three commitment anchors are confirmed — no manual trigger, no trusted coordinator.
- **Both sides reveal, both cryptographically verified.** The researcher's `reveal_researcher_result` recomputes `SHA-256(msgpack(metrics) || nonce)` and checks it against the hash committed at submission. Each validator's `submit_attestation` recomputes `SHA-256(msgpack(attestation) || nonce)` and verifies it against the `CommitmentAnchor.commitment_hash` written at seal time.
- A **HarmonyRecord** is written to the public Governance DHT by one of the validators. It is immediately readable via the researcher node's HTTP API.

---

## What this demo proves — beyond the Oracle demo

The [Oracle demo](AI_VALIDATOR_DEMO.md) runs the same protocol on a single conductor where researcher and all three validators share the same Holochain process. The decentralised demo proves the same protocol works when:

- **Conductors are genuinely isolated** — separate processes, separate keystores, separate databases. Each validator's private attestation cannot be read by any other process.
- **DHT gossip is the only communication channel** — there is no shared memory, no shared socket, no common broker. Data written by the researcher's conductor reaches validators only through the kitsune2 DHT network.
- **Gossip propagation lag is real** — data written by one conductor takes seconds to gossip to others. The implementation handles this gracefully with retry loops at every protocol gate.
- **The HarmonyRecord is created by a participating validator** — not a coordinator process, not a privileged key. Any validator in the round can finalise it.

---

## What "reproduced" means

ValiChord asks: *can an independent party arrive at the same result as the researcher?*

"Reproduced" means the validator got the **same result as the researcher** — not that the result is correct. A study can be reproducible and scientifically wrong. A study can be correct but not reproducible. ValiChord only answers the reproducibility question.

---

## Architecture

```
docker-compose.yml
    │
    ├─ bootstrap  (port 9000)
    │   kitsune2-bootstrap-srv — peer discovery + WebRTC SBD signalling
    │   No DHT participation; no access to entry content
    │
    ├─ researcher (port 3001 on host)
    │   Holochain conductor + researcher.happ (DNAs 1, 3, 4)
    │   researcher-node.mjs — HTTP API:
    │     POST /lock-result, POST /submit-request
    │     POST /reveal, GET /phase, GET /record
    │
    ├─ validator-1 (port 3002 on host)
    ├─ validator-2 (port 3003 on host)
    └─ validator-3 (port 3004 on host)
        Each: Holochain conductor + validator.happ (DNAs 2, 3, 4)
              validator-node.mjs — HTTP API:
                POST /commit, POST /reveal
                POST /create-harmony-record

ai_validator.py --mode decentralised
    │
    ├─ [1/7] Load synthetic study, compute ExternalHash
    ├─ [2/7] Execute study.py → 3 MetricResult objects
    ├─ [3/7] 3 independent Claude API calls → 3 verdicts
    │
    └─ [4/7] run_decentralised_protocol()
              │
              ├─ (0) POST researcher:3001/lock-result
              │       → lock_researcher_result (DNA 1)
              │       → publish_researcher_commitment (DNA 3, auto)
              │       → ResearcherResultCommitment on shared DHT
              │
              ├─ (1) POST researcher:3001/submit-request
              │       → submit_validation_request (DNA 3)
              │       → ValidationRequest on shared DHT
              │       + 20s gossip wait
              │
              ├─ (2) POST validator-1:3002/commit
              │       publish_validator_profile → claim_study (retry 12×5s)
              │       → receive_task → seal_private_attestation
              │       → post_commit → CommitmentAnchor on shared DHT
              │       + 30s gossip wait
              ├─ (3) POST validator-2:3003/commit  (same)
              │       + 30s gossip wait
              ├─ (4) POST validator-3:3004/commit  (same)
              │
              ├─ (5) Poll GET researcher:3001/phase?hash=…
              │       until PhaseMarker(RevealOpen) visible (up to 240s)
              │
              ├─ (6a) POST researcher:3001/reveal
              │        → reveal_researcher_result (DNA 3, SHA-256 verified)
              │        → ResearcherReveal on shared DHT
              │
              ├─ (6b) POST validator-1:3002/reveal
              │        → submit_attestation (DNA 3, SHA-256 verified)
              │        + 15s gossip wait
              │       POST validator-2:3003/reveal  (same)
              │       POST validator-3:3004/reveal  (same)
              │
              └─ (7) POST validator-1:3002/create-harmony-record
                      check_and_create_harmony_record (DNA 4, retry 12×5s)
                      → HarmonyRecord on public Governance DHT
```

---

## Requirements

- Docker and Docker Compose
- Python 3.9+
- An Anthropic API key (`claude-opus-4-6` or better)
- Linux x86_64 (the Holochain binary is downloaded automatically)

---

## Run it

```bash
git clone https://github.com/topeuph-ai/ValiChord.git
cd ValiChord

export ANTHROPIC_API_KEY=sk-ant-...

docker compose -f demo/docker-compose.yml up --build -d
```

The first build downloads the Holochain binary (~50 MB) and installs Node dependencies. Subsequent builds use the Docker cache and are fast.

Wait for all four conductors to start (takes ~30 seconds):

```bash
until [ "$(docker compose -f demo/docker-compose.yml logs 2>/dev/null | grep -c 'node API →')" -ge 4 ]; do sleep 3; done && echo "Ready"
```

Then run the demo:

```bash
python3 demo/ai_validator.py --mode decentralised
```

---

## Expected output

```
╔══════════════════════════════════════════════════════════╗
║    ValiChord AI Validator Demo — 3 Validators           ║
╚══════════════════════════════════════════════════════════╝
  Researcher + 3 independent Claude validators.
  Both sides commit-reveal symmetrically — neither can change
  their result after the other has committed.
  Mode: DECENTRALISED

[1/7] Loading study deposit…
────────────────────────────────────────────────────────────
  ZIP:       /tmp/…zip
  Run ID:    <uuid>
  Data hash: <sha256>…  (860 bytes)

[2/7] Executing study code…
────────────────────────────────────────────────────────────
  Output:
    Slope (coefficient): 2.4086
    Intercept:           1.1742
    R²:                  0.9991
  Elapsed: 0.04s

[3/7] Forming 3 independent verdicts via Claude…
────────────────────────────────────────────────────────────
  Calling Claude (validator 1/3)… Reproduced — High confidence
  Calling Claude (validator 2/3)… Reproduced — High confidence
  Calling Claude (validator 3/3)… Reproduced — High confidence

  Validator 1: Reproduced (High) — The actual output exactly matches the expected output.
  Validator 2: Reproduced (High) — All three metrics match the claimed values precisely.
  Validator 3: Reproduced (High) — The code reproduces the reported results exactly.

[4/7] Running decentralised commit-reveal protocol…
────────────────────────────────────────────────────────────
  Mode: DECENTRALISED — 4 separate conductors communicating via DHT
  Researcher : http://localhost:3001
  Validator 1: http://localhost:3002
  Validator 2: http://localhost:3003
  Validator 3: http://localhost:3004

  (0) Researcher locking result…
      Commitment sealed: uhCEk…
  (1) Submitting ValidationRequest (num_validators_required=3)…
  (1b) Waiting 20s for ValidationRequest to propagate via DHT…
  (2) Validator 1 committing blind…
  (3) Validator 2 committing blind…
  (4) Validator 3 committing blind…
  (5) Polling phase gate… RevealOpen (after N polls).
  (6a) Researcher revealing metrics (SHA-256 verified on-chain)…
  (6b) Validator 1 revealing attestation…
  (6b) Validator 2 revealing attestation…
  (6b) Validator 3 revealing attestation…
  (7)  Creating HarmonyRecord on Governance DHT…

[5/7] All commitments sealed and revealed.
────────────────────────────────────────────────────────────

[6/7] Researcher result verified + 3 validator attestations on DHT.
────────────────────────────────────────────────────────────

[7/7] Permanent record.
────────────────────────────────────────────────────────────
  Outcome:           Reproduced (3/3 validators)
  Agreement level:   ExactMatch
  Discipline:        ComputationalBiology
  HarmonyRecord:     uhCkk…
  Researcher reveal: uhCkk…

  Validator 1: Reproduced (High) — …
  Validator 2: Reproduced (High) — …
  Validator 3: Reproduced (High) — …

  Shareable URL:
  http://localhost:3001/record?hash=uhC8k…

  Verifying record is readable…
  Record confirmed. Outcome: Reproduced  Agreement: ExactMatch  Validators: 3

════════════════════════════════════════════════════════════
  Demo complete. The full ValiChord protocol ran end-to-end.
  Researcher and 3 validators all commit-revealed simultaneously.
════════════════════════════════════════════════════════════
```

Total wall time is approximately 4–5 minutes. The majority is DHT gossip wait time.

---

## Tear down

```bash
docker compose -f demo/docker-compose.yml down -v
```

The `-v` flag removes the named volumes (each conductor's keystore and DHT cache). Without it the next `up` reuses existing identities — which is valid for re-running the demo but can cause "ValidationRequest already exists" errors if the same data hash collides with a prior run.

---

## Infrastructure

| Component | Detail |
|---|---|
| bootstrap container | `kitsune2-bootstrap-srv` 0.3.2 — peer discovery (HTTP) + WebRTC SBD (WebSocket), port 9000, committed to `demo/bin/` |
| researcher container | Holochain 0.6.x, `researcher.happ` (DNAs 1 + 3 + 4), `researcher-node.mjs` bridge, port 3001 exposed on host |
| validator-{1,2,3} containers | Holochain 0.6.x, `validator.happ` (DNAs 2 + 3 + 4), `validator-node.mjs` bridge, ports 3002–3004 on host |
| Holochain binary | Auto-downloaded from GitHub Releases on first build if `demo/bin/holochain` absent |
| Network isolation | Docker bridge network `valichord`; containers reach each other by service name, not host network |
| DHT seed | `valichord-demo-decentralised` — all five conductors join the same network seed; data is visible to all five |

### Role-filtered happs (demo only — not the production model)

The demo uses two role-filtered `.happ` bundles:

| Bundle | DNAs included | Who runs it |
|---|---|---|
| `valichord/workdir/researcher.happ` | DNA 1 (Researcher Repository), DNA 3 (Attestation), DNA 4 (Governance) | researcher container |
| `valichord/workdir/validator.happ` | DNA 2 (Validator Workspace), DNA 3 (Attestation), DNA 4 (Governance) | validator containers |

**This is a demo optimisation, not a production pattern.** In production, every participant runs the full `valichord.happ` with all four DNAs — because the same person might submit a study this month and validate a completely different study next month. DNA 1 stores your research deposits; DNA 2 stores your validation work. You need both regardless of which role you're playing today.

The conflict-of-interest check is **per-study, not per-person**: `StudyClaim validate()` rejects the same agent as both submitter and claimant of the *same* `ValidationRequest`. It places no restriction on a person who submitted Study A validating Study B.

The role-filtered happs exist in the demo for two practical reasons: (1) each container saves ~30% memory on a single-machine Docker stack by not loading DNAs it will never use during the run; (2) they accurately model the demo scenario where those specific containers will never switch roles. They are not meant to imply that validators should be denied researcher capabilities in deployment.

---

## DHT propagation and retry design

The hardest engineering problem in this demo is DHT gossip propagation lag: data written by one conductor takes seconds (sometimes tens of seconds) to propagate to other conductors. The implementation handles this at every protocol gate:

| Gate | Mechanism | Maximum wait |
|---|---|---|
| ValidationRequest visible to validators | Explicit 20s sleep after `/submit-request` before any validator commits | 20s (fixed) |
| `claim_study` — ValidationRequest gossiped | 12-attempt retry loop, 5s apart in `validator-node.mjs` | 60s per validator |
| Phase gate (RevealOpen) | Python polls `GET /phase` every 2s | 240s |
| Validator CommitmentAnchors staggered | 30s sleep between validator commits | n/a |
| HarmonyRecord creation | 12-attempt retry loop, 5s apart in `validator-node.mjs` | 60s |
| `get_current_phase` gossip miss | `Ok(None)` return — caller retries | per-call |

The key insight: `get_current_phase` in Rust returns `Ok(None)` (not an error) when the PhaseMarker record body hasn't gossiped yet — even if the link to it has. This allows JavaScript callers to retry gracefully rather than receiving a 502.

Similarly, `claim_study` returns `Option<ActionHash>` — `None` when the ValidationRequest hasn't propagated yet. The JavaScript commit loop retries until it gets `Some(hash)`.

---

## Commit-reveal protocol — both sides

The protocol is symmetric across five isolated conductors. Neither the researcher nor any validator can change their result after the other has committed:

| Step | Who | What | Verified where |
|---|---|---|---|
| (0) Researcher locks | DNA 1 (researcher container) | `SHA-256(msgpack(metrics) || nonce)` sealed privately; hash only published to shared DHT via `publish_researcher_commitment` | On-chain at step (6a) |
| (1) Submit request | DNA 3 (researcher container) | `ValidationRequest` with `num_validators_required=3` | DHT validates entry integrity |
| (2–4) Validators commit | DNA 2 (each validator container) | Each seals verdict privately; `post_commit` → `CommitmentAnchor` on shared DHT | Hash recomputed at reveal |
| (5) Phase gate | DNA 3 (any conductor) | `PhaseMarker(RevealOpen)` written once all 3 `CommitmentAnchor` entries seen | Any conductor can verify |
| (6a) Researcher reveals | DNA 3 (researcher container) | `reveal_researcher_result` verifies `SHA-256(msgpack(metrics) || nonce)` on-chain; `ResearcherReveal` published | Rust zome, rejects mismatch |
| (6b) Validators reveal | DNA 3 (each validator container) | `submit_attestation` with nonce retrieved from DNA 2; verifies `SHA-256(msgpack(attestation) || nonce) == CommitmentAnchor.commitment_hash` | Rust zome, rejects mismatch |
| (7) HarmonyRecord | DNA 4 (validator-1 container) | Permanent immutable record on public Governance DHT | Governance integrity zome validates author ∈ participants |

---

## The synthetic study

The "research" is real computation: ordinary least-squares linear regression on 20 `(temperature_variability_index, species_richness_index)` data points. `study.py` computes the OLS slope, intercept, and R² from first principles using only Python stdlib.

**Claimed results:**

```
Slope (coefficient): 2.4086
Intercept:           1.1742
R²:                  0.9991
```

Each validator runs `study.py` and checks whether its output matches those three values to 4 decimal places. Python's `float` arithmetic is IEEE 754 and deterministic — every independent run produces identical output.

---

## Key files

| File | Role |
|---|---|
| `demo/docker-compose.yml` | 5-container stack definition; ports, volumes, env vars |
| `demo/Dockerfile.node` | Shared image for researcher and validator containers; installs Holochain + Node deps |
| `demo/node-entrypoint.sh` | Container startup: installs happ, starts conductor, starts node API |
| `demo/conductor-config-node.yaml` | Conductor config template; bootstrap URL is interpolated at startup |
| `demo/researcher-node.mjs` | Node.js HTTP API for researcher conductor |
| `demo/validator-node.mjs` | Node.js HTTP API for each validator conductor |
| `demo/node-lib.mjs` | Shared helpers: `withSession`, `retryOnTx5`, `loadHcClient`, `externalHashFromB64` |
| `demo/ai_validator.py` | Python orchestrator — `--mode decentralised` calls the five node APIs |
| `demo/bin/kitsune2-bootstrap-srv` | Pre-compiled bootstrap server binary |
| `valichord/workdir/researcher.happ` | Role-filtered happ for researcher containers (DNAs 1, 3, 4) |
| `valichord/workdir/validator.happ` | Role-filtered happ for validator containers (DNAs 2, 3, 4) |
| `demo/synthetic_study/` | Minimal reproducible study (README, data.csv, study.py) |

---

## Rebuilding from source

If you modify the Rust zome code, rebuild before running:

```bash
cd valichord
export PATH="$HOME/.cargo/bin:$PATH"
cargo build --target wasm32-unknown-unknown --release
hc dna pack dnas/attestation                -o workdir/attestation.dna
hc dna pack dnas/governance                 -o workdir/governance.dna
hc dna pack dnas/researcher_repository      -o workdir/researcher_repository.dna
hc dna pack dnas/validator_workspace        -o workdir/validator_workspace.dna
hc app pack researcher                      -o workdir/researcher.happ
hc app pack validator                       -o workdir/validator.happ
cd ..
docker compose -f demo/docker-compose.yml up --build -d
```

Requires: `cargo`, `wasm32-unknown-unknown` target, and `hc` CLI (`cargo install holochain_cli --version 0.6.0 --locked`).
