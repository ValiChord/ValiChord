# ValiChord Demo Video Script

**Runtime:** ~7 minutes
**Format:** Screen recording — terminal on Oracle Cloud + browser
**Structure:** Three acts. The problem → the analysis tool → the full live protocol

---

## Pre-recording setup

Everything runs on the Oracle Cloud server. Do this before you hit record:

```bash
# SSH to Oracle, then:
export ANTHROPIC_API_KEY=sk-ant-...
bash demo/start_oracle.sh --fresh
```

Wait for:
```
=== Stack is up ===
  HTTP Gateway:  http://<IP>:8090
  Public API:    http://<IP>:5000
```

Have a browser tab open and ready — you'll paste the shareable URL into it at the end.

---

## [SECTION 1 — 0:00 to 0:45] The problem

*[Screen: blank terminal or title card]*

> "Around seventy percent of researchers say they've failed to reproduce another scientist's computational experiment. Not because the science was wrong — more often because the code had a hardcoded path on someone's laptop, or the software versions were never recorded, or the data was never shared publicly.
>
> ValiChord is built to fix this. Not a checklist, not a PDF badge — a distributed protocol where independent validators verify that a study reproduces, and the outcome is written permanently to a peer-to-peer network where no single party can alter it.
>
> Let me show you what it does today."

---

## [SECTION 2 — 0:45 to 2:30] ValiChord at Home — deposit analysis

*[Switch to: browser at https://topeuph-ai.github.io/ValiChord/valichord-at-home.html]*

> "The first tool is ValiChord at Home — a self-service deposit checker. A researcher uploads their repository ZIP before formal validation and gets an immediate report of everything that would block an independent validator."

*[Upload a deposit ZIP — or show a pre-loaded result]*

> "ValiChord at Home runs over a hundred pattern checks in the background — hardcoded paths, missing dependency files, undocumented data columns, human-subjects data left unredacted, absolute paths that only work on one machine. The findings are grouped by severity.
>
> CRITICAL findings are blockers. SIGNIFICANT would likely cause failures. LOW CONFIDENCE are worth checking.
>
> This is the preparation layer. A researcher fixes these before submitting for formal validation. Now let me show you what formal validation looks like."

---

## [SECTION 3 — 2:30 to 5:30] The live protocol — Oracle demo

*[Switch to: terminal on Oracle Cloud]*

> "This is a live Holochain network running on Oracle Cloud. Four separate peer-to-peer networks — the researcher's private network, each validator's private workspace, a shared coordination network, and a public governance network. Five independent agent identities on one conductor."

```bash
python3 demo/ai_validator.py
```

*[Let it run — narrate each step as it appears]*

> "Step one: the study is loaded. This is a real piece of mathematics — ordinary least-squares linear regression on twenty data points. Temperature variability versus species richness. The script computes slope, intercept, and R² from first principles in pure Python. No external dependencies."

*[Step 2 appears — execution output]*

> "Step two: the study code runs. These are the actual results — slope 2.4086, intercept 1.1742, R² 0.9991. Deterministic on any platform. Any developer can verify this by running the script themselves."

*[Step 3 appears — three Claude calls]*

> "Step three: three independent Claude AI agents each read the study README and the actual execution output. Separate API calls. Each forms its own verdict — Reproduced, PartiallyReproduced, FailedToReproduce, or UnableToAssess — with a confidence level and one sentence of reasoning. They don't see each other's verdicts."

*[Step 4 appears — protocol starting]*

> "Step four: the commit-reveal protocol begins. Watch what happens.
>
> First — the researcher seals a cryptographic commitment to their result. SHA-256 of the metrics combined with a random nonce. Only the hash leaves their private network. They are bound to their claimed results from this point.
>
> Then the three validators each seal their verdicts blind. Their actual assessments stay private on each validator's own network. Only the commitment hashes go to the shared DHT.
>
> The phase gate — written into the Holochain DNA in Rust — waits until all three commitment hashes are confirmed on the network. When they are, it opens the reveal phase automatically. No trusted coordinator. No manual trigger.
>
> Now both sides reveal simultaneously. The researcher's reveal is verified on the network — SHA-256 of their metrics and nonce is recomputed and checked against what they committed earlier. Cryptographic proof they didn't adjust their claimed values after seeing what the validators found.
>
> And finally — a HarmonyRecord is written to the public governance network."

*[Step 7 appears — output with shareable URL]*

---

## [SECTION 4 — 5:30 to 6:30] The shareable URL — open in browser

*[Copy the URL from terminal output — paste into browser]*

> "That URL. No Holochain installation. No API key. No authentication. Just a URL."

*[Browser shows clean JSON]*

```json
{
  "outcome":         { "type": "Reproduced" },
  "agreement_level": "ExactMatch",
  "discipline":      { "type": "ComputationalBiology" },
  "validator_count": 3
}
```

> "This is the HarmonyRecord. Outcome: Reproduced. Three validators, exact match. It's on the network. Anyone — a journal editor, a funder, another researcher — can read this. Nobody can edit it. The Rust validation rules physically reject any attempt to update or delete a HarmonyRecord after it's written.
>
> The researcher committed their result before any validator started. The validators committed blind before the phase gate opened. Neither side could move the goalposts. The envelopes were sealed before anyone opened theirs."

---

## [SECTION 5 — 6:30 to 7:00] The proof

*[Switch to: terminal or screenshot of test results]*

> "Everything I've just shown you is backed by ninety-four integration tests running on real Holochain conductors — not mocks, not simulations. Each test launches independent conductor processes with their own agent identities, source chains, and DHT participation.
>
> Membrane proof tests. Full commit-reveal across all four networks. Security tests — double-attestation rejected, conflict of interest blocked at the Rust level. Mixed-outcome HarmonyRecord assembly. Stuck round recovery.
>
> One test is skipped — it requires seven simultaneous conductors for the Gold badge threshold. Hardware constraint, not architectural.
>
> Everything is at github.com/topeuph-ai/ValiChord."

---

## Recording notes

**Windows to have open:**
1. Browser — `valichord-at-home.html` (Section 2)
2. Terminal — Oracle SSH session (Sections 3–4)
3. Browser (2nd tab) — ready for the shareable URL (Section 4)

**Pacing:**
- Let the protocol output breathe — each step label appears naturally, don't rush past it
- The shareable URL in the browser is the visual punchline — pause on the JSON
- Section 2 (ValiChord at Home) can be shortened or cut entirely for a technical audience

**Optional cuts:**
- **5-minute version:** drop Section 2 (ValiChord at Home) — go straight from the problem to the Oracle terminal
- **3-minute version:** drop Sections 2 and 5; problem → protocol run → URL in browser

---

## Start-up checklist

```
[ ] Oracle stack running (bash demo/start_oracle.sh --fresh)
[ ] ANTHROPIC_API_KEY exported in Oracle SSH session
[ ] Terminal font size ≥ 16pt
[ ] Notifications off
[ ] Browser tab open and ready for shareable URL
[ ] ValiChord at Home tab loaded (if including Section 2)
```
