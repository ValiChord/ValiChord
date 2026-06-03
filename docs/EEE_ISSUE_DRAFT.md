# DRAFT — EveryEvalEver issue (for review, NOT yet posted)

Target repo: `evaleval/every_eval_ever` (issues enabled). Gift-first, no-pressure,
composition-not-competition — same posture as the inspect_evals outreach. Posting
is the user's call. A personal warm intro to **MattFisher** (contributor to both
EEE and inspect_evals) is handled separately (see `OUTREACH_MESSAGE_DRAFT.md`); this
public issue body stays clean and does not @-mention.

Honesty constraints baked in (do not soften):
- The worked example is **same-model** (3× claude-sonnet-4-6). It proves
  non-copying + determinism, **not** full operator/model independence.
- The per-sample layer is **thin for CORE-Bench** (1 capsule = 1 sample; the
  report.json scorer leaves `target`/`model_answer` empty). The substance is in
  the metrics, not the samples — say so.
- The HarmonyRecord is real and live today; it reflects the **all-Sonnet** round
  that actually produced it. We do not claim cross-model.

---

## Title

A run-provenance layer for generated submissions: tamper-evident proof that N parties independently reproduced a result (CORE-Bench worked example)

## Body

Hi — I've been building something that sits right next to EEE and wanted to put
it in front of you, in case it's useful. No ask attached.

#144 (making adapters mandatory for generated submissions) is close to it. #144
makes the *transformation* reproducible — `source → adapter → record`, so a
record can't be quietly hand-edited after the fact. As the issue itself notes, it
"would not prove that the source data or adapter are correct": it secures the
*transformation*, not the *run* that produced the source data.

That run-level gap is what I've been working on, as a layer that sits *above* the
adapter rather than competing with it:

> Can you show that several parties independently re-ran an eval, each sealed its
> result before seeing the others, and none could have copied another — without
> trusting any single submitter?

The mechanism is a blind commit–reveal: each party commits a hash of its result,
then all reveal together, and the outcome is written to a tamper-evident record
on a peer-to-peer network (Holochain — no blockchain, no token, no central
server). The record is content-addressed and reflects exactly who participated.

Here's a real one. I ran the inspect_evals `core_bench` task — `capsule-0851068`,
reproducing a paper's AUC — with three validators reproducing it blind. All three
landed on the same value to 16 digits (`0.9157952669235003`), inside the
researcher's pre-committed interval. The shared record is live right now:

```
curl "http://132.145.34.27:3001/record?hash=uhC8k4j2xO83gyCFCBMTAtx2Nyy_i_Yr4oDk-X1XJlbOZsI0-bYNT"
# -> { outcome: Reproduced, agreement_level: ExactMatch, validator_count: 3, ... }
```

The part relevant to EEE: I ran each validator's native `.eval` log through your
inspect converter (`every_eval_ever convert inspect`), and the provenance attaches
naturally in `source_metadata` — an `attestation_uri` pointing every record at the
one shared anchor:

```jsonc
// source_metadata on each per-validator record
"source_metadata": {
  "evaluator_relationship": "third_party",
  "additional_details": {
    "protocol": "valichord-commit-reveal",
    "attestation_uri": "http://132.145.34.27:3001/record?hash=uhC8k4j2xO83gyCFCBMTAtx2Nyy_i_Yr4oDk-X1XJlbOZsI0-bYNT",
    "outcome": "Reproduced",
    "agreement_level": "ExactMatch",
    "committed_interval": "[0.9148794716565768, 0.9167110621904239]"
  }
}
```

That keeps the exact `source → adapter → record` pipeline #144 is after, and adds
one optional pointer: a link to a single record showing the three reproductions
were independent and blind.

Two things I'm not claiming, to keep it straight:
- This example is **same-model** (three runs of one model). It demonstrates
  non-copying and determinism, not full independence — that needs different
  operators/models, which is easy to run but isn't what this record shows.
- For CORE-Bench, one capsule is one sample, and its scorer doesn't fill the
  usual per-sample `target`/`model_answer` fields, so the weight is on the metric
  and the attestation, not rich per-sample rows.

The actual question: would a record-level `attestation_uri` — a stable link to an
independent-reproduction record — be worth EEE carrying, e.g. as a recognised key
under `source_metadata.additional_details`? It's the same provenance concern as
#144, one level up. If it's useful I'll put the worked example up as a
`[Submission]` PR to the EEE_datastore — the `eval.schema.json` record plus its
instance-level `_samples.jsonl` — so you can see it end to end; if not, no problem
and no need to reply.

---

## If they reply positively → step 3 (submission mechanics, verified from EEE docs 2026-06-03)

- Submissions are **PRs to the Hugging Face datastore** `evaleval/EEE_datastore`,
  not the GitHub repo. Layout: `data/{benchmark}/{developer}/{model}/{uuid}.json`
  (an `EvaluationLog`, `eval.schema.json` v0.2.2) **plus** `{uuid}_samples.jsonl`
  (instance-level, `instance_level_eval.schema.json`). `[Submission]` PR-title prefix.
- Validation: `uv run python -m every_eval_ever validate data/` locally, or comment
  `/eee validate changed` on the HF PR. An EvalEval member reviews + merges.
- **We have NOT produced an `EvaluationLog` yet** — only a `valichord_attestation`
  bundle whose samples came via the inspect converter. Step 3 = assemble the real
  `EvaluationLog` + `_samples.jsonl` from the logs (`every_eval_ever convert inspect
  --log_path …`) and put the `attestation_uri` in `source_metadata.additional_details`.
- `source_metadata.additional_details` is **string-valued only**
  (`additionalProperties: {type: string}`) — encode `committed_interval` and any
  non-string value as a string.
- Only propose a *recognised* `attestation_uri` field after the example lands —
  never the opening move.
- If cross-model independence is wanted as the headline, do the paid mixed-model
  run first (different models/operators) and host that record before submitting.
