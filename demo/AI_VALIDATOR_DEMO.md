# AI Validator Demo — 3 Validators + Researcher Reveal
### Technical guide for developers

---

## What this demo is

A fully automated, end-to-end run of the ValiChord protocol on a live Holochain network — showing everything the system is built to do, in a single command.

**This is not a simulation.** Every step involves real zome calls to real Holochain DNA cells running on a live conductor on Oracle Cloud. The HarmonyRecord lands on a live distributed network and is immediately readable at a public URL — no Holochain node, no API key, no authentication.

What happens when you run it:

- A **real piece of mathematics** is computed: ordinary least-squares linear regression on 20 data points, implemented from scratch in pure Python. The results are deterministic — any independent party running the same script on the same data gets the same numbers to 4 decimal places.
- The **researcher seals a cryptographic commitment** to those results before any validator has seen them. From this point, they cannot change their claimed values.
- **Three independent Claude AI agents** each read the study README and the actual execution output and form their own reproducibility verdict — without seeing each other's. Three separate API calls; three separate judgements.
- All three validators **commit their verdicts blind** to the shared Holochain DHT. The content stays hidden; only the commitment hash is visible.
- A **phase gate** on the Holochain network opens automatically when all three commitment anchors are confirmed — no manual trigger, no trusted coordinator.
- **Both sides reveal simultaneously, both cryptographically verified.** The researcher's `reveal_researcher_result` recomputes `SHA-256(msgpack(metrics) || nonce)` on the Holochain network and checks it against the hash committed at submission. Each validator's `submit_attestation` recomputes `SHA-256(msgpack(attestation) || nonce)` and verifies it against the `CommitmentAnchor.commitment_hash` written at seal time. Neither side can reveal different values than they committed to.
- A **HarmonyRecord** is written to the public Governance DHT. It is readable at a shareable URL within seconds.

---

## What the demo proves

- **The full protocol runs end-to-end.** 8 internal steps, no manual intervention, ~2 minutes wall time.
- **The full protocol is production-grade on both sides.** Researcher and validators are fully symmetric — neither can reveal different values than they committed to, and neither can see the other's values before committing their own.
- **All 3 validators commit blind.** The phase gate in DNA 3 enforces that no reveal is accepted until all 3 CommitmentAnchors are on the DHT.
- **Both reveals are cryptographically verified on the Holochain network.** `reveal_researcher_result` verifies `SHA-256(msgpack(metrics) || nonce)` against the researcher's commitment hash. `submit_attestation` verifies `SHA-256(msgpack(attestation) || nonce)` against each validator's `CommitmentAnchor`. Both checks are in Rust zome code — no trust assumption on either side.
- **AI validators are first-class citizens.** Same zome functions, same DHT entries, same phase gate as human validators.
- **The HarmonyRecord is permanent and publicly verifiable.** Anyone can fetch it at the shareable URL and read the outcome, agreement level, discipline, and validator count in clean JSON — no Holochain node, no API key, no authentication.

---

## What "reproduced" means

ValiChord asks: *can an independent party arrive at the same result as the researcher?*

"Reproduced" means the validator got the **same result as the researcher** — not that the result is correct. A study can be reproducible and scientifically wrong. A study can be correct but not reproducible. ValiChord only answers the reproducibility question.

---

## Architecture

```
ai_validator.py
    │
    ├─ [1/7] Load synthetic study from demo/synthetic_study/
    │         Package as ZIP, SHA-256(data + run_id) as ExternalHash
    │
    ├─ [2/7] Execute demo/synthetic_study/study.py
    │         Captures stdout → parse into 3 MetricResult objects
    │
    ├─ [3/7] 3 independent Claude API calls (claude-opus-4-6)
    │         Each: README + actual output → JSON { outcome, confidence, reasoning }
    │         Verdicts formed before any Holochain commitment
    │
    └─ [4/7] POST /holochain/validate-round-multi → demo/serve.mjs
                  │
                  └─ _runFullProtocolRound() — 8 internal steps:
                      │
                      ├─ (0) lock_researcher_result       (researcher_repository DNA)
                      │       SHA-256(msgpack(metrics) || nonce) → commitment hash
                      │       auto cross-DNA call: publish_researcher_commitment
                      │       → ResearcherResultCommitment on shared attestation DHT
                      │
                      ├─ (1) submit_validation_request    (attestation DNA, researcher)
                      │       num_validators_required = 3
                      │
                      ├─ (2) Validator 1: profile → claim → receive_task → seal
                      │       post_commit → CommitmentAnchor on shared DHT
                      ├─ (3) Validator 2: same
                      ├─ (4) Validator 3: same
                      │
                      ├─ (5) poll get_current_phase until RevealOpen
                      │       (PhaseMarker written when all 3 CommitmentAnchors seen)
                      │
                      ├─ (6a) reveal_researcher_result    (attestation DNA, researcher)
                      │        verifies SHA-256(msgpack(metrics) || nonce) on-chain
                      │        → immutable ResearcherReveal on shared DHT
                      ├─ (6b) submit_attestation × 3      (attestation DNA, validators)
                      │
                      └─ (7) check_and_create_harmony_record  (governance DNA)
                              → HarmonyRecord on public Governance DHT
```

After the round completes, `serve.mjs` returns a JSON summary (outcome, agreement level, researcher reveal hash, all 3 validator verdicts, ExternalHash for the shareable URL).

---

## Infrastructure

| Component | Detail |
|---|---|
| Oracle Cloud server | VM.Standard.A1.Flex, Ubuntu 22.04, port 5000 open |
| Holochain conductor | 0.6.0, single conductor, local bootstrap server (port 9000) |
| Bootstrap/SBD | `kitsune2-bootstrap-srv` 0.3.2 — pre-compiled binary in `demo/bin/` |
| Node.js bridge | `demo/serve.mjs`, port 8888 (internal) |
| Public API | `demo/serve.mjs`, port 5000 — exposes endpoints (authenticated) and `/record/<hash>` (unauthenticated) |
| HTTP Gateway | `hc-http-gw` 0.3.1, port 8090 — exposes raw zome calls via HTTP |
| Apps installed | `valichord-demo` (single-validator, network `valichord-demo`) + `valichord-researcher`, `valichord-validator-1/2/3` (3-validator, network `valichord-demo-multi`) |

---

## Running the demo on Oracle

### One-time setup

SSH to the Oracle server, then:

```bash
cd ~/valichord
git pull

# Install Node.js dependencies (first time only)
cd demo && npm install && cd ..

# Install Python dependencies (first time only)
pip install anthropic
```

### Starting the stack

```bash
export ANTHROPIC_API_KEY=sk-ant-...
bash demo/start_oracle.sh --fresh
```

`--fresh` clears `demo/conductor_data/` before starting. Required if Holochain WASM has changed or if the previous run left a stale study claim.

Wait for:
```
=== Stack is up ===
  HTTP Gateway:  http://<IP>:8090
  Public API:    http://<IP>:5000
```

### Running the demo

```bash
python3 demo/ai_validator.py
```

### Expected output

```
╔══════════════════════════════════════════════════════════╗
║    ValiChord AI Validator Demo — 3 Validators           ║
╚══════════════════════════════════════════════════════════╝
  Researcher + 3 independent Claude validators.
  Both sides commit-reveal symmetrically — neither can change
  their result after the other has committed.

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

[4/7] Running commit-reveal protocol (researcher + 3 validators)…
────────────────────────────────────────────────────────────
  (0) Researcher sealing result commitment — blind, before any reveal
  (1) ValidationRequest published to shared DHT
  (2–4) 3 validators sealing blind commitments to DHT
  (5) Phase gate opens when all 3 CommitmentAnchors confirmed
  (6) Dual reveal: researcher + all 3 validators simultaneously
  (7) HarmonyRecord written to Governance DHT

  Submitting to Holochain bridge (may take 60–120 seconds)…

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
  http://<IP>:5000/record/uhC8k…

  Verifying record is readable…
  Record confirmed. Outcome: {'type': 'Reproduced'}  Agreement: ExactMatch  Validators: 3

════════════════════════════════════════════════════════════
  Demo complete. The full ValiChord protocol ran end-to-end.
  Researcher and 3 validators all commit-revealed simultaneously.
════════════════════════════════════════════════════════════
```

### Running it remotely (no Oracle SSH required)

If the Oracle stack is already running, `ai_validator.py` can be run from any machine — including this Codespace — by pointing it at the public API:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export VALICHORD_BRIDGE_URL=http://132.145.34.27:5000
export VALICHORD_API_KEY=valichord-demo-2026
python3 demo/ai_validator.py
```

---

## The shareable URL

After a successful run, the demo prints a URL of the form:

```
http://132.145.34.27:5000/record/uhC8k<hash>
```

This endpoint (`GET /record/<external-hash-b64>`) is served by `demo/serve.mjs` on port 5000. It:

- Requires no authentication
- Strips the multibase `u` prefix before base64url-decoding
- Tries the `valichord-demo-multi` network first (3-validator records), then the legacy `valichord-demo` network (single-validator records)
- Calls `get_harmony_record(ExternalHash)` on the Governance DNA
- Decodes the entry bytes with `@msgpack/msgpack`
- Returns clean JSON: `{ harmony_record_hash, outcome, agreement_level, discipline, validator_count }`

---

## The synthetic study — what the maths actually is

The "research" in the demo is real computation, not a mock. It is deliberately simple so that any developer can verify it by hand.

### The dataset

`demo/synthetic_study/data.csv` contains 20 rows of paired observations:

| `x` | `y` |
|-----|-----|
| 1 | 4.2 |
| 2 | 5.8 |
| 3 | 9.1 |
| … | … |
| 20 | 49.6 |

`x` is a temperature variability index (unitless, 1–20). `y` is a species richness index (number of species at that site). The values are synthetic but follow a strong linear trend by design.

### What `study.py` computes

`study.py` is pure Python stdlib — no numpy, no scipy, no external dependencies. It computes ordinary least-squares linear regression from first principles in ~15 lines:

**1. Means**

```
x̄ = Σxᵢ / n        ȳ = Σyᵢ / n
```

**2. Slope** (the OLS estimator β₁)

```
β₁ = Σ(xᵢ − x̄)(yᵢ − ȳ)  /  Σ(xᵢ − x̄)²
```

This minimises the sum of squared vertical residuals. It is the exact same formula used by every statistics package; `study.py` just spells it out explicitly.

**3. Intercept** (β₀)

```
β₀ = ȳ − β₁ · x̄
```

The fitted line passes through the point (x̄, ȳ) by construction.

**4. R² (coefficient of determination)**

```
SS_res = Σ(yᵢ − ŷᵢ)²        (sum of squared residuals — how much the line misses)
SS_tot = Σ(yᵢ − ȳ)²          (total variance in y)
R²     = 1 − SS_res / SS_tot
```

R² = 1 means the line fits perfectly. R² = 0 means the line does no better than predicting ȳ for every point.

### The claimed results

```
Slope (coefficient): 2.4086
Intercept:           1.1742
R²:                  0.9991
```

The high R² (0.9991) is expected: the data was generated close to a straight line, so temperature variability is an excellent linear predictor of species richness *in this dataset*. This is not a surprising scientific finding — it is a designed property of the synthetic data that makes reproduction unambiguous.

### What reproduction means here

Each validator runs `study.py` and checks whether its output matches those three claimed values to 4 decimal places. There is no floating-point ambiguity: Python's `float` arithmetic is IEEE 754 and deterministic on any platform, so every independent run of `study.py` on `data.csv` produces identical output.

This is the cleanest possible case for a reproducibility check — and intentionally so. ValiChord is being demonstrated, not the science.

---

## Commit-reveal protocol — both sides

The protocol is symmetric. Neither the researcher nor any validator can change their result after the other has committed:

| Step | Who | What |
|---|---|---|
| (0) Researcher locks | `researcher_repository` DNA | `SHA-256(msgpack(metrics) || nonce)` sealed privately; hash published to shared DHT |
| (1) Submit request | `attestation` DNA | ValidationRequest with `num_validators_required=3` |
| (2–4) Validators commit | `validator_workspace` DNA | Each seals verdict privately; CommitmentAnchor published to shared DHT |
| (5) Phase gate | `attestation` DNA | RevealOpen PhaseMarker written once all 3 CommitmentAnchors confirmed |
| (6a) Researcher reveals | `attestation` DNA | `reveal_researcher_result` verifies SHA-256 on-chain; ResearcherReveal published |
| (6b) Validators reveal | `attestation` DNA | Each calls `get_private_attestation_for_task` on DNA 2 to retrieve their sealed nonce, then calls `submit_attestation` on DNA 3. On-chain: `SHA-256(msgpack(attestation) \|\| nonce) == CommitmentAnchor.commitment_hash` verified in Rust. |
| (7) HarmonyRecord | `governance` DNA | Permanent immutable record on public DHT |

**Why the researcher also commits**: The commitment is a two-way blind. First, it prevents the researcher from waiting to see all validator outputs and then claiming their result matches — the hash published at step (0) locks them in before any validator commits. Second, and equally important, it prevents validators from seeing the researcher's claimed values before forming their own verdict. Validators see only the commitment hash during the commit phase — not the actual metrics — so their assessment cannot be anchored or biased by what the researcher claimed. Both directions of information leakage are blocked by the same mechanism.

---

## Key files

| File | Role |
|---|---|
| `demo/ai_validator.py` | Python orchestrator — 7-step demo runner |
| `demo/serve.mjs` | Node.js bridge — AppWebsocket client + public API server |
| `demo/setup.mjs` | Installs 5 apps on conductor (1 single-validator + 4 multi-validator) |
| `demo/start_oracle.sh` | Stack startup script for Oracle |
| `demo/conductor-config.yaml` | Holochain conductor config — local bootstrap, dev mode |
| `demo/synthetic_study/` | Minimal reproducible study (README, data.csv, study.py) |
| `demo/bin/kitsune2-bootstrap-srv` | Pre-compiled local bootstrap/SBD server binary |
