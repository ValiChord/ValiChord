<div align="center">
  <img src="https://github.com/topeuph-ai/ValiChord/blob/main/Images/Valichord%20logo-standard%20v2-1.5x.jpeg" width="550px" alt="ValiChord Logo">
</div>

# ValiChord at Home


## Your Private Research Companion for Pre-Submission Readiness

**ValiChord at Home** is a standalone, self-service tool designed to help researchers assess and improve their computational materials privately before engaging with formal validation. It serves as the "friendly, accessible face" of the ValiChord ecosystem, acting as a mentor rather than a gatekeeper.

<div align="center">
<img src="https://github.com/topeuph-ai/ValiChord/blob/main/Images/Valichord%20at%20Home.png" alt="ValiChord at Home Architecture Overview" width="800">
</div>

### 🔬 Bridging the "Cognitive Gap"

Not every researcher who produces groundbreaking science thinks in tidy file structures. Some of the most significant breakthroughs come from "conceptual thinkers"—brilliant minds who may not be naturally systematic organizers. **ValiChord at Home** bridges this gap by taking brilliant ideas expressed in messy repositories and showing the researcher exactly how to make them reproducible.

### 🛠️ How It Works: Level 1 Support

The tool provides **Level 1: Pre-Submission Self-Assessment** through a local, private workflow:

* **Static Analysis Scan:** The tool scans local repositories for "reproducibility failure modes," such as hardcoded absolute paths, missing documentation, or unpinned dependencies.


* **AI-Assisted Auto-Generation:** It can proactively draft missing components—including `README_DRAFT.md`, `LICENCE_DRAFT.txt`, and dependency requirements—based on the detected code and data structure.


* **Actionable Triage:** It identifies exactly what a validator would need to find and provides specific guidance on how to fix each gap before submission.


* **Environment Fingerprinting:** The tool automatically captures a standardised snapshot of the researcher's computational environment — OS family, CPU architecture, GPU presence, and RAM class — alongside the software environment inferred from the deposit's dependency files (requirements.txt, environment.yml, sessionInfo() output, Dockerfile, or similar). This fingerprint is stored locally and only transmitted to the ValiChord network at submission time, with the researcher's explicit consent. It is used by the validator selection algorithm to prioritise validators whose setup is closest to the researcher's, reducing setup-attributable divergence before validation begins. Researchers who submit without ValiChord at Home can provide the hardware portion (OS, CPU architecture, GPU) via a short form at submission; the software portion is inferred automatically from a well-prepared deposit.



### 🛡️ The "Anti-Authority" Philosophy

ValiChord at Home operates on a strict **Anti-Authority** principle:

* **Researcher in Control:** The tool only suggests; the researcher is responsible for all final decisions.


* **Truth Over Compliance:** If a generated correction contradicts the researcher's knowledge, the tool is considered wrong—the researcher's expertise always takes precedence.


* **Manual Verification:** All generated files include a `_DRAFT` suffix, requiring the researcher to verify and approve changes before use.



### 🔐 Privacy-First & Agent-Centric

Consistent with the broader ValiChord architecture, the "at Home" tool is designed for **absolute data sovereignty**:

* **On-Device Execution:** The tool runs locally on the researcher's machine; it never executes research code or transmits data without explicit consent.


* **Zero-Knowledge Analysis:** It provides high-level mentorship and "semantic healing" while keeping the researcher's messy first attempts entirely private.



### 📅 Development Roadmap

* **Stage A (Early Preview):** A lightweight best-practice checklist to build community engagement and generate ecosystem data. Stage A also captures environment fingerprints from the outset, even before the validator matching algorithm is automated. The Phase 0 data on environment diversity across researchers and validators is itself valuable metascience — it reveals how heterogeneous the computational landscape is across fields, and grounds the matching thresholds that Phase 1 will need to design.


* **Stage B (Calibrated Tool):** An advanced version using empirical data from Phase 0 to predict validation difficulty and estimate time ranges. Stage B activates automated environment matching: the fingerprint captured at submission is compared against the registered validator pool, and the selection algorithm prioritises validators by setup similarity before applying the discipline and independence filters.



---

For more information on the full validation pipeline, see the [ValiChord Vision & Architecture](https://github.com/topeuph-ai/ValiChord/blob/main/docs/Vision%20%26%20Architecture.md) and the [Researcher Support Document](https://github.com/topeuph-ai/ValiChord/blob/main/ValiChord_Researcher_Support.md)
