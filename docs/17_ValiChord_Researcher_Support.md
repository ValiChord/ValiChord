
<div align="center">
  <img src="https://github.com/topeuph-ai/ValiChord/blob/main/Valichord%20logo-standard%20v2-1.5x.jpeg" width="550px" alt="ValiChord Logo">
</div>

# ValiChord Researcher Support
## How ValiChord Helps Researchers Improve Their Work

**Author:** Ceri John
**Date:** February 2026

**© 2026 Ceri John. All Rights Reserved.**

**Contact:** topeuph@gmail.com

---

How much important science has never been validated — not because it was wrong, but because the researcher who produced it wasn't the kind of person who organises a tidy repository? Reproducibility infrastructure that only serves researchers who are already systematic in how they work doesn't solve the reproducibility crisis. It just validates the people who needed the least help.

ValiChord's researcher support tools are designed for everyone — the meticulous organiser and the chaotic visionary alike. But the biggest impact falls on the latter: the brilliant minds who aren't brilliant organisers, and whose work has been quietly filtered out by systems that equate tidiness with quality.

---

## What It Is

*ValiChord at Home* is a self-service tool that helps researchers assess and improve their computational materials before submitting them to ValiChord for formal validation. It runs on the researcher's own machine, scans their repository, identifies what's missing or weak, and provides actionable guidance on how to fix it.

It is not part of ValiChord's distributed infrastructure. It requires no Holochain, no validators, no governance overhead. It is a standalone companion product — the friendly, accessible face of the ValiChord ecosystem.

---

## Why It Exists

### The Institutional Gap

Researchers who produce meticulously documented, perfectly containerised code repositories tend to be those in well-funded labs with dedicated research software engineers and institutional support. Early-career researchers, those in under-resourced institutions, and interdisciplinary thinkers who learned to code independently may produce groundbreaking science with poorly organised materials.

Without a tool like *ValiChord at Home*, any validation infrastructure — including ValiChord — disproportionately serves well-resourced labs. The studies that pass triage are the ones that were already most likely to be reproducible. That's not solving the reproducibility crisis. That's reinforcing existing advantages.

### The Cognitive Gap

Not every researcher who produces important science thinks in tidy file structures and well-organised repositories. Some of the most significant breakthroughs come from conceptual thinkers — people who see connections, make leaps, and generate ideas that nobody else has had — but who are not naturally systematic in how they organise and document their work.

*ValiChord at Home* bridges that gap. It takes brilliant ideas expressed in messy repositories and shows the researcher exactly how to make them reproducible, without requiring them to become a different kind of thinker.

### The Operational Case

Without pre-vetting, ValiChord's triage pipeline absorbs the cost of every messy submission. If 40% of submissions fail triage and require feedback cycles, significant resources are spent on studies that aren't ready yet. *ValiChord at Home* moves that assessment upstream. Researchers fix the obvious problems before they ever touch ValiChord's infrastructure. The triage pipeline receives cleaner submissions. Validators spend less time on avoidable friction. The system scales more easily.

---

## What It Does

The tool scans a local repository and checks for known indicators of validatability:

- **Documentation:** Does a README exist? Does it describe the analysis, the data, the method? Is there a methods section or equivalent?
- **Dependencies:** Are dependencies listed? Are versions pinned? Is there a requirements.txt, environment.yml, or equivalent?
- **Environment:** Is there a containerisation file (Dockerfile, Singularity)? Is the computational environment specified?
- **Data accessibility:** Do data URLs resolve? Is data downloadable without manual access requests? Are access instructions provided?
- **Code structure:** Is the code organised? Are scripts named meaningfully? Is there a clear entry point?
- **Study age:** How old are the commits? Are dependencies still maintained?

For each item, the tool reports what's present, what's missing, and provides guidance on how to fix each gap — with links to best-practice examples and templates.

### What It Produces

A report. Not a score, not a traffic light, not a badge. A clear, readable report that says: here's what any validator would need to find in your repository, and here's what's currently missing.

This is a deliberate design decision. A single score or pass/fail signal creates a target that gets gamed — researchers optimise for the number rather than actual quality. A report teaches researchers what validatable research looks like by showing them the specifics of their own work.

### What It Does NOT Do

- **Execute research code.** The tool analyses repositories statically — it reads files, counts lines, checks whether files exist. It never runs scripts, installs packages, or executes any code from the repository. This prevents malicious repositories from exploiting the scanning process.
- **Confer any status within ValiChord.** Pre-vetting with *ValiChord at Home* carries zero authority in ValiChord's pipeline. There is no fast-track, no preferential treatment, no "pre-approved" status. ValiChord runs its own triage regardless of what the tool reported.
- **Transmit data without consent.** The tool works fully offline by default. Anonymous usage analytics (which problems are most common, which disciplines use the tool) are strictly opt-in and anonymised before transmission.
- **Hide its standards.** The scoring rubric is public by design. Transparency about what ValiChord expects is the feature, not a vulnerability. Researchers understanding the standards is the entire point.

---

## The Full Feedback Pipeline

*ValiChord at Home* is one part of a broader system that helps researchers improve their work at every stage. The full pipeline has three levels, each building on the last.

### Level 1: Pre-Submission Self-Assessment (ValiChord at Home)

This is what the tool does. Before a researcher ever interacts with ValiChord's formal infrastructure, they scan their own repository and get a clear report on what's present, what's missing, and how to fix each gap. They iterate privately, at their own pace. Nobody sees their messy first attempt. When they're satisfied, they submit.

The tool also includes an auto-generate feature. Rather than just telling the researcher what's missing, it can draft the missing pieces: a README based on what it can see in the code, a requirements file from detected import statements, a Dockerfile from identified dependencies, a suggested folder structure from the existing file layout. The researcher reviews what the tool produced, edits anything that doesn't accurately represent their work, and saves the corrected files to their repository — all locally, all private.

**A clear warning accompanies every auto-generated suggestion: review this carefully before accepting.** Auto-generated corrections can be subtly wrong. A drafted README might mischaracterise what the code does. A pinned dependency might be at the wrong version. A restructured folder might break relative paths. The tool does the tedious organisational work — but only the researcher knows whether the result faithfully represents their science.

### Level 2: Post-Submission Diagnostic Feedback

A researcher submits a study to ValiChord and it doesn't pass triage. Instead of a bare rejection, ValiChord's triage system generates a diagnostic report. The system already knows *why* the study failed — the same surface features it used to assess difficulty tell it exactly what's weak. So the researcher receives targeted, actionable feedback: your documentation scored 2/5 — here's what a validatable README looks like, with examples; your dependencies aren't pinned — here's how to create a requirements file with version numbers; your data requires manual access requests — here's how to set up automated downloads. Each recommendation includes what to fix, why it matters for validation, a link to best-practice guidance, and an estimate of how long the fix would take.

The researcher addresses the issues and resubmits. The system didn't just reject their study — it taught them what validatable research looks like using the specifics of their own work.

### Level 3: Assisted Correction (Phase 2+)

Beyond diagnostic feedback, ValiChord can generate *proposed corrections* — a drafted README, pinned dependencies, restructured file organisation, clearer method descriptions — that the researcher reviews and approves before resubmission.

This is where the system does the tedious organisational work that the researcher couldn't or didn't do themselves. The conceptual thinker who produced brilliant science in a chaotic repository gets handed a clean version of their own work and just has to check it's right.

**Critical constraint: ValiChord never modifies or submits research materials without explicit author approval.** Automated corrections might pin the wrong dependency version, mischaracterise a method, or restructure code in a way that subtly changes what it does. Only the author knows whether the corrected version faithfully represents their work. A clean-looking README that misrepresents the analysis is worse than a messy one that's honest. The author's name is on the research; the author retains control.

The workflow is: submit study → triage scores it → study doesn't meet threshold → ValiChord generates proposed corrections → author reviews → author approves, edits, or rejects → approved version enters the validation pipeline.

### How the Levels Interact

Each level reduces the load on the next. Researchers who use *ValiChord at Home* (Level 1) — including its auto-generate feature — submit cleaner studies, so fewer fail triage. Studies that do fail triage get diagnostic feedback (Level 2), so most can be fixed quickly. Studies that need more help get assisted correction (Level 3), so even the messiest repository can reach validation if the science is sound.

The auto-generate feature in Level 1 and the assisted correction in Level 3 do similar work — drafting READMEs, pinning dependencies, proposing restructures — but in different contexts. Level 1 operates locally and privately, before anyone sees the work. Level 3 operates within ValiChord's formal pipeline, after submission and triage, with the full scoring context. Both require explicit researcher approval. A researcher who uses the auto-generate feature in Level 1 is unlikely to need Level 3 — which is the point.

Over time, the baseline improves. Researchers learn what ValiChord expects. Repositories get cleaner. Fewer studies need Level 2 or 3 support. The feedback pipeline works itself out of a job — which is exactly what success looks like.

The technical implementation (data structures, scoring logic, author approval workflows) is detailed in the Technical Reference companion document.

---

## Two Development Stages

### Stage A: Best-Practice Checklist (Released alongside Phase 0 results)

The initial version is a lightweight checklist based on established best practices — FAIR principles, existing code quality standards, and known reproducibility requirements. It does not predict difficulty or estimate validation time. It checks for what should be present and tells the researcher what's missing.

Stage A can be built quickly: one developer, a few weeks, standard web technologies. It could take the form of a command-line tool, a simple web app where the researcher pastes a GitHub URL, or a GitHub Action that runs automatically when code is pushed. No Holochain, no distributed systems, no governance infrastructure required.

Stage A is ValiChord's first public-facing product. It builds community engagement, generates name recognition, and creates a natural pipeline into formal validation — researchers who use the tool become familiar with ValiChord's standards and are more likely to submit studies.

### Stage B: Calibrated Pre-Vetting Tool (Phase 2)

The full version replaces Stage A with empirically calibrated scoring derived from Phase 0 and Phase 1 data. It uses the same difficulty-assessment rubric as ValiChord's triage system, with weights set by evidence — not assumptions — about which surface features predict actual validation difficulty.

Stage B can predict difficulty tiers, estimate validation time ranges, and generate targeted improvement recommendations with confidence levels. It produces the same `DifficultyAssessment` scores that ValiChord's triage uses, so researchers know exactly where they stand before submitting.

Stage B requires Phase 0's evidence (which surface features predict difficulty) and Phase 1's operational data (calibrated weights and thresholds). Building it earlier would mean enforcing assumptions rather than evidence-based standards — which contradicts ValiChord's core philosophy.

**Stage A builds the community and generates data. Stage B turns that data into precision.**

---

## Security Model

| Concern | Mitigation |
|---|---|
| Malicious repository exploits scanning | Static analysis only; no code execution; sandboxed file reads |
| Gaming the rubric to pass triage | Tool checks form, not substance; ValiChord triage includes human review above complexity threshold |
| Spoofed pre-vetting certificates | Tool output has zero authority in ValiChord pipeline; no fast-track for pre-vetted submissions |
| Analytics data exfiltration | Opt-in only; anonymised before transmission; tool fully functional offline |
| Reverse-engineering scoring algorithm | Rubric is intentionally public; understanding standards is the point |

---

## Anonymous Analytics (Opt-In Only)

If researchers consent to anonymous usage reporting, ValiChord aggregates data on:

- Most common failure points across disciplines (e.g., "73% of psychology submissions lack pinned dependencies")
- Distribution of readiness levels by field
- Which recommendations are most acted on
- Improvement trajectories (do researchers who use the tool repeatedly produce cleaner repositories?)

This generates a dataset on computational research practices across the whole ecosystem — not just the studies that reach formal validation. Nobody else has this data.

---

## Strategic Value

### For Researchers

A free tool that helps them improve their computational reproducibility, privately and at their own pace. Useful whether or not they ever submit to ValiChord.

### For ValiChord

Reduces triage load, builds community before the full infrastructure exists, generates ecosystem data, and creates a natural adoption pipeline.

### For the Field

Every researcher who uses the tool produces more reproducible work, whether or not it enters ValiChord's formal pipeline. *ValiChord at Home* extends ValiChord's impact from the studies it validates to the practices of every researcher who downloads the tool. Over time, the baseline quality of computational research improves because researchers learn what validatable work looks like — not through mandates, but through a tool that helps them get there.

### For Funders

Demonstrates that ValiChord is not just verification infrastructure but an active driver of better research practices. The equity argument — ensuring validation accessibility isn't determined by institutional resources or cognitive style — aligns with current UK research funding priorities around inclusion and accessibility.

---

## Relationship to ValiChord Core

*ValiChord at Home* is architecturally independent from ValiChord's distributed validation infrastructure. It shares standards and rubric definitions but no code, no infrastructure, and no dependencies. It is not on the critical path for ValiChord's core development.

The two products are parallel development tracks:

- **ValiChord Core:** Distributed validation recording, Harmony Records, Holochain infrastructure — the main engineering effort
- **ValiChord Researcher Support:** Self-assessment tools, feedback pipeline, community building, ecosystem data — a lightweight companion product track

They converge at the rubric: *ValiChord at Home* uses the same standards as ValiChord's triage, so researchers who pass the tool's checks are likely to pass formal triage. But passing the tool confers no status, and ValiChord always runs its own assessment.

**An important distinction:** Because *ValiChord at Home* will exist before ValiChord's core infrastructure does, there is a risk that external audiences mistake the companion tool for the main product. To be clear: *ValiChord at Home* is a companion tool. ValiChord is a distributed validation infrastructure. The tool helps researchers prepare. The infrastructure validates their science. They are not the same thing. Similarly, journals or funders should not treat *ValiChord at Home* readiness as a gatekeeping metric or de facto submission requirement — that would reproduce exactly the kind of metric capture that ValiChord's governance framework is designed to resist.

---

## Timeline

| Stage | When | Depends on | What it delivers |
|---|---|---|---|
| Stage A | Alongside Phase 0 results | Known best practices (FAIR, code quality standards) | Best-practice checklist, community building, ecosystem data |
| Stage B | Phase 2 | Phase 0 evidence + Phase 1 operational data | Calibrated scoring, difficulty prediction, targeted recommendations |

---

**Companion Documents:**
- *ValiChord Vision & Architecture* — What ValiChord is and why it matters
- *ValiChord Technical Reference* — Architecture sketches for engineering discussion
- *ValiChord Phase 0 Proposal* — Workload Discovery Pilot (£69K, 6 months)
- *ValiChord Governance Framework* — How the system resists corruption, capture, and domestication

**Contact:** Ceri John — topeuph@gmail.com

**© 2026 Ceri John. All Rights Reserved.**
