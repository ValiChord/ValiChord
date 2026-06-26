# CORE-Bench × ValiChord — an independent-verification layer for reproduction evals

> For the inspect_evals maintainers. This describes a working demo that runs the
> existing `core_bench` task and adds a multi-party, blinded, tamper-evident
> verification layer on top. Composition, not competition — Inspect runs the
> reproduction; this makes the result independently checkable.
>
> Run guide in this repo: `demo/CORE_BENCH_DEMO.md`.

## The gap this fills

A CORE-Bench `.eval` log is **single-author and self-attested**. Nothing in it
proves a *second* party would get the same output, nothing stops the producer
re-running until the number looks right, and there is no multi-party, blinded,
tamper-evident record of who got what. That is a real gap in the eval-framework
space, and it is not a feature Inspect built worse — it is a category Inspect has
no mechanism for. Inspect **runs** the reproduction; ValiChord makes the
reproduction's result **independently checkable** by a third party who wasn't in
the room. The two compose; neither replaces the other.

## What you'd actually see

The demo runs the `core_bench` task on a single deterministic capsule,
`capsule-0851068` (Medical Sciences, Python — an MLP COVID/skin classifier with
one question: *"Report the final AUC after training."*). A researcher runs the
capsule and seals the result; three validators each reproduce it blind in isolated
sandboxes; all commit, then reveal simultaneously; a HarmonyRecord is written.

The headline output is a per-validator numeric panel: each validator's produced
value against the researcher's **committed** interval — pure arithmetic, not a
model's opinion. For this capsule every faithful run lands on the same value
(`0.9157952669235003`), so the agreement is `ExactMatch`.

The record is public and recomputable. One from a real run:

```bash
curl "http://<researcher-node>/record?hash=uhC8k4j2xO83gyCFCBMTAtx2Nyy_i_Yr4oDk-X1XJlbOZsI0-bYNT"
```

It returns the outcome, the agreement level, the participating validators, and —
on a node running the current code — a `numeric_convergence` panel. This is **real
output, captured 2026-06-01 from a verified local run** (all-Sonnet, three blind
validators), abridged for length:

```json
{
  "outcome": "Reproduced",
  "agreement_level": "ExactMatch",
  "validator_count": 3,
  "execution_agreement": {
    "level": "ExactMatch",
    "means": "agreement_level='ExactMatch' is independent EXECUTION agreement: all participating validators independently produced a result. It is NOT a claim that their numbers agree — see numeric_convergence."
  },
  "numeric_convergence": [
    {"validator": 1, "metric": "Report the final AUC after training.",
     "value": "0.9157952669235003", "lower": 0.9148794716565768, "upper": 0.9167110621904239, "match": true},
    {"validator": 2, "metric": "Report the final AUC after training.",
     "value": "0.9157952669235003", "lower": 0.9148794716565768, "upper": 0.9167110621904239, "match": true},
    {"validator": 3, "metric": "Report the final AUC after training.",
     "value": "0.9157952669235003", "lower": 0.9148794716565768, "upper": 0.9167110621904239, "match": true}
  ],
  "committed_claim": [
    {"metric": "Report the final AUC after training.",
     "value": "0.9157952669235003", "interval": "[0.9148794716565768, 0.9167110621904239] (explicit_tolerance)"}
  ]
}
```

> Honest note: the *public* record linked above (on a hosted node) is from the run
> that first proved the protocol end-to-end; that hosted node runs older code, so a
> `curl` of *that* record shows the base fields without the panel. The JSON shown
> here is real output from a **local** run on 2026-06-01 that we verified against a
> live conductor — reproduce it for yourself below to get the same panel on your
> own node.

## What it does

- **N agents reproduce the same capsule, blind and isolated.** Each validator runs
  the `core_bench` hard-difficulty agent in its own Docker sandbox. Hard mode
  deletes `results/`, `REPRODUCING.md`, and the run scripts, so the agent gets only
  code + data + README + the question — it cannot read the target.
- **A pre-round blinding gate proves the answer isn't readable from retained
  files.** Deletion is necessary but not sufficient (a README could quote the
  number). Before any validator runs, the gate scans every retained file for the
  committed answer and **hard-aborts the round** if it leaks — turning "the agent
  can't see the target" from an assumption into a per-round, tested check.
- **The verdict is arithmetic, not opinion.** A validator's committed outcome is
  execution-success only; the *match* against the researcher's claim is computed at
  reveal as `lower ≤ value ≤ upper` (inclusive) against the researcher's
  **committed** interval. No adjudicator model sits in the trust path.
- **Commit-reveal removes last-mover advantage.** Each validator seals its
  `report.json` before any other reveals; copying would require predicting the
  others' outputs.
- **The record is recomputable.** The outcome, agreement level, and the per-metric
  numeric panel are derivable from a single `curl` — you don't have to trust the
  demo, the researcher, or any validator.

## What it doesn't do yet

Stated plainly, because this audience is equipped to notice an overclaim:

- **One capsule.** The demo uses a single, pre-verified, deterministic capsule.
  The more representative case — a *stochastic* capsule where multiple validators
  triangulate a noisy quantity — is not yet wired in.
- **Validators self-assign.** There is no assignment engine, conflict-of-interest
  detection, or institutional balancing yet (Phase 0); validators claim a study
  directly.
- **Reputation is `Provisional` in production.** Badge tiers currently reflect
  participant count and agreement only, not an earned validator track record.
- **No automated handoff** from a `.eval` log to the protocol — running the demo is
  a manual sequence today.
- **The `/record` numeric panel + gossip-free echo are verified against a live
  local conductor (all-Sonnet, 2026-06-01)** — that is the source of the real JSON
  above — **but not yet in a mixed-model run or a hosted deployment.** The only
  *publicly* curl-able record today is on a hosted node running older code, so it
  shows the base fields without the panel; the panel is reproducible locally (see
  below).

## How it fills the gap

| | CORE-Bench alone | ValiChord alone | Combined |
|---|---|---|---|
| Reproduction is computational | ✅ agent runs real code | ❌ (web-search demo) | ✅ |
| Verdict is objective | ✅ code output matches or not | ❌ agent forms an opinion | ✅ |
| Multiple independent parties | ❌ one agent, one result | ✅ N validators | ✅ |
| Structural independence | ❌ a second runner can see the first's result | ✅ commit-reveal | ✅ |
| Permanent verifiable record | ❌ a log file | ✅ HarmonyRecord | ✅ |
| No post-hoc adjustment | ❌ re-run and pick the best | ✅ commit-reveal | ✅ |

**What N independent runs actually prove** (stated narrowly, because precision
matters here): for deterministic code with pinned dependencies, N correct runs
produce the same output — so commit-reveal's guarantee is **prevented result-copying
and fabrication**, not *prevented opinion-anchoring*. Concretely, N hard-mode runs
show: (1) the capsule executes from scratch with no hints; (2) the result is robust
across independent environments; (3) no agent fabricated or copied a result.

Two precision rules we hold to, and ask you to hold us to:

- **Claim the right guarantee.** For deterministic code the value is anti-copying
  and anti-fabrication — not anti-anchoring. We state it that narrowly.
- **Don't overclaim independence.** N runs of the *same* model by the *same*
  operator are correlated, not independent. Genuine independence comes from
  diversity across the validator set (different models / operators / environments).
  The demo defaults to mixed models for exactly this reason; an all-one-model run
  is labelled honestly as same-model.

## Reproduce it yourself

Everything runs on your own machine — nothing depends on our servers.

**Prerequisites**

- **Docker, privileged.** The inspect sandbox's `compose.yaml` sets
  `privileged: true`.
- **A paid provider API key.** Agentic reproduction needs a capable model; free
  tiers are not enough (OpenAI free → `insufficient_quota`; Google free excludes
  `gemini-2.5-pro`). The cheapest working setup is all-Anthropic (one key).
- **~30 GB free disk** (each sandbox grows to ~14 GB; validators run sequentially,
  one at a time).
- **`git` on the host** — the `inspect_evals` pin is a `git+` URL.
- ~30–45 min wall-clock for a full run.

**Steps**

```bash
# 1. Install the demo deps (kept out of the web requirements on purpose)
cd demo
pip install -r requirements-core-bench.txt

# 2. (optional) confirm the capsule reproduces before a full run (~10 min)
python3 core_bench_spike.py --capsule capsule-0851068 \
    --model anthropic/claude-sonnet-4-6

# 3. Bring up YOUR OWN 5-conductor stack. The happs ship prebuilt, so there is
#    no Rust/Holochain build step.
docker compose -f docker-compose.yml up --build -d
until [ "$(docker compose -f docker-compose.yml logs 2>/dev/null | grep -c 'node API →')" -ge 4 ]; do sleep 3; done && echo Ready

# 4. Point the runner at your local stack (so the record is written to YOUR DHT)
export VALICHORD_RESEARCHER_URL=http://localhost:3001
export VALICHORD_VALIDATOR_1_URL=http://localhost:3002
export VALICHORD_VALIDATOR_2_URL=http://localhost:3003
export VALICHORD_VALIDATOR_3_URL=http://localhost:3004

# 5. Full run (all-Sonnet: one key, deterministic capsule, same-model label)
python3 core_bench_runner.py --capsule capsule-0851068 --researcher-runs 1 \
    --researcher-model anthropic/claude-sonnet-4-6 \
    --validator-models anthropic/claude-sonnet-4-6 anthropic/claude-sonnet-4-6 anthropic/claude-sonnet-4-6

# 6. Verify the record yourself, from your own node
curl "http://localhost:3001/record?hash=<external_hash_from_the_run_output>"

# 7. Tear down between runs
docker compose -f docker-compose.yml down -v
```

The steps above use **all-Sonnet** — one API key, and the configuration we have
verified end-to-end. It demonstrates that the protocol works; it is honestly a
*same-model* run (see "How it fills the gap").

### Mixed-model — untested, and we'd genuinely value your report

The configuration that earns the word *independent* without an asterisk is three
**different** models, so a shared model blind-spot can't pass undetected through
all three. We have plumbed this path (provider-specific wiring for OpenAI and
Google is in place), **but we have not completed a mixed-model run end-to-end** —
we haven't had paid API access across all three providers at once. If you do
(AISI very likely does), you're better-placed than we are to run it. The only
change is the model list:

```bash
python3 core_bench_runner.py --capsule capsule-0851068 --researcher-runs 1 \
    --researcher-model anthropic/claude-sonnet-4-6 \
    --validator-models anthropic/claude-sonnet-4-6 openai/gpt-4o google/gemini-2.5-pro
```

Prerequisite: **paid** keys for all three (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
`GOOGLE_API_KEY`) — free tiers won't do agentic reproduction. This is explicitly
**untested**: it may surface a provider-specific bug, and if it does, that report
is exactly what we'd want. Pass or fail, we'd love to hear how it goes.

## What still needs doing

- ~~**Make the local stack the default run target.**~~ Done — the runner now
  defaults to `localhost:3001–3004`, and `demo/run_local_demo.sh` brings up the
  stack and runs the demo in one command. To record on the Oracle DHT instead,
  set the `VALICHORD_*_URL` env vars explicitly.
- **Exercise mixed-model and a hosted, public record.** The local all-Sonnet
  end-to-end is verified (2026-06-01); still to do: a mixed-model run (Claude /
  GPT-4o / Gemini) and a hosted node running the current code so there is a
  *publicly* curl-able, panel-showing record (today's public record predates the
  panel).
- **Add a stochastic capsule** so the demo shows multiple validators triangulating
  a noisy quantity, not just confirming a deterministic value.
- **Validator assignment, reputation, and packaging** are Phase-1 work (see
  `docs/7_ValiChord_4-DNA_architecture_technical.md`).

**A possible future step — entirely optional, and not something this doc is asking
for.** If it were ever useful, an optional `valichord_attestation_uri` field in the
inspect_evals register schema would let a task point at a HarmonyRecord, making an
independent-verification attestation discoverable from the eval itself. It needs
nothing from you to *exist* — the demo already runs without it — it would only make
the integration *discoverable* later. Mentioned for completeness, not as a request.

## In one sentence

Several agents ran the code in isolated environments. None could see the others'
results before they committed. The record, on a network no single party controls,
shows what each one got — and you can verify it yourself with a single `curl`. A
CORE-Bench *score* becomes a CORE-Bench *attestation*.
