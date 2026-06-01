# Maintainer-facing CORE-Bench Doc — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write `docs/CORE_BENCH_FOR_INSPECT_EVALS.md` — a thorough, respectful, in-repo doc for inspect_evals maintainers describing the CORE-Bench × ValiChord demo (what it does / doesn't yet do / what's needed / the gap it fills), plus a "reproduce it yourself" section that defaults to a local stack.

**Architecture:** A single Markdown doc, written section by section against the approved design spec (`docs/superpowers/specs/2026-06-01-core-bench-inspect-evals-doc-design.md`). It re-frames material already in `docs/CORE_BENCH_INTEGRATION.md` (internal strategy) and `demo/CORE_BENCH_DEMO.md` (internal run guide) for a new reader; it does not duplicate their internal parts. "Verification" for each task is a fact-check against the repo plus a check of the spec's honesty/exclusion constraints — there is no code and no test runner.

**Tech Stack:** Markdown. Fact-checks use `git`/`grep`/`ls` against this repo.

**Source facts (verified this session — reuse verbatim, do not re-derive):**
- Chosen capsule: `capsule-0851068` (Medical Sciences, Python, MLP COVID/skin classification). Single question; deterministic ground truth **`0.9157952669235003`**.
- Public HarmonyRecord (Oracle DHT, 2026-05-31 all-Sonnet run): `uhC8k4j2xO83gyCFCBMTAtx2Nyy_i_Yr4oDk-X1XJlbOZsI0-bYNT`. **Predates the `/record` numeric panel** — use only as the commit-reveal artifact; never show the panel as live on it.
- Prebuilt happs are committed: `valichord/workdir/valichord.happ`, `researcher.happ`, `validator.happ` → no Rust/Holochain toolchain needed to run the stack.
- Runner defaults to the Oracle nodes (`demo/demo_runner.py:23-26`) unless `VALICHORD_*_URL` is set.
- Prereqs: privileged Docker (`privileged: true` in the inspect sandbox compose), a paid provider API key (free tiers insufficient), ~30 GB free disk, `git` on host (the inspect_evals pin is a `git+` URL), ~30–45 min wall-clock, validators run sequentially.

**Hard rules from the spec (must hold in every task's prose):**
- **No claim of a verified clean local end-to-end run.** The `/record` panel + gossip-free echo were unit-tested and `node --check`'d only; the last full run used our Oracle nodes. State the local path as the intended route; list "verify local end-to-end" as a to-do.
- **Claim the right guarantee** (commit-reveal prevents result-copying/fabrication for deterministic code, not opinion-anchoring).
- **Don't overclaim independence** (same model + same operator = correlated, not independent).
- **Exclude** (these stay in the internal docs): outreach tactics; Oracle IP as the default run target; per-run dollar costs; Codespace disk sizes; the GPG password for the ground-truth dataset.

**Commit after every task.** Push only in the final task.

---

## Task 1: Scaffold the doc + the gap opener (§1) and close (§8)

**Files:**
- Create: `docs/CORE_BENCH_FOR_INSPECT_EVALS.md`

- [ ] **Step 1: Create the file with the full section skeleton and the framing bookends**

Write exactly this skeleton (the eight `##` headings in order), then fill §1 and §8 with the prose below; leave the other sections as a single-line HTML comment placeholder `<!-- written in a later task -->` directly under each heading:

```markdown
# CORE-Bench × ValiChord — an independent-verification layer for reproduction evals

> For the inspect_evals maintainers. This describes a working demo that runs the
> existing `core_bench` task and adds a multi-party, blinded, tamper-evident
> verification layer on top. Composition, not competition — Inspect runs the
> reproduction; this makes the result independently checkable.
>
> Related (internal) docs in this repo: `demo/CORE_BENCH_DEMO.md` (run guide),
> `docs/CORE_BENCH_INTEGRATION.md` (architecture & rationale).

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

<!-- written in a later task -->

## What it does

<!-- written in a later task -->

## What it doesn't do yet

<!-- written in a later task -->

## How it fills the gap

<!-- written in a later task -->

## Reproduce it yourself

<!-- written in a later task -->

## What still needs doing

<!-- written in a later task -->

## In one sentence

Several agents ran the code in isolated environments. None could see the others'
results before they committed. The record, on a network no single party controls,
shows what each one got — and you can verify it yourself with a single `curl`. A
CORE-Bench *score* becomes a CORE-Bench *attestation*.
```

- [ ] **Step 2: Verify the framing constraints hold**

Run:
```bash
cd /workspaces/ValiChord && grep -niE "superior|better than|replace|beats|lead with the demo|open warm|demote" docs/CORE_BENCH_FOR_INSPECT_EVALS.md
```
Expected: **no matches** (no competition language, no outreach tactics). If anything matches, reword to composition framing.

- [ ] **Step 3: Commit**

```bash
git add docs/CORE_BENCH_FOR_INSPECT_EVALS.md
git commit -m "docs(core-bench): inspect_evals doc — scaffold + gap opener and close"
```

---

## Task 2: §2 "What you'd actually see"

**Files:**
- Modify: `docs/CORE_BENCH_FOR_INSPECT_EVALS.md` (replace the §2 placeholder)

- [ ] **Step 1: Replace the `## What you'd actually see` placeholder with this prose**

```markdown
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
on a node running the current code — a `numeric_convergence` panel like:

​```json
{
  "outcome": "Reproduced",
  "agreement_level": "ExactMatch",
  "validator_count": 3,
  "numeric_convergence": [
    {"validator": 1, "metric": "AUC", "value": "0.9157952669235003",
     "lower": 0.9148, "upper": 0.9167, "match": true}
  ]
}
​```

> Honest note: the public record linked above is from the run that first proved
> the protocol end-to-end; it predates the `numeric_convergence` panel, so a
> `curl` of *that* record shows the base fields without the panel. The JSON above
> is the panel's shape as produced by the current node code (see "Reproduce it
> yourself").
```

(Replace the two `​```json` fences' zero-width-space marker with normal triple backticks when writing — they are shown here only to nest the block inside this plan.)

- [ ] **Step 2: Verify the record hash and capsule facts against the repo**

Run:
```bash
cd /workspaces/ValiChord && grep -c "uhC8k4j2xO83gyCFCBMTAtx2Nyy_i_Yr4oDk-X1XJlbOZsI0-bYNT" PROJECT_STATUS.md demo/CORE_BENCH_DEMO.md && grep -c "0.9157952669235003" demo/CORE_BENCH_DEMO.md
```
Expected: the hash appears in both source docs (counts ≥ 1 each) and the AUC value appears in the run guide. If the hash does not match, fix the doc to the value in `PROJECT_STATUS.md`.

- [ ] **Step 3: Commit**

```bash
git add docs/CORE_BENCH_FOR_INSPECT_EVALS.md
git commit -m "docs(core-bench): inspect_evals doc — what you'd actually see (artifact)"
```

---

## Task 3: §3 "What it does" + §4 "What it doesn't do yet"

**Files:**
- Modify: `docs/CORE_BENCH_FOR_INSPECT_EVALS.md` (replace the §3 and §4 placeholders)

- [ ] **Step 1: Replace the `## What it does` placeholder**

```markdown
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
```

- [ ] **Step 2: Replace the `## What it doesn't do yet` placeholder**

```markdown
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
- **The `/record` numeric panel + the gossip-free outcome echo are unit-tested and
  syntax-checked, but have not yet been exercised against a live conductor.** The
  most recent *full* run used hosted nodes for the commit-reveal half; a clean
  local end-to-end with the current node code is a pending verification step (see
  "What still needs doing").
```

- [ ] **Step 3: Verify the candor claims match the repo's own caveats**

Run:
```bash
cd /workspaces/ValiChord && grep -niE "Provisional|self-assign|self-claim|select_validators" docs/7_ValiChord_4-DNA_architecture_technical.md | head && grep -niE "not yet|importorskip|node --check|manual" demo/CORE_BENCH_DEMO.md | head
```
Expected: the Phase-0 limitations (Provisional tiers, stub validator assignment) appear in the architecture doc, confirming §4's claims are grounded. Adjust §4 wording to match if anything differs.

- [ ] **Step 4: Commit**

```bash
git add docs/CORE_BENCH_FOR_INSPECT_EVALS.md
git commit -m "docs(core-bench): inspect_evals doc — what it does / doesn't do yet"
```

---

## Task 4: §5 "How it fills the gap"

**Files:**
- Modify: `docs/CORE_BENCH_FOR_INSPECT_EVALS.md` (replace the §5 placeholder)

- [ ] **Step 1: Replace the `## How it fills the gap` placeholder**

```markdown
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
```

- [ ] **Step 2: Verify the table and claims are consistent with the internal doc**

Run:
```bash
cd /workspaces/ValiChord && grep -niE "composition, not competition|correlated, not independent|result-copying" docs/CORE_BENCH_INTEGRATION.md | head
```
Expected: these load-bearing phrases exist in the internal strategy doc, confirming the reframing is faithful (not invented). If absent, reconcile wording with `CORE_BENCH_INTEGRATION.md`.

- [ ] **Step 3: Commit**

```bash
git add docs/CORE_BENCH_FOR_INSPECT_EVALS.md
git commit -m "docs(core-bench): inspect_evals doc — how it fills the gap"
```

---

## Task 5: §6 "Reproduce it yourself" (local-stack default)

**Files:**
- Modify: `docs/CORE_BENCH_FOR_INSPECT_EVALS.md` (replace the §6 placeholder)

- [ ] **Step 1: Replace the `## Reproduce it yourself` placeholder**

```markdown
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
until [ "$(docker compose -f docker-compose.yml logs 2>/dev/null | grep -c 'node API ->')" -ge 4 ]; do sleep 3; done && echo Ready

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

For a genuine *independence* claim rather than a "the protocol works"
demonstration, pass three different models to `--validator-models` (e.g. Claude /
GPT-4o / Gemini) — see "How it fills the gap".
```

(When writing, render the inner ```bash fence as a normal fenced block.)

- [ ] **Step 2: Verify every path and command exists / is correct**

Run:
```bash
cd /workspaces/ValiChord && ls demo/requirements-core-bench.txt demo/docker-compose.yml demo/core_bench_spike.py demo/core_bench_runner.py valichord/workdir/valichord.happ && grep -nE "node API ->|node API →" demo/*.mjs | head -2 && grep -nE "researcher-runs|validator-models|researcher-model" demo/core_bench_runner.py | head
```
Expected: all listed files exist; the readiness grep string matches what the node scripts actually print (adjust the `grep -c` token in the doc to the real arrow character if it differs); the three CLI flags exist in the runner. Fix the doc to match reality if any check fails.

- [ ] **Step 3: Commit**

```bash
git add docs/CORE_BENCH_FOR_INSPECT_EVALS.md
git commit -m "docs(core-bench): inspect_evals doc — reproduce it yourself (local-stack default)"
```

---

## Task 6: §7 "What still needs doing" (incl. the optional register field)

**Files:**
- Modify: `docs/CORE_BENCH_FOR_INSPECT_EVALS.md` (replace the §7 placeholder)

- [ ] **Step 1: Replace the `## What still needs doing` placeholder**

```markdown
## What still needs doing

- **Make the local stack the default run target.** The runner currently defaults
  to hosted nodes; a maintainer should never accidentally write to ours. Flip the
  default to localhost (or ship a one-command `make demo`).
- **Verify the local end-to-end with the current node code** — the `/record` panel
  and gossip-free echo are unit-tested but not yet run against a live conductor.
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
```

- [ ] **Step 2: Verify the optional-ask framing (no pressure language)**

Run:
```bash
cd /workspaces/ValiChord && grep -niE "we need|you must|please add|required|we request|we ask you" docs/CORE_BENCH_FOR_INSPECT_EVALS.md
```
Expected: **no matches** in the register-field area (the ask must read as optional). Reword if anything matches.

- [ ] **Step 3: Commit**

```bash
git add docs/CORE_BENCH_FOR_INSPECT_EVALS.md
git commit -m "docs(core-bench): inspect_evals doc — what still needs doing + optional register field"
```

---

## Task 7: Final pass — exclusions audit, cross-links, push

**Files:**
- Modify: `docs/CORE_BENCH_FOR_INSPECT_EVALS.md`
- Modify: `docs/CORE_BENCH_INTEGRATION.md` (add one cross-link line)
- Modify: `demo/CORE_BENCH_DEMO.md` (add one cross-link line)

- [ ] **Step 1: Exclusions audit — the doc must NOT contain internal-only material**

Run:
```bash
cd /workspaces/ValiChord && grep -niE "132\.145\.34\.27|reproducibility|gpg|\\\$[0-9]|per run|codespace|128 ?gb|lead with|open warm|demote the" docs/CORE_BENCH_FOR_INSPECT_EVALS.md
```
Expected: **no matches.** Specifically: no Oracle IP, no GPG/dataset password, no dollar costs, no Codespace/disk figures, no outreach tactics. If anything matches, remove or reword it. (The only allowed mention of hosted nodes is the honest "the last full run used hosted nodes" caveat — which uses the word "hosted", not the IP.)

- [ ] **Step 2: Overclaim audit — no claim of a verified live run**

Run:
```bash
cd /workspaces/ValiChord && grep -niE "verified live|we ran the local|confirmed end-to-end locally|tested against a live conductor" docs/CORE_BENCH_FOR_INSPECT_EVALS.md
```
Expected: **no matches** asserting a live local run. The doc may say the panel is "unit-tested" and "not yet run live" — confirm that honest phrasing is present:
```bash
grep -niE "not yet|unit-tested" docs/CORE_BENCH_FOR_INSPECT_EVALS.md | head
```
Expected: at least one match (the §4 / §7 honesty caveat).

- [ ] **Step 3: Add cross-links from the two internal docs to the new one**

In `docs/CORE_BENCH_INTEGRATION.md`, under the top `## What this is` paragraph, add:
```markdown
> **Maintainer-facing version:** for an external, respectful summary to share with
> inspect_evals maintainers, see `docs/CORE_BENCH_FOR_INSPECT_EVALS.md` (this doc is
> the internal strategy/architecture source it draws from).
```

In `demo/CORE_BENCH_DEMO.md`, directly under the title line, add:
```markdown
> Maintainer-facing summary (external, respectful): `docs/CORE_BENCH_FOR_INSPECT_EVALS.md`.
```

- [ ] **Step 4: Full read-through against the spec's success criteria**

Read `docs/CORE_BENCH_FOR_INSPECT_EVALS.md` end to end and confirm against
`docs/superpowers/specs/2026-06-01-core-bench-inspect-evals-doc-design.md`:
- a maintainer can understand what it proves, what it doesn't, and how to run it;
- no internal tactics, no infra-default;
- every in-scope limitation stated; no unverified claim;
- the register-field ask is unmistakably optional.
Fix any prose that fails a criterion.

- [ ] **Step 5: Commit and push**

```bash
git add docs/CORE_BENCH_FOR_INSPECT_EVALS.md docs/CORE_BENCH_INTEGRATION.md demo/CORE_BENCH_DEMO.md
git commit -m "docs(core-bench): finalize inspect_evals maintainer doc + cross-links"
git push origin main
```
Expected: push succeeds; `git status -sb` shows `main...origin/main` with no ahead/behind.

---

## Self-review (completed by plan author)

- **Spec coverage:** §1 gap → Task 1; §2 artifact → Task 2; §3 does → Task 3; §4 doesn't-yet → Task 3; §5 fills-gap → Task 4; §6 reproduce → Task 5; §7 needs-doing + optional ask → Task 6; §8 close → Task 1; honesty/exclusion constraints → Tasks 1, 6, 7 audits. All spec sections covered.
- **Placeholder scan:** the only `<!-- ... -->` placeholders are the deliberate skeleton markers in Task 1, each replaced by name in Tasks 2–6. No "TBD"/"handle appropriately" steps.
- **Consistency:** section headings used in the audits (Task 7) match the exact headings created in Task 1 (`What you'd actually see`, `What it does`, `What it doesn't do yet`, `How it fills the gap`, `Reproduce it yourself`, `What still needs doing`). The capsule id, AUC value, and record hash are identical across Tasks 2–5.
