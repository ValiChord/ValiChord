# Google DeepMind — ValiChord Engagement Plan

**Created:** 2026-05-17  
**Status:** Ready to execute — start with #1 or #5

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
**Action:** File an issue

**What it does:** Challenge infrastructure (CTF, self-proliferation, self-reasoning tasks) for evaluating frontier model dangerous capabilities. Companion to a published paper.

**The gap:** Results come from a single internal team. No mechanism prevents teams adjusting prompting strategy after seeing partial results. No independent replication machinery. The repo explicitly says "you will need to implement your own infrastructure." No commit-reveal, no tamper-evident record of who found what and when.

**Why Project A fits perfectly:** Safety capability evaluations are the highest-stakes context where "can an independent party, working blind, arrive at the same conclusion?" is exactly the question. If two teams assessing dangerous capabilities can see each other's preliminary findings, the safety signal is compromised — this is structurally identical to ValiChord's commit-reveal problem statement.

**Pitch angle:**
> Capability evaluations are only as trustworthy as their independence. ValiChord's commit-reveal protocol means two teams evaluating the same capability challenge must each commit a sealed verdict before either sees the other's — preventing the herding effect that threatens multi-team safety evaluations. The HarmonyRecord on the DHT provides a tamper-evident permanent record of what each team found and when.

**Issue structure:**
- Title: "Multi-team evaluation independence: case for a commit-reveal coordination layer"
- Section 1: The problem — single-team results and anchoring risk
- Section 2: What commit-reveal would add — two teams, sealed verdicts, simultaneous reveal
- Section 3: ValiChord as a reference implementation
- Section 4: What this would require from the repo (no code change needed — external coordination layer)
- Keep it short and framed as a question/proposal, not a sales pitch

---

## Priority 2 — `concordia`

**URL:** https://github.com/google-deepmind/concordia  
**Stars:** 1,425 | **Last updated:** 2026-05-17 (very active)  
**Project:** A + B  
**Action:** Issue + PR (two steps)

**What it does:** Generative agent simulation framework for multi-agent social experiments. Ran the NeurIPS 2024 contest where submitted agents competed.

**The gap:** The NeurIPS 2024 contest evaluation pipeline was deleted in the v2.0 API overhaul (open issue #5, PR #265 unmerged). No mechanism pins the model version or outputs at contest time. "Model drift" (GPT-4o changing between runs) means scores diverge from 2024 originals even when the code is correct.

**Step 1 — Project B issue:** Link the reproducibility concerns to attestation. The contest produces simulation logs; a valichord_attestation bundle committed alongside each official contest run would pin model version + outputs permanently.

**Step 2 — Project B PR:** Instrument the evaluation script to emit a `bundle.json` alongside the simulation log. Attach to the open PR #265 discussion.

**Step 3 (longer term) — Project A conversation:** Once the Project B PR is merged, the natural follow-up for the next contest edition is: "independent agent evaluators should commit sealed scores before comparing" — that's ValiChord proper.

**Pitch angle:**
> The NeurIPS 2024 contest reproducibility collapse (issue #5) happened because there was no tamper-evident record of what was run at contest time. valichord_attestation produces a two-hash bundle (bundle_hash for identity, content_hash for scientific equivalence) that could be committed alongside every official contest run, making future editions independently verifiable.

**Note:** PR #265 is the live discussion thread — read it before filing anything.

---

## Priority 3 — `debate`

**URL:** https://github.com/google-deepmind/debate  
**Stars:** 120 | **Last updated:** 2026-05-10  
**Project:** A (philosophically deepest fit)  
**Action:** Issue (conceptual, no code)

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
**Action:** Issue (proposal for next contest edition)

**What it does:** Multi-agent RL benchmark (cooperation, competition, deception, trust). Ran the NeurIPS 2023 Melting Pot contest. Leaderboard accepts self-reported scores.

**The gap:** In a multi-agent social scenario, the independence of evaluation teams matters as much as the independence of the agents. No mechanism prevents teams tuning their agents after observing how competitors' agents behaved. Leaderboard is self-reported.

**Pitch angle:**
> For multi-agent benchmarks where the evaluation is itself a social game, the independence of evaluators matters as much as the independence of the agents. ValiChord's commit-reveal prevents evaluation teams from adjusting their agents after observing preliminary results from other teams — ensuring the leaderboard reflects genuine independent reproduction.

---

## Priority 5 — `bbeh` (BIG-Bench Extra Hard)

**URL:** https://github.com/google-deepmind/bbeh  
**Stars:** 120 | **Last updated:** 2026-05-15  
**Project:** B (easiest win in the org)  
**Action:** Issue then PR

**What it does:** Harder replacement for BIG-Bench Hard, 4520 reasoning examples, community leaderboard.

**The gap:** Leaderboard is email-based — you email scores to `mehrankazemi@google.com` and they are manually added. Zero verification that reported scores were produced by the stated model under the stated conditions.

**PR plan:**
1. Issue: propose requiring an attestation bundle with leaderboard submissions
2. PR: update README with submission instructions + valichord_attestation usage example (4 lines of code)

**Pitch angle:**
> Leaderboard cherry-picking is a known problem in ML benchmarking. valichord_attestation's content_hash is a Merkle root over all per-sample outputs — two runs that produce the same aggregate score but differ on individual samples will have different content_hashes. This is a pip-installable addition to the existing evaluation script.

---

## Priority 6 — `physics-IQ-benchmark`

**URL:** https://github.com/google-deepmind/physics-IQ-benchmark  
**Stars:** 291 | **Last updated:** 2026-05-14  
**Project:** B  
**Action:** Issue + PR

**What it does:** Video generation benchmark for physical understanding. Models generate videos scored against real-world footage. Leaderboard maintained via PRs.

**The gap:** Leaderboard PRs add a row with a self-reported score and a paper link. No requirement to submit per-video prediction outputs or any hash of the evaluation run.

**PR plan:** Add a section to the README explaining how to generate a `bundle.json` from the Step B evaluation script outputs and include it in the leaderboard PR.

**Pitch angle:**
> Physics-IQ leaderboard entries are currently trust-on-submit. valichord_attestation generates a content_hash over all per-video predictions; including it in the leaderboard PR means any future challenger can verify they are measuring the same thing.

---

## Priority 7 — `long-form-factuality`

**URL:** https://github.com/google-deepmind/long-form-factuality  
**Stars:** 684 | **Last updated:** 2026-05-12  
**Project:** B  
**Action:** Issue first, then PR if interest shown

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
**Action:** Issue on `alphaevolve_results`

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
