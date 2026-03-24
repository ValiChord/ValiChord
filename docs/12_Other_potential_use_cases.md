<div align="center">
  <img src="https://github.com/topeuph-ai/ValiChord/blob/main/Images/Valichord%20logo-standard%20v2-1.5x.jpeg" width="550px" alt="ValiChord Logo">
</div>

# ValiChord: The Verification Crisis Isn't Just in Science
## A Strategic Map of Where the Pattern Applies

**Author:** Ceri John
**Date:** March 2026
**Status:** INTERNAL — Not for external distribution

**© 2026 Ceri John. All Rights Reserved.**

---

**This document is for strategic thinking only. It is not part of the ValiChord proposal suite and should not be shared with funders, PIs, or institutional partners at this stage. The purpose is to map where ValiChord's core pattern could extend if it succeeds in its home domain — so that architectural decisions made now don't accidentally close off future possibilities.**

---

## The Core Pattern

ValiChord's architecture solves a general problem, not a science-specific one. The pattern is:

1. Someone makes a verifiable claim ("my methodology produces these results")
2. Independent parties attempt to reproduce those results
3. Agreement and disagreement are both recorded permanently
4. The record is cryptographically verifiable and tamper-resistant
5. Gaming, collusion, and institutional capture are detected and resisted
6. The full picture — including uncertainty and disagreement — is visible to anyone who looks

The claim can be computational, experimental, clinical, or hardware-based. Methodology and data go in — whether that is a Python script, a lab protocol, a synthesis procedure, or a device assembly guide — and validators reproduce the work. The protocol does not care what validators are doing with their hands or their computers. What it cares about is that they do it independently, commit before seeing each other's results, and that the full record is preserved.

This pattern applies wherever verifiable claims carry consequences and independent verification is valuable. Science is the first and most natural home. Within science, computation is the first and most tractable instance. Neither is the limit.

The same structural failure recurs across every domain in this document: genuine crisis → institutional response → compliance theatre. Not sabotage. A hundred small accommodations. ClinicalTrials.gov was meant to make clinical trial suppression impossible. It didn't work. The carbon credit registries were meant to make greenwashing detectable. They didn't work. The rating agencies were meant to make financial risk transparent. They didn't work. In each case, the infrastructure was captured by the interests it was designed to scrutinise — not through conspiracy, but through the slow gravitational pull of funding dependence, access dependence, and the path of least resistance.

ValiChord's governance framework was designed to resist exactly this. That design is domain-agnostic. The verification crisis isn't just in science. It's everywhere that computation meets consequence and independence matters.

---

## Domain Analysis

### 1. Clinical Trial Selective Reporting

**The problem:** This is the verification crisis closest to ValiChord's home domain — and the one with the most directly documented body count.

Clinical trials are the foundation of evidence-based medicine. Their results determine which drugs are approved, which treatments are recommended, and which risks are disclosed to patients. The integrity of that foundation depends on one assumption: that trial results are reported fully and accurately, with outcomes defined before the data is seen.

That assumption is false. Studies consistently find that 40–62% of clinical trials change, introduce, or omit at least one primary outcome between the registered protocol and the published paper. Statistically significant outcomes are two to five times more likely to be fully reported than non-significant ones. An estimated 53% of registered trials are never published at all. The direction of this suppression is not random — it favours sponsors, favours positive results, and disadvantages patients.

The consequences are not abstract. GlaxoSmithKline conducted at least five trials on the paediatric use of paroxetine. They published one — which showed mixed results. The others, which showed no efficacy and suggested increased suicidality in children, were suppressed. It took a lawsuit by the New York Attorney General to surface them. This is not an isolated case. It is the documented pattern across antidepressants, COX-2 inhibitors, anti-arrhythmic drugs, and dozens of other therapeutic areas.

**Why existing solutions haven't worked:** The field's primary response was ClinicalTrials.gov — a centralised US government registry where trial protocols must be pre-registered before enrollment begins. In principle, this should make outcome-switching detectable: compare the registered protocol with the published paper. In practice, it hasn't worked for a structural reason that ValiChord's design addresses directly.

ClinicalTrials.gov is a mutable central database. Investigators can modify trial information — including primary outcomes, start dates, and completion dates — even after a trial has been completed. The central registry itself can be edited after the fact. This is not a bug that can be patched; it is the consequence of centralised architecture. A mutable central database controlled by a single authority will always be modifiable by those with access, under pressure from those with financial interests in the outcome.

**How ValiChord fits:** The core requirement for clinical trial integrity is identical to ValiChord's core mechanism: seal a commitment before the data is seen, make the seal cryptographically tamper-evident, and distribute the proof across independent parties so that no single authority can modify it.

In ValiChord's home domain, what gets sealed is a validation commitment — the validator's assessment, submitted before seeing other validators' results. In the clinical trial domain, what gets sealed is the outcome definition — the pre-specified primary and secondary endpoints, locked with a cryptographic timestamp before the first patient is enrolled. Any subsequent modification leaves an immutable trace in the distributed record, visible to regulators, journal editors, and the public.

Holochain's architecture is specifically suited to this requirement:
- Patient data is subject to GDPR and HIPAA and cannot leave trial sites or sit on a central immutable ledger. Holochain keeps data local; only the cryptographic proof of the pre-registered protocol is distributed.
- Multi-site international trials require coordination across dozens of sites in multiple jurisdictions without any single party controlling the master record — exactly what agent-centric distributed architecture enables.
- The Harmony Record captures not just whether a trial reproduced, but the full provenance chain: what was pre-registered, when, by whom, and how the published paper's outcomes compare.

**The anti-capture dimension:** This is where ValiChord's governance framework is most directly relevant. Every existing clinical trial verification initiative — ClinicalTrials.gov, the AllTrials campaign, journal pre-registration requirements, the Declaration of Helsinki amendments — has encountered the same resistance: the entities with the most financial interest in trial outcomes are the same entities that fund, conduct, and control access to the trials. Independent verification infrastructure that depends on pharmaceutical company cooperation for access, data, or funding will be domesticated. The anti-capture mechanics in ValiChord's governance framework — funding concentration tripwires, conflict of interest screening, structural independence requirements — address this directly.

**Potential partners:** MHRA, EMA, AllTrials campaign, Cochrane Collaboration, EQUATOR Network, TranspariMED.

**Complications:** Patient data confidentiality is the primary architectural constraint — solved by Holochain's local data model. Commercial confidentiality of proprietary statistical methods is a political constraint requiring regulatory mandate rather than technical solution. Regulatory timelines may not accommodate independent validation without process redesign. These are real complications but not architectural blockers.

**Why this matters for ValiChord's long-term positioning:** The reproducibility crisis in computational science is serious. But "a paper that can't be reproduced" is abstract harm. "A drug was approved because negative trial results were suppressed and children were harmed" is concrete, documented, and has generated billion-dollar legal settlements. If ValiChord's architecture is ever described as critical infrastructure — rather than a useful research tool — clinical trial pre-registration integrity is the domain that makes that case.

---

### 2. Carbon Credit Verification

**The problem:** The voluntary carbon market exists to allow companies and governments to offset their emissions by funding projects that reduce or sequester carbon elsewhere — protecting forests, funding renewable energy, capturing methane. It is a multi-billion dollar market. Its entire value depends on one claim being true: that the carbon reductions claimed actually happened.

In 2023, an investigation by The Guardian, Die Zeit, and SourceMaterial found that approximately 90% of Verra's rainforest carbon credits — Verra being the world's largest carbon credit registry — were effectively worthless. The forests they claimed to be protecting were not under meaningful threat, were already protected by other means, or did not sequester the claimed quantities of carbon. Verra's CEO resigned. The voluntary carbon market, which had been projected to reach $50 billion by 2030, lost credibility it has not recovered.

The structural cause is the same as in clinical trials and research reproducibility: the verifier is paid by the entity being verified. The verification methodology is proprietary. The computational claim — this forest sequestered X tonnes of CO₂, calculated from satellite imagery and ground data using model Y — is never independently reproduced. The permanent record is held by a central authority with a financial interest in positive verification outcomes.

**How ValiChord fits:** The carbon sequestration claim is a computational claim: a model applied to satellite imagery, sensor data, and ground-truth measurements produces a figure. Independent validators can download the model, apply it to the stated data, and record whether the outputs match the claimed sequestration figures. Disagreement is preserved in the Harmony Record. The multi-validator architecture means that systematic fraud by a captured verifier is detectable — not by any single authority deciding the verifier is corrupt, but by the simple fact of independent validators producing different results.

Holochain's architecture is well-suited to the specific data constraints:
- Forest monitoring data — satellite imagery, ground sensor readings, indigenous land records — is collected in multiple jurisdictions with varying data protection laws and indigenous data sovereignty frameworks. It cannot and should not sit on a central immutable ledger. Holochain keeps data local and deletable; only cryptographic proofs of verification outcomes are distributed.
- Carbon projects span decades. The verification infrastructure needs to outlast any single organisation — exactly the resilience that distributed architecture provides and centralised registries cannot.
- Indigenous communities and forest nations have legitimate sovereignty claims over data collected on their land. Agent-centric architecture, where each participant controls their own data, is structurally compatible with these claims in a way that centralised databases are not.

**The anti-capture dimension:** Verra failed not because its verification methodology was technically wrong — it was because the institutional incentives made systematic rigour impossible. Verifiers who consistently found that projects didn't meet claimed targets would lose clients. The gradual accommodation of commercial pressure over scientific integrity is identical to the pattern ValiChord's governance framework was designed to resist.

**Potential partners:** Gold Standard Foundation, Plan Vivo, ICROA, Woodland Carbon Code (UK), UK Centre for Ecology and Hydrology, Verra (as a potential institutional partner in rebuilding credibility), CarbonPlan (US-based independent carbon credit analysis organisation).

**Complications:** Satellite data processing pipelines are complex and require specialist validators with remote sensing expertise — a different validator pool from computational research. Ground-truth data collection involves indigenous communities and requires consent frameworks beyond standard research ethics. Proprietary sequestration models raise commercial confidentiality issues requiring regulatory mandates for access. These are significant but not architectural blockers.

**Market context:** The voluntary carbon market needs this infrastructure to function. The Verra scandal demonstrated that markets built on unverifiable computational claims collapse when the verification fails. Restoring credibility requires infrastructure that structurally cannot be captured — which is precisely ValiChord's core claim.

---

### 3. Government Policy Modelling

**The problem:** Governments make policy decisions based on computational models — economic impact assessments, infrastructure cost-benefit analyses, public health projections, climate adaptation plans. These models are rarely independently verified. When they are challenged, the challenge is political ("your model is biased") rather than technical ("your model doesn't reproduce from the stated inputs").

**How ValiChord fits:** An independent validator downloads the model, runs it with the stated parameters and data, and records whether the outputs match the published results. Disagreement is preserved. The Harmony Record sits alongside the policy document.

**UK context:** The government's Aqua Book (2015) already recommends independent verification of analytical models used in policy. The Infrastructure and Projects Authority requires assurance of major project models. But there is no infrastructure for systematic, independent, transparent verification. ValiChord's pattern fills that gap directly.

**Potential partners:** Government Analysis Function, National Audit Office, Institute for Government, What Works centres.

**Complications:** Government models often involve restricted data (economic data, health data, security-sensitive inputs). ValiChord's architecture — where data stays local and only cryptographic proofs are distributed — is specifically designed for this constraint. But political sensitivity is a different challenge from scientific sensitivity. A Harmony Record showing that a government's flagship policy model doesn't reproduce is not just an academic finding — it's a political event.

---

### 4. Economic and Financial Forecasting

**The problem:** Central banks, international institutions (IMF, World Bank, OECD), and financial regulators publish forecasts based on computational models. These forecasts influence markets, policy, and public expectations. The models are complex, proprietary, and almost never independently reproduced.

**How ValiChord fits:** Independent reproduction of published forecasts from stated models and data. Did the Bank of England's inflation model actually produce the published forecast from the stated inputs? A Harmony Record doesn't judge whether the model is *good* — it verifies whether the published outputs match what the model actually produces.

**Potential partners:** Bank of England (which has an active research agenda on model transparency), Office for Budget Responsibility, National Institute of Economic and Social Research.

**Complications:** Financial models are often proprietary. Model parameters may be commercially sensitive. Validator access to full model specifications may be restricted. ValiChord would need a secure validation environment — validators see the model long enough to verify it, but don't retain it. This is architecturally feasible (secure enclaves, time-limited access) but adds significant complexity.

**Credit rating models — a specific case:** The 2008 financial crisis was partly a failure of captured computational verification. Rating agencies were paid by the entities whose securities they rated. Their models were not independently reproducible. The pattern is identical to ValiChord's home domain; the consequences were global. Independent verification of rating methodologies — not whether the ratings are correct, but whether the published model actually produces the published ratings from the stated inputs — is a direct application of ValiChord's architecture.

---

### 5. Regulatory Submissions (Pharmaceutical / Environmental)

**The problem:** Pharmaceutical companies submit computational analyses to regulators (MHRA, FDA, EMA) as part of drug approval processes. Environmental impact assessments involve computational modelling. These submissions are reviewed but rarely independently reproduced end-to-end.

**How ValiChord fits:** Independent reproduction of submitted computational analyses. Did the statistical model produce the claimed efficacy results from the trial data? Does the environmental model produce the claimed impact projections from the stated inputs?

**The FDA connection:** The FDA has been moving toward requiring reproducible computational submissions through its CDER (Center for Drug Evaluation and Research) modernisation programme. The EMA's regulatory science strategy explicitly mentions computational reproducibility. ValiChord's pattern aligns with where regulators are already heading.

**Potential partners:** MHRA, NICE (which already does independent health technology assessment), environmental regulators.

**Complications:** Patient data confidentiality. Commercial confidentiality of drug trial data. Regulatory timelines that may not accommodate validation delays. However, ValiChord's architecture — local data, distributed proofs — is designed for exactly this data sensitivity challenge.

---

### 6. Software Verification

**The problem:** Critical software systems (aviation, medical devices, financial trading, infrastructure control) undergo formal verification. But verification is typically done by the developer or a contracted third party with close ties to the developer. Independent, transparent verification with preserved disagreement is rare.

**How ValiChord fits:** Independent validators test whether software behaves as specified. Not full formal verification (which is a different discipline) but empirical verification: does this software produce the documented outputs from the documented inputs across a range of conditions?

**Potential partners:** Software Sustainability Institute, Alan Turing Institute, safety-critical industries.

**Complications:** Software verification is a mature field with established tools and methodologies. ValiChord's contribution would be the *social* infrastructure (independent validators, preserved disagreement, anti-gaming) rather than the technical verification methods. This is a complement, not a replacement.

---

### 7. AI Model Auditing

**The problem:** AI models are increasingly used in consequential decisions — hiring, lending, criminal justice, healthcare. Auditing these models for bias, accuracy, and reproducibility is a growing regulatory requirement (EU AI Act, proposed UK framework). But auditing is typically done by the developer or a contracted auditor.

**How ValiChord fits:** Independent validators reproduce claimed model performance metrics. Does this model actually achieve the stated accuracy on the stated test set? Do the claimed fairness metrics hold? A Harmony Record for an AI model would show whether independent auditors agree on its performance — and where they disagree.

**Potential partners:** Centre for Data Ethics and Innovation, Ada Lovelace Institute, AI Safety Institute.

**Complications:** Model access (proprietary models may not be available for independent testing), dataset access (test sets may be restricted), and the rapidly evolving regulatory landscape. But ValiChord's anti-capture governance is particularly relevant here — auditors need to be genuinely independent of the companies whose models they're auditing, which is exactly the conflict-of-interest problem ValiChord's governance addresses.

---

### 8. Journalism and Fact-Checking

**The problem:** Data journalism increasingly involves computational analysis — processing leaked documents, analysing public datasets, building models to support investigative claims. These analyses are rarely independently verified before publication.

**How ValiChord fits:** A data journalism outlet could submit its computational analysis for independent reproduction before publication. The Harmony Record becomes a credibility signal: "our analysis was independently reproduced by three validators."

**Potential partners:** Bureau of Investigative Journalism, Full Fact, First Draft.

**Complications:** Speed. Journalism operates on deadlines that may not accommodate validation cycles. Pre-publication verification would need to be fast. This may limit ValiChord's applicability to longer-form investigative work rather than breaking news.

---

### 10. Open Hardware Reproducibility

**The problem:** Open hardware is the fastest-growing frontier of the reproducibility crisis — and the least discussed. A published hardware design makes an implicit claim: "a third party, using these files and this bill of materials, can build a device that performs as stated." This claim is almost never independently verified. Hardware projects are published to repositories with CAD files, firmware, and assembly guides — and then assumed to be reproducible because the files are open.

They often aren't. Reasons range from components that are discontinued, regionally unavailable, or single-vendor; to CAD files in proprietary formats that require expensive licensed software to open; to Arduino firmware with unpinned library dependencies that silently changed behaviour in newer versions; to assembly guides that assume tacit expertise the author didn't know they had. The gap between "open" and "reproducible" in hardware is as large as it is in research software — and the consequences can be more directly physical. A medical device built from a misunderstood calibration procedure doesn't just fail to reproduce — it may give wrong clinical readings.

The context in which this use case became concrete for ValiChord: in 2026, Sensorica's Breathing Games collaboration produced the PEP Master device — a breath-flow controller for cystic fibrosis therapy, clinically validated at CHU Sainte-Justine with 158 children and published in JMIR Serious Games. The device repository (https://gitlab.com/breathinggames/bg_device) contains 13 device iterations, 3D-printed enclosures, Arduino firmware, KiCad PCB designs, and calibration procedures using a syringe reference standard. This is exemplary open hardware. It has also never been independently reproduced by a third party who wasn't part of the original team.

**How ValiChord fits:** The validation logic maps cleanly onto ValiChord's existing architecture, with two structured sub-claims replacing the single "code + data → result" claim:

*Claim 1 — Buildability:* A validator with no prior knowledge of the project can, using only the repository files and the stated BOM, assemble a working device. Deviations — component substitutions, assembly ambiguities, firmware modifications required — are recorded in the Harmony Record.

*Claim 2 — Performance:* The assembled device, calibrated using the stated procedure and reference standard, meets the performance specification. For PEP Master: peak expiratory flow measurements agree with conventional spirometry within the stated tolerance.

Validators commit their build and performance assessments independently before seeing each other's results — the same blind commit-reveal that prevents collusion in research validation. The Harmony Record captures the full picture: which validators built successfully, what substitutions were required, whether the device met spec, and — critically — geographic variation in component availability.

**What's different from research validation:**

*Timeline:* Building a physical device takes days to weeks, not hours. Sourcing components, 3D printing, soldering, calibration. A validation round for hardware may span four to six weeks rather than four to six days. Compensation bands need to reflect this.

*Material costs:* Validators incur real component costs — potentially £50–£300 per build depending on device complexity. The compensation model must account for this, either through reimbursement or elevated validator fees. This is architecturally novel for ValiChord.

*Geographic dependency:* Component availability is not uniform. A validator sourcing an Adafruit Feather 32U4 Bluefruit LE in the EU faces different lead times, prices, and import duties than a validator in Canada. Recording validator geography in the Harmony Record, and treating component substitution as structured data rather than a free-text note, is essential for the record to be useful.

*Split performance definition:* Research validation has one question: does the code produce the stated output? Hardware validation has two: can it be built, and does it work? A device may build successfully but underperform. A device may fail to build in some regions due to component unavailability but build fine in others. The Harmony Record format needs to capture both dimensions independently.

**New failure modes for ValiChord at Home (hardware edition):**

The existing ValiChord at Home detector framework would need a hardware-specific extension. Analogous to the research failure mode codes, hardware failure modes would include:

- **[BOM]** Missing or incomplete Bill of Materials — no component list, no quantities, no part numbers
- **[BOM-S]** Single-vendor or discontinued components — sourcing risk for validators outside the author's region
- **[CAD-F]** Proprietary CAD format — Fusion360 `.f3d` files require a commercial licence; `.scad`, `.step`, or `.stl` are open
- **[FW-D]** Unpinned firmware dependencies — Arduino library versions not specified; behaviour may have changed in current releases
- **[CAL]** No calibration procedure — device performance cannot be independently verified without a reference standard and stated procedure
- **[PERF]** No measurable performance specification — "works" is not a testable claim; a specification with tolerances is required
- **[TOL]** No manufacturing tolerances — 3D-printed parts with tight fits require stated tolerances; missing tolerances make assembly ambiguous
- **[LIC-H]** No hardware-specific licence — code licences (MIT, Apache) do not cover hardware designs; CERN-OHL or TAPR OHL required

The PEP Master bg_device repository scores well on most of these — firmware is open (Arduino `.ino`), CAD includes `.stl` and `.scad`, calibration uses a documented syringe reference standard — but has no standalone licence file at root, and Arduino library dependencies are embedded without explicit version pinning. ValiChord at Home run against this repository would surface these findings as a concrete demonstration of the hardware use case.

**The NDO connection:** A Nondominium Object (NDO) *is* a hardware device, in exactly this sense. The PEP Master NDO packages device designs, firmware, documentation, validation studies, and the contributor network into a single governed object. ValiChord validation of an NDO is validation that the NDO's hardware claims are independently reproducible. This is the concrete instantiation of "ValiChord as integrity layer for NDOs" — not an abstraction, but three validators in three countries attempting to build the same device and recording the result in a Harmony Record.

**Potential partners:** Breathing Games / Sensorica (immediate — the collaboration is already in progress); Open Source Hardware Association (OSHWA — they certify hardware as open but don't verify reproducibility); CERN Open Hardware (maintain CERN-OHL licence and have a community of hardware validation practice); Gathering for Open Science Hardware (GOSH); Wikifactory (hardware version control platform with a reproducibility interest).

**Complications:** Validator compensation is more complex than for research validation — material costs are real and variable by region. The validation timeline is much longer, creating cash flow challenges if validators are reimbursed only on completion. The performance specification must be machine-readable and unambiguous before validation begins, which requires more upfront work from hardware authors than research authors. And the validator pool — hardware engineers with access to 3D printers, soldering equipment, and calibration instruments — is smaller and less geographically distributed than the computational research validator pool.

None of these are architectural blockers. They are configuration and compensation challenges — exactly the "what needs rebuilding per domain" category described in the section below.

---

### 9. Actuarial Models in Insurance

**The problem:** Insurance pricing models have massive social consequences — discriminatory pricing, redlining, denial of coverage — and are almost never independently verified. Regulators review submissions but rarely reproduce the computational claims end-to-end. The model that determines whether someone can afford home insurance in a flood zone, or health insurance with a pre-existing condition, is a black box to everyone except the insurer that built it.

**How ValiChord fits:** Independent reproduction of pricing model outputs from stated inputs. Does the model that claims to predict flood risk actually produce the published risk scores from the stated variables? A Harmony Record doesn't adjudicate whether the model is fair — it verifies whether it is what it claims to be. That is the precondition for any meaningful regulatory oversight.

**Potential partners:** Financial Conduct Authority, Prudential Regulation Authority, actuarial professional bodies.

**Complications:** Proprietary model protection. Commercial sensitivity. Regulatory mandate likely required before voluntary adoption.

---

## What Transfers Directly

Some components of ValiChord's architecture transfer to new domains without modification:

- **Holochain infrastructure.** Agent-centric, local data, distributed proofs. Domain-agnostic by design.
- **Harmony Record format.** Multiple independent assessments, preserved disagreement, confidence levels, provenance chain. Works for any computational claim.
- **Governance framework.** Anti-capture, anti-domestication, anti-gaming. The threats are universal.
- **Conflict of interest screening.** Independent validators, institutional attribution, collusion detection. Applies wherever independence matters.
- **Anti-Domestication Mechanics.** Funding concentration tripwires, default salience rules, API display requirements. These resist the same pressures in any domain.

## What Needs Rebuilding Per Domain

Some components are calibrated for computational science and would need domain-specific evidence:

- **Difficulty assessment rubric.** What makes a policy model hard to verify is different from what makes a genomics study hard to validate. Each domain needs its own Phase 0.
- **Compensation bands.** Validator rates depend on the labour market in each domain.
- **Triage rules.** What's validatable and what isn't depends on domain norms.
- **Disciplinary Standards Committees.** Each domain needs its own standards body with domain expertise.
- **ValiChord at Home rubrics.** The checklist for a well-organised carbon credit submission is different from the checklist for a well-organised research repository.

---

## Strategic Implications for Current Design

Even though these extensions are years away, some architectural decisions made now could either enable or block them:

**Keep the core domain-agnostic.** The Holochain DNA, the Harmony Record format, and the governance framework should not contain science-specific assumptions at the infrastructure level. Science-specific rules should sit in configuration layers, not in the core architecture. This is already the case in the current design — but it's worth being deliberate about maintaining it.

**Design the rubric system to be pluggable.** The difficulty assessment, triage rules, and compensation bands should be modular — swappable per domain without architectural changes. If the current design hard-codes science-specific rubrics into core infrastructure, future extension becomes a rebuild rather than a configuration change.

**Keep "Harmony Record" generic.** The term and format should describe any multi-validator assessment with preserved disagreement, not just scientific reproducibility assessments. The current design already does this — but naming matters, and "reproducibility" language in the core format could limit perception.

**Document the pattern, not just the implementation.** If ValiChord's contribution to knowledge is the *pattern* (independent distributed verification with preserved disagreement and anti-capture governance), then documenting that pattern clearly — separate from the science-specific implementation — creates the foundation for future extension.

---

## Timing

None of this should appear in external communications until ValiChord has:

1. Completed Phase 0 and published results
2. Built and tested the MVP
3. Operated at Phase 1 scale with real validators and real studies
4. Demonstrated that the pattern works in its home domain

Premature talk of "verifying government policy" or "auditing AI models" or "fixing the carbon credit market" would undermine credibility and distract from the focused pitch that gets Phase 0 funded.

The right moment to start these conversations is when ValiChord has published Harmony Records that people can point to and say: "this pattern works." At that point, someone in clinical trials regulation or carbon credit verification will see it and ask: "could this work for us?" The answer should be: "yes, and here's the document we wrote three years ago explaining how."

That's what this document is for.

---

**This document is not part of the ValiChord proposal suite.**
**It is internal strategic thinking for future reference.**

**© 2026 Ceri John. All Rights Reserved.**
