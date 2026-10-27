# What ValiChord Does

*A plain-English summary for integrators — what's real, what's a proxy, and what isn't done yet.*

---

## The one-paragraph version

ValiChord asks: *can an independent party arrive at the same result as the researcher?* A validator (human or AI) runs the research code independently, forms a verdict, and submits it via a blind commit-reveal protocol on a Holochain peer-to-peer network. Neither party can change their claim after seeing what the other found. The cryptographic outcome — a HarmonyRecord — is publicly verifiable by anyone with the URL, with no login and no central authority.

---

## What is genuinely working right now

### 1. The Holochain commit-reveal protocol

ValiChord runs a blind commit-reveal round across four Holochain DNAs. A validator submits their verdict; it is sealed (committed) before any reveal is possible, then revealed with cryptographic verification. The result is written as a `HarmonyRecord` to the Governance DHT:

- The outcome (`Reproduced` / `PartiallyReproduced` / `FailedToReproduce`)
- A SHA-256 hash of the deposit (proof of exactly what was verified)
- A `harmony_record_hash` — unique cryptographic identifier, permanent on the DHT
- A publicly readable link — the demo nodes serve each record at `GET /record?hash=…` (the HTTP Gateway deployment that used to populate `harmony_record_url` was retired in July 2026)

Since v0.6.6 (October 2026) every peer also checks, before accepting them: each joining validator's credential, each HarmonyRecord's signed validator attestations (participants, outcome, agreement level, cohort size), and each validator profile's tier against what its credential grants.

This is the core of ValiChord. Everything else is supporting infrastructure.

### 2. The protocol API

- ⚠️ **Not working, and archived 2026-10-27:** `app_protocol.py` fails at import (its `holochain_bridge` module was removed in April 2026), so it was moved to `docs/archive/backend/` — see its `README.md`. The design:
- `POST /attest` — **validator path**: pass `data_hash` + verdict; returns HarmonyRecord synchronously (~60 s, no polling, no upload required)
- `GET /health` — liveness check + conductor status

### 3. Symmetric commit-reveal (as of March 2026)

Both researcher and validators commit blind and reveal simultaneously:

- Researcher seals result in DNA 1 before validators begin; only the hash is published
- Each validator seals verdict privately in DNA 2; `post_commit` publishes commitment hash to shared DHT
- Phase gate opens automatically when all commitment anchors are present
- Both sides reveal with SHA-256 verification in the zome code — neither can change their claim

---

## Two outcome modes

The `validator_attested` field in the response tells you which path produced the outcome.

### Validator-attested (`validator_attested: true`)

A real validator (human or AI) actually ran the code and submitted their replication verdict via `POST /attest`. The outcome means exactly what it says:

- `Reproduced` — the validator ran it and got the same result
- `PartiallyReproduced` — it ran but outputs differed in specific ways
- `FailedToReproduce` — it failed to run, or outputs were fundamentally different

This is the real thing. This is what ValiChord is designed for.

### Proxy (`validator_attested: false`)

No validator has run the code yet. The outcome is derived from deposit quality findings — a structural assessment of whether the repository *looks* runnable. This comes from [valichord_at_home](https://github.com/topeuph-ai/valichord_at_home) when a researcher submits via `POST /validate`.

A messy deposit can still reproduce. A tidy deposit can still fail. The proxy doesn't distinguish these cases. It is replaced by a genuine attestation once a validator submits one.

---

## What ValiChord does NOT yet do

| What's missing | Why it matters |
|---|---|
| Multiple validators in production | The protocol supports multi-validator rounds (validators per study is a per-study setting, 1–255) — the decentralised demo runs 3 validators; production deployment with real researchers and validators is Phase 1 |
| Always-on production network | A public demo network runs on one Oracle Cloud host (`132.145.23.78`, Holochain 0.7.1 since its fresh install on 2026-10-19); a production deployment with independent nodes is Phase 1, awaiting funding |
| Human validator onboarding | The original vision includes credentialed human researchers as validators — none are on a live network yet |
| Validator reputation tracking | Badge tiers (Bronze/Silver/Gold) reflect participant count and agreement level, using placeholder thresholds (3/5/7) still to be calibrated with real data; who writes validator reputation in production is undecided |

---

*Last updated: April 2026; status facts corrected 2026-10-18 (v0.6.6).*
