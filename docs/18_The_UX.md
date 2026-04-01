# ValiChord — User Experience Design

**Version:** 1.0 — March 2026
**Author:** Ceri John

---

## Overview

ValiChord is used by five distinct types of person. Each has a fundamentally different relationship with the system, a different level of technical knowledge, and a different emotional stake in the outcome. The UX for each must be designed around their specific context — not as variations of a single interface, but as genuinely separate experiences that happen to share an underlying protocol.

The five personas are:

1. **The Researcher** — submits their work for validation
2. **The Validator** — performs the validation
3. **The Public Reader** — journals, funders, colleagues, members of the public who want to know if a study is reproducible
4. **The Credential Issuer** — the ValiChord governance body or institutional representative who authorises validators
5. **The Governance Recorder** — the designated person who writes governance decisions into the permanent record

---

## 1. The Researcher

### Who they are

A computational scientist — postdoctoral researcher, principal investigator, or PhD student — who has completed a study and wants it formally validated. They are comfortable with computers and scientific software but are not necessarily Holochain developers. They are probably anxious about the outcome. Their work is their career. Validation is an act of professional courage.

They work at a university desk or from home. They use a laptop. They are likely to be accessing ValiChord between other tasks — writing grants, supervising students, reviewing papers.

### What they want

To submit their work, know it has been received, and eventually see the result. Nothing else. They do not want to manage the validation process. They do not want to know which validators are working on their study or what progress looks like. They want to be told when it is done.

### Their journey

**Screen 1 — Dashboard: My Submissions**

A clean, sparse list. Each row is a study they have submitted. The status column has one of three states:

- `Awaiting validators` — grey dot — their deposit is in the queue
- `Under review` — amber dot — validators are working on it; no further detail
- `Complete` — green dot — a result exists

Nothing else is shown during the review process. The researcher cannot see how many validators have claimed, whether any have committed, or what phase the protocol is in. This is intentional: partial information during the review is more anxiety-inducing than no information, and seeing validator identities or progress details would undermine the blind.

**Screen 2 — Submit**

A two-step form.

Step 1: Provide access. Two fields:
- `Dataset URL` — where validators can download the study deposit (OSF, Zenodo, institutional repository, Figshare)
- `Pre-registration URL` — the analysis plan (OSF, AsPredicted, ClinicalTrials — optional)

Step 2: Confirm details. Read-only summary showing:
- The SHA-256 hash of their deposit (computed locally before submission — the actual data never leaves their machine)
- Discipline
- Validation tier (Basic / Enhanced / Comprehensive)
- Number of validators required
- Their institution (used only for conflict-of-interest checking — never shown to validators)

A single `Submit for validation` button. Once submitted, they return to the dashboard.

**Screen 3 — Result**

Shown when a Harmony Record exists on the public DHT. This is the only substantive information the researcher receives about the validation process.

The result screen shows:
- The overall outcome: `Reproduced` / `Partially Reproduced` / `Failed to Reproduce` / `Unable to Assess`
- The agreement level: `Exact Match` / `Within Tolerance` / `Directional Match` / `Divergent` / `Unable to Assess`
- The number of validators who participated (e.g. "5 validators")
- Total validation time invested (e.g. "combined 87 hours across all validators")
- Any Reproducibility Badge issued: Gold / Silver / Bronze / Failed
- A permanent link to the public Harmony Record (for inclusion in papers, grant applications, and journal submissions)
- Any deviation flags raised (structured — not free-text accusations — e.g. "2 validators noted an undeclared model substitution")

The tone is factual and non-judgemental. A `Failed to Reproduce` result is presented as scientific information, not a verdict. The visual language should reflect this: no red warning icons, no congratulatory fanfare. The same calm visual design for all outcomes.

### Visual scene description (for image generation)

*A researcher in their early thirties sits at a cluttered university desk, natural light from a window to their left. They are looking at a laptop screen showing a clean, minimal web application with a white background and soft blue accents. The screen displays a list of three submitted studies. One row has a green dot labelled "Complete" and the researcher is hovering their cursor over it, about to click. Books and printed papers are stacked around the desk. A coffee mug sits beside the laptop. The expression on the researcher's face is cautiously hopeful.*

---

## 2. The Validator

### Who they are

A credentialed researcher in the relevant scientific discipline — someone with genuine expertise in the methods used by the study. They hold an institutional affiliation that has been verified by ValiChord's governance body. They may be a full-time academic, a research scientist in industry, or an independent researcher. They are comfortable running computational code, interpreting statistical output, and writing structured scientific assessments.

Validation is skilled work. Validators are compensated for their time. They choose which studies to take on — ValiChord is not an assignment system, it is a job board.

They use a laptop or desktop with a full development environment available. They may work in an office, at home, or in a shared research space. A validation task may take hours to days of focused work.

### What they want

To find studies that match their expertise, do rigorous work, record their findings honestly, and be paid fairly. They want to know the outcome of the round when it is done — but their job ends the moment they submit their sealed assessment. Everything after that is automatic.

### Their journey

**Screen 0 — Onboarding**

First time only. Three steps:

1. `Your profile` — discipline(s), institution, ORCID, certification tier. This is published to the shared DHT so researchers' studies can be matched appropriately and conflict-of-interest can be checked.
2. `Your credential` — the validator uploads their institutional membrane proof (provided by ValiChord's credential issuer). This is the cryptographic key that allows them to join the Attestation network.
3. `Confirmation` — profile published, credential verified, ready to browse.

**Screen 1 — Study Queue**

A job board. A list of validation requests in the validator's discipline(s), filtered to studies they are eligible for (no conflict of interest, slots available). Each row shows:

- Study identifier (the SHA-256 hash — opaque, not the researcher's name or institution)
- Discipline
- Validation tier
- Estimated difficulty (Standard / Moderate / Complex / Extreme) and estimated time range
- Number of validators still needed (e.g. "2 of 5 slots filled")
- A `Claim this study` button

Studies the validator is ineligible for (conflict of interest, already claimed, slots full) are either hidden or shown greyed-out with a reason.

**Screen 2 — Active Workspace**

Once a study is claimed, it opens a workspace. This is the primary working environment — potentially occupied for hours or days.

The workspace has three sections:

*Access panel (left):*
- Direct download link for the dataset
- Link to the pre-registered analysis plan
- Difficulty assessment (code volume, dependency count, documentation quality, data accessibility, environment complexity, study age)
- ValiChord analysis report — the automated pre-screening output from ValiChord at Home, showing known reproducibility issues in the deposit

*Notes panel (centre):*
- A private scratchpad. Text written here stays on the validator's own device (DNA 2 — Validator Workspace). It never leaves. This is where they record what they tried, what broke, what succeeded.
- A structured time log: four categories — Environment setup / Data acquisition / Code execution / Troubleshooting — with running timers the validator can start and stop.

*Assessment panel (right):*
- Outcome selector: `Reproduced` / `Partially Reproduced` / `Failed to Reproduce` / `Unable to Assess`
- Per-metric results table: metric name, expected value, produced value, within tolerance yes/no
- Deviation flags: structured entries for any deviation from the pre-registered protocol that the researcher did not declare
- Computational resources: checkboxes for personal hardware / HPC / GPU / cloud compute required
- Confidence: High / Medium / Low

When the validator is satisfied with their assessment, a single `Seal my assessment` button locks it in. This triggers the commit — their private assessment is written immutably to their local Workspace DNA, and a public commitment anchor appears on the shared Attestation network. The assessment content stays private.

**Screen 3 — Committed / Waiting**

A calm holding screen. It says: *"Your assessment is sealed. When the other validators on this round have also sealed their assessments, your result will be published automatically. You do not need to do anything."*

A progress indicator shows how many validators have sealed (e.g. "3 of 5 sealed") — informational only, not a gate. The validator can close the app entirely. When the reveal window opens and all validators have committed, the app publishes their assessment automatically in the background.

A notification appears when complete: *"Your assessment for study [hash] has been published."*

**Screen 4 — Result**

The same Harmony Record view as the researcher sees, with one addition: a personal summary showing how the validator's own outcome compared to the consensus. Not to expose others' identities — just to show whether they agreed with the majority. This feeds into their reputation record over time.

They can also see their compensation confirmation here.

### Visual scene description (for image generation)

*A scientist in their mid-forties sits at a standing desk in a home office. They are wearing glasses and looking intently at a large monitor. The screen shows a split-panel web application: on the left, a technical assessment form with dropdown menus and a structured results table; in the centre, a notes panel with text about dependency installation errors; on the right, a progress timer showing "Code execution: 2h 14m". A terminal window is open in the background showing Python output. The validator has a notepad with handwritten observations next to their keyboard. Their expression is focused and engaged — this is professional work.*

---

## 3. The Public Reader

### Who they are

Anyone who wants to know whether a specific computational study has been independently validated. This includes:

- **Journal editors** checking whether a submitted paper carries a ValiChord badge before acceptance
- **Funders** (UKRI, Wellcome, NIH) verifying validation status before releasing stage-gate funding
- **Fellow researchers** in the field checking whether they should build on a study's findings
- **Science journalists** reporting on a finding's reliability
- **Members of the public** who have heard about a study in the news

They range from computationally sophisticated (a peer reviewer with domain expertise) to entirely non-technical (a journalist). The interface must be readable by all of them. No Holochain node required — this is a public HTTP Gateway.

### What they want

A clear, trustworthy answer to a single question: *"Was this study independently reproduced?"*

### Their journey

**Screen 1 — Search**

A single search box. Accepts:
- The study's DOI
- The dataset's SHA-256 hash (for technical users)
- The study title (fuzzy search — best-effort, not guaranteed)

A browse mode is also available: filter by discipline, outcome, badge type, date range.

**Screen 2 — Harmony Record**

The result page for a specific study. Structured in three sections:

*Summary (top):*
- Large, clear outcome badge: `Reproduced` / `Partially Reproduced` / `Failed to Reproduce` / `Unable to Assess`
- Reproducibility badge if issued: Gold / Silver / Bronze with explanatory text ("5 independent validators, exact match")
- One-sentence plain-English summary

*Evidence (middle):*
- Agreement level with explanation
- Number of validators and total time invested
- Breakdown: how many validators reached each outcome
- Any deviation flags raised (structured, not attributable to individual validators)
- Validation date

*Provenance (bottom):*
- Link to the original dataset (the URL the validators used)
- Link to the pre-registered analysis plan
- The Harmony Record's DHT address — a permanent, tamper-evident identifier
- Explanation of what ValiChord is and how the protocol works (expandable)

No validator identities are shown. No individual assessments are shown. The Harmony Record is the aggregate — this is by design.

### Visual scene description (for image generation)

*A journal editor in her fifties sits at a glass-topped office desk. She has a printed manuscript in front of her and is looking at a second screen showing a clean public-facing website. The screen shows a study result page with a prominent silver badge labelled "Reproduced — Within Tolerance" and a clear summary: "5 independent validators — 4 confirmed reproduction, 1 partial". Below are structured details about validation methodology. The design is clean and academic — white background, navy blue headings, subtle grey data tables. The editor is making a note on a yellow sticky note next to the manuscript.*

---

## 4. The Credential Issuer

### Who they are

A designated representative of ValiChord's governance body — or, in an institutional deployment, a university research office administrator. They are responsible for issuing the cryptographic membrane proofs that allow validators to join the Attestation network. They hold the authorised signing key.

They are not necessarily technical but will have been trained in the credential issuance process. They handle a small volume of requests — issuing credentials is not a high-frequency activity.

### What they want

To issue a credential to a verified validator quickly, accurately, and with a clear audit trail.

### Their journey

**Screen 1 — Pending requests**

A list of validators who have applied for credentials. Each row shows:
- Validator name and institution
- Discipline(s)
- Supporting documentation status (e.g. "CV uploaded, institutional email verified")
- Requested date

**Screen 2 — Issue credential**

For an approved validator:
- Their AgentPubKey is shown (the Holochain identity they will use)
- A single `Issue credential` button
- The system signs their key with the authorised issuer keypair and generates a 64-byte membrane proof
- The proof is displayed as a downloadable file and a copyable string
- A confirmation entry is written to the audit log

The issuer sends the proof to the validator out of band (email, secure message). The validator uploads it during onboarding.

**Screen 3 — Audit log**

A complete record of all credentials issued: who, when, which key, which signing ceremony.

### Visual scene description (for image generation)

*A university administrator in his sixties sits at a formal office desk with institutional certificates on the wall behind him. He is looking at a tablet showing a minimal administrative interface — a list of three pending validator applications with green tick and red cross buttons. The screen is clean and form-based, resembling a secure administrative portal. He has a printed verification checklist next to the tablet. The room is quiet and official — this is a trusted role.*

---

## 5. The Governance Recorder

### Who they are

The designated person (or small committee) responsible for recording ValiChord's governance decisions on the permanent public DHT. When ValiChord's governance body votes on a policy question — a change to validation tiers, a new discipline, a protocol update — the outcome is recorded immutably by this person using their designated key.

They are likely a senior member of the ValiChord team or an elected governance representative. They use this interface rarely — only when a formal vote has concluded.

### What they want

To accurately record a governance decision with its vote counts, knowing the entry is permanent and public.

### Their journey

**Screen 1 — Decision log**

A chronological list of all governance decisions ever recorded. Each entry shows:
- Proposal text
- Decision text
- Votes for / votes against
- Date (from the Holochain Action timestamp — not self-reported)
- DHT address (permanent link)

**Screen 2 — Record a decision**

Four fields:
- `Proposal` — the text of the governance question that was put to a vote
- `Decision` — the outcome as ratified
- `Votes for`
- `Votes against`

A `Record decision` button. The entry is written to the public DHT and cannot be altered or deleted by anyone, including the recorder.

### Visual scene description (for image generation)

*A woman in her fifties sits at a conference table after a meeting. The room is emptying — colleagues are gathering papers in the background. She is focused on a laptop showing a minimal form interface with four text fields and a single "Record decision" button. The screen confirms a previous entry: "Motion carried: 7 for, 2 against". The interface is austere and deliberate — it feels like signing a legal document. She is reading through the text carefully before pressing the button.*

---

## Interface design principles across all five UXs

**1. Each persona sees only what they need.**
The researcher sees no validation progress. The public reader sees no individual validator assessments. The validator sees no researcher identity. Data minimalism is both a privacy principle and a UX principle.

**2. The protocol is invisible.**
Commit, reveal, PhaseMarker, CommitmentAnchor, DHT, WASM — none of this language appears in any user-facing interface. The system does its work behind clean, plain-English screens.

**3. Automatic over manual wherever possible.**
The validator's reveal is automatic. The HarmonyRecord triggers automatically when the last attestation is submitted. The researcher does not need to chase anything.

**4. Permanent means permanent.**
The result screen for every persona — researcher, public reader, governance recorder — makes clear that what is written cannot be changed. This is not a bureaucratic warning but a feature: the tamper-evidence is the value.

**5. Failure is information, not shame.**
A `Failed to Reproduce` result is presented in the same visual language as `Reproduced`. No red warning states, no apologetic copy, no emphasis on the negative. Scientific disagreement is the system working, not the system failing.

---

## Technical note for implementation

Each of these interfaces connects to a different DNA via the local Holochain WebSocket:

| Persona | Primary DNA connection |
|---|---|
| Researcher | DNA 1 (Researcher Repository) + DNA 3 (submit only) |
| Validator | DNA 2 (Validator Workspace) + DNA 3 (Attestation) |
| Public Reader | DNA 4 (Governance) via HTTP Gateway — no Holochain node required |
| Credential Issuer | External signing tool — no DNA connection needed |
| Governance Recorder | DNA 4 (Governance) — requires `system_coordinator_key` |

The Researcher and Validator UXs are local applications distributed with the Holochain runtime (Kangaroo or p2p Shipyard). The Public Reader interface is a conventional web application hitting the HTTP Gateway. The Credential Issuer tool is a standalone signing utility. The Governance Recorder interface is a restricted web form requiring the system coordinator key.
