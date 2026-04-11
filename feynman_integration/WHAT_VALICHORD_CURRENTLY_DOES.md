# What ValiChord Currently Does

*A plain-English summary of the current state — what's real, what's a proxy, and what isn't done yet.*

---

## The one-paragraph version

ValiChord asks: *can an independent party arrive at the same result as the researcher?* A validator (human or AI) runs the research code independently, forms a verdict, and submits it via a blind commit-reveal protocol on a Holochain peer-to-peer network. Neither party can change their claim after seeing what the other found. The cryptographic outcome — a HarmonyRecord — is publicly verifiable by anyone with the URL, with no login and no central authority.

---

**Note on valichord_at_home:** The codebase also contains `valichord_at_home` — a separate static analysis tool that checks a deposit's *structure* (missing README, hardcoded paths, no requirements file, 100+ checks). This is a **researcher prep tool**, not the core of ValiChord. It answers a different question: *does this deposit look like someone could run it?* PI and Feynman as validators do not use it — they actually run the code, which supersedes any structural check. The 100+ checks are bundled into `POST /validate` as a deposit quality service for researchers; validators use `POST /attest` and bypass them entirely.

---

## What is genuinely working right now

### 1. The Holochain commit-reveal protocol
ValiChord runs a blind commit-reveal round across the four DNAs. A validator submits their verdict, it is sealed (committed) before any reveal is possible, then revealed. The result is written as a `HarmonyRecord` to the Governance DHT:
- The outcome (`Reproduced` / `PartiallyReproduced` / `FailedToReproduce`)
- A SHA-256 hash of the deposit (proof of exactly what was verified)
- A `harmony_record_hash` — unique cryptographic identifier, permanent on the DHT
- A `harmony_record_url` — publicly verifiable link (null until a permanent gateway is deployed)

This is the core of ValiChord. Everything else is supporting infrastructure.

### 2. The REST API
- `POST /attest` — **validator path** (PI, Feynman): pass `data_hash` + verdict; returns HarmonyRecord synchronously (~60 s, no polling, no upload)
- `POST /validate` — **researcher path** (valichord_at_home): submit a ZIP, get back a job ID; runs 100+ structural checks; poll `GET /result/<job_id>` until done
- `GET /result/<job_id>` — poll for `POST /validate` results

### 3. valichord_at_home deposit analysis (researcher tool)
When a researcher submits a ZIP via `POST /validate`, ValiChord checks it for structural reproducibility issues — missing README, hardcoded paths, no requirements file, undocumented data, 100+ checks. Each issue is classified CRITICAL / SIGNIFICANT / LOW CONFIDENCE. This produces genuinely useful feedback for researchers fixing up a deposit before publication.

**This is not the validation.** It is a deposit quality pre-check. It does not tell you whether the code runs. PI and Feynman skip this entirely.

### 4. The PI / Feynman integration
PI and Feynman act as AI validators. They run the research code, form a verdict from what they observed, compute the SHA-256 of the deposit locally, and call `POST /attest`. No upload, no structural analysis — straight to the Holochain protocol. The HarmonyRecord comes back synchronously.

---

## Two modes: validator-attested vs proxy

The `AttestationOutcome` in the HarmonyRecord can now come from one of two places.
The response field `harmony_record_draft.validator_attested` tells you which.

### Validator-attested (`validator_attested: true`)

A real validator (human or AI — PI / Feynman, for example) actually ran the code and
submitted their replication verdict via `POST /attest` (passing `data_hash` and
`outcome`). The outcome means exactly what it says:

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

**When PI / Feynman runs the code and calls `POST /attest`**, the proxy is
replaced by a genuine attestation. The HarmonyRecord on Holochain will then
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
