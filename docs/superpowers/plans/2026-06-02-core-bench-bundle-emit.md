# CORE-Bench Bundle-Emit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in `--emit-bundles` step to the CORE-Bench demo that, after a successful commit-reveal round, writes one `valichord_attestation` bundle per validator — metrics from the validator's reproduced report, samples via EveryEvalEver's `InspectAIAdapter`, and `meta.attestation_uri` pointing at the shared HarmonyRecord.

**Architecture:** Three changes. (1) `core_bench_validator.run_validator_eval` returns `(report, eval_log_path)` and accepts an optional `log_dir` (Approach A — single code path, the published-record error guard untouched). (2) New `demo/core_bench_bundle.py` builds + writes per-validator bundles. (3) `core_bench_runner` threads a per-run `log_dir`, collects the eval-log paths, and calls the emitter after the HarmonyRecord — wrapped so a bundle failure never invalidates a completed round.

**Tech Stack:** Python, pytest (monkeypatch/mock), `valichord_attestation` (`build_bundle`, `hash_bundle`, `bundle_to_dict`), `every_eval_ever` `InspectAIAdapter`, `inspect_ai` / `inspect_evals`.

**Spec:** `docs/superpowers/specs/2026-06-02-core-bench-bundle-emit-design.md`

**Working dir for all commands:** `demo/` (tests import modules by bare name, e.g. `import core_bench_runner`). Prepend `export PATH="/home/codespace/.cargo/bin:$PATH"` is not needed (pure Python), but run from `demo/`.

---

## Task 1: Validator seam — `run_validator_eval` returns `(report, eval_log_path)`

**Files:**
- Modify: `demo/core_bench_validator.py` (`run_validator_eval`, `run_researcher_claim`)
- Test: `demo/test_core_bench_validator.py`

- [ ] **Step 1: Update the existing tests and add two new ones**

In `demo/test_core_bench_validator.py`, replace `test_run_validator_eval_returns_report` and `test_run_validator_eval_returns_none_when_success_but_no_report` with the versions below, add the two new tests after them, and update the two `run_researcher_claim` tests' fakes to return tuples.

```python
def test_run_validator_eval_returns_report_and_log_path():
    good = mock.Mock(status="success", location="/logs/run.eval")
    with mock.patch.object(cbv, "build_validator_task", lambda cid: "TASK"), \
         mock.patch.object(cbv, "inspect_eval", lambda *a, **k: [good]), \
         mock.patch.object(cbv, "extract_report_from_log", lambda logs: {"Q": 2.0}):
        report, path = cbv.run_validator_eval("capsule-5507257", "anthropic/claude-opus-4-8")
    assert report == {"Q": 2.0}
    assert path == "/logs/run.eval"


def test_run_validator_eval_passes_log_dir_to_inspect_eval():
    captured = {}

    def fake_eval(task, model=None, log_dir=None):
        captured["log_dir"] = log_dir
        return [mock.Mock(status="success", location="/l/x.eval")]

    with mock.patch.object(cbv, "build_validator_task", lambda cid: "TASK"), \
         mock.patch.object(cbv, "inspect_eval", fake_eval), \
         mock.patch.object(cbv, "extract_report_from_log", lambda logs: {"Q": 1.0}):
        cbv.run_validator_eval("capsule-5507257", "m", log_dir="/l")
    assert captured["log_dir"] == "/l"


def test_run_validator_eval_returns_none_when_success_but_no_report():
    """A *successful* eval that produced no report.json is a genuine
    no-reproduction (-> FailedToReproduce later), distinct from an infra
    failure -- so report is None rather than raising."""
    good_log = mock.Mock(status="success", samples=[], location="/l/x.eval")
    with mock.patch.object(cbv, "build_validator_task", lambda cid: "TASK"), \
         mock.patch.object(cbv, "inspect_eval", lambda *a, **k: [good_log]):
        report, _ = cbv.run_validator_eval("capsule-5507257", "anthropic/claude-opus-4-8")
    assert report is None
```

Update the two researcher tests' fakes to return `(report, path)` tuples (the new contract):

```python
def test_run_researcher_claim_runs_n_times_and_derives():
    calls = []

    def fake_eval(cid, model):
        calls.append(model)
        return {"Q": 96.125}, None

    with mock.patch.object(cbv, "run_validator_eval", fake_eval):
        claim = cbv.run_researcher_claim("capsule-5507257", "anthropic/claude-opus-4-8", n_runs=3)
    assert len(calls) == 3
    assert claim["Q"]["value"] == pytest.approx(96.125)


def test_run_researcher_claim_raises_on_failed_run():
    with mock.patch.object(cbv, "run_validator_eval", lambda c, m: (None, None)):
        with pytest.raises(RuntimeError):
            cbv.run_researcher_claim("capsule-5507257", "m", n_runs=2)
```

(`test_run_validator_eval_raises_on_non_success_eval` is unchanged — it still raises before returning.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd demo && python -m pytest test_core_bench_validator.py -q`
Expected: FAIL — `test_run_validator_eval_returns_report_and_log_path` / `..._passes_log_dir...` error (old `run_validator_eval` returns a bare dict / doesn't accept `log_dir`), and the researcher tests fail unpacking.

- [ ] **Step 3: Implement the seam change**

In `demo/core_bench_validator.py`, replace `run_validator_eval` with:

```python
def run_validator_eval(capsule_id: str, model: str, log_dir: Optional[str] = None):
    """Run one CORE-Bench eval with `model`; return (report, eval_log_path).

    report is the agent's report.json (or None for a genuine no-reproduction —
    a *successful* eval that produced no report.json). eval_log_path is the
    written .eval log location (set `log_dir` to control where inspect writes
    it), or None when unavailable.

    An infra failure (rate limit, quota, auth, interruption) yields a
    non-success EvalLog; that still raises so the round aborts with the real
    error and is never recorded as a bogus FailedToReproduce verdict.
    """
    task = build_validator_task(capsule_id)
    logs = inspect_eval(task, model=model, log_dir=log_dir)
    if logs:
        status = getattr(logs[0], "status", None)
        if status is not None and status != "success":
            err = getattr(logs[0], "error", None)
            detail = getattr(err, "message", None) or (str(err) if err else "no error detail")
            raise RuntimeError(f"eval did not complete (status={status}): {detail}")
    report = extract_report_from_log(logs)
    eval_log_path = getattr(logs[0], "location", None) if logs else None
    return report, eval_log_path
```

In `run_researcher_claim`, change the call site (inside the `for` loop) from `report = run_validator_eval(capsule_id, model)` to:

```python
        report, _ = run_validator_eval(capsule_id, model)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd demo && python -m pytest test_core_bench_validator.py -q`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add demo/core_bench_validator.py demo/test_core_bench_validator.py
git commit -m "feat(core-bench): run_validator_eval returns (report, eval_log_path)"
```

---

## Task 2: `core_bench_bundle.py` — metrics mapping + bundle writing (EEE boundary mocked)

**Files:**
- Create: `demo/core_bench_bundle.py`
- Test: `demo/test_core_bench_bundle.py`

- [ ] **Step 1: Write the failing tests**

Create `demo/test_core_bench_bundle.py`:

```python
import json
import pytest

pytest.importorskip("valichord_attestation")
pytest.importorskip("inspect_evals")  # core_bench_bundle imports CAPSULE_CHECKSUMS
import core_bench_bundle as cbb


_CLAIM = {
    "Q": {"value": 96.125, "lower": 96.0, "upper": 96.25, "basis": "explicit_tolerance"},
    "R": {"value": 0.5, "lower": 0.49, "upper": 0.51, "basis": "explicit_tolerance"},
}


def test_metrics_from_report_uses_panel_values():
    report = {"Q": 96.125, "R": "0.5"}
    metrics = cbb._metrics_from_report("V1", report, _CLAIM)
    assert {"key": "Q", "value": 96.125} in metrics
    assert {"key": "R", "value": 0.5} in metrics


def test_metrics_from_report_skips_missing_keys():
    report = {"Q": 96.125}  # R absent
    metrics = cbb._metrics_from_report("V1", report, _CLAIM)
    assert metrics == [{"key": "Q", "value": 96.125}]


def _result():
    return {
        "record_url": "http://oracle/record?hash=uhC8kEXT",
        "harmony_record_hash": "uhC8kHARM",
        "external_hash_b64": "uhC8kEXT",
        "outcome": "Reproduced",
        "agreement_level": "ExactMatch",
        "committed_claim": _CLAIM,
    }


def test_emit_writes_one_bundle_per_validator(tmp_path, monkeypatch):
    monkeypatch.setattr(cbb, "_samples_from_eee_log",
                        lambda path: [{"sample_id": "1", "input": "i",
                                       "target": "t", "model_answer": "a", "correct": True}])
    validator_reports = [("V1-opus", {"Q": 96.125, "R": 0.5}),
                         ("V2-gpt", {"Q": 96.13, "R": 0.5}),
                         ("V3-gemini", {"Q": 96.12, "R": 0.5})]
    paths = cbb.emit_core_bench_bundles(
        capsule_id="capsule-0851068",
        researcher_model="anthropic/claude-opus-4-8",
        validator_models=["anthropic/claude-opus-4-8", "openai/gpt-4o", "google/gemini-2.5-pro"],
        validator_reports=validator_reports,
        validator_eval_logs=["/l/v1.eval", "/l/v2.eval", "/l/v3.eval"],
        result=_result(),
        out_dir=tmp_path,
    )
    assert len(paths) == 3
    doc = json.loads(paths[0].read_text())
    assert doc["bundle"]["model_id"] == "anthropic/claude-opus-4-8"
    assert doc["bundle"]["task_id"] == "inspect_evals/core_bench:capsule-0851068"
    assert doc["bundle"]["meta"]["attestation_uri"] == "http://oracle/record?hash=uhC8kEXT"
    assert doc["bundle"]["meta"]["validator_model"] == "anthropic/claude-opus-4-8"
    assert doc["samples"]  # non-empty
    assert len(doc["_source"]["bundle_sha256"]) == 64
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd demo && python -m pytest test_core_bench_bundle.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core_bench_bundle'`.

- [ ] **Step 3: Create the module**

Create `demo/core_bench_bundle.py`:

```python
"""Emit per-validator valichord_attestation bundles from a completed CORE-Bench
commit-reveal round.

Each bundle is a model x task record: the validator's reproduced metrics (from
report.json, via the same extraction as the numeric panel), samples parsed via
EveryEvalEver's InspectAIAdapter, and a meta.attestation_uri pointing at the
shared HarmonyRecord. Opt-in (called by core_bench_runner only under
--emit-bundles); a derived artifact that never affects the committed record."""
import json
import tempfile
from pathlib import Path

from valichord_attestation import build_bundle, hash_bundle
from valichord_attestation.canonical import bundle_to_dict
from inspect_evals.core_bench.dataset import CAPSULE_CHECKSUMS

from report_to_verdict import build_numeric_panel

EEE_COMMIT = "dec1ae43e0741a37003425eafe6699d3296145ec"
EEE_INSTALL = (
    "every-eval-ever[inspect] @ "
    f"git+https://github.com/evaleval/every_eval_ever.git@{EEE_COMMIT}"
)
TASK_PREFIX = "inspect_evals/core_bench"


def _metrics_from_report(label, report, committed_claim):
    """raw_metrics for build_bundle from this validator's reproduced values,
    using the same extraction as build_numeric_panel (so the bundle's metrics
    equal the panel's values by construction). Skips keys the validator did not
    produce a parseable number for."""
    rows = build_numeric_panel([(label, report)], committed_claim)[0]["rows"]
    return [
        {"key": row["question"], "value": round(float(row["value"]), 6)}
        for row in rows if row["value"] is not None
    ]


def _eee_adapter():
    """Return an EEE InspectAIAdapter; raise a clear, actionable error if EEE is
    not installed. Isolated so unit tests can patch it."""
    try:
        from every_eval_ever.converters.inspect.adapter import InspectAIAdapter
    except ImportError as e:
        raise RuntimeError(
            "every-eval-ever[inspect] is required for --emit-bundles.\n"
            f"Install: pip install '{EEE_INSTALL}'"
        ) from e
    return InspectAIAdapter(strict_validation=False)


def _samples_from_eee_log(eval_log_path):
    """Parse a CORE-Bench .eval log into bundle samples via EEE's
    InspectAIAdapter. Real EEE call; unit tests monkeypatch this function."""
    adapter = _eee_adapter()
    samples = []
    with tempfile.TemporaryDirectory() as tmpdir:
        adapter.transform_from_file(
            str(eval_log_path),
            metadata_args={
                "source_organization_name": "valichord_core_bench_demo",
                "evaluator_relationship": "third_party",
                "parent_eval_output_dir": tmpdir,
                "file_uuid": "valichord",
            },
        )
        for jf in sorted(Path(tmpdir).rglob("*.jsonl")):
            for line in jf.read_text().splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                inp = rec.get("input") or {}
                out = rec.get("output") or {}
                ev = rec.get("evaluation") or {}
                reference = inp.get("reference") or []
                raw_outputs = out.get("raw") or []
                samples.append({
                    "sample_id": rec.get("sample_id"),
                    "input": (inp.get("raw") or "")[:200].strip(),
                    "target": reference[0].strip() if reference else "",
                    "model_answer": raw_outputs[0].strip() if raw_outputs else "",
                    "correct": bool(ev.get("is_correct", False)),
                })
    return samples


def build_one_bundle(*, capsule_id, researcher_model, validator_model, label,
                     report, committed_claim, eval_log_path, result):
    """Return (bundle, samples) for one validator reproduction."""
    raw_metrics = _metrics_from_report(label, report, committed_claim)
    samples = _samples_from_eee_log(eval_log_path)
    meta = {
        "protocol": "valichord-commit-reveal",
        "attestation_uri": result["record_url"],
        "harmony_record_hash": result["harmony_record_hash"],
        "external_hash_b64": result["external_hash_b64"],
        "outcome": result["outcome"],
        "agreement_level": result["agreement_level"],
        "committed_claim": committed_claim,
        "capsule_id": capsule_id,
        "capsule_checksum": CAPSULE_CHECKSUMS[capsule_id],
        "researcher_model": researcher_model,
        "validator_model": validator_model,
        "validator_label": label,
        "eee_commit": EEE_COMMIT,
    }
    bundle = build_bundle(
        model_id=validator_model,
        task_id=f"{TASK_PREFIX}:{capsule_id}",
        raw_metrics=raw_metrics,
        samples=samples,
        harness_version=TASK_PREFIX,
        meta=meta,
    )
    return bundle, samples


def emit_core_bench_bundles(*, capsule_id, researcher_model, validator_models,
                            validator_reports, validator_eval_logs, result, out_dir):
    """Write one bundle JSON per validator into out_dir. Returns the paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    committed_claim = result["committed_claim"]
    paths = []
    for i, (label, report) in enumerate(validator_reports):
        validator_model = validator_models[i]
        bundle, samples = build_one_bundle(
            capsule_id=capsule_id, researcher_model=researcher_model,
            validator_model=validator_model, label=label, report=report,
            committed_claim=committed_claim,
            eval_log_path=validator_eval_logs[i], result=result,
        )
        wrapper = {
            "_source": {
                "note": (
                    f"CORE-Bench {capsule_id} reproduced by {validator_model}; "
                    "metrics from validator report.json, samples via EEE "
                    f"InspectAIAdapter @ {EEE_COMMIT[:12]}; "
                    "attestation_uri -> HarmonyRecord."
                ),
                "eee_commit": EEE_COMMIT,
                "bundle_sha256": hash_bundle(bundle),
            },
            "bundle": bundle_to_dict(bundle),
            "samples": samples,
        }
        safe_model = validator_model.replace("/", "_")
        p = out_dir / f"bundle_{capsule_id}_{safe_model}.json"
        p.write_text(json.dumps(wrapper, indent=2) + "\n")
        paths.append(p)
    return paths
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd demo && python -m pytest test_core_bench_bundle.py -q`
Expected: PASS. (If `valichord_attestation` is not installed, tests are skipped — install with `pip install -e ../valichord_attestation` to run them.)

- [ ] **Step 5: Commit**

```bash
git add demo/core_bench_bundle.py demo/test_core_bench_bundle.py
git commit -m "feat(core-bench): core_bench_bundle — per-validator attestation bundles"
```

---

## Task 3: `_samples_from_eee_log` via a patchable EEE adapter

**Files:**
- Modify: `demo/test_core_bench_bundle.py` (add one test)
- (No production change — `_eee_adapter` / `_samples_from_eee_log` already written in Task 2; this task verifies the EEE boundary with a fake adapter.)

- [ ] **Step 1: Write the failing test**

Append to `demo/test_core_bench_bundle.py`:

```python
def test_samples_from_eee_log_maps_jsonl(monkeypatch):
    """_samples_from_eee_log drives EEE's adapter, which writes per-sample JSONL
    into parent_eval_output_dir; we map those records to bundle samples."""
    from pathlib import Path as _P

    class FakeAdapter:
        def transform_from_file(self, path, metadata_args=None):
            outdir = _P(metadata_args["parent_eval_output_dir"])
            rec = {
                "sample_id": "1",
                "input": {"raw": "compute the AUC", "reference": ["0.9158"]},
                "output": {"raw": ["0.9158"]},
                "evaluation": {"is_correct": True},
            }
            (outdir / "samples.jsonl").write_text(json.dumps(rec) + "\n")
            return object()

    monkeypatch.setattr(cbb, "_eee_adapter", lambda: FakeAdapter())
    samples = cbb._samples_from_eee_log("/ignored/path.eval")
    assert samples == [{
        "sample_id": "1",
        "input": "compute the AUC",
        "target": "0.9158",
        "model_answer": "0.9158",
        "correct": True,
    }]


def test_eee_adapter_raises_actionable_error_when_missing(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def blocked_import(name, *a, **k):
        if name.startswith("every_eval_ever"):
            raise ImportError("no every_eval_ever")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    with pytest.raises(RuntimeError) as exc:
        cbb._eee_adapter()
    assert "every-eval-ever" in str(exc.value) and "pip install" in str(exc.value)
```

- [ ] **Step 2: Run the tests to verify they pass (production code already present)**

Run: `cd demo && python -m pytest test_core_bench_bundle.py -q`
Expected: PASS — both new tests green against the `_eee_adapter` / `_samples_from_eee_log` written in Task 2. If `test_samples_from_eee_log_maps_jsonl` fails, the bug is in the JSONL→sample mapping in `_samples_from_eee_log`; fix it there until green.

- [ ] **Step 3: Commit**

```bash
git add demo/test_core_bench_bundle.py
git commit -m "test(core-bench): cover EEE adapter boundary in core_bench_bundle"
```

---

## Task 4: Runner wiring — `--emit-bundles`, log-dir threading, emit call

**Files:**
- Modify: `demo/core_bench_runner.py` (`_run_one_validator`, `run_core_bench_protocol`, the validator loop + return, `main`)
- Test: `demo/test_core_bench_runner.py`

- [ ] **Step 1: Update existing validator mocks + add wiring tests**

In `demo/test_core_bench_runner.py`, every `monkeypatch.setattr(cbr, "run_validator_eval", ...)` must now return `(report, eval_log_path)` and accept a `log_dir` kwarg. Apply these exact replacements:

`test_run_protocol_drives_full_sequence` (was `lambda cid, model: {"Q": 96.125}`):
```python
    monkeypatch.setattr(cbr, "run_validator_eval",
                        lambda cid, model, log_dir=None: ({"Q": 96.125}, None))
```

`test_validators_run_sequentially_not_concurrently` — change `tracking_eval` signature and return:
```python
    def tracking_eval(cid, model, log_dir=None):
        with lock:
            state["in_flight"] += 1
            state["max_in_flight"] = max(state["max_in_flight"], state["in_flight"])
        time.sleep(0.05)  # hold the slot so any overlap is observable
        with lock:
            state["in_flight"] -= 1
        return {"Q": 96.125}, None
```

`test_run_protocol_aborts_when_a_validator_fails` — change `flaky_eval`:
```python
    def flaky_eval(cid, model, log_dir=None):
        if model == "openai/gpt-4o":
            raise RuntimeError("sandbox build failed")
        return {"Q": 96.125}, None
```

`_full_run` helper (was `lambda cid, model: {"AUC": 96.0}`):
```python
    monkeypatch.setattr(cbr, "run_validator_eval",
                        lambda cid, model, log_dir=None: ({"AUC": 96.0}, None))
```

(`test_run_protocol_aborts_on_capsule_leak`'s `fail_if_called(*a, **k)` already accepts any args — leave it.)

Then append two new wiring tests:

```python
import sys
import types


def _emit_run(monkeypatch, emitter):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    monkeypatch.setattr(cbr, "load_retained_capsule_text", lambda cid: {})
    monkeypatch.setattr(cbr, "run_researcher_claim",
                        lambda cid, model, n_runs, rel_tolerance:
                        {"Q": {"value": 96.125, "lower": 96.0, "upper": 96.25, "basis": "x"}})
    monkeypatch.setattr(cbr, "run_validator_eval",
                        lambda cid, model, log_dir=None: ({"Q": 96.125}, f"/l/{model}.eval"))
    monkeypatch.setattr(cbr, "_node_get", lambda url, timeout=30: {"phase": "RevealOpen"})
    monkeypatch.setattr(cbr, "_sleep", lambda s: None)

    def fake_post(url, payload, timeout=600):
        if url.endswith("/lock-result"): return {"external_hash_b64": "uhC8kEXT"}
        if url.endswith("/reveal"): return {"researcher_reveal_hash": "uhCkkREV"}
        if url.endswith("/create-harmony-record"): return {"harmony_record_hash": "uhC8kHARM"}
        return {}
    monkeypatch.setattr(cbr, "_node_post", fake_post)

    # Inject a fake core_bench_bundle so the runner's lazy import picks it up
    # without requiring valichord_attestation to be installed.
    fake_mod = types.SimpleNamespace(emit_core_bench_bundles=emitter)
    monkeypatch.setitem(sys.modules, "core_bench_bundle", fake_mod)

    return cbr.run_core_bench_protocol(
        capsule_id="capsule-0851068",
        researcher_model="anthropic/claude-opus-4-8",
        validator_models=["anthropic/claude-opus-4-8", "openai/gpt-4o", "google/gemini-2.5-pro"],
        emit_bundles=True,
        bundle_dir="bundles",
    )


def test_emit_bundles_calls_emitter_with_collected_logs(monkeypatch):
    seen = {}

    def emitter(**kwargs):
        seen.update(kwargs)
        return ["bundles/b1.json", "bundles/b2.json", "bundles/b3.json"]

    res = _emit_run(monkeypatch, emitter)
    assert res["bundles"] == ["bundles/b1.json", "bundles/b2.json", "bundles/b3.json"]
    assert seen["validator_eval_logs"] == [
        "/l/anthropic/claude-opus-4-8.eval",
        "/l/openai/gpt-4o.eval",
        "/l/google/gemini-2.5-pro.eval",
    ]
    assert "bundles_error" not in res


def test_emit_failure_does_not_break_the_round(monkeypatch):
    def emitter(**kwargs):
        raise RuntimeError("EEE not installed")

    res = _emit_run(monkeypatch, emitter)
    # The published round still succeeds; the failure is reported, not fatal.
    assert res["harmony_record_hash"] == "uhC8kHARM"
    assert "EEE not installed" in res["bundles_error"]
    assert "bundles" not in res
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd demo && python -m pytest test_core_bench_runner.py -q`
Expected: FAIL — `run_core_bench_protocol` does not accept `emit_bundles`/`bundle_dir`, `_run_one_validator` still unpacks a 2-tuple, and `res["bundles"]` is absent.

- [ ] **Step 3: Implement the runner changes**

(3a) Replace `_run_one_validator` with the log-dir-threading, 3-tuple version:

```python
def _run_one_validator(capsule_id, required_keys, model, log_dir=None):
    """Run a validator eval (one retry with a fresh sandbox)
    -> (report, verdict, eval_log_path)."""
    last_err = None
    for _ in range(_MAX_VALIDATOR_ATTEMPTS):
        try:
            report, eval_log_path = run_validator_eval(capsule_id, model, log_dir=log_dir)
            verdict = report_to_verdict(report, required_keys)
            return report, verdict, eval_log_path
        except Exception as exc:  # noqa: BLE001 - surfaced below with model context
            last_err = exc
    raise RuntimeError(f"Validator model '{model}' failed after {_MAX_VALIDATOR_ATTEMPTS} attempts: {last_err}")
```

(3b) Change the `run_core_bench_protocol` signature (add two kwargs) and add `import uuid` at the top of the file if not already imported (it is — `uuid` is used by `compute_capsule_data_hash` callers). Update the signature line:

```python
def run_core_bench_protocol(capsule_id, researcher_model, validator_models,
                            discipline=None, n_researcher_runs=3, rel_tolerance=0.001,
                            emit_bundles=False, bundle_dir="bundles"):
```

(3c) Just before the validator loop (the `results = {}` / `for i, m in enumerate(validator_models):` block), create the per-run log dir when emitting:

```python
    log_dir = None
    if emit_bundles:
        log_dir = str(Path(bundle_dir) / "logs" / uuid.uuid4().hex)
```

Add `from pathlib import Path` to the imports at the top of the file if absent.

(3d) In the loop, pass `log_dir` and unpack the 3-tuple. Replace the loop + the `validator_reports`/`verdicts` extraction with:

```python
    results = {}
    errors = []
    for i, m in enumerate(validator_models):
        try:
            results[i] = _run_one_validator(capsule_id, required_keys, m, log_dir=log_dir)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
    if errors:
        raise RuntimeError("Validator reproduction failed; round aborted:\n  - " + "\n  - ".join(errors))
    validator_reports = [(f"V{i+1}-{validator_models[i].split('/')[-1]}", results[i][0]) for i in range(3)]
    verdicts = [results[i][1] for i in range(3)]
    validator_eval_logs = [results[i][2] for i in range(3)]
```

(3e) At the end of the function, change the `return {...}` to assign to `result`, then run the opt-in emit, then return. Replace `return {` with `result = {` and after the dict literal closes add:

```python
    if emit_bundles:
        try:
            import core_bench_bundle
            paths = core_bench_bundle.emit_core_bench_bundles(
                capsule_id=capsule_id,
                researcher_model=researcher_model,
                validator_models=validator_models,
                validator_reports=validator_reports,
                validator_eval_logs=validator_eval_logs,
                result=result,
                out_dir=bundle_dir,
            )
            result["bundles"] = [str(p) for p in paths]
        except Exception as exc:  # noqa: BLE001 - a derived artifact must never fail a published round
            result["bundles_error"] = str(exc)
    return result
```

(3f) Wire the CLI in `main`. Add two arguments after `--tolerance`:

```python
    parser.add_argument("--emit-bundles", action="store_true",
                        help="after the round, write one valichord_attestation bundle per validator")
    parser.add_argument("--bundle-dir", default="bundles",
                        help="directory for emitted bundles (default: ./bundles, relative to CWD)")
```

And pass them through in the `run_core_bench_protocol(...)` call inside `main`:

```python
    result = run_core_bench_protocol(
        capsule_id=args.capsule,
        researcher_model=args.researcher_model,
        validator_models=args.validator_models,
        n_researcher_runs=args.researcher_runs,
        rel_tolerance=args.tolerance,
        emit_bundles=args.emit_bundles,
        bundle_dir=args.bundle_dir,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd demo && python -m pytest test_core_bench_runner.py test_core_bench_validator.py test_core_bench_bundle.py -q`
Expected: PASS (bundle tests may SKIP if `valichord_attestation` isn't installed; runner + validator tests must pass).

- [ ] **Step 5: Commit**

```bash
git add demo/core_bench_runner.py demo/test_core_bench_runner.py
git commit -m "feat(core-bench): --emit-bundles wires per-validator bundle emission"
```

---

## Task 5: Full demo-suite regression + spec cross-check

**Files:** none (verification only)

- [ ] **Step 1: Run the whole demo test suite**

Run: `cd demo && python -m pytest -q`
Expected: PASS (with the usual skips when optional deps are absent). No regressions in `test_core_bench_*`, `test_app.py`, `tests/`.

- [ ] **Step 2: Confirm the CLI help shows the new flags**

Run: `cd demo && python core_bench_runner.py --help`
Expected: output lists `--emit-bundles` and `--bundle-dir`.

- [ ] **Step 3: Commit any final touch-ups (if needed)**

```bash
git add -A demo/
git commit -m "chore(core-bench): bundle-emit feature complete" || echo "nothing to commit"
```

---

## Self-review

**Spec coverage:**
- Per-validator bundles → Task 2 (`emit_core_bench_bundles` loops validators) ✓
- Hybrid: metrics from report, samples via EEE → Task 2 (`_metrics_from_report` + `_samples_from_eee_log`) ✓
- Validator seam Approach A (additive return, guard untouched) → Task 1 ✓
- `meta.attestation_uri = record_url` + provenance block → Task 2 `build_one_bundle` ✓
- `--emit-bundles` opt-in, default behaviour unchanged → Task 4 (log_dir None unless emitting) ✓
- Error handling: emit failure never invalidates the round → Task 4 (3e try/except → `bundles_error`) + test `test_emit_failure_does_not_break_the_round` ✓
- EEE missing → actionable error → Task 2 `_eee_adapter` + test in Task 3 ✓
- Tests mocked, no live evals → all tasks use monkeypatch/mock/fakes ✓
- Out of scope (EEE submission, issue draft, researcher bundle, challenge-response script) → not present ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every test step shows the assertion. ✓

**Type/name consistency:** `run_validator_eval -> (report, eval_log_path)` (Task 1) is consumed by `_run_one_validator -> (report, verdict, eval_log_path)` (Task 4 3a) and indexed `results[i][2]` (4 3d). `emit_core_bench_bundles(**)` keyword names match the runner call (4 3e) and the test emitter (`seen["validator_eval_logs"]`). `run_core_bench_protocol` gains `emit_bundles`/`bundle_dir`, matching `main` (4 3f) and the wiring tests. `_eee_adapter` / `_samples_from_eee_log` names consistent across Tasks 2–3. ✓

**Note for implementer:** The spec referred to the runner entry point as `run_core_bench_demo`; the real function is `run_core_bench_protocol` (used throughout this plan).
