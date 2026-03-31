# What ValiChord Currently Does

*A plain-English summary of the current state — what's real, what's a proxy, and what isn't done yet.*

---

## The one-paragraph version

A researcher (or Feynman) submits a ZIP file containing their research deposit — code, data, and documentation. ValiChord runs 100+ automated checks on it, produces a structured report of issues, maps those issues to a reproducibility verdict, and writes that verdict as a tamper-evident record to a Holochain network. Anyone with the record's URL can independently verify it — no login, no central authority.

---

## What is genuinely working right now

### 1. Deposit analysis
ValiChord checks the deposit for reproducibility issues — missing README, hardcoded file paths, no requirements file, undocumented data, and 100+ other checks. Each issue is classified as:
- **CRITICAL** — blocks reproduction entirely
- **SIGNIFICANT** — makes reproduction very difficult
- **LOW CONFIDENCE** — worth fixing but not a blocker

This part works well and produces genuinely useful feedback for researchers.

### 2. The REST API
Any system (including Feynman) can submit a deposit and get results back via two simple calls:
- `POST /validate` — submit a ZIP file, get back a job ID immediately
- `GET /result/<job_id>` — poll until done, get back the full verdict

### 3. The HarmonyRecord on Holochain
When a validation completes, ValiChord writes a `HarmonyRecord` to a Holochain DHT — a distributed, tamper-evident ledger. The record includes:
- The outcome (`Reproduced` / `PartiallyReproduced` / `FailedToReproduce`)
- A SHA-256 hash of the deposit (proof of exactly what was submitted)
- A `harmony_record_hash` — a unique cryptographic identifier
- A `harmony_record_url` — a publicly clickable link anyone can use to verify the record independently

### 4. The Feynman integration
Feynman can call `POST /validate`, poll for the result, and present the verdict and HarmonyRecord hash to the user. The skill is live in Feynman 0.2.15.

---

## Two modes: validator-attested vs proxy

The `AttestationOutcome` in the HarmonyRecord can now come from one of two places.
The response field `harmony_record_draft.validator_attested` tells you which.

### Validator-attested (`validator_attested: true`)

A real validator (human or AI — Feynman, for example) actually ran the code and
submitted their replication verdict via the `validator_outcome` field on
`POST /validate`. The outcome means exactly what it says:

- `Reproduced` — the validator ran it and got the same result
- `PartiallyReproduced` — it ran but outputs differed in specific ways
- `FailedToReproduce` — it failed to run, or outputs were fundamentally different

This is the real thing. This is what ValiChord is designed for.

### Proxy (`validator_attested: false`)

No validator has run the code yet. The outcome is derived from deposit quality
findings — a structural assessment of whether the repository *looks* runnable:

- CRITICAL findings → `FailedToReproduce`
- SIGNIFICANT findings only → `PartiallyReproduced`
- No findings → `Reproduced`

This is a reasonable stand-in, but it conflates two different questions:
- **Deposit quality** — is the repository well documented and structured?
- **Reproducibility** — does the code actually run and produce the same results?

A messy deposit can still reproduce. A tidy deposit can still fail. The proxy
doesn't distinguish these cases.

**When Feynman runs `/replicate` and submits `validator_outcome`**, the proxy
is replaced by a genuine attestation. The HarmonyRecord on Holochain will then
reflect what actually happened when someone ran the code.

---

## What ValiChord is NOT doing yet

| What's missing | Why it matters |
|---|---|
| Feynman running `/replicate` before submitting | PR #15 (in progress) wires this up — currently Feynman submits without running the code first |
| Multiple validators | The protocol supports many validators reaching consensus — currently only one (the system itself) |
| Bronze / Silver / Gold badges | These require multi-validator consensus in the Governance DNA — not yet triggered |
| Always-on hosting | The system runs in a Codespace that sleeps when inactive — not production-ready |
| API authentication | `POST /validate` is currently open with no API keys or rate limiting |
| Human validators | The original ValiChord vision includes human researchers as validators — none are on the network yet |

---

## The current live demo

The full stack is running in a Codespace:

- **API:** `https://improved-space-couscous-5gjwpp546jrg27p5q-5000.app.github.dev`
- **Health check:** `GET /health` — shows whether the Holochain conductor is live
- **Submit a deposit:** `POST /validate` with a ZIP file in the `file` field
- **Get results:** `GET /result/<job_id>`

*Note: the Codespace sleeps when inactive. If the health check shows the conductor as offline, the Codespace needs waking up.*

---

*Last updated: March 2026*
