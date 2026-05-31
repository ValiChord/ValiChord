# CORE-Bench × ValiChord CLI Demo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A fully-local CLI demo that runs one real CORE-Bench capsule through ValiChord's blind commit-reveal protocol with three mixed-model AI validators, producing a HarmonyRecord whose replication verdict is decided by recomputable arithmetic, not LLM opinion.

**Architecture:** Reuse the inspect_evals `core_bench` task (model-agnostic `react`+`bash`) with a **custom capture scorer** that lifts each validator's `report.json` out of its sandbox. A pure adapter maps reports → ValiChord verdicts (committed execution-success outcome, blind) and computes the post-reveal numeric match against the researcher's sealed interval. An orchestrator drives commit-reveal through the existing demo node HTTP APIs against the existing 5-conductor docker-compose stack.

**Tech Stack:** Python 3 (demo/ flat modules), `inspect_ai` + `inspect_evals` (pinned), `scipy`/`statistics` for the prediction interval, pytest. Existing: `demo/docker-compose.yml`, the node `.mjs` HTTP APIs, `demo/agreement.py`, `demo/demo_runner.py` helpers.

**Spec:** `docs/superpowers/specs/2026-05-31-core-bench-demo-design.md`

---

## Conventions for this plan

- `demo/` modules are **flat** (no package): import siblings directly, e.g. `from agreement import derive_agreement_level`. Tests live in `demo/test_*.py` and run with `pytest` from inside `demo/`.
- Run all commands from `/workspaces/ValiChord/demo/` unless stated otherwise.
- Inspect-dependent tests start with `pytest.importorskip("inspect_ai")` so they skip cleanly where the heavy deps aren't installed; the pure `report_to_verdict` tests have no such guard and always run.
- Commit after every task (frequent commits). Branch is already `core-bench-demo`.

---

## File structure

| File | Responsibility |
|---|---|
| `demo/requirements.txt` (modify) | add `inspect_ai`, `inspect_evals`, `scipy` pins |
| `demo/report_to_verdict.py` (create) | **pure**: committed-claim derivation, interval match, validator verdict (blind), reveal-time numeric panel |
| `demo/core_bench_capture_scorer.py` (create) | Inspect scorer that captures `report.json`; never reads ground truth |
| `demo/core_bench_validator.py` (create) | build the validator Task, run one eval, extract the captured report; researcher N-run claim |
| `demo/core_bench_runner.py` (create) | orchestrator + CLI: key validation → researcher claim → 3 mixed-model validators → commit-reveal → HarmonyRecord → numeric panel |
| `demo/core_bench_spike.py` (create) | Phase-0 helper: run one capsule/one model, print value + timing for capsule selection |
| `demo/CORE_BENCH_DEMO.md` (create) | run instructions, model/key matrix, honest independence claim, skeptic-proof verification |
| `demo/test_report_to_verdict.py` (create) | unit tests for the pure adapter (always run) |
| `demo/test_core_bench_capture_scorer.py` (create) | scorer tests + blinding guard (importorskip) |
| `demo/test_core_bench_validator.py` (create) | task-build (blinding guard) + extraction + claim tests, eval mocked (importorskip) |
| `demo/test_core_bench_runner.py` (create) | orchestration wiring + fail-fast key validation, evals + HTTP mocked |

---

## Task 0: Dependencies + import smoke test

**Files:**
- Modify: `demo/requirements.txt`
- Create: `demo/test_core_bench_imports.py`

- [ ] **Step 1: Read the current requirements file**

Run: `cat demo/requirements.txt`
Note the existing contents so the append doesn't clobber them.

- [ ] **Step 2: Append the new dependencies**

Append these lines to `demo/requirements.txt` (keep existing lines intact):

```
# CORE-Bench demo (inspect_evals integration)
# Pinned to a verified main commit: the PUBLISHED release (0.3.103) lags main and
# uses basic_agent (not react), lacks filter_out_vision, and lacks CAPSULE_CHECKSUMS
# — all of which this demo relies on. Verified against this exact SHA.
inspect_ai>=0.3.50
inspect_evals @ git+https://github.com/UKGovernmentBEIS/inspect_evals@34617f8b01356c6b802d429fbfaca97c9eaf1386
scipy>=1.11
```

> The git+SHA pin is deliberate and fully reproducible — do NOT fall back to the
> PyPI release, whose CORE-Bench API differs (it would break Tasks 4–6). The smoke
> test below guards the exact import surface; if it fails on the pinned SHA, report
> BLOCKED rather than swapping in the published package.

- [ ] **Step 3: Install**

Run: `pip install -r demo/requirements.txt`
Expected: completes; `inspect_ai`, `inspect_evals`, `scipy` resolved.

- [ ] **Step 4: Write the import smoke test**

Create `demo/test_core_bench_imports.py`:

```python
"""Guards the exact inspect_evals import surface the demo depends on.
If inspect_evals reorganises these, this test fails loudly and the pins
in requirements.txt must be revisited."""
import pytest

pytest.importorskip("inspect_ai")
pytest.importorskip("inspect_evals")


def test_inspect_evals_surface_importable():
    from inspect_evals.core_bench.dataset import (  # noqa: F401
        read_core_bench_dataset,
        CAPSULE_CHECKSUMS,
    )
    from inspect_evals.core_bench.core_bench import default_solver  # noqa: F401
    from inspect_evals.core_bench.utils import (  # noqa: F401
        calculate_prediction_intervals,
        categorize_keys,
    )


def test_inspect_ai_scorer_surface_importable():
    from inspect_ai.scorer import (  # noqa: F401
        scorer, Scorer, Score, Target, accuracy, CORRECT, INCORRECT,
    )
    from inspect_ai.solver import TaskState  # noqa: F401
    from inspect_ai.util import sandbox  # noqa: F401
```

- [ ] **Step 5: Run the smoke test**

Run: `cd demo && python3 -m pytest test_core_bench_imports.py -v`
Expected: both tests PASS (or SKIP if inspect not installed — but Step 3 installed it, so PASS).

- [ ] **Step 6: Commit**

```bash
git add demo/requirements.txt demo/test_core_bench_imports.py
git commit -m "build(core-bench): add inspect_ai/inspect_evals deps + import smoke test"
```

---

## Task 1: `report_to_verdict.py` — claim derivation + interval match (numeric core)

**Files:**
- Create: `demo/report_to_verdict.py`
- Test: `demo/test_report_to_verdict.py`

- [ ] **Step 1: Write the failing tests**

Create `demo/test_report_to_verdict.py`:

```python
import math
import pytest
from report_to_verdict import derive_committed_claim, match_value

Q = "Report the accuracy of the model."


def test_deterministic_runs_use_explicit_tolerance():
    runs = [{Q: 96.125}, {Q: 96.125}, {Q: 96.125}]
    claim = derive_committed_claim(runs, rel_tolerance=0.001)
    spec = claim[Q]
    assert spec["value"] == pytest.approx(96.125)
    assert spec["basis"] == "explicit_tolerance"
    # ±0.1% of 96.125
    assert spec["lower"] == pytest.approx(96.125 * (1 - 0.001))
    assert spec["upper"] == pytest.approx(96.125 * (1 + 0.001))


def test_stochastic_runs_use_prediction_interval():
    runs = [{Q: 0.982}, {Q: 0.815}, {Q: 0.978}]
    claim = derive_committed_claim(runs, rel_tolerance=0.001)
    spec = claim[Q]
    assert spec["basis"] == "prediction_interval"
    # interval is symmetric about the mean and strictly wider than the spread
    mean = (0.982 + 0.815 + 0.978) / 3
    assert spec["value"] == pytest.approx(mean)
    assert spec["lower"] < min(0.982, 0.815, 0.978)
    assert spec["upper"] > max(0.982, 0.815, 0.978)


def test_match_value_boundaries():
    assert match_value(5.0, 4.0, 6.0) is True
    assert match_value(4.0, 4.0, 6.0) is True   # inclusive lower
    assert match_value(6.0, 4.0, 6.0) is True   # inclusive upper
    assert match_value(3.999, 4.0, 6.0) is False
    assert match_value("5.0", 4.0, 6.0) is True  # string coercion
    assert match_value("not a number", 4.0, 6.0) is False
```

- [ ] **Step 2: Run to verify failure**

Run: `cd demo && python3 -m pytest test_report_to_verdict.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'report_to_verdict'`.

- [ ] **Step 3: Implement the numeric core**

Create `demo/report_to_verdict.py`:

```python
"""Pure adapter between CORE-Bench report.json and ValiChord verdicts.

No Holochain, no network, no Inspect — just arithmetic and dict-shaping, so it
is fully unit-testable. Two sides:

  * researcher side  — derive the committed claim (value + 95% prediction
    interval, or an explicit tolerance for deterministic capsules) from N runs.
  * validator side   — map a (blind) report.json to a committed verdict, and
    (after reveal) compute the numeric match against the researcher's claim.

The prediction-interval formula matches inspect_evals
core_bench.utils.calculate_prediction_intervals exactly (verified in tests):
    margin = t.ppf(0.975, n-1) * stdev(values, ddof=1) * sqrt(1 + 1/n)
"""
import math
import statistics
from typing import Optional

from scipy.stats import t as _t


def derive_committed_claim(runs: list[dict], rel_tolerance: float = 0.001) -> dict:
    """runs: list of {question: numeric}. Returns {question: spec} where spec is
    {value, lower, upper, basis}. For >=2 runs with non-zero spread the bounds
    are the 95% prediction interval; otherwise an explicit +/- rel_tolerance
    band (so the researcher always commits a concrete, on-chain interval)."""
    if not runs:
        raise ValueError("derive_committed_claim requires at least one run")
    questions = list(runs[0].keys())
    claim = {}
    for q in questions:
        values = [float(r[q]) for r in runs]
        mean = statistics.mean(values)
        n = len(values)
        margin = 0.0
        basis = "explicit_tolerance"
        if n >= 2:
            std = statistics.stdev(values)  # sample std, ddof=1
            if std > 0.0:
                t_value = _t.ppf(0.975, n - 1)
                margin = t_value * std * math.sqrt(1 + 1 / n)
                basis = "prediction_interval"
        if margin == 0.0:
            margin = abs(mean) * rel_tolerance
            basis = "explicit_tolerance"
        claim[q] = {
            "value": mean,
            "lower": mean - margin,
            "upper": mean + margin,
            "basis": basis,
        }
    return claim


def match_value(value, lower: float, upper: float) -> bool:
    """True iff value is inside [lower, upper]. Non-numeric -> False."""
    try:
        v = float(str(value).replace("%", "").strip())
    except (ValueError, TypeError):
        return False
    return lower <= v <= upper
```

- [ ] **Step 4: Run to verify pass**

Run: `cd demo && python3 -m pytest test_report_to_verdict.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add demo/report_to_verdict.py demo/test_report_to_verdict.py
git commit -m "feat(core-bench): committed-claim derivation + interval match"
```

---

## Task 2: `report_to_verdict.py` — validator verdict (blind) + numeric panel + consistency

**Files:**
- Modify: `demo/report_to_verdict.py`
- Modify: `demo/test_report_to_verdict.py`

- [ ] **Step 1: Write the failing tests (append)**

Append to `demo/test_report_to_verdict.py`:

```python
from report_to_verdict import report_to_verdict, build_numeric_panel

REQ = [Q]


def test_verdict_valid_numeric_report_is_reproduced():
    v = report_to_verdict({Q: 96.125}, REQ)
    assert v["outcome"] == "Reproduced"
    assert v["metrics"][0]["metric_name"] == Q
    assert v["metrics"][0]["produced_value"] == "96.125"
    # blind: no researcher value known at commit time
    assert v["metrics"][0]["expected_value"] == ""
    assert v["metrics"][0]["within_tolerance"] is False


def test_verdict_no_report_is_failed():
    v = report_to_verdict(None, REQ)
    assert v["outcome"] == "FailedToReproduce"
    assert v["metrics"] == []


def test_verdict_missing_key_is_unable_to_assess():
    v = report_to_verdict({"some other question": 1.0}, REQ)
    assert v["outcome"] == "UnableToAssess"


def test_verdict_non_numeric_value_is_unable_to_assess():
    v = report_to_verdict({Q: "ran out of time"}, REQ)
    assert v["outcome"] == "UnableToAssess"


def test_numeric_panel_marks_match_and_divergence():
    claim = derive_committed_claim([{Q: 96.125}, {Q: 96.125}, {Q: 96.125}])
    panel = build_numeric_panel(
        [("V1-claude", {Q: 96.125}), ("V2-gpt4o", {Q: 50.0})], claim
    )
    assert panel[0]["rows"][0]["match"] is True
    assert panel[1]["rows"][0]["match"] is False
    assert panel[1]["rows"][0]["value"] == pytest.approx(50.0)


def test_interval_matches_inspect_evals():
    """Pin our prediction interval to inspect_evals' own implementation."""
    pytest.importorskip("inspect_evals")
    from inspect_evals.core_bench.utils import calculate_prediction_intervals
    runs = [{Q: 0.982}, {Q: 0.815}, {Q: 0.978}]
    ours = derive_committed_claim(runs)[Q]
    theirs_lo, theirs_hi = calculate_prediction_intervals(runs, [Q])[Q]
    assert ours["lower"] == pytest.approx(theirs_lo)
    assert ours["upper"] == pytest.approx(theirs_hi)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd demo && python3 -m pytest test_report_to_verdict.py -v`
Expected: FAIL — `ImportError: cannot import name 'report_to_verdict'`.

- [ ] **Step 3: Implement verdict + panel (append to module)**

Append to `demo/report_to_verdict.py`:

```python
def _coerce_number(raw) -> Optional[float]:
    try:
        return float(str(raw).replace("%", "").strip())
    except (ValueError, TypeError):
        return None


def report_to_verdict(report: Optional[dict], required_keys: list[str]) -> dict:
    """Map a (blind) report.json to a committed ValiChord verdict.

    Outcome is EXECUTION-SUCCESS only -- the validator cannot compare against the
    researcher's sealed value at commit time, so this never encodes a match.
    The researcher-relative match is computed at reveal by build_numeric_panel.

      valid numeric report, all keys present -> Reproduced
      no report / unparseable                -> FailedToReproduce
      parsed but a required key missing/non-numeric -> UnableToAssess
    """
    if not report:
        return {
            "outcome": "FailedToReproduce",
            "confidence": "High",
            "reasoning": "Agent produced no valid report.json -- the capsule did not reproduce.",
            "metrics": [],
        }
    metrics = []
    ok = True
    for k in required_keys:
        raw = report.get(k, None)
        num = _coerce_number(raw)
        if k not in report or num is None:
            ok = False
        metrics.append({
            "metric_name": k,
            # produced_value is the validator's OWN reproduced value; expected
            # is blank because the researcher's claim is sealed at commit time.
            "produced_value": ("" if raw is None else (repr(num) if num is not None else str(raw))),
            "expected_value": "",
            "within_tolerance": False,
        })
    if not ok:
        return {
            "outcome": "UnableToAssess",
            "confidence": "Medium",
            "reasoning": "report.json was produced but a required answer was missing or non-numeric.",
            "metrics": metrics,
        }
    return {
        "outcome": "Reproduced",
        "confidence": "High",
        "reasoning": "Agent independently executed the capsule from scratch and produced a valid numeric result.",
        "metrics": metrics,
    }


def build_numeric_panel(validator_reports: list, committed_claim: dict) -> list:
    """Reveal-time match. validator_reports: list of (label, report_dict|None).
    Returns per-validator rows comparing each value against the committed
    interval -- the verifiable, recomputable headline of the demo."""
    panel = []
    for label, report in validator_reports:
        rows = []
        for q, spec in committed_claim.items():
            raw = None if not report else report.get(q, None)
            num = _coerce_number(raw)
            rows.append({
                "question": q,
                "value": num,
                "lower": spec["lower"],
                "upper": spec["upper"],
                "match": False if num is None else match_value(num, spec["lower"], spec["upper"]),
            })
        panel.append({"validator": label, "rows": rows})
    return panel
```

Note `repr(num)` keeps full float precision in the committed metric (so `96.125` round-trips, not a truncated display string).

- [ ] **Step 4: Run to verify pass**

Run: `cd demo && python3 -m pytest test_report_to_verdict.py -v`
Expected: all tests PASS (the consistency test runs because Task 0 installed inspect_evals).

- [ ] **Step 5: Commit**

```bash
git add demo/report_to_verdict.py demo/test_report_to_verdict.py
git commit -m "feat(core-bench): blind validator verdict + reveal-time numeric panel"
```

---

## Task 3: `core_bench_capture_scorer.py` — capture report.json, never read ground truth

**Files:**
- Create: `demo/core_bench_capture_scorer.py`
- Test: `demo/test_core_bench_capture_scorer.py`

- [ ] **Step 1: Write the failing tests**

Create `demo/test_core_bench_capture_scorer.py`:

```python
import asyncio
import json
import pytest

pytest.importorskip("inspect_ai")
from core_bench_capture_scorer import read_report_from_sandbox


class _FakeSandbox:
    def __init__(self, content, raise_not_found=False):
        self._content = content
        self._raise = raise_not_found
        self.read_calls = []

    async def read_file(self, path):
        self.read_calls.append(path)
        if self._raise:
            raise FileNotFoundError(path)
        return self._content


def test_reads_and_parses_report():
    sb = _FakeSandbox(json.dumps({"Q": 96.125}))
    report = asyncio.run(read_report_from_sandbox(sb))
    assert report == {"Q": 96.125}
    assert sb.read_calls == ["report.json"]


def test_missing_report_returns_none():
    sb = _FakeSandbox("", raise_not_found=True)
    assert asyncio.run(read_report_from_sandbox(sb)) is None


def test_invalid_json_returns_none():
    sb = _FakeSandbox("not json {")
    assert asyncio.run(read_report_from_sandbox(sb)) is None


def test_blinding_guard_source_never_references_ground_truth():
    """The capture path must not read state.metadata['results'] (the sealed
    ground truth). Enforce structurally by scanning the source."""
    import inspect, core_bench_capture_scorer as mod
    src = inspect.getsource(mod)
    assert "results" not in src or "report.json" in src  # sanity: file is about reports
    assert 'metadata["results"]' not in src
    assert "metadata['results']" not in src
```

- [ ] **Step 2: Run to verify failure**

Run: `cd demo && python3 -m pytest test_core_bench_capture_scorer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core_bench_capture_scorer'`.

- [ ] **Step 3: Implement the scorer**

Create `demo/core_bench_capture_scorer.py`:

```python
"""Inspect scorer that CAPTURES the agent's report.json into the eval log.

Unlike inspect_evals' stock evaluate_task_questions, this scorer does NOT read
the sealed ground truth (state.metadata["results"]). It only lifts the agent's
own report.json out of the sandbox so the orchestrator can commit it blind.
Ground-truth comparison is a separate, post-reveal overlay -- never here."""
import json
from typing import Optional

from inspect_ai.scorer import CORRECT, INCORRECT, Score, Scorer, Target, accuracy, scorer
from inspect_ai.solver import TaskState
from inspect_ai.util import sandbox


async def read_report_from_sandbox(sb) -> Optional[dict]:
    """Read and parse /capsule report.json from a sandbox-like object.
    Returns the dict, or None if absent/unparseable. Pure of ground truth."""
    try:
        raw = await sb.read_file("report.json")
    except FileNotFoundError:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


@scorer(metrics=[accuracy()])
def capture_report() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        report = await read_report_from_sandbox(sandbox())
        if report is None:
            return Score(
                value=INCORRECT,
                answer="",
                explanation="report.json missing or unparseable",
                metadata={"report": None},
            )
        return Score(
            value=CORRECT,
            answer=json.dumps(report),
            explanation="captured report.json",
            metadata={"report": report},
        )
    return score
```

- [ ] **Step 4: Run to verify pass**

Run: `cd demo && python3 -m pytest test_core_bench_capture_scorer.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add demo/core_bench_capture_scorer.py demo/test_core_bench_capture_scorer.py
git commit -m "feat(core-bench): capture scorer that lifts report.json (blind to ground truth)"
```

---

## Task 4: `core_bench_validator.py` — build task, extract report, run eval, researcher claim

**Files:**
- Create: `demo/core_bench_validator.py`
- Test: `demo/test_core_bench_validator.py`

- [ ] **Step 1: Write the failing tests**

Create `demo/test_core_bench_validator.py`:

```python
from unittest import mock
import pytest

pytest.importorskip("inspect_ai")
pytest.importorskip("inspect_evals")
import core_bench_validator as cbv


def test_build_validator_task_uses_hard_blind_filters():
    """Blinding guard: hard difficulty + no-GPU + no-vision + the one capsule."""
    captured = {}

    def fake_read(**kwargs):
        captured.update(kwargs)
        return "DATASET"

    with mock.patch.object(cbv, "read_core_bench_dataset", fake_read), \
         mock.patch.object(cbv, "default_solver", lambda **k: "SOLVER"), \
         mock.patch.object(cbv, "capture_report", lambda: "SCORER"), \
         mock.patch.object(cbv, "Task", lambda **k: k) as _:
        task = cbv.build_validator_task("capsule-5507257")

    assert captured["difficulty"] == "hard"
    assert captured["capsule_ids"] == ["capsule-5507257"]
    assert captured["filter_out_gpu"] is True
    assert captured["filter_out_vision"] is True
    assert task["scorer"] == "SCORER"


def test_extract_report_from_log_reads_score_metadata():
    fake_score = mock.Mock(metadata={"report": {"Q": 1.0}})
    fake_sample = mock.Mock(scores={"capture_report": fake_score})
    fake_log = mock.Mock(samples=[fake_sample])
    assert cbv.extract_report_from_log([fake_log]) == {"Q": 1.0}


def test_extract_report_from_log_handles_no_samples():
    fake_log = mock.Mock(samples=[])
    assert cbv.extract_report_from_log([fake_log]) is None


def test_run_validator_eval_returns_report():
    with mock.patch.object(cbv, "build_validator_task", lambda cid: "TASK"), \
         mock.patch.object(cbv, "inspect_eval", lambda *a, **k: ["LOG"]) as ev, \
         mock.patch.object(cbv, "extract_report_from_log", lambda logs: {"Q": 2.0}):
        report = cbv.run_validator_eval("capsule-5507257", "anthropic/claude-opus-4-8")
    assert report == {"Q": 2.0}


def test_run_researcher_claim_runs_n_times_and_derives():
    calls = []

    def fake_eval(cid, model):
        calls.append(model)
        return {"Q": 96.125}

    with mock.patch.object(cbv, "run_validator_eval", fake_eval):
        claim = cbv.run_researcher_claim("capsule-5507257", "anthropic/claude-opus-4-8", n_runs=3)
    assert len(calls) == 3
    assert claim["Q"]["value"] == pytest.approx(96.125)


def test_run_researcher_claim_raises_on_failed_run():
    with mock.patch.object(cbv, "run_validator_eval", lambda c, m: None):
        with pytest.raises(RuntimeError):
            cbv.run_researcher_claim("capsule-5507257", "m", n_runs=2)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd demo && python3 -m pytest test_core_bench_validator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core_bench_validator'`.

- [ ] **Step 3: Implement the validator module**

Create `demo/core_bench_validator.py`:

```python
"""Run the inspect_evals CORE-Bench task for one capsule/one model and return
the agent's report.json. Also derives the researcher's committed claim from N
runs. The Inspect eval runs in its own privileged Docker sandbox; this module
is the seam between that and ValiChord's commit-reveal."""
from typing import Optional

from inspect_ai import Task, eval as inspect_eval
from inspect_evals.core_bench.dataset import read_core_bench_dataset
from inspect_evals.core_bench.core_bench import default_solver

from core_bench_capture_scorer import capture_report
from report_to_verdict import derive_committed_claim


def build_validator_task(capsule_id: str) -> Task:
    """Build a hard-mode, blind, single-capsule CORE-Bench task whose scorer
    captures report.json instead of comparing against ground truth."""
    return Task(
        dataset=read_core_bench_dataset(
            difficulty="hard",
            language="Python",
            capsule_ids=[capsule_id],
            filter_out_gpu=True,
            filter_out_vision=True,
        ),
        solver=default_solver(),
        scorer=capture_report(),
    )


def extract_report_from_log(logs) -> Optional[dict]:
    """Pull the captured report dict out of the first sample's capture_report
    score. Returns None if no sample/score/report present."""
    if not logs:
        return None
    samples = getattr(logs[0], "samples", None) or []
    if not samples:
        return None
    scores = getattr(samples[0], "scores", None) or {}
    for score in scores.values():
        md = getattr(score, "metadata", None) or {}
        if "report" in md:
            return md["report"]
    return None


def run_validator_eval(capsule_id: str, model: str) -> Optional[dict]:
    """Run one CORE-Bench eval with `model` and return the agent's report.json
    (or None on failure)."""
    task = build_validator_task(capsule_id)
    logs = inspect_eval(task, model=model)
    return extract_report_from_log(logs)


def run_researcher_claim(capsule_id: str, model: str, n_runs: int = 3,
                         rel_tolerance: float = 0.001) -> dict:
    """Run the capsule n_runs times to establish the committed claim (mean +
    95% prediction interval, or explicit tolerance for deterministic output)."""
    runs = []
    for _ in range(n_runs):
        report = run_validator_eval(capsule_id, model)
        if not report:
            raise RuntimeError(
                f"Researcher run for {capsule_id} produced no report.json -- "
                f"cannot establish a committed claim."
            )
        runs.append(report)
    return derive_committed_claim(runs, rel_tolerance=rel_tolerance)
```

> **Live-run note:** `extract_report_from_log` encodes our assumption about the `EvalLog` shape (`logs[0].samples[0].scores[name].metadata["report"]`). The mocked test pins that assumption; confirm it against a real `inspect_eval` return during Task 9 and adjust the accessor if the structure differs.

- [ ] **Step 4: Run to verify pass**

Run: `cd demo && python3 -m pytest test_core_bench_validator.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add demo/core_bench_validator.py demo/test_core_bench_validator.py
git commit -m "feat(core-bench): validator eval wrapper + researcher N-run claim"
```

---

## Task 5: `core_bench_runner.py` — claim→metrics, data hash, key validation

**Files:**
- Create: `demo/core_bench_runner.py`
- Test: `demo/test_core_bench_runner.py`

- [ ] **Step 1: Write the failing tests**

Create `demo/test_core_bench_runner.py`:

```python
import pytest

# core_bench_runner imports CAPSULE_CHECKSUMS from inspect_evals at module load.
pytest.importorskip("inspect_evals")
import core_bench_runner as cbr


def test_claim_to_metrics_encodes_committed_interval():
    claim = {"Q": {"value": 96.125, "lower": 96.0, "upper": 96.25, "basis": "explicit_tolerance"}}
    metrics = cbr.claim_to_metrics(claim)
    assert metrics[0]["metric_name"] == "Q"
    assert metrics[0]["produced_value"] == repr(96.125)
    # the committed interval is sealed in expected_value, on-chain & inspectable
    assert "96.0" in metrics[0]["expected_value"] and "96.25" in metrics[0]["expected_value"]
    assert metrics[0]["within_tolerance"] is True


def test_data_hash_binds_to_capsule_checksum():
    h1 = cbr.compute_capsule_data_hash("capsule-5507257", salt=b"\x00" * 16)
    h2 = cbr.compute_capsule_data_hash("capsule-5507257", salt=b"\x01" * 16)
    assert len(h1) == 64 and h1 != h2  # salted, fresh per run


def test_validate_model_keys_fails_fast_when_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    with pytest.raises(RuntimeError) as exc:
        cbr.validate_model_keys(["anthropic/claude-opus-4-8", "openai/gpt-4o", "google/gemini-1.5-pro"])
    assert "OPENAI_API_KEY" in str(exc.value)


def test_validate_model_keys_passes_when_all_present(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    cbr.validate_model_keys(["anthropic/claude-opus-4-8", "openai/gpt-4o", "google/gemini-1.5-pro"])
```

- [ ] **Step 2: Run to verify failure**

Run: `cd demo && python3 -m pytest test_core_bench_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core_bench_runner'`.

- [ ] **Step 3: Implement the helpers**

Create `demo/core_bench_runner.py`:

```python
"""Orchestrates the CORE-Bench commit-reveal demo: researcher claim -> three
mixed-model validators -> commit-reveal via the existing demo node HTTP APIs ->
HarmonyRecord -> recomputable numeric panel.

Reuses demo_runner's node HTTP helpers and agreement.py so the displayed
outcome matches the on-chain HarmonyRecord by construction."""
import hashlib
import os

from inspect_evals.core_bench.dataset import CAPSULE_CHECKSUMS

# provider env var expected per model-string prefix
_PROVIDER_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
}


def claim_to_metrics(claim: dict) -> list:
    """Encode the committed claim as a MetricResult list for /lock-result.
    The interval is sealed in expected_value (string) so it is committed
    on-chain and any third party can read the bounds the match was judged
    against."""
    metrics = []
    for q, spec in claim.items():
        metrics.append({
            "metric_name": q,
            "produced_value": repr(spec["value"]),
            "expected_value": f"[{spec['lower']!r}, {spec['upper']!r}] ({spec['basis']})",
            "within_tolerance": True,
        })
    return metrics


def compute_capsule_data_hash(capsule_id: str, salt: bytes) -> str:
    """data_hash = SHA-256(capsule_tarball_checksum_bytes || salt). Binds the
    claim to the exact verified capsule; salt makes each run a fresh identity."""
    checksum_hex = CAPSULE_CHECKSUMS[capsule_id]
    return hashlib.sha256(bytes.fromhex(checksum_hex) + salt).hexdigest()


def validate_model_keys(models: list) -> None:
    """Fail fast if any required provider key is missing, naming the offender."""
    missing = []
    for model in models:
        provider = model.split("/", 1)[0]
        env = _PROVIDER_KEY_ENV.get(provider)
        if env is None:
            raise RuntimeError(f"Unknown model provider in '{model}' (expected one of {list(_PROVIDER_KEY_ENV)})")
        if not os.environ.get(env):
            missing.append(f"{env} (needed for validator model '{model}')")
    if missing:
        raise RuntimeError("Missing required provider API keys:\n  - " + "\n  - ".join(missing))
```

- [ ] **Step 4: Run to verify pass**

Run: `cd demo && python3 -m pytest test_core_bench_runner.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add demo/core_bench_runner.py demo/test_core_bench_runner.py
git commit -m "feat(core-bench): claim->metrics encoding, capsule data hash, key validation"
```

---

## Task 6: `core_bench_runner.py` — full protocol orchestration

**Files:**
- Modify: `demo/core_bench_runner.py`
- Modify: `demo/test_core_bench_runner.py`

- [ ] **Step 1: Write the failing test (append)**

Append to `demo/test_core_bench_runner.py`:

```python
def test_run_protocol_drives_full_sequence(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("GOOGLE_API_KEY", "x")

    posts = []

    def fake_post(url, payload, timeout=600):
        posts.append((url, payload))
        if url.endswith("/lock-result"):
            return {"external_hash_b64": "uhC8kEXT"}
        if url.endswith("/reveal"):
            return {"researcher_reveal_hash": "uhCkkREV"}
        if url.endswith("/create-harmony-record"):
            return {"harmony_record_hash": "uhC8kHARM"}
        return {}

    def fake_get(url, timeout=30):
        return {"phase": "RevealOpen"}

    # researcher + each validator returns the exact deterministic value
    monkeypatch.setattr(cbr, "_node_post", fake_post)
    monkeypatch.setattr(cbr, "_node_get", fake_get)
    monkeypatch.setattr(cbr, "run_researcher_claim",
                        lambda cid, model, n_runs, rel_tolerance:
                        {"Q": {"value": 96.125, "lower": 96.0, "upper": 96.25, "basis": "explicit_tolerance"}})
    monkeypatch.setattr(cbr, "run_validator_eval", lambda cid, model: {"Q": 96.125})
    monkeypatch.setattr(cbr, "_sleep", lambda s: None)

    result = cbr.run_core_bench_protocol(
        capsule_id="capsule-5507257",
        researcher_model="anthropic/claude-opus-4-8",
        validator_models=["anthropic/claude-opus-4-8", "openai/gpt-4o", "google/gemini-1.5-pro"],
    )

    urls = [u for u, _ in posts]
    assert any(u.endswith("/lock-result") for u in urls)
    assert any(u.endswith("/submit-request") for u in urls)
    assert sum(u.endswith("/commit") for u in urls) == 3
    assert sum(u.endswith("/reveal") for u in urls) == 4  # researcher + 3 validators
    assert any(u.endswith("/create-harmony-record") for u in urls)
    assert result["harmony_record_hash"] == "uhC8kHARM"
    assert result["agreement_level"] == "ExactMatch"  # 3/3 Reproduced
    # numeric panel: all three inside committed interval
    assert all(row["match"] for v in result["numeric_panel"] for row in v["rows"])
```

- [ ] **Step 2: Run to verify failure**

Run: `cd demo && python3 -m pytest test_core_bench_runner.py::test_run_protocol_drives_full_sequence -v`
Expected: FAIL — `AttributeError: module 'core_bench_runner' has no attribute 'run_core_bench_protocol'`.

- [ ] **Step 3: Implement the orchestrator (append to module)**

Append to `demo/core_bench_runner.py`:

```python
import time
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor

from agreement import derive_agreement_level, derive_majority_outcome
from core_bench_validator import run_validator_eval, run_researcher_claim
from report_to_verdict import report_to_verdict, build_numeric_panel
# Reuse the battle-tested node HTTP helpers + URL config from demo_runner.
from demo_runner import _node_post, _node_get, RESEARCHER_URL, VALIDATOR_URLS

_MAX_VALIDATOR_ATTEMPTS = 2


def _sleep(seconds):  # indirection so tests can stub out real waiting
    time.sleep(seconds)


def _run_one_validator(capsule_id, required_keys, model):
    """Run a validator eval (one retry with a fresh sandbox) -> (report, verdict)."""
    last_err = None
    for attempt in range(_MAX_VALIDATOR_ATTEMPTS):
        try:
            report = run_validator_eval(capsule_id, model)
            verdict = report_to_verdict(report, required_keys)
            return report, verdict
        except Exception as exc:  # noqa: BLE001 - surfaced below with model context
            last_err = exc
    raise RuntimeError(f"Validator model '{model}' failed after {_MAX_VALIDATOR_ATTEMPTS} attempts: {last_err}")


def run_core_bench_protocol(capsule_id, researcher_model, validator_models,
                            discipline=None, n_researcher_runs=3, rel_tolerance=0.001):
    """Drive the full CORE-Bench commit-reveal round. Returns a result dict with
    harmony_record_hash, outcome, agreement_level, numeric_panel, record_url."""
    if len(validator_models) != 3:
        raise ValueError("This demo uses exactly three validators.")
    validate_model_keys([researcher_model] + validator_models)
    disc = discipline or {"type": "Other", "content": "Computational Reproducibility"}

    # 1. Researcher establishes + seals the claim.
    claim = run_researcher_claim(capsule_id, researcher_model,
                                 n_runs=n_researcher_runs, rel_tolerance=rel_tolerance)
    required_keys = list(claim.keys())
    metrics = claim_to_metrics(claim)
    data_hash = compute_capsule_data_hash(capsule_id, salt=uuid.uuid4().bytes)

    lock = _node_post(f"{RESEARCHER_URL}/lock-result", {"data_hash_hex": data_hash, "metrics": metrics})
    ext = lock["external_hash_b64"]
    _node_post(f"{RESEARCHER_URL}/submit-request",
               {"external_hash_b64": ext, "discipline": disc, "num_validators_required": 3})
    _sleep(20)  # DHT propagation

    # 2. Three mixed-model validators reproduce in parallel, blind.
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_run_one_validator, capsule_id, required_keys, m): (i, m)
                   for i, m in enumerate(validator_models)}
        results = {}
        errors = []
        for fut in futures:
            i, m = futures[fut]
            try:
                results[i] = fut.result()
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
    if errors:
        raise RuntimeError("Validator reproduction failed; round aborted:\n  - " + "\n  - ".join(errors))
    validator_reports = [(f"V{i+1}-{validator_models[i].split('/')[-1]}", results[i][0]) for i in range(3)]
    verdicts = [results[i][1] for i in range(3)]

    # 3. Commit each verdict blind.
    for i, (vurl, verdict) in enumerate(zip(VALIDATOR_URLS, verdicts)):
        _node_post(f"{vurl}/commit", {
            "external_hash_b64": ext, "verdict": verdict,
            "metrics": verdict["metrics"], "discipline": disc,
        })
        if i < 2:
            _sleep(30)

    # 4. Wait for reveal phase.
    phase_url = f"{RESEARCHER_URL}/phase?hash={urllib.parse.quote(ext)}"
    for _ in range(120):
        if _node_get(phase_url).get("phase") == "RevealOpen":
            break
        _sleep(2)
    else:
        raise RuntimeError("Reveal phase did not open after 240s")

    # 5. Simultaneous reveal (researcher + validators).
    reveal = _node_post(f"{RESEARCHER_URL}/reveal", {"external_hash_b64": ext, "metrics": metrics})
    for i, vurl in enumerate(VALIDATOR_URLS):
        _node_post(f"{vurl}/reveal", {"external_hash_b64": ext})
        if i < 2:
            _sleep(15)

    # 6. Finalise.
    harmony = _node_post(f"{VALIDATOR_URLS[0]}/create-harmony-record", {"external_hash_b64": ext})
    harmony_hash = harmony.get("harmony_record_hash")
    if not harmony_hash:
        raise RuntimeError(f"HarmonyRecord not written after gossip retries (ext={ext[:20]}...)")

    # 7. Display + the verifiable numeric headline.
    outcomes = [v["outcome"] for v in verdicts]
    return {
        "harmony_record_hash": harmony_hash,
        "external_hash_b64": ext,
        "outcome": derive_majority_outcome(outcomes),
        "agreement_level": derive_agreement_level(outcomes),
        "researcher_reveal_hash": reveal.get("researcher_reveal_hash"),
        "record_url": f"{RESEARCHER_URL}/record?hash={urllib.parse.quote(ext)}",
        "committed_claim": claim,
        "numeric_panel": build_numeric_panel(validator_reports, claim),
        "validator_verdicts": [
            {"validator": i + 1, "model": validator_models[i], **{k: verdicts[i][k] for k in ("outcome", "confidence", "reasoning")}}
            for i in range(3)
        ],
    }
```

> `agreement.py`'s `derive_agreement_level`/`derive_majority_outcome` are pure (operate on outcome strings), so importing them here is safe and keeps display == on-chain.

- [ ] **Step 4: Run to verify pass**

Run: `cd demo && python3 -m pytest test_core_bench_runner.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add demo/core_bench_runner.py demo/test_core_bench_runner.py
git commit -m "feat(core-bench): full commit-reveal orchestration with mixed-model validators"
```

---

## Task 7: `core_bench_runner.py` — CLI entrypoint + human-readable output

**Files:**
- Modify: `demo/core_bench_runner.py`
- Modify: `demo/test_core_bench_runner.py`

- [ ] **Step 1: Write the failing test (append)**

Append to `demo/test_core_bench_runner.py`:

```python
def test_format_result_output_contains_headline_facts():
    result = {
        "outcome": "Reproduced", "agreement_level": "ExactMatch",
        "harmony_record_hash": "uhC8kHARM", "record_url": "http://x/record?hash=uhC8kEXT",
        "validator_verdicts": [
            {"validator": 1, "model": "anthropic/claude-opus-4-8", "outcome": "Reproduced", "confidence": "High", "reasoning": "ok"},
            {"validator": 2, "model": "openai/gpt-4o", "outcome": "Reproduced", "confidence": "High", "reasoning": "ok"},
            {"validator": 3, "model": "google/gemini-1.5-pro", "outcome": "Reproduced", "confidence": "High", "reasoning": "ok"},
        ],
        "numeric_panel": [
            {"validator": "V1-claude-opus-4-8", "rows": [{"question": "Q", "value": 96.125, "lower": 96.0, "upper": 96.25, "match": True}]},
        ],
    }
    text = cbr.format_result(result)
    assert "ExactMatch" in text
    assert "uhC8kHARM" in text
    assert "96.125" in text and "96.0" in text  # numeric panel rendered
    assert "claude-opus-4-8" in text and "gpt-4o" in text and "gemini-1.5-pro" in text
```

- [ ] **Step 2: Run to verify failure**

Run: `cd demo && python3 -m pytest test_core_bench_runner.py::test_format_result_output_contains_headline_facts -v`
Expected: FAIL — `AttributeError: ... has no attribute 'format_result'`.

- [ ] **Step 3: Implement output formatter + CLI (append to module)**

Append to `demo/core_bench_runner.py`:

```python
import argparse

_DEFAULT_MODELS = ["anthropic/claude-opus-4-8", "openai/gpt-4o", "google/gemini-1.5-pro"]


def format_result(result: dict) -> str:
    lines = []
    a = lines.append
    a("=" * 60)
    a("  ValiChord x CORE-Bench - Computational Reproducibility")
    a("=" * 60)
    a(f"  Outcome:          {result['outcome']}")
    a(f"  Agreement level:  {result['agreement_level']}  (independent execution agreement)")
    a(f"  HarmonyRecord:    {result['harmony_record_hash']}")
    a("")
    a("  Validators (mixed models, blind, isolated sandboxes):")
    for v in result["validator_verdicts"]:
        a(f"    V{v['validator']} [{v['model']}]: {v['outcome']} ({v['confidence']}) - {v['reasoning']}")
    a("")
    a("  Numeric convergence vs researcher's committed interval (recomputable):")
    for v in result["numeric_panel"]:
        for row in v["rows"]:
            verdict = "MATCH" if row["match"] else "OUTSIDE"
            a(f"    {v['validator']}: {row['value']} in [{row['lower']!r}, {row['upper']!r}] -> {verdict}")
    a("")
    a(f"  Verify independently:")
    a(f"    curl \"{result['record_url']}\"")
    a("=" * 60)
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="ValiChord x CORE-Bench CLI demo")
    parser.add_argument("--capsule", required=True, help="capsule_id, e.g. capsule-5507257")
    parser.add_argument("--researcher-model", default=_DEFAULT_MODELS[0])
    parser.add_argument("--validator-models", nargs=3, default=_DEFAULT_MODELS,
                        help="three model strings, e.g. anthropic/claude-opus-4-8 openai/gpt-4o google/gemini-1.5-pro")
    parser.add_argument("--researcher-runs", type=int, default=3)
    parser.add_argument("--tolerance", type=float, default=0.001, help="relative tolerance for deterministic capsules")
    args = parser.parse_args(argv)

    result = run_core_bench_protocol(
        capsule_id=args.capsule,
        researcher_model=args.researcher_model,
        validator_models=args.validator_models,
        n_researcher_runs=args.researcher_runs,
        rel_tolerance=args.tolerance,
    )
    print(format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run to verify pass**

Run: `cd demo && python3 -m pytest test_core_bench_runner.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add demo/core_bench_runner.py demo/test_core_bench_runner.py
git commit -m "feat(core-bench): CLI entrypoint + human-readable result output"
```

---

## Task 8: `core_bench_spike.py` — Phase-0 capsule-selection helper

**Files:**
- Create: `demo/core_bench_spike.py`

- [ ] **Step 1: Implement the spike script (no unit test — it is a thin live wrapper)**

Create `demo/core_bench_spike.py`:

```python
#!/usr/bin/env python3
"""Phase-0 capsule-selection helper. Runs ONE capsule through the validator
eval with one model, in hard mode, and prints the produced value + wall-clock
time. Use it to confirm a candidate reproduces clean (<5 min, no GPU) before
wiring it into the demo.

    export ANTHROPIC_API_KEY=sk-ant-...
    python3 demo/core_bench_spike.py --capsule capsule-5507257 \
        --model anthropic/claude-opus-4-8
"""
import argparse
import time

from core_bench_validator import run_validator_eval


def main(argv=None):
    p = argparse.ArgumentParser(description="CORE-Bench capsule spike")
    p.add_argument("--capsule", required=True)
    p.add_argument("--model", default="anthropic/claude-opus-4-8")
    args = p.parse_args(argv)

    print(f"[spike] running {args.capsule} with {args.model} (hard mode)...")
    t0 = time.time()
    report = run_validator_eval(args.capsule, args.model)
    elapsed = time.time() - t0
    print(f"[spike] elapsed: {elapsed:.0f}s")
    if not report:
        print("[spike] RESULT: no report.json produced -> did NOT reproduce")
        return 1
    print(f"[spike] RESULT: report.json = {report}")
    print(f"[spike] reproduced in {elapsed:.0f}s -> "
          f"{'GOOD demo candidate' if elapsed < 300 else 'TOO SLOW for <5min target'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Sanity-check it imports (no eval run)**

Run: `cd demo && python3 -c "import core_bench_spike; print('ok')"`
Expected: prints `ok` (import-only; no Docker/eval invoked).

- [ ] **Step 3: Commit**

```bash
git add demo/core_bench_spike.py
git commit -m "feat(core-bench): Phase-0 capsule-selection spike helper"
```

---

## Task 9: Live verification — capsule spike + one full run (manual, NOT CI)

**Files:** none (operational). Produces the verification evidence for the build.

> This task needs **privileged Docker + three provider keys (Anthropic, OpenAI, Google) + several minutes**. It is the `verification-before-completion` evidence and is **not** part of CI.

- [ ] **Step 1: Provider keys**

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export GOOGLE_API_KEY=...
```

- [ ] **Step 2: Spike the candidate capsules, pick one**

Run each (deterministic candidates first):

```bash
cd demo
python3 core_bench_spike.py --capsule capsule-5507257 --model anthropic/claude-opus-4-8
python3 core_bench_spike.py --capsule capsule-9660931 --model anthropic/claude-opus-4-8
python3 core_bench_spike.py --capsule capsule-0851068 --model anthropic/claude-opus-4-8
```

Pick the first that prints `reproduced in <300s` with the value matching the dataset ground truth (e.g. `96.12499...` for `capsule-5507257`). Record the chosen capsule_id.

Also confirm `extract_report_from_log` returned a non-None report — if it printed `no report.json produced` despite the agent clearly succeeding, the `EvalLog` accessor in `core_bench_validator.extract_report_from_log` needs adjusting to the real log shape (see the live-run note in Task 4). Fix, re-run, then commit the fix.

- [ ] **Step 3: Bring up the local conductor stack**

```bash
cd /workspaces/ValiChord
hc app pack valichord -o valichord/workdir/valichord.happ   # if not already packed
docker compose -f demo/docker-compose.yml up --build -d
until [ "$(docker compose -f demo/docker-compose.yml logs 2>/dev/null | grep -c 'node API ->')" -ge 4 ]; do sleep 3; done && echo "Ready"
```

- [ ] **Step 4: Run the full demo against local nodes**

```bash
cd demo
export VALICHORD_RESEARCHER_URL=http://localhost:3001
export VALICHORD_VALIDATOR_1_URL=http://localhost:3002
export VALICHORD_VALIDATOR_2_URL=http://localhost:3003
export VALICHORD_VALIDATOR_3_URL=http://localhost:3004
python3 core_bench_runner.py --capsule <chosen-capsule-id>
```

Expected: the formatted output ends with a `HarmonyRecord:` hash, a numeric panel where all three validators read `MATCH`, and a `curl` verify line.

- [ ] **Step 5: Independently verify the record**

```bash
curl "http://localhost:3001/record?hash=<external_hash_from_output>"
```

Expected: JSON HarmonyRecord whose outcome/agreement match the printed result, and whose committed interval (in the researcher metrics) contains each validator's revealed value.

- [ ] **Step 6: Tear down**

```bash
docker compose -f demo/docker-compose.yml down -v
```

- [ ] **Step 7: Record the verified capsule + any accessor fix**

If Step 2 required an `extract_report_from_log` fix, ensure it is committed. No code commit otherwise — this task is evidence, captured in the next task's doc.

---

## Task 10: `CORE_BENCH_DEMO.md` — documentation

**Files:**
- Create: `demo/CORE_BENCH_DEMO.md`

- [ ] **Step 1: Write the doc**

Create `demo/CORE_BENCH_DEMO.md` covering, with the values confirmed in Task 9:

- **What it shows** — three different models independently reproduce one capsule, blind, in isolated sandboxes; arithmetic (not opinion) decides the match; the record is recomputable.
- **The gap it fills** — a `.eval` log is single-author and self-attested; ValiChord adds the multi-party, blinded, tamper-evident layer.
- **Prerequisites** — privileged Docker; `pip install -r requirements.txt`; `ANTHROPIC_API_KEY` + `OPENAI_API_KEY` + `GOOGLE_API_KEY`.
- **Run** — the `docker compose up` stanza + `python3 core_bench_runner.py --capsule <id>` (use the capsule confirmed in Task 9).
- **The honest independence claim** — quote the wording: mixed models earn "independent"; the committed `agreement_level` is *independent execution agreement*; the numeric convergence is the verifiable headline. Cross-link `docs/CORE_BENCH_INTEGRATION.md` §"Where the independence actually comes from".
- **Blinding** — hard mode deletes `results/`; agents never see the target; the researcher's value/interval is sealed until reveal.
- **Skeptic-proof verification** — the `curl` command + how to redo the interval check by hand.
- **Capsule note** — deterministic chosen for legibility; `capsule-6003668` (stochastic) is the more representative follow-up (cross-link the spec's §3 note).
- **Files table** — the five new modules and their responsibilities.

- [ ] **Step 2: Commit**

```bash
git add demo/CORE_BENCH_DEMO.md
git commit -m "docs(core-bench): CLI demo run guide + honest independence framing"
```

---

## Task 11: Update project docs

**Files:**
- Modify: `PROJECT_STATUS.md`
- Modify: `docs/CORE_BENCH_INTEGRATION.md`

- [ ] **Step 1: Update PROJECT_STATUS.md**

In `PROJECT_STATUS.md` §"What is NOT done yet" item 5 (CORE-Bench demo): change status from NOT STARTED to in-progress/done as appropriate, and **correct the stale trigger** — the demo no longer waits on the inspect_evals issue (the strategy inverted to "lead with the demo"; outreach to Scott Simmons was a direct LinkedIn message, not an issue). Add a "Recently completed" entry pointing at `demo/CORE_BENCH_DEMO.md` and the chosen capsule.

- [ ] **Step 2: Update CORE_BENCH_INTEGRATION.md**

Mark the demo as built; point the "What needs to be built" section at the implemented modules; note the chosen capsule and the inspect_evals (not AutoGPT) foundation.

- [ ] **Step 3: Commit**

```bash
git add PROJECT_STATUS.md docs/CORE_BENCH_INTEGRATION.md
git commit -m "docs: mark CORE-Bench CLI demo built; correct stale inspect_evals trigger"
```

---

## Self-review notes (for the implementer)

- **Blinding is enforced in two tests:** `test_build_validator_task_uses_hard_blind_filters` (hard difficulty) and `test_blinding_guard_source_never_references_ground_truth` (scorer never reads `metadata["results"]`). Do not weaken either.
- **Display == on-chain:** the runner derives agreement only via `agreement.py`. Never compute an agreement label any other way.
- **The numeric match is display/headline, not the committed outcome.** Committed outcomes are execution-success only (Task 2). Keep that separation — it is the whole Option-1 design.
- **The one fragile seam** is `extract_report_from_log` (EvalLog shape). It is mock-pinned but only the real run (Task 9 Step 2) confirms it. Expect to adjust it once.
- **Intentionally deferred (spec §4/§6 "optional overlay"):** the post-reveal ground-truth score via inspect_evals' stock `evaluate_task_questions()`. It is explicitly optional, off the critical path, and not a success criterion — add it as a follow-on once the core demo is verified, keeping it strictly post-reveal so it never touches the commit path.
