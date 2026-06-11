# PEP Master — Hardware-Verification Demo (ValiChord, Version A)

A runnable demonstration that the **ValiChord** commit-reveal protocol can verify
**open-hardware measurement reproducibility** — not just AI/computational results.

It runs a real, decentralised, blind commit-reveal round for the **Breathing Games /
Sensorica 2024 "PEP Master" pressure device** and publishes a tamper-evident
**HarmonyRecord** to a peer-to-peer DHT — with no central server vouching for the result.

> ## ⚠️ This is Version A — a protocol demonstration with stand-in numbers
>
> The three builder readings in this demo are **illustrative stand-in values, NOT three
> real independent physical builds.** This proves the ValiChord protocol carries
> hardware-shaped measurement data end-to-end to a HarmonyRecord. It does **not** prove
> medical correctness or regulatory approval of the device.
>
> Turning this into **Version B** (a real result) is a single-file edit: replace the three
> readings in `pep_master_bundle.json` with real measured deviations. No code changes.

---

## 1. What it is — and what it proves

**The device.** The PEP Master (*Organic Controller 3V Pressure Device*, Breathing Games /
Sensorica, 2024) is a **PEP — positive expiratory pressure — therapy device**. A
differential-pressure sensor (MPXV5010DP / MP3V5010DP / LPS35HW) on an ESP32 / Adafruit
Feather measures **expiratory pressure across 0–20 cmH₂O**, sampled every 0.2 s. Sensor
datasheet accuracy: **±5%**.

**The claim being verified.** *"An independently built PEP Master, calibrated per the
published procedure, reports expiratory pressure across 0–20 cmH₂O matching a reference
PariPEP gauge within ±5% — verified by 3 independent builds that reveal their readings
blind."*

**What a passing HarmonyRecord proves:** three independent builds of the published design,
by parties who **could not see each other's numbers before committing**, all landed inside
the spec. The commit-reveal protocol removes any last-mover advantage — no builder can nudge
their reading toward the pack after seeing it.

**What it does NOT prove:** that the spec is medically correct. "Reproduced" means *the
builders got the same result*, not that the result is clinically right. (This is the same
"reproduced ≠ correct" discipline used throughout ValiChord.)

---

## 2. Prerequisites

You need a host with:

- **Docker** + **Docker Compose v2** (`docker compose version`)
- **Python 3.8+** (standard library only — **no `pip install` needed**)
- **No API keys.** Unlike ValiChord's AI-validator demos, the builder verdicts here come
  from the measurement bundle, not from a model. Nothing calls out to any LLM.
- An **x86_64 Linux host** is recommended (the bundled Holochain + bootstrap binaries are
  Linux x86_64). **GitHub Codespaces is the easiest path** — it just works. On Apple Silicon,
  run Docker with amd64 emulation.

Everything else — the four Holochain conductors, the compiled device hApps, and the
peer-discovery (bootstrap) server — runs inside Docker containers built from this repo. No
Holochain install required on the host.

---

## 3. Quick start

Run all commands **from the repository root**.

```bash
# 1. Build and start the 5-container stack:
#    bootstrap (peer discovery) + researcher + 3 validators, each its own conductor.
docker compose -f demo/docker-compose.yml up --build -d

# 2. Wait until all four node APIs are ready (~1 minute).
until [ "$(docker compose -f demo/docker-compose.yml logs 2>/dev/null | grep -c 'node API →')" -ge 4 ]; do sleep 3; done && echo "Ready"

# 3. Run the round (~4 minutes — mostly real peer-to-peer DHT gossip time).
python3 demo/pep_master_round.py --bundle demo/pep_master_bundle.json

# 4. Tear down and wipe conductor state when finished (do this between runs).
docker compose -f demo/docker-compose.yml down -v
```

That's it. Step 3 prints the full protocol, the per-builder outcomes, the published
HarmonyRecord hash, and an independent fetch-back of that record from a *different*
conductor than the one that authored it.

---

## 4. What you'll see

Step 3 prints a 7-stage progress trace, then a permanent-record summary. Abridged:

```
================================================================
  ValiChord — PEP Master hardware-verification round (VERSION A)
================================================================
  Device:   PEP Master — Organic Controller 3V Pressure Device
  Spec:     expiratory pressure 0-20 cmH2O, within +/-5% of reference gauge (setpoints 5/10/15/20)
  Builders: 3 (illustrative stand-in readings)

  !! VERSION A — PROTOCOL DEMONSTRATION, NOT REAL BUILDS !!
  This proves reproducibility across builds, not medical correctness or regulatory
  approval — Version A uses illustrative stand-in readings, not real independent builds.

[4/7] Running decentralised commit-reveal protocol…
  Mode: DECENTRALISED — 4 separate conductors communicating via DHT
  (0) Researcher locking result…            Commitment sealed: uhC8k…
  (1) Submitting ValidationRequest (num_validators_required=3)…
  (2) Validator 1 committing blind…
  (3) Validator 2 committing blind…
  (4) Validator 3 committing blind…
  (5) Polling phase gate… RevealOpen.
  (6a) Researcher revealing metrics (SHA-256 verified on-chain)…
  (6b) Validator 1 breaking seal… Reproduced (High) — Builder A (Montreal lab): max deviation 3.1% …
  (6b) Validator 2 breaking seal… Reproduced (High) — Builder B (Lyon hospital): max deviation 4.4% …
  (6b) Validator 3 breaking seal… Reproduced (High) — Builder C (Seoul makerspace): max deviation 2.7% …
  (7)  Creating HarmonyRecord on Governance DHT…

================================================================
  PERMANENT RECORD (HarmonyRecord on the public DHT)
================================================================
  Outcome:         Reproduced (3/3 builders)
  AgreementLevel:  ExactMatch
  Discipline:      Open-Hardware Engineering
  HarmonyRecord:   uhCkk…
  Researcher ref:  uhCkk…

  Builder A (Montreal lab): max deviation 3.1%  -> Reproduced
  Builder B (Lyon hospital): max deviation 4.4%  -> Reproduced
  Builder C (Seoul makerspace): max deviation 2.7%  -> Reproduced

  Independently fetching the record back from the researcher node
  (a different conductor than the validator that authored it)…
  Record confirmed on the DHT. Outcome: Reproduced  Agreement: ExactMatch  Validators: 3
```

The **independent fetch-back** at the end is the point: the *researcher* conductor reads a
HarmonyRecord that a *validator* conductor authored, straight from the shared DHT. No central
database, no API owner you have to trust.

---

## 5. The measurement bundle (`demo/pep_master_bundle.json`)

This is the single input. It is the *frozen, hashed test protocol* plus the readings.
Blinding is meaningless unless the method is fixed before anyone measures, so the bundle
pins everything up front:

- **`test_protocol`** — the device design, controller, **pinned `firmware_commit`**, sensor,
  measurand (`expiratory_pressure_cmH2O`, range 0–20), per-unit calibration procedure,
  reference instrument (PariPEP gauge), **setpoints `[5, 10, 15, 20]` cmH₂O**, the procedure,
  the **±5% tolerance**, and the `outcome_rule`.
- **`readings`** — one entry per builder: `name`, `location`, `max_deviation_pct` (their
  worst deviation from the reference gauge across all setpoints).

The `outcome_rule` (applied to each builder's max deviation):

| Max deviation across setpoints | Outcome |
|---|---|
| within ±5% | `Reproduced` |
| within ±10% but outside ±5% | `PartiallyReproduced` |
| worse than ±10% | `FailedToReproduce` |
| build/test could not be completed | `UnableToAssess` |

**One open question, marked honestly in the bundle:** whether "±5%" is *of-reading* or
*of-full-scale* (it changes the pass band at low pressures). Version A assumes **of-reading**
and labels the assumption — to be confirmed with Breathing Games.

---

## 6. Making it real → Version B

Replace the three `readings` entries with real measured deviations from real builds. Nothing
else changes:

```jsonc
"readings": [
  { "name": "Sensorica build #1", "location": "Montreal",  "max_deviation_pct": 4.2 },
  { "name": "Partner lab build",  "location": "…",         "max_deviation_pct": 3.8 },
  { "name": "Maker build",        "location": "…",         "max_deviation_pct": 6.1 }
]
```

A builder whose worst deviation exceeds ±5% will come out `PartiallyReproduced` or
`FailedToReproduce`, and the aggregate `AgreementLevel` will reflect the disagreement — the
protocol does not force agreement. Also update `firmware_commit` to the real pinned git SHA
of the sketch that was flashed.

**Keep one reading per validator.** This stack runs **3** validator conductors, so the bundle
must contain **exactly 3 readings**. The driver checks this up front and exits with a clear
message if they don't match — so editing `readings` to 2 or 4 entries fails fast rather than
silently committing the wrong number and stalling the reveal phase gate.

To produce a **permanent, publicly shareable** record (rather than a local one that's wiped on
`down -v`), the same round can be pointed at always-on ValiChord nodes — ask the ValiChord
maintainer for the current node URLs.

---

## 7. How it maps to ValiChord (under the hood)

ValiChord is built on **Holochain** (agent-centric peer-to-peer — *not* a blockchain: no
miners, no tokens, no global ledger). Each participant runs their own conductor; shared state
lives in a peer-validated DHT. The demo runs four conductors across five containers:

| Stage | What happens |
|---|---|
| **Lock** | The researcher seals the reference (spec) pressures behind a cryptographic commitment. |
| **Request** | A `ValidationRequest` is published to the shared DHT (`num_validators_required = 3`). |
| **Commit (blind)** | Each of the 3 builder conductors seals its verdict: `commitment_hash = SHA-256(attestation ‖ nonce)`. No builder can see another's verdict. |
| **Phase gate** | When all 3 commitments are on the DHT, the reveal window opens (poll-driven, not signal-driven). |
| **Reveal** | Researcher and all builders reveal together; each reveal is SHA-256-verified on-chain against its commitment. |
| **HarmonyRecord** | Aggregated outcome + agreement level written to the public DHT — tamper-evident, immutable, fetchable by anyone. |

This is the **same protocol and the same code** ValiChord uses for computational
reproducibility. The Holochain layer does not care that the number came from a benchtop
pressure gauge instead of a re-run script — which is exactly the point.

---

## 8. Honest limits — what survives on-chain in Version A

Version A demonstrates agreement **at the outcome level**. Specifically, what the public
HarmonyRecord and attestations carry today:

- ✅ Each builder's **outcome** (`Reproduced` / …) and **confidence** (High / Medium / Low).
- ✅ The researcher's **shared reference vector** (the expected pressures at each setpoint).
- ❌ Each builder's **own per-setpoint measured numbers do not survive into the record.** In
  the current node layer, the attestation's `key_metrics` carries the shared researcher
  reference vector, and a `Reproduced` outcome is a tag with no payload — so a builder's
  individual deviation is shown in the live run but is not embedded in the record.

Carrying each builder's full numeric vector into the record (so a skeptic can see all three
independent measurement vectors, not just three "Reproduced" verdicts) is a small, known
extension for the real build:

1. Thread each validator's measured values through the `/commit` payload into their
   attestation's `key_metrics` (currently shared).
2. Encode the ±5% tolerance as an **interval** in the researcher's reference values (e.g.
   `@10 → [9.5, 10.5]`) so the per-validator numeric-convergence panel populates.

(These two go together — doing the second without the first would misleadingly show three
identical values.) Recording a builder's measured value even when it *passes* additionally
requires an integrity-layer change. These are flagged for the real build, not faked here.

Other real-world notes: a real validation round takes **days/weeks** (build + test), not
seconds — the protocol already tolerates async rounds. And ValiChord verifies *agreement
between independent builds*; if every builder's reference gauge is mis-calibrated the same
way, you get agreement on a wrong value. The reference instrument's traceability is a trust
anchor ValiChord does not itself certify.

---

## 9. Files

| File | Purpose |
|---|---|
| `demo/pep_master_bundle.json` | The frozen, hashed test protocol + the three builder readings. **The only file you edit for Version B.** |
| `demo/pep_master_round.py` | The driver: reads the bundle, builds the researcher reference metrics and the three builder verdicts, runs the existing decentralised commit-reveal round, prints and re-fetches the HarmonyRecord. |
| `demo/test_pep_master_round.py` | Unit tests for the outcome rule and bundle wiring (`python3 -m pytest demo/test_pep_master_round.py`). |
| `demo/docker-compose.yml` | The 5-container stack (bootstrap + researcher + 3 validators). |
| `demo/researcher-node.mjs`, `demo/validator-node.mjs` | HTTP APIs over each conductor (one per role). |

---

## 10. Troubleshooting

- **`Ready` never prints / nodes slow to start.** First start compiles ~30 MB of WASM per
  conductor; give it up to ~2 minutes. Re-run the `until …` line.
- **Phase gate slow to open.** The staggered commits and DHT gossip are deliberately paced for
  single-machine stability; ~2–4 minutes is normal, not an error.
- **Re-running.** Always `docker compose -f demo/docker-compose.yml down -v` between runs to
  wipe conductor state — otherwise a fresh round may collide with stale DHT data.
- **The published record is local.** With this stack the HarmonyRecord lives on the local
  containers' DHT and is wiped by `down -v`. That is expected for Version A. For a permanent,
  externally shareable record, run against always-on nodes (see §6).
