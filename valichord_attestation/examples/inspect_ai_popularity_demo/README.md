# inspect_ai Popularity Demo — ValiChord Attestation v1.1

## What this demo is

A reference demonstration of the ValiChord v1.1 attestation protocol against an `inspect_ai` `.eval` log, parsed via EveryEvalEver's `InspectAIAdapter` for ecosystem alignment. The demo builds a canonical attestation bundle from real evaluation output, runs a probabilistic challenge-response against the resulting Merkle commitment, and verifies tamper detection. The committed `bundle.json` is fixture-derived for protocol-scale demonstration (50 samples); a real `.eval` parse path is also provided (10 samples, no GPU required for verification). This is a protocol demo, not a statistically powered benchmark run.

---

Demo of the ValiChord attestation protocol (v1.1) against an
[inspect_ai](https://inspect.aisi.org.uk/) `.eval` log file.

**Task:** `popularity` — AI personality self-assessment ("Is the following
statement something you would say?")  
**Model:** `openai/gpt-4o-mini`  
**Source:** inspect_ai test suite — `tests/scorer/logs/` in
[UKGovernmentBEIS/inspect_ai](https://github.com/UKGovernmentBEIS/inspect_ai)  
**Scorer:** `match`  **Accuracy:** 80% (8/10 correct on the real log;
40/50 on the simulated fixture)

This demonstrates the v1.1 attestation protocol on real harness output. The sample size is illustrative — these are reference demos for the cryptographic protocol, not statistically powered benchmark runs.

---

## What this demonstrates

| Feature | Where |
|---|---|
| **inspect_ai .eval parsing via EEE** | `build_bundle.py --eval-path` — reads a real `.eval` ZIP via EEE's `InspectAIAdapter` (pinned to commit `dec1ae43`) |
| **`samples_total` declared explicitly** | `build_bundle.py` — exercises sample-omission defence (threat model §10(d)) |
| **Probabilistic challenge-response** | `challenge_response_demo.py` — k=20 samples challenged against 50-sample fixture |
| **Tamper detection** | Step 5 of demo — replacing one hash causes rejection |
| **Merkle round-trip** | `build_bundle.py` re-canonicalises and confirms hash matches |
| **Fixture mode** | Works without any download — simulated data, same protocol |

Protocol flow:

```
 Researcher / Adapter
│
▼
┌───────────────────┐
│ build_bundle.py   │ (per-sample outputs + raw_metrics
│                   │  → canonicalise → SHA-256 + Merkle root)
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│   bundle.json     │ (verifiable statement; signed log = attested claim)
└─────────┬─────────┘
          │
          ▼
Verifier picks k random sample indices
(verifier_nonce + bundle_hash → deterministic seed)
          │
          ▼
┌─────────────────────────┐
│ challenge_response_demo │ (holder reveals samples + Merkle paths;
│                         │  verifier checks paths against root)
└─────────────┬───────────┘
              │
              ▼
      ✅ verified / ❌ tamper detected
```

---

## Relationship to upstream issues

**Issue #15 — production inspect_evals adapter**  
This demo is a preview of the field mapping needed for a production adapter.
`build_bundle.py` shows the EEE-based extraction pattern:
`EvaluationLog.evaluation_results → metrics`, `InstanceLevelEvaluationLog → per-sample dicts → Merkle tree`.
A production adapter would wrap this in an `AdapterBase` subclass (see
`valichord_attestation/adapters/inspect_evals_stub.py` for the field mapping
comments) and handle the full range of scorer types across inspect_evals tasks.

**inspect_evals#910 — executable evaluation reports**  
Scott Simmons's proposal for reports that can be re-executed to verify
claims maps closely to ValiChord's commit-reveal model: the `.eval` log
is the execution record; the bundle is the cryptographic seal on its outputs.
This demo shows that the v1.1 protocol works directly against inspect_ai-produced
data — the format round-trip is solved.

---

## EveryEvalEver (EEE) as the parsing layer

`build_bundle.py` uses EveryEvalEver's `InspectAIAdapter` (pinned to commit
`dec1ae43`) as the `.eval` parsing layer instead of calling
`inspect_ai.log.read_eval_log()` directly.

**Why EEE?**  The demo's strategic purpose is to demonstrate alignment with
the EvalEval Coalition's aggregate schema — referenced by Matt Fisher in PR
#1610 and Scott Simmons's inspect_evals#910 proposal for executable evaluation
reports.  Using EEE's converter is a concrete signal that ValiChord's
attestation format is compatible with the ecosystem's emerging eval-record
standards.

**Trade-offs (honest):**

1. **Extra transitive dependencies.** EEE's inspect converter pulls in
   `duckdb`, `seaborn`, and requires `huggingface-hub<1.0.0` — which conflicts
   with `inspect-evals`'s `>=1.2.0` requirement.  Both install successfully;
   pip warns about the conflict but EEE imports and runs correctly.

2. **File-system side-effect.** EEE writes per-sample JSONL to a temporary
   directory as an intermediate step.  `build_bundle.py` reads those files
   before the tempdir is removed, so no persistent files are left on disk.

3. **Merkle root change from int → str sample_id.** `read_eval_log()` returns
   integer sample ids (`1, 2, …`); EEE emits them as strings (`"1", "2", …`).
   Because ValiChord's Merkle tree hashes the JCS representation of each sample
   dict, the different JSON type changes every leaf hash and therefore the
   Merkle root.  The old root (`56c91950…`) was produced with int sample_ids;
   the current root (`227b5f8d…`) reflects EEE's native string output.  This
   is documented in `build_bundle.py`'s module docstring.

4. **Re-mapping still required.** EEE's JSONL schema needs a translation step
   before it serves as Merkle leaves — the same observation that applied to the
   original evaluation.  `extract_bundle_samples_from_eee()` in `build_bundle.py`
   provides that mapping explicitly, with field-by-field comments.

**EEE alignment is the right long-term direction.** If EEE's schema stabilises
to a form that naturally exposes Merkle-ready per-sample dicts, the re-mapping
layer will thin.  See Issue #15 for the production adapter roadmap.

---

## About the .eval file

The `.eval` file downloaded by `download_eval.sh` is a test fixture committed
to the inspect_ai repository to validate the `match` scorer.  It is **not** an
inspect_evals benchmark result.  It was chosen because it is the smallest
publicly available real inspect_ai `.eval` log:

| Property | Value |
|---|---|
| Size | 21 KB |
| Task | `popularity` |
| Model | `openai/gpt-4o-mini` |
| Samples | 10 |
| Scorer | `match`  (C/I values — correct / incorrect) |
| Accuracy | 0.80 (stderr 0.133) |
| Produced by | inspect_ai 0.3.58.dev16+g6a87748b |
| Licence | MIT (UKGovernmentBEIS/inspect_ai) |

The `.eval` file is a ZIP archive containing `header.json`, per-sample JSON
files under `samples/`, `summaries.json`, and `reductions.json`.
`read_eval_log()` handles parsing; the ZIP is never opened manually.

---

## No download? Run the demo anyway

**Quickest run:** `bash verify_demo.sh`

The committed `bundle.json` was produced from built-in simulated data
(`random.Random(42)`, 50 samples, 80% accuracy).  All scripts run without any
download or API key:

```bash
# Reproduce the committed bundle from scratch (fixture mode):
python build_bundle.py --fixture --generated-at "2026-05-07T00:00:00+00:00"

# Run the challenge-response demo:
python challenge_response_demo.py
```

---

## Full reproduction (with the real .eval log)

**Step 1 — download the eval log**

```bash
bash download_eval.sh
# Saves: popularity.eval  (21 KB)
```

**Step 2 — build the bundle from the real log**

```bash
python build_bundle.py --eval-path ./popularity.eval
```

This parses the `.eval` log, extracts 10 samples and the accuracy metric,
and writes `bundle.json`.  Note: the committed `bundle.json` was built from
the 50-sample fixture, not the real 10-sample log.  Regenerating will replace
it with a different hash and a smaller sample count.

**Step 3 — run the challenge-response demo**

```bash
python challenge_response_demo.py
```

No download required.  Loads `bundle.json` and runs the full v1.1 protocol.
When run against the real 10-sample log, `k` is automatically capped at 10.

---

## Files

| File | Purpose |
|---|---|
| `verify_demo.sh` | One-step verification: builds bundle (fixture mode) + runs challenge-response demo |
| `download_eval.sh` | Downloads `popularity.eval` (21 KB) from inspect_ai's GitHub |
| `build_bundle.py` | Parses `.eval` log (or fixture) → `bundle.json` |
| `challenge_response_demo.py` | Challenge-response walkthrough |
| `bundle.json` | Committed bundle (simulated fixture; replace with real eval) |

**Not committed** (gitignored):

```
*.eval          # the downloaded .eval log file
```

---

## Honest framing

This is a **reference demo**, not a production adapter.

- The `.eval` file is an inspect_ai test fixture, not an inspect_evals benchmark
  result.  It was chosen for size (21 KB) and accessibility (public GitHub URL),
  not for scientific significance.

- The committed `bundle.json` is produced from simulated data.  It demonstrates
  that the ValiChord v1.1 protocol works against inspect_ai-format inputs — the
  field mapping is correct and the round-trip validates.

- The 10-sample real log (80% accuracy) is not a statistically meaningful
  evaluation of GPT-4o-mini.  The full `popularity` task has more items.

- A production adapter would need to handle the full diversity of inspect_evals
  tasks: multi-metric scorers, numeric score values (not just C/I), multi-epoch
  runs, and tasks with structured (non-string) inputs.  `build_bundle.py` handles
  the common case cleanly; edge cases are noted in comments.

---

## Pinned versions

| Component | Version |
|---|---|
| inspect_ai | ≥ 0.3.46 (`.eval` format introduced) — tested with 0.3.217 |
| valichord_attestation | v1.1 |
| Python | 3.10+ |
