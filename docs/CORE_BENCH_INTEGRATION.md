# ValiChord + CORE-Bench Integration

## What this is

[CORE-Bench](https://arxiv.org/abs/2409.11363) tests whether an AI agent can computationally reproduce the results of scientific papers. [ValiChord](https://github.com/topeuph-ai/ValiChord) proves that independent parties reached the same conclusion without being able to coordinate after the fact. Neither system alone provides what both together do.

This document describes the integration architecture, the combined demo, and what needs to be built.

---

## Why the combination is superior to either alone

| | CORE-Bench alone | ValiChord alone | Combined |
|---|---|---|---|
| **Reproduction is computational** | ✅ Agent runs actual code | ❌ Current demo uses web search | ✅ |
| **Verdict is objective** | ✅ Code output matches or it doesn't | ❌ Agent forms an opinion | ✅ |
| **Multiple independent parties** | ❌ One agent, one result | ✅ N validators (configurable) | ✅ |
| **Structural independence** | ❌ Second runner can see first's result | ✅ Commit-reveal prevents this | ✅ |
| **Permanent verifiable record** | ❌ Results live in a log file | ✅ HarmonyRecord on DHT | ✅ |
| **No post-hoc adjustment** | ❌ Anyone could re-run and pick the best | ✅ Commit-reveal prevents this | ✅ |

**CORE-Bench alone** answers: *"can an AI reproduce this paper?"* — but gives you one result, which you still have to trust came from a genuine independent run.

**ValiChord alone** proves independent parties agreed — but the current demo validators form opinions via web search, which is subjective.

**Combined**: N agents independently execute the same code in isolated environments, each commits their `report.json` before seeing others' results, all reveal simultaneously. The verdict is objective (the code produces what it produces), the independence is structurally guaranteed, and the outcome is permanently recorded on a distributed network no single party controls.

### What N independent runs actually prove

It is worth being precise here, because the value of commit-reveal is different for objective code than for subjective claims.

For deterministic code with fixed seeds and pinned dependencies, N correct runs will produce byte-identical output. Agreement is then near-tautological — there is no opinion to coordinate on. What commit-reveal protects against in the objective setting is not *"validator B anchored on validator A's interpretation"* but *"validator B copied validator A's `report.json` instead of running the code."* That is still a real and defensible guarantee, just a different one from the subjective case.

N independent hard-difficulty runs concretely prove:

1. **The capsule executes from scratch** — any party with no hints can follow the instructions and reach the code's output
2. **The result is robust to independent environments** — package installs, library versions, hardware variance across N separate runs
3. **No agent fabricated or copied a result** — commit-reveal means each agent committed before seeing any other's `report.json`; copying would have required predicting the others' outputs

This is the honest value proposition for the objective setting. State it this way and it is hard to poke.

### Validator count is a parameter, not a constant

ValiChord places no architectural limit on the number of validators. The current demo uses three because that is a convenient number for illustration — not because the protocol requires it. A routine benchmark check might warrant three; a regulatory submission might warrant thirty; a contested safety evaluation might warrant more still.

The optimal number is an open empirical question. It depends on the expected agreement rate, the required statistical confidence, the cost per validation run, and the stakes of the claim. This is directly analogous to statistical power analysis in clinical trial design — a question for statisticians once the protocol is in wider use, not something the architecture should pre-answer.

---

## CORE-Bench solves ValiChord's hardest UX problem

ValiChord's deepest challenge is not the protocol — it's the input. For commit-reveal verification to work, a researcher has to structure their claim precisely enough that an independent party can verify it without guidance. That means:

- A clear, unambiguous statement of what is being claimed
- All materials needed to reproduce it
- Specific, pre-defined metrics the validator can check against

This is a lot to ask. The current demo sidesteps it by using free-text claims that web-search agents assess subjectively. For computational research the bar needs to be higher — verdicts should flow from running code, not forming opinions.

**A CodeOcean capsule is exactly what ValiChord needs as its input layer.**

A CORE-Bench capsule already contains everything:

| Capsule component | ValiChord role |
|---|---|
| Code + data | The claim, operationally defined |
| `README.md` / `REPRODUCING.md` | Instructions any independent party can follow |
| Specific numerical outputs | The pre-defined metrics validators check against |

A researcher who has a CodeOcean capsule has already done ValiChord's hardest UX work — without knowing it. They don't need to learn a new way of structuring their research. The capsule is the structured input.

### Automatic metric extraction closes the loop

CORE-Bench's agent can be run once by the researcher to extract the key numerical outputs from their code. Those outputs become the metrics the researcher commits to ValiChord before any validator starts. The researcher didn't manually define metrics — their code defined them.

The complete workflow:

```
1. Researcher runs their capsule once
        ↓
2. Agent extracts key numerical outputs → these become the committed metrics
        ↓
3. Researcher commits metrics + capsule reference to ValiChord
   (sealed before any validator starts)
        ↓
4. Three independent agents download the same capsule, run it in isolation,
   compare their outputs against the committed metrics, write report.json
        ↓
5. Each commits their report.json blind — no agent can see the others'
        ↓
6. Simultaneous reveal → HarmonyRecord
```

The capsule is the unit of commitment. The code is the claim. CORE-Bench provides the scaffolding that turns both into something any third party can independently verify.

This matters because it makes ValiChord accessible to computational researchers without asking them to change how they work. If they already have a reproducible capsule — the standard CodeOcean format, increasingly required by journals — they already have what ValiChord needs. The protocol wraps around their existing artefact rather than demanding a new one.

---

## How CORE-Bench's agent becomes a ValiChord validator

### What CORE-Bench's agent does

Given a research paper's code repository (a "capsule"), the agent:
1. Reads `README.md` or `REPRODUCING.md`
2. Installs dependencies and runs the code (hard difficulty)
3. Writes its findings as structured JSON to `/capsule/report.json`
4. The scorer compares `report.json` against the ground-truth answers

`report.json` looks like:
```json
{
  "What is the mean squared error on the test set?": 0.0423,
  "How many epochs until convergence?": 47,
  "What is the final accuracy?": 0.891
}
```

This structured output — the agent's answer to specific verifiable questions about the paper's results — is exactly what a ValiChord validator verdict needs to contain.

### The mapping

| CORE-Bench concept | ValiChord concept |
|---|---|
| Agent runs the capsule | Validator independently reproduces the claim |
| `report.json` | Validator's sealed verdict |
| Scorer checks against CORE-Bench ground truth | Separate optional overlay — not used for the ValiChord HarmonyRecord |
| ValiChord compares validators' reports against researcher's committed claim | The actual agreement computation |
| One agent, one run | Three agents, three independent runs |
| Result stored in log file | HarmonyRecord on DHT |

### Hard difficulty is required

- **Easy**: the agent is *given* the expected results and just reads them. No execution. The validator already knows the answer — defeats blinding.
- **Medium**: the agent runs a Docker command from `REPRODUCING.md`. Partial execution, but the instructions are standardised and may contain hints about expected outputs.
- **Hard**: the agent reads `README.md`, installs dependencies, and runs everything from scratch. This is the appropriate difficulty for ValiChord validation — the agent cannot see the expected outputs before committing.

---

## Integration architecture

```
Researcher                    Validator 1           Validator 2     ...   Validator N
    |                              |                     |                     |
    | Commits result hash          |                     |                     |
    |---> ValiChord DHT            |                     |                     |
    |                              |                     |                     |
    |      [30s DHT propagation]   |                     |                     |
    |                              |                     |                     |
    |                    [N CORE-Bench agents run in parallel, isolated]
    |                              |                     |                     |
    |                    Downloads capsule    Downloads capsule    Downloads capsule
    |                    Runs code (hard)     Runs code (hard)     Runs code (hard)
    |                    Writes report.json   Writes report.json   Writes report.json
    |                              |                     |                     |
    |                    Commits report hash to ValiChord DHT (each blind)
    |                              |                     |                     |
    |      [All N committed — ValiChord opens reveal phase]
    |                              |                     |                     |
    |                    Reveals report.json  Reveals             Reveals
    |                              |                     |                     |
    |      ValiChord compares all N reports against researcher's committed claim
    |      Writes HarmonyRecord to DHT:
    |        - ExactMatch: all validators reproduced, outputs match
    |        - WithinTolerance: validators reproduced, within numeric tolerance
    |        - Divergent: validators disagree or failed to reproduce
```
*(Diagram shows N=3 for clarity. The protocol supports any number of validators.)*

---

## What needs to be built

### 1. `demo/core_bench_validator.py`

An Inspect AI task wrapper that:
- Takes a capsule ID and task questions as input
- Runs the CORE-Bench hard-difficulty agent against the capsule
- Reads the `report.json` the agent produces
- Returns a structured ValiChord verdict

```python
async def run_core_bench_validator(
    capsule_id: str,
    task_questions: list[str],
    validator_url: str,
    external_hash_b64: str,
    discipline: dict,
    api_key: str,
) -> dict:
    """
    Run a CORE-Bench hard-difficulty agent and commit its findings to ValiChord.
    Returns the validator's verdict dict.
    """
    # 1. Download capsule
    # 2. Run inspect_ai eval with react() agent + bash tools (hard difficulty)
    # 3. Read report.json from the sandbox
    # 4. Format as ValiChord verdict
    # 5. POST /commit to validator_url
    # 6. Return verdict
```

### 2. `demo/core_bench_runner.py`

Orchestrator that runs N validators in parallel:
- Validator count is a runtime parameter, not hardcoded
- Each validator runs a separate Inspect AI eval against the same capsule in isolation
- Each commits before seeing others' results (enforced by ValiChord protocol)
- Initiates reveal phase once all N have committed
- Returns the HarmonyRecord

### 3. Verdict format adapter

Maps CORE-Bench `report.json` to ValiChord's verdict structure.

**Important design constraint:** validators commit their raw `report.json` *before* the researcher reveals. The comparison is researcher-claim-relative — each validator's output is compared against the researcher's committed metrics at reveal time. CORE-Bench ground truth (the encrypted HuggingFace dataset) is a separate, optional overlay for benchmark scoring and must not be passed into the commit-time adapter, as doing so would give validators knowledge of the expected answer before they commit, defeating blinding.

```python
def report_json_to_verdict(report: dict, tolerance_config: dict) -> dict:
    """
    Convert CORE-Bench report.json to a ValiChord validator verdict.
    Called at commit time — report contains only what the agent found;
    the researcher's claimed values are not available yet.

    outcome: 'Reproduced' | 'PartiallyReproduced' | 'FailedToReproduce'
             (Note: 'FailedToReproduce' not 'NotReproduced' — must match
             the AttestationOutcome enum in shared_types/src/lib.rs)
    confidence: 'High' | 'Medium' | 'Low'
    reasoning: summary of what the agent found and any execution issues
    metrics: list of per-question results for the HarmonyRecord
    """
```

**Tolerance function caveat:** the numeric tolerance (e.g., "within 0.5% counts as a match") is applied client-side in this Python adapter before the output becomes an outcome enum (`Reproduced` / `PartiallyReproduced` / `FailedToReproduce`). Once it is an enum, the tolerance decision is no longer visible or verifiable on-chain. For a system whose pitch is "no trust required at any layer," the tolerance configuration should be pinned and committed alongside the researcher's metrics — not buried in the adapter implementation. Otherwise a validator could quietly use a generous tolerance and nobody could check.

CORE-Bench ground truth scoring (comparing validator output against the benchmark's official answers) is a separate step that can run after the HarmonyRecord is written. It does not affect the ValiChord protocol.

### 4. Docker isolation for validators

Each validator agent runs in an isolated Docker sandbox (CORE-Bench already uses Docker via Inspect AI's sandbox feature). For the demo, three separate sandbox environments ensure the agents cannot share state.

---

## Demo specification

### What it shows

A live run of the full protocol on a specific CORE-Bench capsule. Three independent AI agents each reproduce a research paper's computational results in isolated Docker environments, commit their findings blind, reveal simultaneously, and produce a permanent HarmonyRecord. Three validators is a demonstration choice — the protocol imposes no upper limit, and the right number for any given claim is a function of its stakes and the statistical confidence required.

### Demo capsule selection criteria

For a demo that runs reliably:
- Python (not R) — faster install, more portable
- No GPU required
- Hard difficulty executable in under 5 minutes
- Produces specific numeric outputs (not just plots)
- Small capsule size (< 500 MB)

Good candidates from the CORE-Bench test set: capsules in the Social Sciences or Medical Sciences fields with simple Python pipelines.

### Demo output (target)

```
ValiChord + CORE-Bench — Computational Reproducibility Demo
============================================================

Paper: [paper title from capsule]
Capsule: capsule-XXXXXXX

[1/6] Researcher runs capsule, extracts key outputs, locks result...
      SHA-256 commitment sealed on DHT. Validators cannot see claimed values.
      ValidationRequest posted. Waiting for DHT propagation (30s)...

[2/6] Three independent agents downloading and running capsule...
      Validator 1: installing dependencies...
      Validator 2: installing dependencies...
      Validator 3: installing dependencies...

[3/6] Agents executing code and writing findings...
      Validator 1 committed ✓  (3m 12s, report.json written)
      Validator 2 committed ✓  (3m 47s, report.json written)
      Validator 3 committed ✓  (4m 01s, report.json written)
      All three committed blind. Reveal phase open.

[4/6] Simultaneous reveal...
      Researcher reveals: {"mean_squared_error": 0.0423, "accuracy": 0.891}
      Validator 1 reveals: {"mean_squared_error": 0.0423, "accuracy": 0.891}
      Validator 2 reveals: {"mean_squared_error": 0.0424, "accuracy": 0.891}
      Validator 3 reveals: {"mean_squared_error": 0.0423, "accuracy": 0.890}

[5/6] Agreement computed against researcher's committed claim...
      Outcome:   Reproduced (3/3 validators matched within tolerance)
      Agreement: WithinTolerance
      (Note: all-PartiallyReproduced panels reach WithinTolerance, not ExactMatch;
       ExactMatch requires Reproduced outcomes from all validators)

[6/6] HarmonyRecord written to distributed network.
      HarmonyRecord:   uhC8k...
      Shareable URL:   http://.../record?hash=uhC8k...

      Verify independently: curl "http://.../record?hash=uhC8k..."

============================================================
  Three agents ran the code independently.
  None could see the others' results before committing.
  The record cannot be changed. The capsule reproduces.
============================================================
```

### Infrastructure requirements

| Component | Status |
|---|---|
| ValiChord Holochain nodes (researcher + 3 validators) | ✅ Running on Oracle |
| Inspect AI | Needs installing in demo environment |
| Docker (for agent sandboxes) | Needs enabling in validator containers |
| CORE-Bench capsules | Public at `corebench.cs.princeton.edu/capsules/{id}.tar.gz` |
| CORE-Bench task questions + ground truth | Encrypted HuggingFace dataset — password in [siegelz/core-bench](https://github.com/siegelz/core-bench) |
| Anthropic API key | Already required for existing demo |

### Build estimate

| Task | Effort |
|---|---|
| Capsule selection — find one that runs clean in hard mode, no GPU, < 5 min, numeric output | 1–2 days |
| `core_bench_validator.py` — Inspect AI agent wrapper | 1–2 days |
| Verdict adapter (report.json → ValiChord verdict) + tolerance config design | 1 day |
| `core_bench_runner.py` — parallel orchestrator | 1 day |
| Docker isolation in demo containers | 0.5–1 day |
| End-to-end testing and reliability hardening | 1–2 days |
| **Total** | **~6–8 days** |

Capsule selection is on the critical path — everything else depends on a capsule that runs reliably. Start there.

---

## What to show inspect_evals

The demo makes one argument that neither system alone can make:

> *Three agents independently ran the code. None could see the others' results before they committed. The record on the distributed network shows they all got the same answer. You don't have to trust any one of them — you can verify the record yourself with a single curl command.*

This is demonstrably superior because:

1. **CORE-Bench without ValiChord**: tells you an AI can reproduce a paper. Doesn't prove the person reporting the score ran it fairly, or that a second party would agree.

2. **ValiChord without CORE-Bench**: proves structural independence. Current validators form opinions via web search — useful for general claims, but subjective.

3. **Combined**: three agents independently ran the code in isolation. None could copy another's `report.json` before committing — the commit-reveal protocol structurally prevents it. The result is not an opinion; it is what the code produces. The record is permanent.

Be precise when presenting this: for deterministic code the value of commit-reveal is not "prevented opinion anchoring" but "prevented result copying." That is a real guarantee and a defensible one — state it that way.

The demo is the proof.

---

## Relationship to the inspect_evals issue/PR

The integration doc and demo are what you bring to the conversation *after* the issue gets a positive response — not in the opening issue. The issue makes a low-friction schema ask (two optional YAML fields). The demo is what you offer when they ask "can you show us this working?"

The sequence:
1. Issue → schema fields accepted
2. Demo → proof the combined system works on a real CORE-Bench capsule
3. Collaboration → AISI's independent runs committed via ValiChord, HarmonyRecord in the register

---

*Last updated: 2026-05-29*
