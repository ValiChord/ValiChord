# Independent Stability Attestation for L1 Feature Selection

A self-contained demonstration: five independent parties resample separately, run a
pre-registered selection procedure, seal their results, and reveal simultaneously — so the
question *"would anyone else have selected these features?"* is answered by parties who could
not see each other's answer.

**Read [`REPORT.md`](REPORT.md) for the argument and the results.**

```bash
pip install -r requirements.txt
./run_all.sh
```

No API key, no GPU, no network, no Holochain conductor. Runs in about a minute.

## Why L1 selection

An L1 penalty is tuned by a single scalar. Nudge it and a specific coefficient goes to exactly
zero. Nothing in a published model reveals how many values were tried, or that the final one was
chosen because of which variable it excluded. *"We did not use postcode"* and *"L1 dropped
postcode at the penalty strength we happened to select"* are materially different claims that
produce an identical model card.

A complete record of every run *would* expose that — if the recorder recorded everything. That is
self-policing, and it answers *"what did I do?"* It cannot answer *"would anyone else, on their
own split, have chosen these features?"*

## Files

| File | Step |
|---|---|
| `generate.py` | Synthetic data with correlated blocks; fixed seed, published hash |
| `lambda_rule.py` | The pre-registered procedure — hashed into `protocol.json` as code, not prose |
| `protocol.py` | Pre-registration record, canonicalised (JCS) and hashed |
| `party.py` | One party: resample → rule → support → seal |
| `round.py` | Commit all, reveal all, verify each reveal against its seal |
| `aggregate.py` | Exact-match verdict, per-feature frequency, per-block frequency |
| `lambda_shop.py` | The adversarial exhibit, and the honest limit |
| `bundles.py` | One `valichord_attestation` bundle per party; verifies the two-hash semantics |
| `sweep.py` | Repeats the round over many datasets — detection rate, false-alarm rate, operating curve |
| `arbitration.py` | Scores three rules for picking a block's true member against known ground truth |

Artefacts land in `artifacts/` and are regenerated on every run.

`run_all.sh` covers the single round (about a minute). The two studies are run
separately because they take longer:

```bash
python3 sweep.py --replications 150       # ~25 min
python3 arbitration.py --replications 100 # ~12 min
```

## Scope

The commit-reveal arithmetic, the attack, and the bundles are real. The **parties are simulated** —
six processes in one script, not six agents on a DHT — and **nothing here runs on Holochain**.
The blinding is enforced by a guard in `round.py`, not by a network. See `REPORT.md` §"What was
real and what was not" before quoting any of it.

Plan: `docs/FEATURE_SELECTION_STABILITY_PLAN.md`.
