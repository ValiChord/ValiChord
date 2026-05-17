---
name: generate-attestation-bundle
description: Generate a ValiChord cryptographic attestation bundle for an inspect_ai evaluation run. Use when: (1) an inspect_ai .eval log file is available, (2) the user wants to attest or publish evaluation results with a verifiable hash, (3) adding attestation as a step in an eval-report workflow. Produces a bundle.json containing bundle_hash and content_hash that can be committed alongside evaluation artifacts.
---

# Generate ValiChord Attestation Bundle

This skill produces a cryptographically verifiable attestation bundle from an
inspect_ai evaluation log and optionally an `eval.yaml` metadata file.

The bundle commits to:
- The model identifier and task
- All scalar metrics (accuracy, stderr, etc.)
- A Merkle root over every per-sample output
- Provenance (harness version, git commit, timestamp)

Two hashes are produced:
- **`bundle_hash`** — full identity hash including meta/provenance
- **`content_hash`** — scientific equivalence hash (excludes meta); identical
  across reruns of the same eval with different provenance

## When to use

Add this as the final step after an evaluation report is complete:
- After `make check` passes and the README table is filled in
- The `.eval` log file is available in `logs/`
- Optional: `eval.yaml` metadata is available for task-level provenance

## Workflow

### Step 1 — Identify inputs

1. Find the relevant `.eval` log file (most recent success in `logs/`):
   ```bash
   uv run inspect log list --json --status success | tail -5
   ```
2. Note the eval name and version from the `@task` function's `version` argument
   (or from `eval.yaml`).
3. Note whether `eval.yaml` exists in `src/<eval_name>/`.

### Step 2 — Generate the bundle

Run the following Python snippet (adapt paths as needed):

```python
from valichord_attestation import InspectAILogAdapter
from valichord_attestation.canonical import bundle_to_dict, hash_bundle, content_hash
import json, yaml
from pathlib import Path

LOG_PATH  = "logs/<your-log-file>.eval"     # path to .eval log
EVAL_YAML = "src/<eval_name>/eval.yaml"      # optional
OUT_PATH  = "agent_artefacts/<eval_name>/attestation_bundle.json"

# Load eval.yaml metadata (optional enrichment)
eval_yaml_metadata = None
if Path(EVAL_YAML).exists():
    with open(EVAL_YAML) as f:
        eval_yaml_metadata = yaml.safe_load(f)
    # Remove the evaluation_report block if present — it's handled separately
    eval_yaml_metadata.pop("evaluation_report", None)

# Build the bundle
adapter = InspectAILogAdapter()
bundle = adapter.to_bundle(
    LOG_PATH,
    meta_extras=eval_yaml_metadata and {
        "paper_arxiv": eval_yaml_metadata.get("arxiv"),
        "eval_group":  eval_yaml_metadata.get("group"),
    },
)

bh = hash_bundle(bundle)
ch = content_hash(bundle)
bundle_dict = bundle_to_dict(bundle)

Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
Path(OUT_PATH).write_text(json.dumps({
    "bundle_hash":   bh,
    "content_hash":  ch,
    "bundle":        bundle_dict,
}, indent=2) + "\n")

print(f"bundle_hash:  {bh}")
print(f"content_hash: {ch}")
print(f"Written: {OUT_PATH}")
```

### Step 3 — Add hashes to the README evaluation report

After the results table in `README.md`, add:

```markdown
**Attestation:**
- bundle_hash: `<bundle_hash_hex>`
- content_hash: `<content_hash_hex>` (scientific equivalence — stable across reruns)
- Full bundle: `agent_artefacts/<eval_name>/attestation_bundle.json`
```

### Step 4 — Commit the bundle file

```bash
git add agent_artefacts/<eval_name>/attestation_bundle.json README.md
git commit -m "Add ValiChord attestation bundle for <eval_name>"
```

## Alternative: using InspectEvalsAdapter (eval.yaml evaluation_report path)

If the eval.yaml has an `evaluation_report:` block and you have per-sample
dicts available (e.g., from a previous EEE parse), use `InspectEvalsAdapter`:

```python
from valichord_attestation import InspectEvalsAdapter
import yaml

with open("src/<eval_name>/eval.yaml") as f:
    full_yaml = yaml.safe_load(f)

eval_report_block = full_yaml.pop("evaluation_report")
eval_yaml_metadata = full_yaml  # remaining keys: title, arxiv, group, tasks, ...

adapter = InspectEvalsAdapter()
bundle = adapter.to_bundle(
    eval_report_block,
    eval_log_samples,           # list of per-sample dicts
    eval_yaml_metadata=eval_yaml_metadata,
)
```

This path folds `arxiv`, `group`, `human_baseline`, and floating-dataset
warnings from `eval.yaml` into `Bundle.meta`.

## Checklist gap note

The `EVALUATION_CHECKLIST.md` currently has no cryptographic verification
step. Committing an attestation bundle fills that gap: the `content_hash`
lets any third party verify that the published accuracy figures correspond to
the exact eval run that produced them, without re-running the evaluation.

## Verification (challenge-response)

To verify that a bundle is not fabricated (spot-check k random samples):

```python
from valichord_attestation import build_response, verify_response, Challenge
import json, os

with open("agent_artefacts/<eval_name>/attestation_bundle.json") as f:
    data = json.load(f)

bundle_hash = data["bundle_hash"]
samples     = data["samples"]
nonce       = os.urandom(16)
k           = 20

challenge = Challenge(bundle_hash=bundle_hash, k=k, verifier_nonce=nonce)
response  = build_response(challenge, samples)
ok        = verify_response(challenge, response, samples)
print("Verified:", ok)   # True iff all k Merkle paths check out
```
