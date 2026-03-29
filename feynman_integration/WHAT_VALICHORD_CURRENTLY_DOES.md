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

## What is a proxy (important to understand)

The current `AttestationOutcome` — `Reproduced`, `PartiallyReproduced`, `FailedToReproduce` — is **derived from the deposit analysis findings**, not from anyone actually running the code.

In other words:
- CRITICAL findings → `FailedToReproduce`
- SIGNIFICANT findings only → `PartiallyReproduced`
- No findings → `Reproduced`

This is a reasonable stand-in for now, but it conflates two different questions:
- **Deposit quality** — is the repository well organised and documented? (what the detectors measure)
- **Reproducibility** — does the code actually run and produce the same results? (what a validator determines by running it)

A messy deposit *can* still reproduce. A tidy deposit *can* still fail. The proxy doesn't distinguish between these cases.

**The proxy will be replaced** when Feynman (or another validator) actually runs `/replicate` on the deposit and submits a genuine attestation based on whether the code ran successfully.

---

## What ValiChord is NOT doing yet

| What's missing | Why it matters |
|---|---|
| A real validator running the code | The verdict currently comes from deposit analysis, not actual execution |
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
