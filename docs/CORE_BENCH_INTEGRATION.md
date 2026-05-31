# ValiChord + CORE-Bench Integration

## What this is

[CORE-Bench](https://arxiv.org/abs/2409.11363) tests whether an AI agent can computationally reproduce the results of scientific papers. [ValiChord](https://github.com/topeuph-ai/ValiChord) proves that independent parties reached the same conclusion without being able to coordinate after the fact. Neither system alone provides what both together do.

This document describes the integration architecture, the combined demo, and what needs to be built.

**The two systems already share an epistemic stance.** CORE-Bench defines its task as reproducing *"the results of running the code… not to ensure that the results reported in the paper are correct."* That is, almost verbatim, ValiChord's core meaning: a validator confirms it reached the **same result** as the researcher, not that the result is *correct*. This is the strongest opening for any conversation with the CORE-Bench / inspect_evals authors — you are not asking them to adopt a foreign concept, you are extending one they already built on.

**And the problem is real.** CORE-Bench's own headline finding is that the **best agent reproduced only ~21% of hard tasks.** Reproduction is hard and unreliable even for capable agents — which is exactly why independently verifying a *claimed* successful reproduction, with no copying between parties, is a missing and valuable trust layer.

---

## Why the combination does more than either alone

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

**Combined**: N agents execute the same code in isolated environments, each commits their `report.json` before seeing others' results, all reveal simultaneously. The verdict is objective (the code produces what it produces), the runs are blinded so no agent can copy another, and the outcome is permanently recorded on a distributed network no single party controls.

> ⚠️ The "multiple independent parties" row carries an asterisk: that guarantee is strongest when validators differ in operator, model, or environment. N invocations of the *same* agent reduce it to the anti-copying / determinism guarantee — still real, but narrower. See [Where the independence actually comes from](#where-the-independence-actually-comes-from--read-before-pitching-this) before making the independence claim out loud.

### What N independent runs actually prove

It is worth being precise here, because the value of commit-reveal is different for objective code than for subjective claims.

For deterministic code with fixed seeds and pinned dependencies, N correct runs will produce byte-identical output. Agreement is then near-tautological — there is no opinion to coordinate on. What commit-reveal protects against in the objective setting is not *"validator B anchored on validator A's interpretation"* but *"validator B copied validator A's `report.json` instead of running the code."* That is still a real and defensible guarantee, just a different one from the subjective case.

N independent hard-difficulty runs concretely prove:

1. **The capsule executes from scratch** — any party with no hints can follow the instructions and reach the code's output
2. **The result is robust to independent environments** — package installs, library versions, hardware variance across N separate runs
3. **No agent fabricated or copied a result** — commit-reveal means each agent committed before seeing any other's `report.json`; copying would have required predicting the others' outputs

This is the honest value proposition for the objective setting. State it this way and it is hard to poke.

### Where the independence actually comes from — read before pitching this

This is the question a sceptical evaluator (e.g. an Inspect maintainer) will ask first, so it must be answered head-on rather than glossed.

**N runs of the same model, by the same operator, are not independent — they are correlated.** Three invocations of the same agent on the same capsule mostly demonstrate determinism, plus the anti-copying guarantee above. They do *not* give you three independent corroborations in any deep sense: if the model has a systematic blind spot, all three share it.

Genuine independence comes from **diversity across the validator set**, not from the count alone:

- **Different operators** running the protocol on different machines/networks (the operational independence the Holochain layer already provides — separate conductors, separate source chains).
- **Different agent stacks or models** where feasible — so a shared model failure mode cannot pass undetected through all N.
- **Different environments** — package resolutions, library versions, hardware — which is what makes "robust to independent environments" a real claim.

The honest hierarchy of what you can claim, weakest to strongest:

1. **Same model, same operator, N times** → proves determinism + no result-copying. Real, narrow.
2. **Same model, different operators/environments** → adds environment-robustness and anti-fabrication.
3. **Different models/operators/environments** → adds defence against a shared model blind spot. This is the only configuration that supports the word "independent" without an asterisk.

The demo therefore should *not* run three identical agents and call them independent — vary the model or the operator across at least some validators, or explicitly state which of the three claims above is being made. Overclaiming independence to the one audience equipped to notice is the fastest way to lose the room.

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

CORE-Bench's agent can be run by the researcher to extract the key numerical outputs from their code. Because the match criterion is a 95% *prediction* interval (see below), the researcher runs the capsule **at least three times** — the spread across those runs defines the interval the metrics are committed with, not a bare point value. Those outputs become the metrics the researcher commits to ValiChord before any validator starts. The researcher didn't manually define metrics — their code defined them.

The complete workflow:

```
1. Researcher runs their capsule 3x (CORE-Bench's own protocol — needed to
   compute the 95% prediction interval, not just a point value)
        ↓
2. Agent extracts key numerical outputs from each run → the per-question
   mean + 95% prediction interval become the committed metrics
        ↓
3. Researcher commits metrics + intervals + capsule reference to ValiChord
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

### Harness contract — verified against `benchmark/benchmark.py`

The CORE-Bench harness hands a validator wrapper a clean, scriptable contract:

- **Capsule fetch:** `https://corebench.cs.princeton.edu/capsules/{capsule_id}.tar.gz`, extracted to `environment/{capsule_id}/` (code / data / results subdirs).
- **Difficulty is set by deletion.** Hard removes both the `results/` directory *and* the `environment/` + `REPRODUCING.md` reproduction guides — the agent gets only code, data, and the README / `task_prompt`. (Medium keeps the Dockerfile + REPRODUCING.md; easy keeps `results/`.) Hard is what we want.
- **Agent invocation:** the harness runs `bash /capsule/{agent_script}` under a timeout in Docker; the agent writes `report.json` anywhere under `environment/`, and the harness locates it after the run.
- **Scoring:** `eval_result_json(gt_result, result_report)` — `gt_result` is the dataset entry's `results` list, `result_report` is the agent's `report.json`.
- **Dataset entry schema (assert-enforced in the harness, confirmed against the decrypted `core_test.json`):** exactly
  `{field, language, capsule_title, capsule_id, capsule_doi, task_prompt, results}`.
  `task_prompt` carries the questions; `results` is a **list of the three ground-truth runs**, each a dict that maps the full **question text to its answer value** — the question *is* the key. A key whose text contains `'fig'` is a vision question. The 95% prediction interval is computed across the three runs. Verified example (`capsule-5507257`):
  ```json
  // results = [run1, run2, run3]; each run is a dict like:
  {"Report the accuracy of the multitask learning model at the end of training on the test set.": 96.12499135323452}
  ```

For ValiChord, `core_bench_validator.py` reuses the harness's own capsule fetch + hard-mode setup + `report.json` discovery, then routes the resulting report through `report_json_to_verdict` instead of (or alongside) `eval_result_json`. The researcher side runs the same path three times to establish the committed interval.

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

> **STATUS (2026-05-31): BUILT on branch `core-bench-demo`.** Implemented against
> the **inspect_evals `core_bench` task** (not the AutoGPT harness) — its
> `react`+`bash` agent is model-agnostic, so validators run different models
> (Claude/GPT-4o/Gemini) trivially. Modules below map to: `core_bench_validator.py`
> (eval wrapper), `core_bench_runner.py` (parallel orchestrator + CLI),
> `report_to_verdict.py` (verdict adapter), and a custom **capture scorer** that
> lifts `report.json` without reading ground truth. Inspect's per-sample Docker
> sandbox provides isolation. **Verified live:** `capsule-0851068` reproduces
> exactly (`0.9157952669235003`); the full HarmonyRecord run is pending a 64 GB+
> machine (sandboxes are ~14 GB each). Full run guide: `demo/CORE_BENCH_DEMO.md`.

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

**Important design constraint:** validators commit their raw `report.json` *before* the researcher reveals. The comparison is researcher-claim-relative — each validator's output is compared against the researcher's committed metrics at reveal time. CORE-Bench ground truth — the official answers and their prediction intervals, distributed as the GPG-encrypted dataset `benchmark/dataset/core_test.json.gpg` (password `reproducibility`) — is a separate, optional overlay for benchmark scoring and **must not be passed into the commit-time adapter**: doing so would hand validators the expected answer before they commit, defeating blinding. Because that ground truth is trivially decryptable, this is an enforceable discipline the demo harness must respect, not a hypothetical.

```python
def report_json_to_verdict(report: dict, prediction_intervals: dict) -> dict:
    """
    Convert CORE-Bench report.json to a ValiChord validator verdict.
    Called at commit time — report contains only what the agent found;
    the researcher's claimed values are not available yet.

    prediction_intervals: the per-question 95% prediction intervals committed
        on-chain by the researcher (the same notion CORE-Bench uses for scoring).
        The match test is "does the agent's value fall inside the interval?",
        and the interval is part of the committed claim — not a private knob.

    outcome: 'Reproduced' | 'PartiallyReproduced' | 'FailedToReproduce'
             (Note: 'FailedToReproduce' not 'NotReproduced' — must match
             the AttestationOutcome enum in shared_types/src/lib.rs)
    confidence: 'High' | 'Medium' | 'Low'
    reasoning: summary of what the agent found and any execution issues
    metrics: list of per-question results for the HarmonyRecord
    """
```

**Match criterion — use CORE-Bench's 95% prediction interval, not an arbitrary tolerance.** CORE-Bench does not score numeric answers by exact match or a hand-picked percentage. It ran each capsule **three times manually** and accepts an answer if it falls **within the 95% prediction interval** of those runs, for *every* question in the task (a task counts only if all its questions pass; only ~17 of the benchmark's ~181 questions are stochastic at all). ValiChord should adopt the same principled criterion rather than inventing one: the researcher's committed metrics should carry the per-question 95% prediction interval, and that interval should be **committed on-chain alongside the metrics** — not applied silently in the Python adapter. Otherwise the match decision is invisible and unverifiable, and a validator could quietly widen the interval with nobody able to check. Pinning the interval at commit time is what lets the "no trust required at any layer" claim actually hold.

*Verified against `benchmark/evaluations.py` (`eval_result_json`):* the interval is computed on the fly from the list of ground-truth runs, not stored as bounds — `t_value = t.ppf(0.975, n-1)`, then `mean ± t_value · std · √(1 + 1/n)`, and an answer passes iff `lower ≤ reported[key] ≤ upper`. Vision questions are identified by the substring `'fig'` in the question key, and a task passes only if every written *and* every vision question is in-interval. Two consequences for the adapter: (a) the researcher commits either the list of their runs or the derived per-question interval — both reduce to the same test; (b) the "no vision questions" capsule filter is mechanical — drop any capsule whose result keys contain `'fig'`.

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
- Small capsule size (< 500 MB)
- **Text/numeric questions only — no vision questions.** CORE-Bench includes vision-based questions whose answers are read from figures and plots. Reading a chart is a model-judgment step, not objective code output — it reintroduces exactly the subjectivity the computational path is meant to remove. Screen these out so "the verdict is what the code produces, not an opinion" stays true.
- **In the reproducible minority, and pre-verified.** The best agent reproduced only ~21% of hard tasks; a randomly chosen capsule will most likely yield `FailedToReproduce` — honest, but not the first impression you want. Pick a capsule and confirm all three independent runs reproduce it reliably *before* wiring it into the demo.

Verified against the decrypted `core_test.json` (a 45-task slice): **34 of 45 tasks contain a vision question** and are disqualified; only 11 are vision-free, split roughly half Python / half R. The strongest first-demo candidates — Python, no vision, a single numeric question — are:

| capsule_id | field | questions |
|---|---|---|
| `capsule-5507257` | Computer Science | 1 (model accuracy) |
| `capsule-6003668` | Computer Science | 1 (continual learning) |
| `capsule-9660931` | Computer Science | 1 (deep-learning library) |
| `capsule-0851068` | Medical Sciences | 1 (MLP COVID/skin classification) |

A single-question, vision-free, Python capsule yields one numeric value and one 95% interval — an unambiguous Reproduced/Failed with nothing for a skeptic to wave away. The one filter left is empirical, and only a test run settles it: confirm the chosen capsule actually reproduces in hard mode, in under 5 minutes, with no GPU (recall the 21%).

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
      Validator 1 reveals: {"mean_squared_error": 0.0423, "accuracy": 0.891}  → Reproduced
      Validator 2 reveals: {"mean_squared_error": 0.0424, "accuracy": 0.889}  → Reproduced (within tolerance)
      Validator 3 reveals: {"mean_squared_error": 0.0451, "accuracy": 0.872}  → PartiallyReproduced

[5/6] Agreement computed against researcher's committed claim...
      Per-validator outcome: 2 Reproduced, 1 PartiallyReproduced
      Agreement: WithinTolerance
      (full_rate = 2/3 = 67% → below the 90% ExactMatch threshold;
       any_rate  = 3/3 = 100% → ≥70% → WithinTolerance.
       ExactMatch needs a Reproduced outcome from ~all validators, not just
       within-tolerance partials — see shared_types::derive_agreement_level.
       If all three had landed Reproduced, this would read ExactMatch.)

[6/6] HarmonyRecord written to distributed network.
      HarmonyRecord:   uhC8k...
      Shareable URL:   http://.../record?hash=uhC8k...

      Verify independently: curl "http://.../record?hash=uhC8k..."

============================================================
  Three agents ran the code in isolated environments.
  None could see the others' results before committing.
  The record cannot be changed. The capsule reproduces, within tolerance.
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

## What to show inspect_evals — framing matters

Lead with composition, not competition. Inspect/CORE-Bench is the **execution layer** — it runs the reproduction. ValiChord is a **verification layer** that sits on top — it makes the reproduction's result trustworthy to a third party who wasn't in the room. These compose; one does not replace or improve the other. Pitched as "you built the thing that runs it, here's a thing that makes the result independently checkable," it is a collaboration story. Pitched as "superior to what you have," it reads as a threat to the people who built something good — and they are exactly the people who can spot an overclaim.

The honest gap it fills (not a feature AISI built worse — a category Inspect has *no* mechanism for): a `.eval` log is single-author and self-attested. Nothing in it prevents the producer from re-running until the number looks right, or proves a second party would get the same output. There is no multi-party, blinded, tamper-evident layer anywhere in the eval-framework space.

The one argument the combination makes that neither part can:

> *Several agents ran the code in isolated environments. None could see the others' results before they committed. The record on a network no single party controls shows what each one got. You don't have to trust any of them — you can verify the record yourself with a single curl command.*

Why each part alone falls short:

1. **CORE-Bench alone**: tells you an AI *can* reproduce a paper. Gives you one self-reported result — useful as a benchmark *score*, but not usable as *evidence* a third party would trust, because nothing proves it came from a fair, independent run.

2. **ValiChord alone**: proves structural independence and non-copying. But the current demo validators form opinions via web search — fine for general claims, subjective for computational ones.

3. **Combined**: the verdict is what the code produces (objective), the runs are isolated and blinded (no `report.json` copying), and the outcome is permanent and independently verifiable. A CORE-Bench score becomes a CORE-Bench *attestation*.

Two precision rules when presenting, both load-bearing with this audience:

- **Claim the right guarantee.** For deterministic code the value of commit-reveal is *prevented result-copying and fabrication*, not *prevented opinion-anchoring*. Real and defensible — state it narrowly.
- **Don't overclaim independence.** See "Where the independence actually comes from" above. Three identical agents are not three independent parties; say what the demo's configuration actually supports.

The demo is the proof. It is also the thing you bring *first* — see the sequencing note below.

---

## Relationship to the inspect_evals issue/PR — lead with the demo, not the issue

The earlier plan had this backwards: it gated the demo behind a schema-change issue getting a positive response. That makes the strongest asset (a working integration — a *gift*) hostage to the weakest one (a request to add two YAML fields — easy for a maintainer to defer or ignore). If the issue stalls, the CORE-Bench conversation never even opens.

Two facts make the inversion obvious:

- **The demo needs nothing from inspect_evals to exist.** Run their existing CORE-Bench agent on a capsule, feed the outputs through ValiChord's commit-reveal, produce a HarmonyRecord. The `valichord_attestation_uri` schema field is about making the integration *discoverable and durable later* — it is not a prerequisite for proving it *works now*. The dependency was self-imposed.
- **Show-don't-ask beats ask-don't-show.** Maintainers engage with artifacts far more than with feature requests — especially on-topic ones, and "did the agent really reproduce it or copy/fabricate?" is the exact question CORE-Bench exists to probe.

The corrected sequence:

1. **Build the minimal standalone demo** — one real capsule through commit-reveal, shareable HarmonyRecord, no inspect_evals dependency. This de-risks everything: you are no longer waiting on anyone's response to start the conversation.
2. **Open warm, not cold.** A note to an existing contact (e.g. via LinkedIn) pointing at the working demo outperforms a fresh public issue — and lets you pressure-test the framing (and the independence/determinism caveats above) privately before anything is on the public record.
3. **Demote the schema field to the follow-on.** Once a working thing points at it, "would a register field make this discoverable to others?" is a far easier yes than the same ask in a vacuum.
4. **Collaboration** → AISI's independent runs committed via ValiChord, HarmonyRecord referenced from the register.

The schema PR isn't wasted work — it's just the wrong opening move. Lead with the gift; let it earn the conversation.

---

*Last updated: 2026-05-30*
