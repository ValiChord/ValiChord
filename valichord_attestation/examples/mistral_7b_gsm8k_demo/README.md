# Mistral-7B GSM8K Demo — ValiChord Attestation v1.1

Real-data example of the ValiChord attestation protocol (v1.1) on a standard
AI benchmark: [GSM8K](https://huggingface.co/datasets/openai/gsm8k) (100-sample
subset) evaluated with
[Mistral-7B-Instruct-v0.3](https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3).

The bundle committed here was produced by the scripts below.  The
`challenge_response_demo.py` script runs against it without any GPU.

---

## What this demonstrates

| Feature | Where |
|---|---|
| `samples_total=100` declared explicitly | `build_bundle.py` — exercises the sample-omission defence (threat model §10(d)) |
| Probabilistic challenge-response | `challenge_response_demo.py` — k=20 samples challenged (20% of log) |
| Tamper detection | Step 5 of demo — replacing one hash causes rejection |
| Merkle round-trip | `build_bundle.py` re-canonicalises and confirms hash matches |

---

## Pinned versions

| Component | Version |
|---|---|
| lm-evaluation-harness | `v0.5.0` |
| transformers | `4.46.3` |
| accelerate | `1.2.1` |
| Mistral-7B-Instruct-v0.3 | `mistralai/Mistral-7B-Instruct-v0.3` (pin revision for strict reproducibility — see `run_eval.sh`) |
| GSM8K dataset | via HuggingFace `openai/gsm8k` |

---

## Cost and runtime

| Resource | Estimate |
|---|---|
| GPU | NVIDIA RTX 4090 (16 GB VRAM) or equivalent |
| Wall-clock time | ~10–15 minutes for 100 samples, 5-shot, batch size 1 |
| Cost | ~£1.50 on RunPod spot instance (~$0.40/hr) |

---

## Reproducing this demo

### Prerequisites

| Requirement | Notes |
|---|---|
| OS | Linux or WSL2 (macOS untested; Windows native not supported by lm-eval) |
| Python | 3.10 or 3.11 (3.12 may have dependency conflicts) |
| CUDA | 12.x (CUDA 11.x not tested with torch 2.5.1) |
| VRAM | ≥16 GB for `bfloat16` · ≥8 GB if you add `load_in_4bit=True` (see below) |
| RAM | ≥32 GB system RAM recommended |
| Disk | ≥20 GB free (model weights ~14 GB + harness output) |

### HuggingFace access

Mistral-7B-Instruct-v0.3 is a gated model.  Before running the eval:

1. Accept the licence at https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3
2. Log in from the terminal:
   ```bash
   pip install huggingface_hub
   huggingface-cli login
   # Paste your HF read-access token when prompted
   ```

If the eval exits with a 401 or `OSError: You are trying to access a gated repo`, you have not accepted the licence or your token is missing/expired.

### Install dependencies

```bash
pip install -r requirements.txt
```

`requirements.txt` pins all versions to match `run_eval.sh`.  Note that
`lm-evaluation-harness v0.5.0` is **not on PyPI** — the latest published
version there is 0.4.11.  `requirements.txt` installs it directly from the
tagged GitHub commit.  Do not run `pip install lm-eval==0.5.0`; that will
install the wrong version.

For the 8 GB VRAM path, also install `bitsandbytes` and add `load_in_4bit=True`
to the `--model_args` line in `run_eval.sh`:

```bash
pip install "bitsandbytes>=0.44.0"
# In run_eval.sh, change:
#   --model_args "pretrained=mistralai/Mistral-7B-Instruct-v0.3,...,dtype=bfloat16"
# to:
#   --model_args "pretrained=mistralai/Mistral-7B-Instruct-v0.3,...,load_in_4bit=True"
```

### Expected outputs

After `bash run_eval.sh` completes:

```
eval_output/
└── mistralai__Mistral-7B-Instruct-v0.3/
    └── <timestamp>/
        ├── results_<timestamp>.json         # accuracy metric
        └── samples_gsm8k_<timestamp>.jsonl  # per-sample outputs (--log_samples)
```

Pass `--output-path ./eval_output` to `build_bundle.py` to parse this structure.

### Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `OSError: 401` or gated-repo error | HF token missing or licence not accepted | `huggingface-cli login`; accept licence at HF |
| `CUDA out of memory` | VRAM too low | Add `load_in_4bit=True` to `--model_args`; install `bitsandbytes` |
| `ModuleNotFoundError: lm_eval` | pip install failed or wrong version | `pip install -r requirements.txt` (not `pip install lm-eval==0.5.0`) |
| `FileNotFoundError` in `build_bundle.py` | `--log_samples` flag missing | Re-run `run_eval.sh`; that flag is required for per-sample output |
| Bundle hash mismatch in demo | `bundle.json` edited after build | Re-run `python build_bundle.py --output-path ./eval_output` |

---

## How to reproduce from scratch

**Step 1 — run the eval (GPU required)**

```bash
# Provision a GPU instance (RunPod, Colab Pro, local hardware).
# Then:
bash run_eval.sh
```

Output written to `./eval_output/`.

**Step 2 — build the bundle**

```bash
python build_bundle.py --output-path ./eval_output
```

This reads the lm-eval results and samples files, extracts the accuracy metric
and per-sample outputs, and writes `bundle.json`.

**Step 3 — run the challenge-response demo**

```bash
python challenge_response_demo.py
```

No GPU required.  Loads `bundle.json` and runs the full v1.1 protocol.

---

## No GPU? Run the demo anyway

The committed `bundle.json` was produced from built-in simulated data
(deterministic, `random.Random(42)`).  All scripts run without a GPU:

```bash
# Reproduce the committed bundle from scratch (fixture mode):
python build_bundle.py --fixture --generated-at "2026-05-06T00:00:00+00:00"

# Then run the demo:
python challenge_response_demo.py
```

The `_source.warning` field in `bundle.json` documents that this is simulated
data.  Run `run_eval.sh` on a GPU to replace it with real eval output.

---

## Files

| File | Purpose |
|---|---|
| `run_eval.sh` | Installs lm-eval, runs GSM8K eval, writes `eval_output/` |
| `requirements.txt` | Pinned deps matching `run_eval.sh` (lm-eval from git, not PyPI) |
| `build_bundle.py` | Parses eval output → `bundle.json` |
| `challenge_response_demo.py` | Challenge-response walkthrough |
| `bundle.json` | Committed bundle (simulated fixture; replace with real eval) |

**Not committed** (add to `.gitignore` before a real eval run):

```
eval_output/       # gigabytes of harness output + model cache
```

---

## Honest framing

This demo uses 100 samples from GSM8K.  The full benchmark is 1,319 test
problems.  A 100-sample subset is sufficient to demonstrate the protocol and
costs far less GPU time, but it is not a statistically robust accuracy
estimate.  Production deployments should target the full benchmark (or whatever
sample size your statistical plan requires), and the declared `samples_total`
should match that plan.

The synthetic fixture accuracy of 35% is consistent with published benchmarks
for Mistral-7B-Instruct-v0.3 on GSM8K (5-shot, greedy decoding).  A real GPU
run may produce slightly different numbers depending on harness version,
sampling strategy, and exact model revision.
