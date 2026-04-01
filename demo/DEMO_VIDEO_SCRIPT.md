# ValiChord Demo Video Script

**Runtime:** ~8 minutes
**Format:** Screen recording — mix of terminal, browser, and API calls
**Structure:** Three acts. The problem → what ValiChord does today → the cryptographic layer

---

## Pre-recording setup

### Terminal 1 — Flask backend
```bash
cd /workspaces/ValiChord/backend
pip install -r requirements.txt -q
python app.py
```
Wait for: `Running on http://0.0.0.0:5000`

### Terminal 2 — Holochain conductor + demo server
```bash
cd /workspaces/ValiChord
export PATH="/home/codespace/.cargo/bin:$PATH"
bash demo/start.sh
```
Wait for: the demo page opens on `http://localhost:8888`
If running in Codespace: make port 8888 **public** (Ports tab → right-click → Public)

### Terminal 3 — ready for curl commands
```bash
cd /workspaces/ValiChord
```

### Test deposit
Have a research deposit ZIP ready — something with deliberate issues (hardcoded paths, missing requirements file, no README, etc.) works best for showing findings. The `autogenerate/tests/` directory is the right place to drop it.

---

## [SECTION 1 — 0:00 to 0:45] The problem

*[Screen: blank terminal or title card]*

> "Around seventy percent of researchers say they've failed to reproduce another scientist's computational experiment. Not because the science was wrong — more often because the code had a hardcoded path on someone's laptop, or the software versions were never recorded, or the data was never shared publicly.
>
> ValiChord is built to fix this. Not a checklist, not a PDF badge — a distributed protocol where independent validators verify that a study reproduces, and the outcome is written permanently to a peer-to-peer network where no single party can alter it.
>
> Let me show you what it does today."

---

## [SECTION 2 — 0:45 to 3:00] The analysis pipeline

*[Switch to: Terminal 3 or browser showing demo.html / or use curl]*

> "The first thing ValiChord does is analyse a research deposit — a ZIP of code, data, and documentation. A researcher or validator uploads it to the API."

### 2a. Submit a deposit

```bash
curl -s -X POST http://localhost:5000/validate \
  -F "file=@autogenerate/tests/YOUR_DEPOSIT.zip" | python3 -m json.tool
```

*[Screen: JSON response with job_id appears]*

> "The API returns a job ID immediately. ValiChord is now running over a hundred pattern checks in the background — hardcoded paths, missing dependency files, undocumented data columns, human-subjects data left unredacted, absolute paths that only work on one machine — plus a Claude semantic analysis pass that reads the actual code for context the patterns can't catch."

### 2b. Poll for results

```bash
# Wait ~20-30 seconds, then:
curl -s http://localhost:5000/result/JOB_ID_HERE | python3 -m json.tool
```

*[Screen: full JSON result — findings array, harmony_record_draft, PRS score]*

> "Here's the result. The findings are organised by severity — CRITICAL findings are blockers that would prevent an independent validator from even attempting to run the code. SIGNIFICANT findings would likely cause failures. LOW CONFIDENCE findings are worth checking.
>
> The Process Reproducibility Score at the top is a single number — a quick signal. High means it's likely reproducible as-is. Critical means a validator would be blocked before they even start.
>
> And here at the bottom — `harmony_record_draft`. This is what gets written to the distributed network. It includes the outcome — in this case PartiallyReproduced — the SHA-256 hash of the deposit, and the summary of findings."

*[Pause, let the JSON sit on screen for a moment]*

> "The harmony_record_hash field — that `uhCkk...` string — is the cryptographic record on the Holochain network. It's already been written. We'll look at what that means in a minute."

---

## [SECTION 3 — 3:00 to 5:00] Feynman runs /valichord

*[Switch to: terminal or slide showing Feynman flow — or if Feynman is installed locally, run it]*

> "ValiChord is designed to be called by any validator — human or AI. The first AI validator is Feynman — an open-source AI research agent that can replicate computational experiments end to end."

*[Show the integration flow — either Feynman running in terminal, or narrate over a diagram/slides]*

> "When a researcher publishes a study, Feynman runs its `/replicate` command — it downloads the code and data, sets up the environment, runs the analysis, and checks whether the outputs match what the paper claims.
>
> Then it calls `/valichord`. That zips up everything it found — the deposit, its execution log, the comparison — and sends it to ValiChord's API. The same pipeline we just saw runs, but now the findings are grounded in actual code execution, not just deposit analysis.
>
> The result comes back with an outcome — Reproduced, PartiallyReproduced, or FailedToReproduce — and a HarmonyRecord hash. That hash is permanent."

*[If able to run Feynman live:]*
```bash
feynman /valichord --deposit path/to/deposit.zip --api http://localhost:5000
```

*[Show the response JSON with harmony_record_draft and harmony_record_hash]*

> "This is what the Feynman integration looks like today — a single API call that returns a structured verdict and a cryptographic anchor on the Holochain network. Feynman 0.2.15 ships with this skill built in."

---

## [SECTION 4 — 5:00 to 7:00] The cryptographic layer — browser demo

*[Switch to: browser at http://localhost:8888 — the demo/index.html page]*

> "Let me show you what's happening under the hood when that HarmonyRecord is created.
>
> This is a browser visualisation of the commit-reveal protocol — the cryptographic mechanism that makes it impossible to game the system."

*[Click 'Run validation round']*

> "Watch the steps.
>
> First: the validator seals their assessment. They generate a random nonce, compute a hash of their findings combined with that nonce, and publish only the hash to the shared network. Their actual findings stay private. This is the commitment.
>
> The researcher also committed their claimed results before any validator started. Neither side can see the other's sealed content — and neither can change it.
>
> Now the network waits for all validators to commit. When both hashes are recorded, the network transitions to reveal phase — watch for that step.
>
> Now both validators publish their full assessments. The network verifies each reveal matches its earlier hash. If anyone tried to change their findings after seeing the other side — hash mismatch — the reveal is rejected.
>
> And at the end: a HarmonyRecord is written to the public Governance network. Immutable. The validation rules in the Rust code physically reject any attempt to update or delete it."

*[Let the animation complete — HarmonyRecord step turns green]*

> "That `uhCkk...` hash is the record. Anyone can query the Governance network with that hash — a journal, a funder, another researcher — and get the full outcome back. No central server, no one who can edit the record after the fact."

---

## [SECTION 5 — 7:00 to 8:00] The proof — test suite summary

*[Switch to: terminal with test results, or show a screenshot of 94 passing]*

> "Everything I've just shown you is backed by a test suite running on real Holochain nodes — not mocks, not simulations.
>
> Ninety-four tests passing across four separate peer-to-peer networks:
>
> — Membrane proof tests: the validation network is credentialed. No certificate, or a forged one, gets rejected at the cryptographic level.
>
> — Commit-reveal tests: two independent validators seal, the phase transitions, both reveal, the HarmonyRecord appears.
>
> — Security tests: double-attestation rejected, conflict of interest blocked, claim-timeout floor enforced. Each is an attempted attack that the protocol defeats.
>
> One test is skipped — it requires seven simultaneous Holochain conductors for the Gold badge threshold. Written, correct; this machine doesn't have the RAM to run seven conductors at once. Hardware constraint, not architectural.
>
> The infrastructure is built and tested. What comes next is putting it in front of real researchers and real validators."

---

## [OUTRO — 8:00]

> "ValiChord today: a live analysis API, a Feynman integration that works, and a Holochain protocol with ninety-four passing tests.
>
> What's not done yet: always-on hosting, multi-validator rounds in production, and API authentication. Those are the Phase 0 asks.
>
> Everything is at github.com/topeuph-ai/ValiChord."

---

## Recording notes

**Order of windows to have open:**
1. Terminal 1 — Flask backend running (can be minimised after Section 2)
2. Terminal 2 — demo server running (keep open)
3. Terminal 3 — curl commands (active during Section 2)
4. Browser — `http://localhost:8888` (active during Section 4)
5. Browser (2nd tab) — test results screenshot or run `npm test` live for Section 5

**Pacing:**
- Section 2 is the heart for a non-technical audience — go slow, let the JSON sit
- Section 4 (browser animation) is the visual peak — narrate each step as it appears
- Don't rush the `uhCkk...` hash reveal — it's the punchline of sections 2, 3, and 4

**If you can't run Feynman live:**
- Section 3 works fine as narration over a slide or a copy of the API response JSON
- The key point is: Feynman calls the same API, gets the same structured response

**Optional cut for a 4-minute version:**
- Skip Section 3 (Feynman) if demoing to a technical audience who just want the protocol
- Skip Section 5 (tests) if demoing to a funder audience who want the application layer
- The 4-minute version is: Problem → API demo → browser animation → one-sentence outro

---

## Start-up checklist

```
[ ] Terminal 1: python backend/app.py  (port 5000)
[ ] Terminal 2: bash demo/start.sh     (port 8888, conductor on 4444)
[ ] Port 8888 set to Public in Codespace Ports tab
[ ] Test deposit ZIP in autogenerate/tests/
[ ] Font size ≥ 16pt in terminal
[ ] Notifications off
[ ] curl command ready to paste (with correct deposit filename)
```
