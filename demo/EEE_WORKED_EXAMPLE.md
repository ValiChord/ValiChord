# EEE worked example — independent-reproduction bundles for CORE-Bench

A small, end-to-end worked example that produces **EveryEvalEver (EEE)-compatible
attestation bundles** from a real ValiChord commit–reveal round, and anchors them
to a live, tamper-evident HarmonyRecord.

It is the artifact behind the EEE outreach (issue [#156](https://github.com/evaleval/every_eval_ever/issues/156)). The point
it demonstrates, concretely:

> Several validators reproduced one CORE-Bench capsule **independently and blind**,
> each sealed its result before seeing the others, all three landed on the same
> number — and every per-validator record is generated through EEE's own
> `InspectAIAdapter` and points at **one shared, content-addressed record** proving
> the reproductions were independent.

---

## What it produces

`demo/eee_worked_example.py` writes one bundle per validator to
`demo/bundles_worked_example/`:

```
bundle_capsule-0851068_v1_anthropic_claude-sonnet-4-6.json
bundle_capsule-0851068_v2_anthropic_claude-sonnet-4-6.json
bundle_capsule-0851068_v3_anthropic_claude-sonnet-4-6.json
```

Each is a `valichord_attestation` v1.2 bundle. The parts that matter:

| Field | Source | Value in this example |
|---|---|---|
| `metrics` | the validator's reproduced `report.json` | AUC `0.915795` |
| `samples` | parsed from the run's `.eval` log via **EEE `InspectAIAdapter`** | 1 sample (`capsule-0851068`) |
| `meta.attestation_uri` | the shared, live HarmonyRecord | `http://132.145.34.27:3001/record?hash=uhC8k4j2…` |
| `meta.committed_claim` | researcher's pre-committed interval | `[0.9148794716565768, 0.9167110621904239]` |
| `outputs_merkle_root` | Merkle tree over the samples | (per bundle) |

All three validators independently reproduced the capsule's final AUC to 16
digits (`0.9157952669235003`), inside the researcher's committed interval — hence
the round's on-chain outcome `Reproduced` / `ExactMatch`.

---

## Two ways to run it

### Path A — regenerate the worked example offline (free, no API key)

This rebuilds the bundles from existing `.eval` logs and the existing public
record. No model calls, no Docker, no Holochain — runs in seconds.

**Requires** the three input logs to be present under `demo/logs/` (the ones
named in `eee_worked_example.py`). They are run artifacts and are `.gitignore`d
by default, so this path works out-of-the-box only where those logs exist (or
once they have been committed alongside — see "Making Path A portable" below).

```bash
# 1. install the two extra Python deps (one-time)
pip install -e ./valichord_attestation
pip install 'every-eval-ever[inspect] @ git+https://github.com/evaleval/every_eval_ever.git@dec1ae43e0741a37003425eafe6699d3296145ec'

# 2. run the generator FROM the demo/ directory (see gotcha below)
cd demo
python3 eee_worked_example.py
```

`inspect_ai` and `inspect_evals` are already pinned in `demo/requirements.txt`;
if you are in a clean environment, `pip install -r demo/requirements.txt` first.

> **cwd gotcha — run from `demo/`, not the repo root.** The repo contains a
> `valichord_attestation/` *directory*; from the repo root that directory shadows
> the installed package and imports fail with `cannot import name 'build_bundle'`.
> Running from `demo/` (or any directory that is not the repo root) resolves the
> installed package correctly.
>
> Installing EEE downgrades `huggingface_hub` (it conflicts with the
> `inspect_evals` pin on paper); both still import and the adapter path works.

Expected output:

```
committed interval: [0.9148794716565768, 0.9167110621904239] (basis=explicit_tolerance)

bundle_capsule-0851068_v1_anthropic_claude-sonnet-4-6.json
  bundle_sha256 : f34c1d08…
  metrics       : [{'key': 'Report the final AUC after training.', 'value': 0.915795}]
  samples       : 1  -> ['capsule-0851068']
  attestation   : http://132.145.34.27:3001/record?hash=uhC8k4j2…
…
3 bundles written to bundles_worked_example/
```

### Path B — a fresh live round (paid, the general path)

Path A reuses one already-completed round. To produce bundles from a brand-new
round of your own, use the shipped `--emit-bundles` flag on the CORE-Bench runner.
This actually runs three AI validators reproducing the capsule in isolated
sandboxes, so it needs an API key, Docker, ~30 GB disk and ~30–45 min, and costs
a few dollars. Full setup is in `demo/CORE_BENCH_DEMO.md`; the short version:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
cd demo
python3 core_bench_runner.py --capsule capsule-0851068 --emit-bundles
# bundles written to ./bundles/  (override with --bundle-dir <path>)
```

The bundle contents and filenames are the same shape as Path A
(`bundle_<capsule>_v<n>_<model>.json`).

---

## Verify it yourself

The shared record the bundles point at is live and self-verifying — anyone can
fetch it without running anything:

```bash
curl "http://132.145.34.27:3001/record?hash=uhC8k4j2xO83gyCFCBMTAtx2Nyy_i_Yr4oDk-X1XJlbOZsI0-bYNT"
# -> { "outcome": {"type":"Reproduced"}, "agreement_level": "ExactMatch", "validator_count": 3, ... }
```

(Use the **full** hash — a truncated hash returns a raw deserialize error.)

Inspect a generated bundle:

```bash
python3 -c "import json; b=json.load(open('bundles_worked_example/bundle_capsule-0851068_v1_anthropic_claude-sonnet-4-6.json'))['bundle']; print(b['metrics'], b['meta']['attestation_uri'])"
```

---

## What this does and does not show (read before quoting it)

- **It does show:** three reproductions of the same capsule that are
  non-copying and deterministic — each validator ran the capsule from scratch,
  sealed its result blind, and all three matched — anchored to one tamper-evident
  record.
- **It does not show full independence.** This example is **same-model** (three
  runs of `claude-sonnet-4-6`, the round that produced the public record). Genuine
  independence needs different models/operators — straightforward to run, just not
  what this particular record shows. Use Path B with three different models for a
  cross-model claim.
- **The per-sample layer is thin for CORE-Bench.** One capsule is one sample, and
  CORE-Bench's `report.json` scorer doesn't populate per-sample `target` /
  `model_answer` fields, so the substance is in `metrics` + the attestation, not
  rich per-sample rows.

---

## Files

| File | Role |
|---|---|
| `demo/eee_worked_example.py` | the offline generator (Path A) |
| `demo/core_bench_bundle.py` | bundle assembly + the real EEE `InspectAIAdapter` call (shared by Path A/B) |
| `demo/report_to_verdict.py` | `derive_committed_claim`, `build_numeric_panel` (committed interval + metrics) |
| `demo/bundles_worked_example/` | the generated bundles |
| `demo/logs/*.eval` | input inspect_ai logs (run artifacts; `.gitignore`d by default) |
| [EEE issue #156](https://github.com/evaleval/every_eval_ever/issues/156) | the outreach issue this example supports |

### Making Path A portable

Because `demo/logs/*.eval` are git-ignored, a fresh clone cannot run Path A. To
let anyone reproduce the exact committed bundles offline, commit the three input
logs (force-add, since they are ignored) alongside the generated bundles:

```bash
git add -f demo/logs/2026-05-31T20-40-04-*.eval \
           demo/logs/2026-05-31T20-44-49-*.eval \
           demo/logs/2026-05-31T20-55-30-*.eval
git add demo/bundles_worked_example/ demo/eee_worked_example.py demo/EEE_WORKED_EXAMPLE.md
```
