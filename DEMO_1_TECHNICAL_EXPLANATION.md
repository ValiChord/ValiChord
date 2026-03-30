# Demo 1 — Deposit Analysis + Holochain Commit-Reveal
### Technical Explanation for Script / Social Media Adaptation

---

## What this demo is

A single browser page that connects two systems end to end:

1. **ValiChord Deposit Analyser** — a Python tool that scans a research deposit (a zip file of code, data, and documentation) and scores how reproducible it is.
2. **Holochain commit-reveal protocol** — a distributed ledger sequence that seals a validator's verdict in a way that cannot be tampered with, backdated, or gamed.

The page is live at the Codespace URL on port 8888. It is served by a Node.js static server that also proxies API calls to a Flask backend running on port 5000.

---

## Step 1 — Deposit Analysis

### What the viewer does
They drag and drop a zip file of a research deposit onto the drop zone, or click to browse. Any zip will do — it can be a real academic dataset or a toy example.

### What happens under the hood
- The zip is sent via HTTP POST to `/api/validate` on the Flask backend (`backend/app.py`).
- The backend extracts the zip to a temporary directory.
- It then runs the full ValiChord detector suite — approximately 30 individual checks — against every file in the deposit. These checks look for things like: missing README, no requirements file, hardcoded absolute paths, missing licence, no definition of what "successful reproduction" looks like, empty code files, nested archives that a validator would have to manually unpack, missing checksums, undocumented output files, and many more.
- Each finding is assigned a severity: **BLOCKER**, **CRITICAL**, **SIGNIFICANT**, or **LOW CONFIDENCE**.
- A **Process Reproducibility Score (PRS)** is calculated on a 0–1 scale. The formula starts at 1.0 and deducts: 0.20 per Blocker, 0.10 per Critical, 0.05 per Significant, 0.01 per Low Confidence, with a small bonus for positive signals (e.g. a CITATION.cff file, a DOI). The score is capped at 0 from below.
- The backend returns a JSON response containing the score, the severity band (High / Moderate / Low / Critical), the top findings, and a `harmony_record_draft` — a preview of what the permanent record would say.
- The job runs asynchronously: the POST returns a `job_id` immediately, and the frontend polls `/api/result/<job_id>` every 2 seconds until status is `done`.

### What the viewer sees
The page runs the analysis silently. When complete, it shows a single quiet confirmation line: **"✓ Deposit analysed"**. The detailed findings stay hidden — they are not the point of this demo. The point is that the system has now formed an informed basis for a verdict.

---

## Step 2 — Choosing a Verdict

### The proxy disclaimer
Because this is Phase 0 (one developer, one conductor, no independent validators), there is no real human or AI validator running the code. Instead, the viewer — the person watching the demo — acts as the validator. They are shown three verdict options and pick one:

- **Reproduced** — the study checks out
- **Partially Reproduced** — some results match, some do not
- **Failed to Reproduce** — the results could not be confirmed

The subtitle on the page is explicit: *"For this demo, you are the validator. In production, the outcome is determined by validators — human or AI — who actually run the code."*

### Why this is honest and intentional
ValiChord is agnostic about whether validators are human or AI. The system does not care — it only cares that the verdict was sealed before the study outcome was known, so it cannot be influenced by what the researcher wants to hear. Showing the viewer as the validator is the simplest way to demonstrate the full pipeline without misrepresenting the current state of the project.

---

## Step 3 — Holochain Commit-Reveal (12 steps)

This is the core protocol. The viewer clicks **"Seal this verdict on Holochain →"** and watches a 12-step timeline execute in real time, each step animating as it completes.

### The four DNAs
ValiChord runs on Holochain with four separate DNA (distributed ledger) contexts:

| DNA | Role | Visibility |
|---|---|---|
| DNA 1 — Researcher Repository | Researcher stores their deposit reference | Private to researcher |
| DNA 2 — Validator Workspace | Validator stores their private sealed verdict | Private to validator |
| DNA 3 — Attestation | Shared coordination space — requests, claims, commitments, reveals | Shared DHT |
| DNA 4 — Governance | Permanent public record of the final outcome | Public DHT |

### The 12 steps in plain English

**Step 1 — Publish validator profile**
The validator registers themselves on the Attestation DHT with their institution, discipline, and availability. This establishes their identity on the network.

**Step 2 — Submit validation request**
A validation request is written to the Attestation DHT. It references the deposit, specifies the discipline, and sets how many validators are required. In Phase 0 this is 1; in production it would typically be 3.

**Step 3 — Claim the study**
The validator claims the study — formally committing to complete it. This locks the slot and prevents others from claiming the same slot after the phase gate opens.

**Step 4 — Create a private task**
A task record is written to the Validator Workspace DNA (private, lives only on the validator's device). This is where the validator's working notes and eventual verdict will be held until reveal.

**Step 5 — Seal the verdict (Commit phase)**
The validator's full attestation — verdict, confidence level, time invested, deviation flags, computational resources used — is written to the private Validator Workspace DNA as a `PrivateAttestation` entry. Holochain's `post_commit` hook then automatically writes a `CommitmentAnchor` — a cryptographic hash of the attestation — to the shared Attestation DHT. The actual verdict is not visible yet; only the hash is public.

**Step 6 — Wait for post_commit propagation**
The system waits ~4 seconds for the CommitmentAnchor to propagate across the DHT so other nodes can see that this validator has committed.

**Step 7 — Check the phase gate**
The system queries `get_current_phase` on the Attestation DHT. The protocol does not advance to the Reveal phase until all required validators have submitted their CommitmentAnchors. In Phase 0 with 1 validator this opens immediately; in a 3-validator study the gate holds until all three have sealed.

**Step 8 — Reveal the verdict**
Now that the phase gate is open, the validator submits the full attestation to the shared Attestation DHT. The network verifies that the revealed attestation hashes to the same value as the CommitmentAnchor submitted in Step 5. If they match, the reveal is accepted. This is what makes the protocol tamper-proof: the verdict was fixed before the gate opened, so it cannot have been changed in response to what other validators said.

**Step 9 — Compute agreement level**
The network compares verdicts across all validators and computes an `AgreementLevel`: `ExactMatch`, `DirectionalMatch`, or `Divergent`. In Phase 0 with one validator this returns `UnableToAssess` — the system correctly reports that it cannot compute inter-validator agreement from a single response.

**Step 10 — Create the HarmonyRecord**
`check_and_create_harmony_record` is called on the Governance DNA. This function checks that all required attestations have been received and revealed, then writes a permanent `HarmonyRecord` entry to the Governance DHT. This record contains: the outcome, the agreement level, a timestamp, and references to all contributing attestations.

**Step 11 — Retrieve and display the HarmonyRecord**
The demo fetches the HarmonyRecord and displays it: outcome, agreement level, and the ActionHash — a unique cryptographic identifier for this specific record on the Governance DHT. The ActionHash is what you would cite in a paper or journal system to point to this verification event.

**Step 12 — Done**
The record is permanent, immutable, and HTTP-accessible. It cannot be deleted, edited, or retracted. If the study is later found to be fraudulent, the record still exists and continues to show what the validators found at the time of verification.

---

## What this demo proves

- A real Holochain conductor is running locally (in a GitHub Codespace) — this is not a simulation.
- Real zome calls are being made to real DNA cells.
- The commit-reveal sequence genuinely prevents a validator from changing their verdict after seeing what others said.
- The deposit analyser runs the full production detector suite — the findings are real.
- The two systems (analysis + blockchain) are now connected in a single user flow.

## What this demo is not claiming

- This is Phase 0. One conductor, one validator, one machine. It is a proof of concept, not a deployed network.
- The verdict in this demo is chosen by the viewer, not by a validator who actually ran the code. That is clearly labelled.
- The Process Reproducibility Score is a structured heuristic, not a peer review. It tells you whether a deposit is *packaged* for reproduction, not whether the science is correct.

---

## Technology stack

| Component | Technology |
|---|---|
| Deposit analyser | Python 3, Flask, custom detector suite (~30 checks) |
| Browser demo | Vanilla HTML/CSS/JS, ES modules |
| Static server + API proxy | Node.js (serve.mjs) |
| Distributed network layer | Holochain 0.6.x, 4-DNA architecture |
| Holochain client | @holochain/client 0.20.2 (ES module, loaded from esm.sh) |
| Serialisation | MessagePack (@msgpack/msgpack 3.1.3) |
| Runtime environment | GitHub Codespace (Linux, 4-core, 16 GB RAM) |
