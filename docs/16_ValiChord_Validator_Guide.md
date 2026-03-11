<div align="center">
  <img src="https://github.com/topeuph-ai/ValiChord/blob/main/Valichord%20logo-standard%20v2-1.5x.jpeg" width="500px" alt="Valichord Logo">
</div>

# The ValiChord Validator Guide

*What it means to be a ValiChord validator — and why it matters*

---

## What Is a ValiChord Validator?

A ValiChord validator is an independent computational researcher who attempts to reproduce published scientific results and records what they find.

That is the core of it. You take a published study — the code, the data, the documented methods — and you try to run it. You compare what you get against what the paper claims. You record your findings honestly, whether they confirm the original results or not.

Your finding is sealed before anyone else's is revealed. This is not a formality — it is the foundation of the entire system. ValiChord is designed to produce independent verdicts, not consensus. What you find matters precisely because you found it without knowing what anyone else found.

---

## Why Does This Matter?

Computational reproducibility is one of the most important unsolved problems in modern science. Studies consistently show that the majority of published computational research cannot be independently verified. Funders are spending billions on findings that may not hold up. Other researchers are building on results that were never checked.

The problem is not usually fraud. It is undocumented dependencies, platform differences, missing environment specifications, code that worked on one machine in 2021 and nowhere else since. These are fixable problems — but only if someone sits down and tries to reproduce the work.

ValiChord validators are the people who sit down and try.

Your work generates something that does not currently exist: a permanent, tamper-proof record of what an independent expert found when they actually ran the code. That record — a Harmony Record — will be publicly readable by journals, funders, institutions, and other researchers. It cannot be altered after you submit it. It will outlast the paper it concerns.

---

## What Credentials Do You Need?

To join ValiChord's validation network, you need an **institutional credential** — a cryptographic certificate issued by an authorised body confirming that you are a verified computational researcher.

In practical terms, this means:

- You are affiliated with a recognised research institution, university, or research organisation
- Your credential is issued by an authorised credential provider (your institution, a recognised research network, or ValiChord's credentialing partner)
- The credential is checked mathematically when you join the network — it cannot be forged or borrowed

This is not about seniority or prestige. PhD students, postdocs, research software engineers, and senior professors all participate on equal terms. The credential confirms you are who you claim to be and that you have a legitimate institutional connection to computational research. It does not rank you.

**In Phase 0**, credentials are issued directly by the ValiChord team in coordination with participating institutions. If you are interested in validating and hold a position at a UK research institution, get in touch.

---

## What Skills Do You Need?

ValiChord validation is computational reproduction, not peer review. You are not assessing whether the methodology is sound or whether the conclusions are justified. You are answering a narrower, more concrete question: *does the code produce the results the paper describes?*

To do this well, you need:

**Essential:**
- Proficiency in at least one computational language (Python, R, Julia, MATLAB, or similar)
- Familiarity with version control (Git)
- Ability to set up and troubleshoot computational environments (conda, Docker, pip, renv, or equivalent)
- Patience with underdocumented codebases

**Helpful:**
- Experience with the discipline of the study you are assigned (though cross-discipline assignments are sometimes made deliberately — see below)
- Familiarity with HPC environments, cloud platforms, or containerisation
- Experience debugging other people's code

**Not required:**
- Deep expertise in the specific scientific domain
- Any particular seniority level
- Previous validation experience

If you can set up an environment, run someone else's code, and compare numerical outputs to a table in a paper — you can validate.

---

## What Does the Work Actually Involve?

A validation task follows a standard protocol. Here is what you will typically do:

**1. Receive your assignment**
You receive a ValidationTask in your private ValiChord workspace — a description of the study, the discipline, the estimated difficulty range, and a time cap. You will not be told the predicted difficulty tier. This is deliberate: your unprimed experience is a data point.

**2. Access the study materials**
You download the study's code and data from the public archive (GitHub, OSF, Zenodo, or wherever the authors deposited them). Everything you need should be publicly accessible. If it is not — if data is behind a login, or proprietary software is required — that is itself a finding worth recording.

**3. Set up the environment**
Follow the authors' documentation to reconstruct the computational environment. Install dependencies. Configure settings. This step is often where the most interesting friction occurs — and where your structured time log begins.

**4. Run the code**
Execute the analysis as documented. Compare the outputs against the published results. You are looking for numerical agreement within reasonable precision (accounting for documented sources of variation such as random seeds or floating-point differences).

**5. Record what you find**
At every stage, you log your time using ValiChord's structured time-tracking tool. At the end, you complete a short assessment covering:
- Whether you reproduced the results (and to what degree)
- Where you encountered barriers and how you resolved them
- Your confidence in your finding
- Any undeclared deviations you noticed between the code and the paper
- The computational resources you used

**6. Seal your assessment**
Before submitting publicly, you seal your private assessment in your local ValiChord workspace. This is the commitment step. Your finding is locked at this point — you cannot change it after seeing what other validators found. This is what makes the process trustworthy.

**7. Reveal when the window opens**
Once all validators on your study have committed, ValiChord opens the reveal window. You publish your full public attestation. It is permanent the moment it is submitted.

---

## How Long Does It Take?

This is genuinely unknown — and discovering the answer is one of the purposes of Phase 0.

Based on what is known from comparable initiatives:
- Simple, well-documented studies with clean code may take **4–8 hours**
- Moderate studies with some documentation gaps or dependency issues: **10–20 hours**
- Complex studies or studies with significant environment friction: **20–40 hours**
- Some studies may prove effectively impossible to validate within a reasonable timeframe

A **40-hour time cap** applies to all Phase 0 tasks. If you reach 40 hours without completing reproduction, you record what you found up to that point and submit. Reaching the cap is not a failure — it is a data point about the study's difficulty.

You will not know in advance where your assigned study falls on this spectrum. That is intentional.

---

## What Are You Paid?

Phase 0 validators are paid at professional rates.

**Standard rate:** £500 per completed validation task

**Difficulty adjustment:** If you are assigned a disproportionately difficult task — one that takes significantly longer than average — additional compensation is provided. This is determined at study end based on the actual workload distribution across all tasks.

You are compensated for your time and expertise regardless of whether the study reproduces. Your job is to find out what happens honestly — not to produce a particular result.

---

## Cross-Discipline Assignments

Some Phase 0 assignments deliberately pair a validator with a study outside their primary domain — for example, a chemist validating a climate modelling study, or an ecologist validating a machine learning pipeline.

This is not an oversight. One of Phase 0's research questions is whether computational competence alone is sufficient for validation, or whether domain expertise materially affects outcomes. If a computational expert from a different field can reproduce the results as reliably as a domain specialist, that tells us something important about the nature of computational validation. If they cannot, that also tells us something important.

You will be informed if your assignment is cross-discipline. You can flag concerns about your ability to complete it, and assignments will be adjusted where genuine competence gaps would make the task meaningless. But a moderate mismatch is intentional and valued.

---

## What Happens After You Submit?

Your attestation becomes part of a permanent record. Once all validators on your study have submitted, ValiChord assembles a **Harmony Record** — the permanent, public account of what the validation round found. You will be able to see the full record, including what the other validators found and how closely you agreed.

Your participation also builds your **Validator Reputation** — a record of your validation history, agreement rates, and discipline coverage that persists on the network. Phase 0 participants are the founding cohort of a professional validator community. The long-term vision is a recognised career track for research validation — Phase 0 is where it starts.

---

## What Validators Are Not Asked To Do

**You are not asked to fix the code.** Reasonable troubleshooting is expected — if a package name has changed, you can update it. If a file path is wrong, you can correct it. But you are not expected to debug, rewrite, or substantially modify the original code. If the code requires significant repair to run at all, that is a finding about the study's reproducibility, not a task for the validator.

**You are not asked to judge the science.** Whether the methodology is appropriate, whether the conclusions are overstated, whether the study should have been published — none of this is your remit. You are checking whether the code does what the paper says it does. Full stop.

**You are not asked to produce a particular result.** A finding of "not reproduced" is as valuable as a finding of "reproduced." ValiChord's usefulness depends entirely on validators reporting honestly what they find. A validator who shades their finding to be more positive — or more negative — undermines the entire system. The blind commit design means we can detect patterns of systematic bias over time. Honest reporting is the only thing we ask.

---

## Interested in Validating?

Phase 0 is recruiting UK-based computational researchers across disciplines and career stages.

If you hold a position at a UK research institution and are interested in participating, contact:

**Ceri John** — [topeuph@gmail.com](mailto:topeuph@gmail.com)

Please include a brief description of your computational background, primary programming languages, and institutional affiliation. Formal expressions of interest will open once the host institution is confirmed and ethics approval is in place.

---

*For more on how a validation round works end-to-end, see [How A Validation Round Works](14_ValiChord_How_A_Validation_Round_Works.md).*

*For the governance principles that protect validator independence, see [Governance Framework](2_ValiChord_Governance_Framework.md).*

*For the technical infrastructure underpinning the process, see [Vision & Architecture](1_ValiChord_Vision&Architecture.md).*
