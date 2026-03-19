<div align="center">
  <img src="https://github.com/topeuph-ai/ValiChord/blob/main/Images/Valichord%20logo-standard%20v2-1.5x.jpeg" width="550px" alt="ValiChord Logo">
</div>

# ValiChord Phase 0: Validation Workload Discovery
## Scaled Design — 12 Months, £158K FEC

**How long does it take to check whether published computational research actually works?**

**Nobody knows. This study finds out.**

---

## EXECUTIVE SUMMARY

Computational methods now underpin research across virtually every scientific discipline — from genomics to climate modelling to social science. The reproducibility crisis in these fields is well documented: studies consistently show that the majority of computational research cannot be independently verified.

Everyone agrees this is a problem. Funders are beginning to mandate data sharing. Journals are introducing reproducibility requirements. Registered Reports address how studies are designed. But all of these initiatives share one untested assumption: that someone can sit down with a published study — the code, the data, the methods — and check whether the results are correct, at a cost someone is willing to pay.

No one has ever measured whether that's true.

How long does computational validation actually take? Four hours? Forty? Does it depend on the quality of the documentation, the complexity of the code, the accessibility of the data? Are some studies straightforward to check and others effectively impossible? What do validators need that they don't currently have?

Without answers to these questions, any reproducibility infrastructure — ours or anyone else's — is being designed on guesswork.

**This study provides the answers.**

We recruit 25–30 UK-based computational researchers, pay them at professional rates to validate published studies across a difficulty spectrum, and measure what happens. Time, difficulty, barriers, pain points. Twelve months. ~£150K FEC. Three validators per study, enabling genuine inter-rater comparison. Sixty to seventy-five validation events — enough data to run exploratory regression on which study features track with validation workload.

The results of Phase 0 do not determine whether ValiChord proceeds — they determine how it proceeds. If validation time is broadly consistent and affordable for certain study types, we gain the first empirical foundation for designing reproducibility infrastructure — and ValiChord knows where to start. If validation is unpredictable or prohibitively expensive for certain study types, that reveals the boundaries — what ValiChord should exclude, what minimum documentation standards must be in place before a study enters the system. If difficulty depends on factors invisible from the surface, that identifies a fundamental design constraint: validators may need to begin work before difficulty can be assessed.

In all scenarios, Phase 0 generates the design evidence that any reproducibility infrastructure needs — and that currently does not exist.

**Budget:** ~£158,000 Full Economic Cost (FEC)
**UKRI contribution (80%):** ~£126,000
**Institutional contribution (20%):** ~£32,000
**Duration:** 12 months
**Funder target:** UKRI Metascience Research Grants, Round 2
**Theme:** Scientometric approaches to understanding research excellence, efficiency, and equity

---

## 1. THE GAP IN THE EVIDENCE

### What We Know

The reproducibility problem is not in dispute. Ioannidis (2005) demonstrated that structural incentives in scientific publishing lead to systematically unreliable findings; subsequent studies confirmed the crisis extends across computational research:

- 67% of computational biology studies fail basic reproducibility checks (Ioannidis et al., 2009)
- Only 26% of published R packages can reproduce their own documentation (Trisovic et al., 2022)
- An estimated 50–90% of published research contains computational errors affecting conclusions (Miller, 2006)

The sources of computational irreproducibility are well documented: insufficient study protocols, missing data documentation, undescribed data processing steps, incomplete code, missing software dependencies, and differences in computational and hardware environments (Schultze et al., 2025, UKRN primer on computational reproducibility).

Funders, journals, and institutions have responded with data sharing mandates, code availability requirements, and reproducibility policies. These are necessary steps. But they address availability, not verification. Making code and data accessible is not the same as proving the results are correct.

### What We Don't Know

Verification requires someone to actually do the work — download the data, run the code, compare the outputs. This is skilled, time-consuming labour. And there is no empirical data on what it involves.

We don't know how long it takes. We don't know what makes it difficult. We don't know which types of studies are practical to verify and which aren't. We don't know what support validators need, what barriers they encounter, or at what point a study becomes effectively impossible to check.

Every reproducibility initiative — journal mandates, funder requirements, proposed validation services — implicitly assumes this work is feasible at reasonable cost. That assumption has never been tested.

**A note on existing efforts.** Several initiatives have attempted computational reproduction — CODECHECK (25+ checks), cascad (economics verification), the Reproducibility Projects (Psychology and Cancer Biology). These measured *whether* studies reproduced. They did not systematically measure *what factors are associated with how long reproduction takes*. CODECHECK does not publish time-per-validation or examine which surface features track with effort. The Reproducibility Projects tracked total cost but not the specific breakdown of where time went or what made some studies harder than others. Where validation workload has been discussed, it confirms the problem is real: an NSF-sponsored workshop on practical reproducibility in HPC reported that artifact evaluation takes significantly more time than paper review, yet reviewers receive less time to do it (Keahey et al., 2025). Journal reproducibility editors have proposed harmonised multi-tier standards partly because the workload is unmanageable without them (Hornung et al., 2025). No existing dataset links observable study features (code quality, documentation, dependency count, data accessibility) to validation workload in a way that could inform the design of a difficulty-assessment system. Phase 0 is not measuring "can studies be reproduced" — that question has partial answers already. It is measuring "what makes reproduction easy or hard, and can you identify those factors from the outside?" That is the genuinely novel question, and the one any scalable infrastructure needs answered.

### Why This Matters

Without workload data, you can't design infrastructure. You can't set compensation rates. You can't tell a funder what validation will cost per study. You can't tell a journal how long verification will take. You can't distinguish between studies that are worth checking and studies that will consume resources without result.

This is the gap Phase 0 fills.

---

## 2. THE WIDER CONTEXT: VALICHORD

This study is the first step in a staged programme called ValiChord — a proposed distributed validation infrastructure for computational research. The full vision is a system where independent researchers validate published computational work and the results are recorded in a cryptographically verifiable, tamper-evident format.

The long-term programme is structured as follows:

- **Phase 0 (this proposal, 12 months, ~£150K FEC):** Workload discovery — measure what validation actually involves
- **Phase 1 (24 months, ~£680K):** Core infrastructure development — *designed around Phase 0 findings*
- **Phase 2 (18 months, ~£420K):** Journal and funder integrations — *informed by Phase 1 evidence*
- **Phase 3 (24 months, ~£800K):** Scale and sustainability — *informed by Phase 2 adoption data*

**Total programme: ~£2.05M over 6 years, with design gates at each phase.**

Phase 0 is a discovery phase. It does not test whether ValiChord should exist — it identifies the conditions under which ValiChord can operate effectively: what to accept, what to exclude, what standards are needed, and what support validators require.

The study has standalone value. The workload data is useful to anyone working on reproducibility — not just ValiChord. Even findings that challenge current assumptions about validation feasibility would be a contribution, because they would reshape how the entire field thinks about reproducibility infrastructure.

### Why Holochain (Brief Context)

The proposed infrastructure uses Holochain — an open-source framework for distributed applications — rather than blockchain. The key advantage is that Holochain's agent-centric architecture allows patient data to stay local and deletable (GDPR-compliant) while distributing only cryptographic validation proofs. This solves the fundamental conflict between data protection law and immutable verification records that killed previous blockchain-based reproducibility projects.

This technical choice has been validated by Holochain Foundation engineers, but it is not relevant to Phase 0. Phase 0 uses standard tools (time tracking, surveys, institutional data storage). The technology question is addressed in later phases. The broader architectural direction — federated, layered, governance-aware — is consistent with emerging academic consensus: Beyvers et al. (2026, *PLOS Computational Biology*) independently propose layered, peer-to-peer architectures for research data ecosystems that preserve domain sovereignty while enabling cross-institutional collaboration.

### Architecture Overview

ValiChord's full architecture spans eight layers, from data integrity through to institutional integration. These are documented in detail in companion technical documents. For Phase 0 purposes, the relevant point is that every layer depends on the same foundational question: what does validation actually cost? Without Phase 0 evidence, the entire architecture is designed on assumptions.

---

## 3. PHASE 0: STUDY DESIGN

### 3.1 Research Questions

**Primary:**
- What is the distribution of validation workload across computational studies?
- What task characteristics (code quality, documentation, data accessibility) are associated with validation time?

**Secondary:**
- What proportion of studies are validatable within reasonable timeframes?
- What specific features make studies difficult or impossible to validate?
- What support do validators need?
- What are common barriers and pain points?
- How consistent are validation outcomes across independent validators assessing the same study?
- Does validator competence explain more variance than study characteristics?

### 3.2 Sample

**20–25 computational studies** selected across difficulty spectrum:

- 5–6 easy (clean code, good docs, public data)
- 6–7 medium (some issues, moderate complexity)
- 5–6 hard (poor docs, access barriers)
- 3–4 extreme (establish upper bounds)

**Why include messy tasks?** Phase 0 maps the current state of computational research, not the future ValiChord workflow. Understanding real-world messiness is essential for designing exclusion criteria, minimum quality standards, and identifying what makes validation impractical.

**Each study validated by 3 independent validators**

This is a step change from a 2-validator design. Three validators per study enables genuine inter-rater comparison: if all three converge, the study's difficulty is well-characterised; if two agree and one diverges, the structured time logs reveal where and why; if all three diverge, the study may be genuinely ambiguous or dependent on validator-specific factors. With only 2 validators, you can spot gross discrepancy but cannot distinguish a majority pattern from an outlier. Three validators provides the minimum for meaningful agreement analysis.

**Total: 60–75 validation events**

**Sample size rationale.** With 60–75 validation events across 4 difficulty tiers, each tier contains 15–21 observations (5–7 studies × 3 validators). This is sufficient for robust descriptive statistics within tiers (means, medians, standard deviations, interquartile ranges), preliminary exploration of which surface features track with validation time (exploratory regression), meaningful inter-rater comparison across the full study set, and enough statistical power to distinguish real tier differences from noise. This is still a discovery study, not a confirmatory one — but it produces findings with substantially more weight than a smaller pilot. The results will support a publication with genuine empirical contribution, not just a proof-of-concept report.

**Study selection criteria:**
- Mix of Python, R, and other languages
- Various domains (biology, social science, climate, economics, physics, etc.)
- Published in last 3 years
- Computational methods central to findings
- At least 2 disciplines with 4+ studies each (enabling within-discipline comparison)

**A note on study selection governance:** Study selection should be governed by the PI with documented selection rationale, transparent inclusion and exclusion criteria, and deliberate recruitment across the difficulty spectrum — including studies the researchers themselves suspect may not reproduce cleanly. If the project team selects only studies likely to produce clean results, the Phase 0 evidence loses credibility and all downstream design decisions become questionable. To mitigate selection bias, the final study selection should be reviewed by at least one external advisor not involved in the project (drawn from the UKRN network or a relevant reproducibility initiative) who can confirm the selection represents genuine diversity rather than convenient choices. The selection process, rationale, and external reviewer's assessment should be published alongside the results.

**A note on difficulty classification:** These tiers are pre-classified based on observable surface features — code length, documentation quality, data accessibility, number of dependencies, and tooling requirements (open-source vs. proprietary/licensed software). This classification is a hypothesis, not a fact. A study that looks easy on the surface may turn out to be difficult for reasons invisible until a validator sits down with it. A study that looks hard may turn out to be straightforward. Testing whether surface features track with actual difficulty is one of the research questions. If they do, they become candidate predictors for future infrastructure to test at scale. If they don't, that tells us difficulty is hidden and the field's assumptions about what makes validation hard may need revising. Either result is valuable.

**A note on proprietary dependencies:** Many computational fields rely on licensed software (MATLAB, SAS, proprietary sequencing pipelines, commercial cloud configurations). If a study's workflow depends on software a validator cannot legally or practically access, reproduction may be impossible regardless of data quality or documentation. Phase 0 should include at least 2–3 studies with proprietary dependencies to capture this dimension empirically. Some studies may prove unvalidatable specifically because of licensing barriers — that is a genuine finding about the boundaries of computational validation, not a system failure.

#### Validators  

**25–30 UK-based computational researchers**
- PhD students to senior research software engineers
- Computational methods expertise
- Available for 2–3 tasks over the study period
- Deliberate recruitment across experience levels (early-career to established) to capture whether competence explains workload variance

**Baseline competence capture:** At recruitment, validators complete a brief self-assessment: primary programming languages and years of experience, familiarity with version control and environment management (Docker, conda, etc.), typical computational work (data analysis scripts, simulation models, machine learning pipelines, etc.), and self-rated troubleshooting confidence. This is not a screening tool — all recruited validators participate regardless of responses. The purpose is to capture whether validator competence explains more variance in validation time than study characteristics do. If a senior research software engineer and a second-year PhD student both take 20 hours on the same study, the study is genuinely hard. If the engineer takes 4 hours and the student takes 20, the variance is about the validator, not the study. With 25–30 validators across a range of experience levels, this comparison becomes meaningful rather than anecdotal.

**Environment fingerprint capture:** Also at recruitment, validators record their hardware environment: operating system, CPU architecture (x86 or ARM), GPU presence and model if applicable, and RAM class. This takes a minute to complete and is not a screening tool. It serves two purposes. First, it is metascience data in its own right — Phase 0 will reveal how homogeneous or heterogeneous the computational landscape is across validators in different institutions and disciplines, and whether environment differences correlate with agreement rates or validation time. Second, it is the foundation for the environment-matched validator selection that Phase 1 will design: the algorithm that prioritises validators whose setup is closest to the researcher's, reducing setup-attributable differences before validation begins rather than trying to explain them afterward. Capturing this from Phase 0 onward means the matching thresholds Phase 1 needs can be calibrated on real data rather than guessed.

**Recruitment:**
- Host institution computational research community
- UK Reproducibility Network (local and national)
- Computational methods mailing lists
- Academic social media
- Direct approach to research software engineering groups (RSE community)

**Phase 0 as validator pipeline:** The Phase 0 cohort serves dual purposes: measuring workload and establishing a foundation for Phase 1 recruitment. Validators who complete Phase 0 tasks gain firsthand experience with validation requirements and pain points, making them ideal candidates for the Phase 1 validator pool. This creates continuity from pilot to operational system and positions validation as professional paid work contributing to infrastructure design, not volunteer service. The long-term vision is a professional "Research Validator" career track, with Phase 0 participants as founding members.

**Informed consent:**
> "Validation workload study. Complete 2–3 validation tasks (estimated 4–25+ hours each). £500 per task. Tasks assigned across difficulty spectrum. Additional compensation provided for disproportionately difficult assignments (determined at study end). Contributing to first systematic validation workload data."

#### Task Assignment

**Stratified assignment:**
- Each study → 3 different validators
- Validators receive mix of difficulties where possible
- No validator does same study twice
- Each validator does 2–3 studies
- At least 3–4 validation tasks should deliberately pair a validator with a study outside their primary domain (e.g. a chemist validating a climate modelling study) to generate empirical evidence on whether computational competence alone is sufficient or whether domain expertise materially affects validation quality and efficiency
- Total: 60–75 validation events

**Blinded to predicted difficulty:** Validators are NOT told the study's predicted difficulty tier. They are informed during recruitment that tasks range from approximately 4 to 25+ hours, that they won't know in advance where their assignment falls, that there is a 40-hour time cap, and that additional compensation is provided if they receive disproportionately difficult tasks by chance.

**Design rationale:** Telling validators a predicted tier would anchor their experience and contaminate the data. A validator told "this is Hard" approaches the task differently — they expect difficulty, allocate more time, and may interpret normal friction as confirmation of the label. Since discovering what makes tasks difficult is the central purpose of Phase 0, priming validators with our predictions would partially pre-answer our own research question. Their unprimed perception of difficulty is a data point we compare against our predicted tiers after the fact. This produces cleaner evidence than asking validators to confirm or deny a label we gave them.

#### What "Validation" Means Operationally

Phase 0 validators are asked to attempt computational reproduction — not methodological review, not peer review, not replication with new data. Specifically:

**The task:** Download the study's code and data. Set up the computational environment as documented. Run the code. Compare outputs against the published results.

**Reproduction success criteria:**
- **Success:** Code runs and produces numerical results matching the published findings within reasonable precision (accounting for documented sources of variation such as random seeds or floating-point differences)
- **Partial success:** Code runs but some results match and others do not, or results are directionally consistent but numerically different beyond documented variation
- **Failure:** Code does not run, or runs but produces results that contradict or do not resemble the published findings
- **Unable to assess:** Validator could not reach the point of running the code (e.g. dependencies unavailable, data inaccessible, environment impossible to reconstruct)

**Scope of effort:** Validators should attempt reasonable troubleshooting but are not expected to debug or rewrite the original code. The standardised protocol will include concrete examples of what falls within and outside scope:

*Within scope:* installing documented dependencies, adjusting file paths to local system, following README instructions, creating a virtual environment or container from provided specifications, consulting the study's documentation and supplementary materials, retrying with different software versions if the documented version is unavailable.

*Outside scope:* rewriting code to fix bugs, reverse-engineering undocumented steps, contacting the original authors for clarification, purchasing proprietary software, acquiring specialised hardware not available to the validator.

If the code does not run after reasonable effort within scope, that is a finding — not a failure by the validator.

**Completion criteria:** A validation is complete when the validator has either (a) successfully run the code and compared outputs, or (b) reached a point where further progress would require information or resources not available in the submitted materials, or (c) reached the 40-hour time cap. At completion, the validator submits a structured report covering all data collection fields.

These criteria will be provided to all validators in a brief standardised protocol document as part of onboarding, ensuring consistent interpretation of what constitutes a completed validation.

#### Data Collection

**For each validation, validators record:**

**Quantitative:**
- Start/end timestamps
- Time by category: (1) environment setup, (2) data acquisition/preparation, (3) code execution and output comparison, (4) troubleshooting and problem-solving
- Total hours (sum of categories, cross-checked against timestamps)
- Difficulty rating (1–5 scale)
- Reproduction outcome (success/partial/fail/unable to assess)
- Computational resources required (own laptop sufficient? institutional HPC needed? cloud computing? GPU? estimated compute cost beyond personal hardware?)

**Qualitative:**
- Pain points (open text)
- What made task easy/hard
- Unexpected barriers
- What would help
- Which study features problematic
- Any suspicion that the submitted repository doesn't reflect the actual research workflow (e.g. documentation that looks polished but doesn't match the code's behaviour, or missing steps that must have existed but aren't recorded)

**Tools:**
- Professional time tracking platform (configured for four-category structured logging)
- Secure survey forms (GDPR compliant)
- Institutional data storage (host university)

**No surveillance. No monitoring software. Trust-based self-reporting.**

**No questions about compensation adequacy, willingness to continue, or fairness during the study period.** Phase 0 measures workload. However, a brief optional post-study exit survey (administered after all workload data is collected, to avoid contamination) should ask validators about sustainable participation: Would you do this regularly? How often? What competing demands would limit your involvement? What would make this work more attractive? This data informs Phase 1 validator pool sizing and retention strategy without compromising Phase 0's primary purpose.

#### Compensation

**Base: £500 per completed task (fixed)**

Because validators complete 2–3 tasks in Phase 0, the £500 flat fee does not create a continuous 'finish fast to earn more' incentive. Validators are compensated per task, not per hour, but the absence of a large task queue means efficiency incentives are limited. We therefore rely on professional norms and intrinsic motivation rather than economic incentives. This is appropriate for a discovery pilot whose purpose is to map workload patterns, not to measure speed under incentive pressure.

**Fairness Adjustment: End-of-study bonus for disproportionate difficulty**

Rationale: Random assignment may give some validators harder tasks through chance. Additional compensation maintains morale, completion rates, and ethical treatment.

Mechanism (disclosed upfront):
- A fixed bonus will be provided to validators who, by random assignment, receive disproportionately difficult tasks
- Validators are informed that additional compensation may be provided, but thresholds and criteria are not disclosed to avoid influencing behaviour
- Criteria are determined at study end

Budget: £7,000 fairness adjustment pool

### 3.3 Analysis

**Descriptive statistics with exploratory regression. No confirmatory modelling.**

Because Phase 0 generates substantially more data than a minimal pilot, the analysis can go beyond pure description while remaining appropriately cautious about inference.

**For each difficulty tier:**
- Mean, median, standard deviation, interquartile range of total time
- Time breakdown by category (setup, data, execution, troubleshooting) — identifying where time is actually spent
- Completion rates
- Difficulty ratings (validator-reported vs. pre-classified tier)
- Success/fail/partial/unable-to-assess patterns

**Inter-rater analysis (new capability with 3 validators per study):**
- Agreement on reproduction outcome (do 3 validators reach the same conclusion?)
- Consistency of total time estimates (how much does time vary across validators on the same study?)
- Where validators disagree on time, do the structured time categories reveal where the difference arose (e.g. one spent longer on setup, the other on troubleshooting)?
- Intraclass correlation coefficient (ICC) for time estimates within studies — a formal measure of inter-rater reliability, feasible with 3 raters per study across 20+ studies
- Patterns: are some studies consistently easy/hard across all validators, while others produce divergent experiences?

**Exploratory regression:**
- Which surface features (code quality score, documentation score, dependency count, data accessibility, language, domain) appear to track with validation time?
- Does validator baseline competence (from self-assessment) explain more variance than study characteristics — if it does, infrastructure design must account for validator skill matching, not just study difficulty
- Is there an interaction between validator experience and study difficulty (i.e. do experienced validators show smaller time differences across tiers)?
- These are exploratory models generating hypotheses, not confirmatory tests — but with 60–75 observations, the patterns identified carry more weight than those from a 16–20 observation pilot

**Overall:**
- Time distribution (histogram, by tier and overall)
- Which surface indicators appear to track with actual time
- Pain point themes (qualitative coding)
- Barrier patterns
- Discipline-specific patterns (with 4+ studies in at least 2 disciplines, within-discipline comparison becomes meaningful)

**Output:** Time ranges per difficulty tier with variance estimates and inter-rater reliability metrics. Candidate predictors identified through exploratory regression for future testing at scale.

Example: "Easy tier: 5–9 hours (n=17, SD=1.6, ICC=0.82), Medium tier: 11–19 hours (n=20, SD=3.4, ICC=0.71), Hard tier: 18–32 hours (n=16, SD=5.8, ICC=0.64) — with troubleshooting accounting for 40–60% of total time in medium and hard tiers. Documentation quality score and dependency count together explain ~35% of variance in validation time (exploratory regression, R²=0.35, p<0.01)."

### 3.4 Deliverables

A central output of Phase 0 is the identification of candidate factors that may inform a future difficulty-assessment system. By examining surface features (code quality, documentation, data accessibility) alongside actual validation time across 60–75 validation events, Phase 0 identifies which features appear to track with workload and which do not — generating hypotheses that Phase 1 can test at scale. This is essential groundwork for any scalable validation infrastructure — without it, every assumption about what makes validation hard or easy is untested.

**1. Workload Distribution Report**
- Time ranges by difficulty tier with variance estimates
- Inter-rater reliability metrics (ICC, agreement rates)
- Time breakdown by category across tiers
- Surface feature associations (exploratory regression results)
- Validator competence vs. study difficulty variance decomposition
- Anonymised raw data (Open Science Framework)

**2. Preliminary Difficulty Framework**
- Initial classification of study features associated with validation difficulty
- Candidate predictors identified through exploratory regression for future testing at scale
- Application guidance for Phase 1 study selection
- Discipline-specific patterns where sample permits

**3. Exclusion Criteria**
- Study characteristics making validation uneconomical
- Thresholds and decision rules (informed by the distribution, not arbitrary cutoffs)
- Recommendations for journals/funders

**4. Validator Experience Report**
- Qualitative synthesis of pain points from 25–30 validators
- Common barriers across experience levels
- Support needs
- Best practices identified
- Sustainable participation signals (from exit survey)

**5. Infrastructure Recommendations**
- Preliminary compensation estimates by difficulty tier (based on observed time ranges + standard rates)
- Validator support requirements
- Training needs identified
- Whether validator skill matching is a design requirement (from competence vs. study difficulty analysis)
- Design parameters and constraints for Phase 1

**6. Academic Publication**
- Target: *Nature Human Behaviour*, *Royal Society Open Science*, *MetaArXiv*, or *eLife*
- Pre-print on MetaArXiv or bioRxiv
- Dataset on OSF
- With 60–75 validation events and inter-rater data, this is a substantive empirical contribution, not a pilot report

**7. Policy Briefing**
- 2-page summary for UKRI and the UK Metascience Unit
- Recommendations for journals/funders
- Plain language, actionable

**8. ValiChord at Home — Readiness Checklist (Stage A Pre-Vetting Tool)**

*Working name. ValiChord at Home is the researcher-facing companion tool — the version you use in your own space, on your own terms, before engaging with the formal validation system.*

Phase 0 generates initial evidence toward a future difficulty-assessment tool (planned for Phase 2, once Phase 1 provides the volume needed for statistical calibration). But a simpler version — a best-practice checklist — can be released alongside Phase 0 results without waiting for calibrated scoring.

This lightweight tool asks researchers basic, answerable questions about their repository: Does it have a README that describes the analysis? Are dependencies pinned with version numbers? Is the data downloadable without manual access requests? Is there a containerisation file or environment specification? These are known good practices drawn from FAIR principles and existing code quality standards — they don't require Phase 0 evidence to justify.

The checklist produces a report, not a score. It identifies what's present, what's missing, and links to guidance on how to fix each gap. It does not estimate difficulty or validation time — that requires the larger datasets from Phase 1 and Phase 2. It tells researchers: "here's what any validator would need to find in your repository."

**Strategic value:** *ValiChord at Home* builds community engagement around ValiChord before the full infrastructure exists. Researchers who use it become familiar with ValiChord's standards. Usage data (opt-in, anonymised) reveals the most common reproducibility gaps across disciplines — supplementing Phase 0's structured sample with broad ecosystem data. It demonstrates value to funders and institutions without requiring Holochain, validators, or governance infrastructure. It is, in effect, ValiChord's first public-facing product.

**Relationship to the full pre-vetting tool:** *ValiChord at Home* is Stage A — based on established best practices. The full self-service pre-vetting tool (Stage B, Phase 2) replaces it with empirically informed scoring derived from Phase 1 and Phase 2 data at scale. *ValiChord at Home* builds the community and generates data. Stage B turns that data into precision.

**Intellectual property and open access.** All Phase 0 outputs — workload data, preliminary difficulty framework, exclusion criteria, validator experience reports, methodology documentation, the *ValiChord at Home* tool, and the academic publication — will be released openly. Raw data will be deposited on the Open Science Framework. The academic publication will be open access. The *ValiChord at Home* tool will be released under a permissive open-source licence. The pre-funding design documents (this proposal and its companions) are currently held under copyright by the author; all funded deliverables and subsequent ValiChord code will be open. This is consistent with UKRI open access requirements and with ValiChord's core commitment to transparency.

### 3.5 Success Criteria

**Phase 0 succeeds if it produces:**
- ≥50 validations completed (of 60–75 target)
- Time ranges per difficulty tier with inter-rater reliability metrics
- Identification of candidate surface features that appear to track with actual difficulty (exploratory regression)
- Preliminary exclusion criteria for studies likely unsuitable for validation
- Validator competence vs. study difficulty variance decomposition
- Design parameters and constraints for infrastructure development

**Phase 0 does NOT require clear patterns** — variance itself is informative. High variance tells us the system needs different design assumptions than low variance does.

**Every pattern discovered — including messy, unexpected, or inconvenient ones — is a design input, not a failure mode.** Phase 0 succeeds by revealing the boundaries and requirements of a scalable validation system.

**A note on unexpectedly easy validation.** The documents address the scenario where validation proves prohibitively hard. But Phase 0 might reveal the opposite: that the majority of studies validate in under 4 hours with minimal barriers. This would be an equally valuable and arguably more disruptive finding — it would suggest the reproducibility crisis is not fundamentally about technical difficulty but about incentives, infrastructure, and coordination. ValiChord remains necessary in that world (the coordination layer, governance, Harmony Records, and gaming detection still solve real problems), but the economic model simplifies, the difficulty triage becomes less critical, and the policy argument shifts from "validation is possible" to "validation is cheap — why isn't everyone doing it?"

**A note on unexpectedly hard validation.** If Phase 0 shows validation consistently takes 20+ hours even for studies with good documentation, the question becomes whether the *distribution* offers a viable subset. If the median is 20 hours but easy studies take 6 and hard ones take 40, ValiChord focuses on the easy-to-medium range and uses Phase 0 evidence to design exclusion criteria for the rest. If *everything* takes 20+ hours regardless of surface features, the economic model changes fundamentally — toward selective validation of high-impact studies only, automated pre-screening to reduce human effort, or institutional validators (research software engineers employed by universities) rather than individual academic volunteers. There is no single hour threshold at which ValiChord becomes unviable, because the response depends on the shape of the distribution, not just the mean. But there is a scenario — if even well-documented studies with clean code routinely take 30+ hours — where the current model of individual compensated validators cannot scale affordably, and a fundamentally different operational model is needed. Phase 0 would identify that scenario clearly, and the finding itself would reshape how the entire field thinks about reproducibility infrastructure. That is a contribution, not a failure.

### 3.6 Ethics

**Host institution Research Ethics Committee approval before recruitment.**

**Informed consent:**
- Written information sheet
- Consent form signed
- Clear explanation of study, time variance, compensation, data use
- Right to withdraw

**Participant protection:**
- Time caps (stop at 40 hours per task, report why)
- Withdrawal without penalty if distressing
- Fairness adjustment for difficult assignments
- Anonymity in publications
- GDPR-compliant data storage

### 3.7 Limitations

**Discovery study, not confirmatory:**
- 60–75 validation events enables robust descriptive statistics and exploratory regression
- Sufficient for inter-rater reliability analysis and preliminary identification of candidate predictors
- Not designed for confirmatory hypothesis testing — findings generate hypotheses for Phase 1 to test at scale
- Exploratory regression results should be interpreted as signals, not definitive effect sizes

**UK-only validators:**
- Payment/legal simplicity
- May not generalise internationally
- Future work should include global validators

**Volunteer bias:**
- Self-selected, may be faster than average
- Conservative estimates (lower bounds)
- Mitigated somewhat by deliberate recruitment across experience levels

**Self-reported time data:**
- Validators report their own time rather than being monitored
- Structured time categories (setup, data, execution, troubleshooting) reduce ambiguity but do not eliminate it
- Monitoring software would change validator behaviour and introduce its own confounds — the choice is between imprecise natural data and precise artificial data, and a discovery study benefits more from the former
- Three validators per study strengthens the consistency check: large discrepancies in reported time for the same study flag potential reporting issues more reliably than two

**Discipline coverage:**
- 20–25 studies cannot represent all computational research
- Adequate for cross-disciplinary patterns with deliberate selection
- At least 2 disciplines sampled with 4+ studies each for within-discipline comparison

**These are appropriate limitations for a discovery study.** Phase 0 establishes workload ranges, identifies design constraints, tests whether surface features track with difficulty, and generates candidate predictors; Phase 1 tests those findings at scale.

### 3.8 Phase 0 Budget: ~£150,000 FEC

#### Direct Costs

**Validators:**
- Base compensation (70 validations × £500): £35,000
- Fairness adjustment pool: £7,000
- **Validator subtotal: £42,000**

**Personnel:**
- Research Associate (1.0 FTE, 12 months, Grade 6/7 including NI/pension): £45,000
  - Study selection and classification
  - Ethics application
  - Validator recruitment, onboarding, and support
  - Data collection coordination
  - Analysis (descriptive, inter-rater, exploratory regression)
  - Report writing and publication drafting
  - ValiChord at Home tool development
  - Dissemination and community engagement
- Host institution statistician (consultant hours, ~25 days): £10,000
- PI oversight and supervision (120 hours across 12 months): £6,000
- **Personnel subtotal: £61,000**

**Infrastructure & Tools:**
- Professional time tracking platform (12 months): £2,500
- Data storage and management: £1,500
- Survey/data collection tools: £500
- Project management software: £500
- **Infrastructure subtotal: £5,000**

**Administrative:**
- Ethics application support: £1,000
- Printing, materials, postage: £500
- Meeting spaces and travel (including UKRI Metascience cohort events): £2,000
- Communication tools: £500
- Dissemination costs (open access publication fees, conference): £2,000
- **Admin subtotal: £6,000**

**Contingency (8%):** £9,100

**Total Direct Costs: £123,100**

**Institutional Overheads (estimated 28%): £34,500**

*(Note: Exact overhead rate depends on host institution and UKRI FEC calculation. This estimate should be confirmed with the host university's research office.)*

**Total Phase 0 FEC: ~£157,600 (rounded to ~£158,000)**

**UKRI contribution (80% FEC): ~£126,000**
**Institutional contribution (20% FEC): ~£32,000**

### 3.9 Budget Justification

**~£158K FEC = well under the £250K cap, with strong value-for-money:**

This budget funds 60–75 validation events with 3 validators per study — enough data for inter-rater reliability analysis, exploratory regression, and a publication with genuine empirical weight. A smaller study (16–20 events, 2 validators per study) would produce preliminary signals; this study produces findings the metascience community can build on.

**Phase 0 provides the design evidence for the full programme:**

**Without Phase 0:** £1.9M infrastructure built on assumptions about workload, difficulty, and cost. No evidence on which studies are feasible to validate. No exclusion criteria. No empirical basis for compensation. No knowledge of what validators actually need.

**With Phase 0:** Infrastructure designed around empirical evidence — what to accept, what to reject, what the likely costs are, how to support validators, whether surface features predict difficulty, and whether validator skill matching matters.

**Cost-benefit:**
- ~£150K produces the design parameters, exclusion criteria, compensation estimates, inter-rater reliability data, candidate predictors, and support requirements that shape £1.9M of infrastructure investment
- Without this evidence, the infrastructure is guesswork
- With it, every subsequent design decision is grounded in data
- The publication alone — the first systematic dataset linking study features to validation workload — has standalone value to the metascience field regardless of ValiChord's future

**The statistical consultant appointment (£10,000, ~25 days) reflects the scope of statistical work involved:**
- Inter-rater reliability analysis (ICC calculation across 20+ studies with 3 raters each) requires statistical expertise beyond standard RA training
- Exploratory regression across 60–75 observations with multiple surface feature predictors requires methodological oversight to avoid overfitting and misinterpretation
- Variance decomposition between validator competence and study characteristics is a non-trivial analytical task
- The statistician reviews the analysis plan before data collection, advises during analysis, and signs off on the regression approach before publication — this is substantive involvement across the study, not a single consultation session

**The Research Associate appointment is the backbone of the study:**
- 12 months at 1.0 FTE provides adequate time for ethics, recruitment, coordination of 60–75 validation events, analysis, and write-up
- 6 months would compress every stage; 12 months allows each to be done properly
- The RA develops genuine expertise in computational reproducibility methodology — building capacity in the UK metascience research community

---

## 4. PHASES 1–3: INFRASTRUCTURE DEVELOPMENT

**The following phases build on Phase 0.** Phase 0 does not determine whether ValiChord proceeds — it determines the scope, standards, and design constraints that make ValiChord workable in practice.

**Phase 0 determines:** what studies ValiChord should accept, what it should exclude, what design constraints apply, what support validators require, what compensation looks like, whether validator skill matching is a design requirement, and what the infrastructure must accommodate. These findings directly shape every subsequent phase.

**Budgets are indicative, subject to revision based on Phase 0 evidence.**

### 4.1 Phase 1: Core Infrastructure (24 months, ~£680K)

**Designed around:** Phase 0 workload evidence, difficulty predictors, inter-rater reliability findings, and compensation estimates.

*(Note: The four-DNA Holochain infrastructure — including the cryptographic commit-reveal protocol — was implemented and integration-tested prior to Phase 1. 87 integration tests pass against live Holochain conductors. Phase 1 builds the user-facing layer on top of that foundation.)*

**Build:**
- Researcher and validator dashboards and submission interface
- Validator identity and credentialing system
- Study submission and matching system
- Validation execution and recording
- Beta with 50 validators, 200 studies

**Budget:**
- Development team (5–6 people, 18 months): £450K
- Beta testing (50 validators, 200 tasks): £140K
- Project management: £90K

### 4.2 Phase 2: Integration & Adoption (18 months, ~£420K)

**Designed around:** Phase 1 operational evidence and partner feedback.

**Build:**
- Journal submission system integrations
- Funder reporting dashboards
- Institutional analytics
- Validation standards and protocols
- Scale to 200 validators, 1,000 studies

**Budget:**
- Integration development: £250K
- Partnership pilots (journals, funders, institutions): £120K
- Community building: £50K

### 4.3 Phase 3: Scale & Sustainability (24 months, ~£800K)

**Designed around:** Phase 2 adoption patterns and sustainability evidence.

**Build:**
- Scale to 1,000+ validators globally
- Financial sustainability model
- 10,000+ validated studies
- Professional validator community
- Policy impact

**Budget:**
- Operations at scale: £500K
- Sustainability model development: £200K
- Impact assessment: £100K

---

## 5. TOTAL PROGRAMME

### Budget Summary

| Phase | Duration | FEC | % | Informed by |
|-------|----------|-----|---|-------------|
| **Phase 0: Workload Discovery** | **12 months** | **~£158K** | **7%** | **This proposal** |
| Phase 1: Core Infrastructure | 24 months | ~£680K | 33% | Phase 0 evidence |
| Phase 2: Integration | 18 months | ~£420K | 20% | Phase 1 evidence |
| Phase 3: Scale | 24 months | ~£800K | 39% | Phase 2 evidence |
| **TOTAL** | **~6 years** | **~£2.05M** | **100%** | **Each phase shapes the next** |

### Timeline (Phase 0)

**Months 1–2:** Ethics application, study identification and classification, validator recruitment
**Months 3–4:** Validator onboarding, first wave of validations begins (10–12 studies assigned)
**Months 5–8:** Validation period — all studies assigned, validators working, RA providing support and collecting data
**Months 9–10:** Final validations complete, data cleaning, analysis begins
**Months 11–12:** Analysis, report writing, publication drafting, ValiChord at Home tool, dissemination, policy briefing

### Design Gates

**After Phase 0:** Findings identify candidate difficulty predictors, exclusion criteria, inter-rater reliability baseline, preliminary compensation estimates, support requirements, and design parameters for Phase 1

**After Phase 1:** Operational evidence determines integration priorities, partner requirements, and scaling approach for Phase 2

**After Phase 2:** Adoption data determines sustainability model, scaling targets, and governance requirements for Phase 3

---

## 6. PARTNERSHIP & TEAM

### Current Status

**Technical Validation:** Holochain Foundation confirmed architecture feasible (January 2026). Arthur Brock (co-founder and architect, Holochain) conducted a solution engineering review (February 2026), confirming the overall direction and providing implementation guidance that shaped the four-DNA membrane architecture. Joel Marcey (Tech Director, Rust Foundation) independently reviewed the architecture and MVP Specification and confirmed the approach is sound (February 2026). The four-DNA Holochain infrastructure has since been implemented in Rust and integration-tested — 87 tests pass against live Holochain conductors as of March 2026.

**Academic Partnership:** Discussions initiated with Cardiff University (Dr. Gillian Bristow, Sustainable Places Research Institute) and Swansea University (UKRN local lead; Secure eResearch Platform). Institutional home to be confirmed.

**Potential Partners:** UKRN, Centre for Open Science, Software Sustainability Institute

### Phase 0 Team

**Principal Investigator** (Host institution academic — TBD)
- Study supervision, ethics oversight, academic credibility
- Metascience or reproducibility expertise

**Co-Investigator** (Ceri John)  
- ValiChord architect, strategic vision, stakeholder coordination

**Research Associate** (To be recruited, 12 months, 1.0 FTE)
- Day-to-day execution, validator recruitment and support
- Study selection, data collection coordination
- Analysis (descriptive, inter-rater, exploratory regression)
- Publication drafting, ValiChord at Home tool development

**Statistical Consultant** (Host institution)
- Analysis support, regression methodology, inter-rater reliability statistics

**External Advisor** (UKRN network or reproducibility initiative)
- Independent review of study selection for bias mitigation

---

## 7. EXPECTED IMPACT

### Scientific
- First systematic dataset linking study features to validation workload
- Inter-rater reliability data for computational reproducibility assessment
- Candidate predictors for difficulty assessment at scale
- Open dataset, open protocols, open tools
- Academic publication with substantive empirical contribution

### Policy
- Evidence-based journal validation requirements
- Funder verification cost estimates
- Institutional quality assurance framework
- Direct input to UK Metascience Unit evidence base

### Community
- Professional validator career path demonstrated
- Academic credit for validation work (CRediT taxonomy)
- Fair compensation benchmarks established
- ValiChord at Home tool for researcher self-assessment
- Research Associate capacity building in metascience methodology

### Long-term Vision (by 2030)
- 50% of computational research validated
- 1,000+ active validators globally
- Validation standard practice like peer review
- Reproducibility crisis substantially addressed

---

## 8. RISK ASSESSMENT

### Phase 0 Risks

**Cannot recruit 25–30 validators**
- Likelihood: Low–Medium (larger pool needed than minimal design)
- Mitigation: Multiple channels, host institution network, UKRN, RSE community, over-recruit to 35
- Fallback: Study design degrades gracefully — 20 validators still produces 60 events if each does 3 tasks

**Validator opportunity cost is higher than compensation**
- Likelihood: Unknown — this is a central question Phase 0 tests
- The incentive mix competes with grant writing, teaching, consulting, reviewing, and actual research. A computational researcher earning £50–100/hour consulting may not find validation work attractive at lower effective rates. The emotional cost of publicly disagreeing with high-status labs is real and not fully offset by governance mechanisms alone. Phase 0 directly tests whether the current incentive mix is sufficient to attract and retain qualified validators. If it isn't, the compensation model and non-financial incentives need redesigning before Phase 1 — and Phase 0's qualitative data (exit surveys, experience reports) will reveal exactly where the incentive structure falls short.
- The non-financial incentive package is strongest for early-career researchers, who are also the most likely recruits: CRediT taxonomy credit for validation work counts toward research output portfolios; co-authorship on the Phase 0 publication is a concrete career output; and Phase 0 validators become founding members of what is designed to become a recognised professional track — Research Validator — at a point where being early confers real reputational advantage. These are not token benefits. For a postdoc or PhD student, a peer-reviewed publication, a CRediT credit, and founding-member status in a new professional infrastructure are competitive with many alternative uses of their time. The financial compensation is a floor, not the ceiling of the incentive case.

**Validators drop out mid-study**
- Likelihood: Medium (tasks may frustrate, life intervenes over 12 months)
- Mitigation: Fairness adjustment maintains morale, strong RA support, over-recruitment provides buffer
- Partial data from a dropout is still useful (time spent, barriers encountered, reason for withdrawal)

**Workload unpredictable**  
- Likelihood: Medium (some variance expected)
- Impact: Directly informs system design and identifies which study types are feasible to validate (this is discovery, not failure)
- Mitigation: Any pattern — including unpredictability — shapes infrastructure design

**Ethics delays**
- Likelihood: Medium
- Mitigation: Submit in month 1, experienced PI, 12-month timeline provides buffer

**Study selection bias**
- Likelihood: Medium (unconscious bias toward convenient or clean studies)
- Mitigation: External advisor reviews selection, documented rationale published, deliberate inclusion of messy studies

### Phases 1–3 Risks

**Technical development fails**
- Likelihood: Very Low — the four-DNA Holochain infrastructure is implemented and integration-tested (87 tests pass against live conductors as of March 2026). The remaining Phase 1 technical work is the user-facing layer on top of a working, tested foundation — not greenfield infrastructure development.
- Mitigation: Existing codebase, Holochain Foundation support, tested architecture

**Validator recruitment at scale fails**
- Likelihood: Medium
- Mitigation: Phase 0 provides evidence on validator experience, informing recruitment strategy

**Journals/funders don't adopt**
- Likelihood: Medium (institutional change is slow)
- Mitigation: Early engagement, demonstrate value, policy advocacy

**Cold-start problem: no records → no prestige → no submissions**
- Likelihood: High — this is inherent in any new infrastructure
- The documents assume funder/journal mandates will drive adoption in Phase 2–3, but the earliest phases cannot rely on mandates that don't yet exist. Bridging strategies for the pre-mandate period: target disciplines where reproducibility failures have caused visible public embarrassment (psychology post-replication crisis, biomedical research post-Begley/Amgen findings) — researchers in these fields are already motivated; partner with journals that have adopted Registered Reports, since their editorial processes already assume back-end verification will exist; use the Phase 0 academic publication as credibility evidence; and release *ValiChord at Home* (the Stage A readiness checklist) as a free tool that builds community, name recognition, and a natural pipeline into formal validation. The cold-start gap is real but not unbridgeable — it requires that early adoption is driven by intrinsic motivation and demonstrated value, not mandates.
- The specific path from Phase 0's 60–75 validations to the first 100 validated studies cannot be mapped in advance, because the route depends on what Phase 0 reveals — which disciplines are most tractable, what journal and funder partnerships emerge during Phase 1, and whether the publication generates inbound interest. Detailing the sequence now would be assumption-driven planning, which is precisely what the staged approach is designed to avoid. What can be stated is the likely shape: Phase 0 produces the publication and the tool (ValiChord at Home), Phase 1's beta targets 200 studies through recruited partnerships and the host institution's network, and the first 100 validated studies are a Phase 1 milestone, not a Phase 0 one.

**Sustainability fails**
- Likelihood: Medium
- Mitigation: Multiple revenue streams, Phase 3 focus

### Risk Management Strategy

**Staged approach with design gates is primary risk mitigation:**
- Moderate investment generates robust design evidence before large investment
- Each phase shapes the next based on findings
- Evidence-based design reduces downstream risk
- ~£150K ensures ~£1.9M infrastructure is built on data, not assumptions

---

## 9. CONCLUSION

### The Case for ValiChord

**Problem:** Computational reproducibility crisis; no scalable validation infrastructure

**Solution:** Distributed infrastructure using validated Holochain technology

**Missing evidence:** What validation actually costs in time and difficulty — the design evidence that any infrastructure needs

**Approach:** Discovery-led staged programme where each phase generates the evidence that shapes the next

**Impact:** First scalable validation infrastructure, designed around empirical evidence rather than assumptions

### Why This Study

1. **Novel contribution:** First systematic dataset linking study features to validation workload with inter-rater data
2. **Right scale:** 60–75 validation events — enough for robust descriptive statistics, exploratory regression, and inter-rater analysis
3. **Right duration:** 12 months allows proper ethics, recruitment, execution, analysis, and dissemination
4. **Value for money:** ~£150K FEC for data that informs the design of reproducibility infrastructure across the field
5. **Technical validation:** Holochain Foundation confirms architecture feasibility
6. **Staged approach:** Each phase shapes the next based on findings
7. **Alignment:** Directly addresses UKRI Metascience programme priorities — using scientific methods to understand how research quality can be measured and improved
8. **Standalone value:** The workload data, inter-rater reliability findings, and ValiChord at Home tool are useful to the metascience community regardless of ValiChord's future phases

### The Ask

**We seek ~£126,000 (UKRI 80% of ~£158,000 FEC) for Phase 0: Validation Workload Discovery**

A 12-month study measuring validation time and difficulty across 60–75 validation events (20–25 studies × 3 validators), producing the first systematic empirical dataset on computational reproducibility workload — including inter-rater reliability data, candidate difficulty predictors, exclusion criteria, compensation estimates, and infrastructure design constraints.

**Phase 0 is not a pass/fail test.** It is the discovery phase that generates the evidence needed to design ValiChord responsibly: what to accept, what to exclude, what standards to enforce, what support validators need, and what the economics look like. The findings shape the infrastructure, not the existence of the programme.

The evidence produced is valuable to the entire metascience community regardless of how ValiChord evolves — and it ensures that any future investment is grounded in data rather than assumptions.

---

## APPENDICES

### Appendix A: Technical Architecture
(Detailed layer diagrams, data flows, cryptographic verification — see companion document *ValiChord Technical Reference*)

### Appendix B: Phase 0 Materials  
(Validator handbook, time tracking interface, survey instruments, consent forms, standardised validation protocol)

### Appendix C: Task Selection Rubric
(Scoring criteria for code/docs/data assessment, difficulty tier classification methodology)

### Appendix D: Letters of Support
(Holochain Foundation validation, host institution partnership, UKRN if available)

### Appendix E: Team CVs
(PI, Co-I, key personnel — R4RI format)

### Appendix F: References

**Hornung, M., Pham, H., Sirvent, R., Badia, R. M., & Beyvers, S. (2025).** Harmonizing computational reproducibility standards across journals: A multi-tier framework proposal. *Computational Research Reproducibility Workshop*.

**Ioannidis, J. P. A. (2005).** Why most published research findings are false. *PLoS Medicine*, 2(8), e124. https://doi.org/10.1371/journal.pmed.0020124

**Ioannidis, J. P. A., Allison, D. B., Ball, C. A., Coulibaly, I., Cui, X., Culhane, A. C., ... & van Noort, V. (2009).** Repeatability of published microarray gene expression analyses. *Nature Genetics*, 41(2), 149-155.

**Keahey, K., et al. (2025).** NSF REPETO Workshop Report: Practical challenges in reproducible high-performance computing. *National Science Foundation Workshop Series*.

**Miller, G. (2006).** A scientist's nightmare: Software problem leads to five retractions. *Science*, 314(5807), 1856-1857.

**Schultze, A., Saul, L., Roesch, E., Rinke, E.M., Mahmoud, O., Kelson, M., DeBruine, L., Coca-Castro, A., Booth, F., & Baykova, R. (2025).** Computational reproducibility: A primer from UKRN. UK Reproducibility Network.

**Trisovic, A., Lau, M. K., Pasquier, T., & Crosas, M. (2022).** A large-scale study on research code quality and execution. *Scientific Data*, 9(1), 60.

---

**END OF PROPOSAL**

**Version:** 3.1 — Scaled Phase 0 for UKRI Metascience Round 2  
**Date:** February 2026  
**Contact:** [PI details TBD]  
**Funding Target:** UKRI Metascience Research Grants, Round 2
