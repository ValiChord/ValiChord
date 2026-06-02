# CORE-Bench bundle-emit — design

**Date:** 2026-06-02
**Status:** Approved (brainstorming complete; ready for implementation plan)
**Scope:** Bundle-emit feature only. Submitting bundles to EveryEvalEver (EEE) and drafting the GitHub issue are separate downstream tasks.

## Motivation

The CORE-Bench × ValiChord demo (`demo/core_bench_runner.py`) runs a full commit-reveal round — researcher claim → three mixed-model validators reproduce blind → simultaneous reveal → HarmonyRecord on the Holochain DHT — and returns a recomputable numeric panel. It does **not** currently produce a `valichord_attestation` bundle, and it never touches EEE.

We want a CORE-Bench run to also emit **per-validator attestation bundles** that can later be submitted to EveryEvalEver as records. Each bundle is a `model × task` record whose metrics are that validator's reproduced numbers and whose `meta.attestation_uri` points at the shared, tamper-evident HarmonyRecord. The strategic value: a database of independent cross-model reproductions of the same eval, each provably blind to the others and cryptographically anchored — a data shape EEE does not currently hold.

The bundle is built through EEE's own `InspectAIAdapter` (already a pinned dependency in `valichord_attestation/examples/inspect_ai_popularity_demo/`), so "built on EEE's tooling" is literally true and visible — a goodwill/trust signal, not a load-bearing dependency for the headline numbers.

## Key decisions (settled in brainstorming)

1. **Per-validator bundles** — one bundle per validator reproduction (not one combined bundle), matching EEE's per-(model, task) granularity. This is the artifact that makes the cross-model-reproduction story land.
2. **Hybrid EEE usage — real + visible, not load-bearing.** CORE-Bench uses a custom `capture_report` scorer: the headline numbers live in `report.json`, not in a standard inspect score EEE can read. So:
   - `raw_metrics` come from ValiChord's own data (the validator's reproduced `report`).
   - `samples` are parsed from the `.eval` log via EEE's `InspectAIAdapter` (gives the Merkle-rooted sample set and makes the EEE dependency real and visible).
3. **Validator seam via additive return (Approach A).** `run_validator_eval` keeps a single code path — including the error guard that protects published HarmonyRecords — and stops discarding the eval log; it returns the `.eval` log path additively.

## Verified API facts (ground truth, checked in code)

- `valichord_attestation.build_bundle(*, model_id, task_id, raw_metrics, samples, samples_total=None, repo_commit=None, harness_version=None, command=None, meta=None, generated_at=None) -> Bundle`.
- `raw_metrics`: `list[dict]` with keys `"key"` (str, required), `"value"` (float, pre-rounded 6 dp, required), `"stderr"` (float, optional), `"filter"` (str, optional). Missing required keys raise `MalformedBundleError`.
- `samples`: `list[dict]`, must be **non-empty**; used to compute `outputs_merkle_root`.
- `build_bundle` raises `MalformedBundleError` if `metrics` is empty, and requires `samples_total >= len(samples)`.
- `Bundle` is a dataclass (not a Pydantic model). Serialise via `bundle_to_dict(bundle)` then `json.dumps(...)`; canonical hash via `hash_bundle(bundle)`; per-sample proof via `merkle_proof(samples, i)`.
- EEE adapter usage (from popularity demo): `from every_eval_ever.converters.inspect.adapter import InspectAIAdapter`; `adapter.transform_from_file(<.eval path>)` → an EEE `EvaluationLog`; helpers `extract_metrics_from_eee` and `extract_bundle_samples_from_eee` map it into `build_bundle` format.
- `demo/core_bench_validator.py::run_validator_eval(capsule_id, model)` currently returns the report dict (or `None` for a genuine no-reproduction); it raises `RuntimeError` on a non-success `EvalLog` status. It is called both by validators and by `run_researcher_claim` (n_runs times).
- `demo/core_bench_runner.py::run_core_bench_demo(...)` returns a dict including `committed_claim`, `validator_reports` (`[(label, report), …]`), `validator_verdicts`, `external_hash_b64`, `harmony_record_hash`, `outcome`, `agreement_level`, `record_url`.

## Components

### 2a. Validator seam — `demo/core_bench_validator.py`

Change `run_validator_eval` to accept an optional `log_dir` and return the eval log path additively:

```
run_validator_eval(capsule_id, model, log_dir=None) -> (report: Optional[dict], eval_log_path: Optional[str])
```

- Pass `log_dir` through to `inspect_eval(task, model=model, log_dir=log_dir)` so the `.eval` file is written to a known location when a `log_dir` is supplied (when `None`, behaviour is unchanged).
- `eval_log_path = getattr(logs[0], "location", None)` after the existing success-status guard (the guard is unchanged — it still raises on non-success status to protect published records).
- `report` is unchanged (still `None` only for a genuine no-reproduction).

Update the single internal caller `run_researcher_claim` to `report, _ = run_validator_eval(capsule_id, model)` (it does not need the log path).

In `core_bench_runner.py`, `_run_one_validator` threads the path through, returning `(report, verdict, eval_log_path)`.

### 2b. New module — `demo/core_bench_bundle.py`

```
emit_core_bench_bundles(
    *,
    capsule_id: str,
    researcher_model: str,
    validator_models: list[str],
    validator_reports: list[tuple[str, dict]],   # [(label, report), ...]
    validator_eval_logs: list[Optional[str]],    # one .eval path per validator
    result: dict,                                # runner return dict (record_url, hashes, claim, ...)
    out_dir: Path,
) -> list[Path]
```

For each validator `i`:
- `model_id = validator_models[i]`; `task_id = f"inspect_evals/core_bench:{capsule_id}"`.
- `raw_metrics` ← validator `i`'s reproduced values, extracted from its `report` for each required claim key (`{"key": q, "value": <reproduced value>}`). These are the numbers *that model produced*. The report-reading logic must reuse the canonical extraction already in `report_to_verdict.py` / `build_numeric_panel` (the same code that derives the verdict and numeric panel), not a second ad-hoc parse — so the bundle's metrics always equal the panel's values by construction.
- `samples` ← EEE: `InspectAIAdapter().transform_from_file(validator_eval_logs[i])` → `extract_bundle_samples_from_eee(...)` (reuse the popularity-demo helpers; copy or import them into a shared location — decided in planning).
- `meta` ← provenance block:
  - `attestation_uri = result["record_url"]` (the HarmonyRecord — the EEE provenance hook)
  - `harmony_record_hash`, `external_hash_b64`, `outcome`, `agreement_level`
  - `committed_claim` (the sealed interval the reproduction was judged against)
  - `capsule_id`, `capsule_checksum` (`CAPSULE_CHECKSUMS[capsule_id]`)
  - `researcher_model`, `validator_model = model_id`, `validator_label = label`
  - `eee_commit`, `protocol = "valichord-commit-reveal"`
- Build via `build_bundle(...)`; serialise to the popularity-demo wrapper shape `{"_source": …, "bundle": bundle_to_dict(b), "samples": samples}`; write to `out_dir / f"bundle_{capsule_id}_{model_id.replace('/', '_')}.json"`.
- `EEE` is imported lazily inside the function; if missing, raise a clear error with the install line (mirror the popularity demo's `_eee_adapter` pattern).

### 2c. Runner wiring — `demo/core_bench_runner.py`

- New CLI flags: `--emit-bundles` (bool) and `--bundle-dir` (default `demo/bundles/`).
- When `--emit-bundles` is set: create a per-run `log_dir` (e.g. a temp dir or `bundle-dir/logs/<run-uuid>/`), pass it into the validator runs, and collect each validator's `eval_log_path` alongside `validator_reports`.
- After the HarmonyRecord is written (step 6), call `emit_core_bench_bundles(...)` and attach `result["bundles"] = [str(p) for p in paths]`.
- When `--emit-bundles` is not set, no `log_dir` is created, the validator runs behave exactly as today, and no bundle code runs.

## Data flow

```
validator eval (log_dir)
   ├─ .eval log  ──► EEE InspectAIAdapter.transform_from_file ──► extract_bundle_samples_from_eee ──► samples
   └─ report.json ──► reproduced values for required keys ─────────────────────────────────────────► raw_metrics
                                                                                                       │
result.record_url / hashes / committed_claim ──────────────────────────────────────────► meta ◄───────┤
                                                                                                       ▼
                                                  build_bundle ──► bundle_to_dict + hash_bundle ──► bundle_<capsule>_<model>.json
```

One bundle per validator; all share `meta.attestation_uri` (the single HarmonyRecord).

## Error handling

- Bundle emission is **derived and opt-in** and runs only after a successful round, so it must never invalidate a completed protocol round. The entire emit call is wrapped in try/except in the runner: on failure, set `result["bundles_error"] = <message>` and still return the successful `result` (the HarmonyRecord remains the source of truth).
- Per-validator failures (EEE parse error, `MalformedBundleError` from empty metrics/samples) are collected and surfaced loudly in `bundles_error` / logs — `--emit-bundles` was explicitly requested — but still do not roll back the protocol.
- Missing EEE dependency raises a clear, actionable error (install instruction) rather than a bare `ImportError`.

## Testing (all mocked — no live evals)

- **`core_bench_bundle`:** fixture `.eval` log (or a stubbed EEE adapter) + a fixture `result` dict → assert N bundles written; each has correct `model_id`/`task_id`; `raw_metrics` match the validator report; `meta.attestation_uri == result["record_url"]`; stable `bundle_hash` across reruns with identical inputs; samples non-empty.
- **Validator seam:** mock `inspect_eval` to return a fake `EvalLog` exposing `.location`, `.status`, `.samples` → `run_validator_eval` returns `(report, path)`; non-success status still raises; the researcher caller still unpacks `report, _`.
- **Runner wiring:** `--emit-bundles` parsed; `emit_core_bench_bundles` called with the collected paths; **emit raising → `result` still returned with `bundles_error` set** (protocol not rolled back).
- Reuse the monkeypatch/`setenv` style already in `demo/test_core_bench_runner.py` and `demo/test_core_bench_validator.py`.

## Out of scope (YAGNI)

- Submitting bundles to EEE (separate task).
- Drafting the GitHub issue / worked example (separate writing artifact).
- A researcher-claim bundle (per-validator only, by decision 1).
- A CORE-Bench-specific challenge-response verification script (the popularity demo already has the verification pattern; not needed to emit).
