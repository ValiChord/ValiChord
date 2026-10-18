# valichord_attestation — Examples

## Synthetic examples

| File | Description |
|---|---|
| `simple_eval.json` | 10-sample GSM8K-shaped bundle (gpt-4o, synthetic) |
| `complex_eval.json` | 16-sample agentdojo/travel bundle with 3 metrics (claude-3-5-sonnet, synthetic) |
| `simple_eval_v2.json` | The same 10 samples as `simple_eval.json`, written as a format **v2** bundle (current format; different Merkle root) |
| `verify_examples.py` | Loads all three JSONs, recomputes hashes and Merkle roots under each bundle's own `format_version`, verifies sample proofs |
| `challenge_response_demo.py` | Full challenge-response walkthrough on a 500-sample synthetic bundle (built now, so it is a v2 bundle) |

> **Format versions (note 2026-10-18).** The committed bundles in this folder and in both demo
> folders are format **v1** except `simple_eval_v2.json`. They still verify. Anything you build
> fresh with `build_bundle` (including the demos' `build_bundle.py`) is **v2**, so its root and
> hashes will not match the committed v1 file.

Run all synthetic verifications:

```bash
python verify_examples.py
python challenge_response_demo.py
```

---

## Real-data examples

### `mistral_7b_gsm8k_demo/`

End-to-end demo of the v1.1 protocol on a real AI benchmark:
Mistral-7B-Instruct-v0.3 evaluated on GSM8K (100-sample subset) via
lm-evaluation-harness v0.5.0.

- Demonstrates `samples_total=100` declared explicitly (sample-omission defence)
- k=20 probabilistic challenge-response against a 100-sample Merkle tree
- Committed `bundle.json` runnable without a GPU (simulated fixture)
- `run_eval.sh` + `build_bundle.py` to reproduce from a real GPU run

See [`mistral_7b_gsm8k_demo/README.md`](mistral_7b_gsm8k_demo/README.md) for
full instructions, cost estimate, and reproduction steps.

---

### `inspect_ai_popularity_demo/`

Demo of the v1.1 protocol against an **inspect_ai `.eval` log** — a different
eval harness format (ZIP-based binary, structured per-sample JSON, C/I scorer
values) from the lm-evaluation-harness JSONL format used in the GSM8K demo.

Task: `popularity` AI personality self-assessment — GPT-4o-mini evaluated on
"Is the following statement something you would say?" questions via the `match`
scorer.  Sourced from inspect_ai's public test suite (21 KB, no GPU required).

- Parses a real inspect_ai `.eval` ZIP via **EEE's `InspectAIAdapter`** (pinned to commit `dec1ae43`)
- Demonstrates `samples_total` declared explicitly on the real 10-sample log
- k=20 probabilistic challenge-response against the 50-sample fixture bundle
- Fixture mode (committed `bundle.json`) runs without any download
- `download_eval.sh` + `build_bundle.py --eval-path` for real `.eval` parsing
- Honest accounting of EEE trade-offs (transitive deps, file-system side-effects, Merkle root change)

See [`inspect_ai_popularity_demo/README.md`](inspect_ai_popularity_demo/README.md)
for full instructions, EEE reasoning, and the relationship to Issue #15 and
inspect_evals#910 (executable evaluation reports).
