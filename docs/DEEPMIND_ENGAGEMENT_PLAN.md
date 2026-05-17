# Google DeepMind — ValiChord Engagement Plan

**Created:** 2026-05-17  
**Status — CAMPAIGN COMPLETE (2026-05-17)**

| # | Repo | Issue | Project | Notes |
|---|---|---|---|---|
| 1 | dangerous-capability-evaluations | [#40](https://github.com/google-deepmind/dangerous-capability-evaluations/issues/40) | A | Safety eval independence, sealed-verdict angle |
| 2 | concordia | [#271](https://github.com/google-deepmind/concordia/issues/271) | B→A | Model drift gap from PR #265; active thread |
| 3 | debate | — | A | **Archived repo** — no issues possible |
| 4 | meltingpot | [#338](https://github.com/google-deepmind/meltingpot/issues/338) | A+B | Post-hoc scenario bug hook from CHANGELOG |
| 5 | bbeh | [#10](https://github.com/google-deepmind/bbeh/issues/10) | B | PR ready on fork; waiting for Mehran Kazemi |
| 6 | physics-IQ-benchmark | [#46](https://github.com/google-deepmind/physics-IQ-benchmark/issues/46) | B | Filed pre-session; PR offer included |
| 7 | long-form-factuality | [#48](https://github.com/google-deepmind/long-form-factuality/issues/48) | B | Triple-drift problem (evaluated model + rater + web search) |
| 8 | alphaevolve_results | [#7](https://github.com/google-deepmind/alphaevolve_results/issues/7) | B→A | Deterministic numpy hook; issue #2 dispute reference |
| 9 | funsearch | — | B | Skipped — weak hook, inactive repo (2024-02-05) |
| 10 | graphcast | — | B | Skipped — benchmark lives in WeatherBench2 not this repo |

**Waiting on:** responses from all filed issues. bbeh PR ready to push on engagement from Mehran Kazemi.

Each entry has a priority, the target project (A = ValiChord proper commit-reveal protocol, B = valichord_attestation library), a specific pitch, and the exact action to take.

---

## Quick-start decision

- **If you want the strongest Project A issue (safety/independence angle):** start with #1 `dangerous-capability-evaluations`
- **If you want the fastest win (Project B, lowest friction):** start with #5 `bbeh`
- **If you want the best trojan horse (B opens door to A):** start with #2 `concordia`

---

## Priority 1 — `dangerous-capability-evaluations`

**URL:** https://github.com/google-deepmind/dangerous-capability-evaluations  
**Stars:** 73 | **Last updated:** 2026-05-07  
**Project:** A (primary) + B (secondary)  
**Status:** Issue filed 2026-05-17 → https://github.com/google-deepmind/dangerous-capability-evaluations/issues/40

**What it does:** Challenge infrastructure (CTF, self-proliferation, self-reasoning tasks) for evaluating frontier model dangerous capabilities. Companion to a published paper.

**The gap:** Results come from a single internal team. No mechanism prevents teams adjusting prompting strategy after seeing partial results. No independent replication machinery. The repo explicitly says "you will need to implement your own infrastructure." No commit-reveal, no tamper-evident record of who found what and when.

**Why Project A fits perfectly:** Safety capability evaluations are the highest-stakes context where "can an independent party, working blind, arrive at the same conclusion?" is exactly the question. If two teams assessing dangerous capabilities can see each other's preliminary findings, the safety signal is compromised — this is structurally identical to ValiChord's commit-reveal problem statement.

**What was filed:** Issue #40 — framed as a research question about multi-team evaluation independence, mapped CTF/self-proliferation/self-reasoning challenge types to ValiChord's sealed-verdict verdicts, explained the herding/anchoring problem, referenced ValiChord as a reference implementation. Closed with a genuine question about whether independent multi-team blind evaluation has been considered.

**Next step:** Wait for response. If maintainers engage, the natural follow-up is Project B (valichord_attestation bundles for evaluation run provenance) as a concrete first step.

**Pitch angle:**
> Capability evaluations are only as trustworthy as their independence. ValiChord's commit-reveal protocol means two teams evaluating the same capability challenge must each commit a sealed verdict before either sees the other's — preventing the herding effect that threatens multi-team safety evaluations. The HarmonyRecord on the DHT provides a tamper-evident permanent record of what each team found and when.

---

## Priority 2 — `concordia`

**URL:** https://github.com/google-deepmind/concordia  
**Stars:** 1,425 | **Last updated:** 2026-05-17 (very active)  
**Project:** A + B  
**Status:** Issue filed 2026-05-17 → https://github.com/google-deepmind/concordia/issues/271

**What it does:** Generative agent simulation framework for multi-agent social experiments. Ran the NeurIPS 2024 contest where submitted agents competed.

**The gap correction:** The engagement plan originally said "issue #5" — that issue is from 2023 and is closed (link to tech report). The real reproducibility thread is issue #159 "Reproducing Concordia Contest @NeurIPS 2024" (open, maintainer `vezhnick` and `locross93` are engaged). PR #265 is by `anshjaiswal12`, currently CLA-blocked — it restores the evaluation pipeline but explicitly acknowledges "model drift" as an unresolved assumption.

**What was filed:** Issue #271 — focused on the model drift gap that PR #265 could not fix. Framed around the `content_hash` Merkle root as a way to detect whether any individual scenario/agent score drifted between two runs even if aggregate Elo matches. Asked three concrete questions: (1) do 2024 contest logs still exist for a reference hash? (2) should the script sit in PR #265 or separately? (3) what is the official per-scenario score aggregation format?

**Step 2 — Project B PR:** Instrument `run.py`'s JSON output to emit a `bundle.json` alongside each simulation run. Wait for issue #271 response before filing.

**Step 3 (longer term) — Project A conversation:** Once the Project B PR is merged, the natural follow-up for the next contest edition is: "independent agent evaluators should commit sealed scores before comparing" — that's ValiChord proper.

**Pitch angle:**
> The NeurIPS 2024 contest reproducibility collapse happened because there was no tamper-evident record of what was run at contest time. valichord_attestation produces a two-hash bundle (bundle_hash for identity, content_hash for scientific equivalence) that could be committed alongside every official contest run, making future editions independently verifiable.

**Note:** PR #265 explicitly flags model drift as an unresolved assumption — that is the entry point. Read PR #265 and issue #159 before any follow-up.

---

## Priority 3 — `debate`

**URL:** https://github.com/google-deepmind/debate  
**Stars:** 120 | **Last updated:** 2026-05-10  
**Project:** A (philosophically deepest fit)  
**Action:** ~~Issue~~ — **REPO IS ARCHIVED (read-only). No issues possible. Skip.**

**What it does:** Lean 4 formalisation of the stochastic doubly-efficient debate protocol — two AI agents compete to convince a judge, with bounded prover and verifier computation. AI safety paper.

**The gap:** The theoretical protocol has strong correctness guarantees. The empirical verification problem is entirely unaddressed — no implementation of an actual debate round, no evaluation of whether AI systems playing debate converge to truth in practice.

**Why Project A fits:** The debate protocol and ValiChord's commit-reveal are addressing the same problem from different angles: how do you get a reliable signal from agents who could anchor on each other's answers? ValiChord's blind-commit phase maps directly onto "prover submits argument before seeing opponent's argument."

**Pitch angle:**
> Debate's theoretical guarantee is that optimal play converges to truth even with bounded computation. ValiChord provides the coordination protocol for empirical debate experiments: provers commit sealed verdicts before any reveal, preventing the anchoring effects that contaminate multi-evaluator measurements. The agent-centric DHT ensures no central party can alter what each prover claimed.

**Tone note:** This repo is highly theoretical. The issue should be framed as "has anyone thought about the empirical evaluation coordination problem?" — not a product pitch. Start a conversation.

---

## Priority 4 — `meltingpot`

**URL:** https://github.com/google-deepmind/meltingpot  
**Stars:** 834 | **Last updated:** 2026-05-16 (active)  
**Project:** A (multi-party coordination) + B  
**Status:** Issue filed 2026-05-17 → https://github.com/google-deepmind/meltingpot/issues/338

**What it does:** Multi-agent RL benchmark (cooperation, competition, deception, trust). Ran the NeurIPS 2023 Melting Pot contest. Leaderboard accepts self-reported scores.

**The gap:** In a multi-agent social scenario, the independence of evaluation teams matters as much as the independence of the agents. No mechanism prevents teams tuning their agents after observing how competitors' agents behaved. Leaderboard is self-reported.

**Pitch angle:**
> For multi-agent benchmarks where the evaluation is itself a social game, the independence of evaluators matters as much as the independence of the agents. ValiChord's commit-reveal prevents evaluation teams from adjusting their agents after observing preliminary results from other teams — ensuring the leaderboard reflects genuine independent reproduction.

---

## Priority 5 — `bbeh` (BIG-Bench Extra Hard)

**URL:** https://github.com/google-deepmind/bbeh  
**Stars:** 120 | **Last updated:** 2026-05-15  
**Project:** B  
**Status:** Issue filed 2026-05-17 → https://github.com/google-deepmind/bbeh/issues/10

**What it does:** Harder replacement for BIG-Bench Hard, 4520 reasoning examples, community leaderboard.

**The gap:** Three compounding weaknesses identified from deep repo read:
1. Decoding parameters undocumented (temperature, top_p, max_tokens) — existing issue #9 unanswered
2. No per-sample verification — cherry-picking (best of N runs) undetectable from aggregate scores alone
3. No run provenance — no timestamp, no artifact linking a leaderboard row to a specific run

**What was filed:** Issue #10 — framed researcher-to-researcher around the reproducibility gaps, referenced issue #9, mentioned valichord_attestation as a pointer not a pitch, explicitly made it optional ("happy to discuss what level feels appropriate"). No PR filed yet.

**PR ready to go if maintainer engages:**
- `bbeh/generate_attestation.py` — ~110 lines; reads `predictions.json`, grades using their own `evaluate_correctness()`, builds a bundle with per-task metrics + per-sample Merkle root, outputs `bundle_hash` + `content_hash`
- `leaderboard.md` — adds a "Reproducibility" section before the table with install + usage instructions; no change to existing rows or columns
- Fork already exists at `topeuph-ai/bbeh`, branch `add-attestation-bundle` with both files written and ready to commit

**Key consideration:** Single maintainer (Mehran Kazemi), lightweight repo, one commit in git history. A cold PR adding an external library dependency before he's engaged would overstep. Wait for a response to issue #10 before pushing the branch.

**Pitch angle:**
> valichord_attestation's content_hash is a Merkle root over all per-sample outputs — two runs producing the same aggregate score but differing on any individual example will have different content_hashes. The grading calls BBEH's own evaluate_correctness() so scores match the leaderboard exactly. pip-installable, no infrastructure.

---

## Priority 6 — `physics-IQ-benchmark`

**URL:** https://github.com/google-deepmind/physics-IQ-benchmark  
**Stars:** 291 | **Last updated:** 2026-05-14  
**Project:** B  
**Status:** Issue filed 2026-05-16 → https://github.com/google-deepmind/physics-IQ-benchmark/issues/46 (0 comments, awaiting response)

**What it does:** Video generation benchmark for physical understanding. Models generate videos scored against real-world footage. Leaderboard maintained via PRs (trust-on-submit, `results/` gitignored, 18 entries as of 2026-05-17).

**The gap:** Leaderboard PRs add a markdown row with a score percentage and paper link. No structured data required. Per-scenario CSVs are gitignored and never enter the repo — submitted score floats free of any verifiable anchor.

**What was filed:** Issue #46 — detailed proposal with concrete code using valichord_attestation against the `calculate_iq_score.py` CSV output, explanation of what content_hash detects (partial submissions, score fabrication, eval code version drift), and an explicit offer to file a PR with: example bundle.json, validate_bundle.py (~20 lines), and README update. Maintainer is "Robert" (from issue greeting).

**PR ready when maintainer engages:**
- `submissions/example/bundle.json` — worked example for an existing leaderboard entry
- `submissions/validate_bundle.py` — ~20 lines: load bundle.json, re-run score, verify hash
- README submission instructions update

**Pitch angle:**
> Physics-IQ leaderboard entries are currently trust-on-submit. valichord_attestation generates a content_hash over all per-scenario metrics; including it in the leaderboard PR means any future challenger can verify they are measuring the same thing — and partial submissions (cherry-picking easy scenarios) are immediately detectable.

---

## Priority 7 — `long-form-factuality`

**URL:** https://github.com/google-deepmind/long-form-factuality  
**Stars:** 684 | **Last updated:** 2026-05-12  
**Project:** B  
**Status:** Issue filed 2026-05-17 → https://github.com/google-deepmind/long-form-factuality/issues/48 (low maintainer engagement pattern — mostly dependabot activity)

**What it does:** LongFact prompt set + SAFE evaluator for long-form factuality in LLMs. Benchmarks OpenAI and Anthropic models.

**The gap:** The evaluation pipeline produces JSON files of prompt-response-judgment triples. No way to verify which model version produced results, or that paper numbers correspond to a specific unmodified run.

**Adapter note:** Custom eval framework (not inspect_ai), but the JSON per-prompt output format is straightforward to adapt. A small `generate_attestation.py` script that reads the output JSONs and calls `build_bundle()` is the PR.

**Pitch angle:**
> Factuality benchmark reproducibility is especially fragile because model outputs change with model versions and API sampling. An attestation bundle from SAFE's per-prompt output JSONs creates a content_hash stable if and only if the model, prompts, and judgments are identical — making paper results independently verifiable.

---

## Priority 8 — `alphaevolve_results` + `alphaevolve_repository_of_problems`

**URLs:**  
https://github.com/google-deepmind/alphaevolve_results (283 stars)  
https://github.com/google-deepmind/alphaevolve_repository_of_problems (220 stars)  
**Project:** B (trojan horse to A)  
**Status:** Issue filed 2026-05-17 → https://github.com/google-deepmind/alphaevolve_results/issues/7 (6 prior issues all closed by maintainers — engaged repo)

**What it does:** Results repos for AlphaEvolve, publishing mathematical discoveries as Colab notebooks with verification code.

**The gap:** Verification notebooks are not signed or time-stamped verifiably. If a construction is updated after publication, there is no audit trail. Independent groups claiming to reproduce an AlphaEvolve result have no tamper-evident artifact proving their reproduction matched.

**Pitch angle:**
> AlphaEvolve's value is that its mathematical constructions are machine-verifiable. Attaching a valichord_attestation bundle to each verified construction creates a content_hash that proves the result was produced by running the verification code — enabling independent groups to prove their own reproductions match the original.

---

## Priority 9 — `funsearch`

**URL:** https://github.com/google-deepmind/funsearch  
**Stars:** 1,061 | **Last updated:** 2026-05-16  
**Project:** B  
**Action:** Issue (respectful — Nature paper)

**What it does:** Program synthesis by LLM + evolutionary search. Published mathematical discoveries (cap sets, bin packing) as Colab notebooks. Nature paper.

**The gap:** Bin-packing evaluation suite is explicitly designed to reproduce paper results, but no verifiable link exists from a reproduction run to the paper's numbers. Open issue #8 is someone asking whether a claimed construction achieves the stated size — exactly the kind of question a content_hash would resolve.

**Tone note:** Nature paper repo — frame this as a research question ("has anyone thought about how to make reproduction claims machine-verifiable?") rather than a proposal.

---

## Priority 10 — `graphcast`

**URL:** https://github.com/google-deepmind/graphcast  
**Stars:** 6,651 | **Last updated:** 2026-05-17 (very active)  
**Project:** B  
**Action:** Issue (question first, proposal second)

**What it does:** GraphCast and GenCast weather models published alongside Science paper. Community running operational forecasts.

**The gap:** Weather model benchmark numbers (RMSE, ACC) are sensitive to dataset version and preprocessing choices. No attestation mechanism links a claimed number back to a specific model + data + evaluation run.

**Tone note:** Highest-visibility repo in this list (6.6k stars, Science paper). Start with a genuine question about reproducibility practices before proposing anything. Read all open issues first.

---

## General notes for filing issues

- **Always read all open issues first** — avoid duplicates and pick up live threads
- **Lead with the problem, not the solution** — describe what's missing before mentioning ValiChord
- **Project A pitches:** frame as a design/architecture question, not a product pitch; these repos have thoughtful maintainers who will engage if the framing is right
- **Project B pitches:** concrete, specific, show the code; maintainers respond to "here's a PR that adds X in 4 lines"
- **No repos in this org use inspect_ai or lm-evaluation-harness** — all custom Python or Colab; valichord_attestation will need a small custom adapter per repo (this is normal and each adapter is itself a contribution)
- **Trojan horse sequencing:** file a Project B issue/PR first; once engaged, the Project A conversation follows naturally from "where do the bundle hashes actually get verified by independent parties?"
