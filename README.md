<div align="center">

<img src="Valichord logo-standard v2-1.5x.jpeg" width="450px" alt="ValiChord Logo">

**An Immune System for Science: Distributed Integrity Infrastructure for Computational Research**

[![Status](https://img.shields.io/badge/Status-Phase_0_Pilot-blue?style=for-the-badge)](https://topeuph-ai.github.io/ValiChord)
[![Language](https://img.shields.io/badge/Language-Rust-orange?style=for-the-badge)](https://github.com/topeuph-ai/ValiChord/blob/main/docs/4_ValiChord_RUST_Scaffold.rs)
[![Grant](https://img.shields.io/badge/Grant-UKRI_Metascience_2-purple?style=for-the-badge)](https://github.com/topeuph-ai/ValiChord/blob/main/docs/5_ValiChord_Phase_0_proposal_ukri_etc.md)

---

## 📖 [**Primary Entry Point: Vision & Architecture**](https://github.com/topeuph-ai/ValiChord/blob/main/docs/1_ValiChord_Vision&Architecture.md)
*The core vision: Why ValiChord matters and how it solves the $200B verification gap.*

---

[ **[Project Website](https://topeuph-ai.github.io/ValiChord)** ] &nbsp;•&nbsp; [ **[Governance Framework](https://github.com/topeuph-ai/ValiChord/blob/main/docs/2_ValiChord_Governance_Framework.md)** ] &nbsp;•&nbsp; [ **[4-DNA Architecture](https://github.com/topeuph-ai/ValiChord/blob/main/docs/8_ValiChord_4-DNA_Membrane_architecture.md)** ] &nbsp;•&nbsp; [ **[ValiChord at Home](https://github.com/topeuph-ai/ValiChord/blob/main/docs/9_Valichord_at_Home.md)** ]

</div>

## 🧬 The Mission
Computational methods now underpin virtually every scientific discipline, yet **70% of researchers** have failed to reproduce another scientist's experiments. This "Verification Gap" results in an estimated **$200 billion in wasted R&D annually**.

**ValiChord** is a distributed, agent-centric infrastructure designed to automate scientific reproducibility. It provides a tamper-evident audit trail—replacing binary "Pass/Fail" verdicts with **Harmony Records** that preserve the full texture of scientific disagreement.

---

## 🏗️ 4-DNA Membrane Architecture
 ValiChord is built as four distinct peer-to-peer networks (DNAs) to ensure absolute data sovereignty and GDPR compliance by design.

| DNA | Purpose | Access Control |
| :--- | :--- | :--- |
| **Researcher Repository** | Private storage of raw code, data, and methods. | **Private** (Researcher/Institution) |
| **Validator Workspace** | The "Witnessing hApp" where reproduction work occurs. | **Private** (Individual Validator) |
| **Attestation** | Shared DHT for validation requests and cryptographic outcomes. | **Credentialed** (Membrane Proof) |
| **Governance & Harmony** | Public results, badges, and reputation scores. | **Open Read** (Public/API) |

---


## 🛠️ Researcher Ecosystem: "ValiChord at Home"
We provide a full feedback pipeline to move research from "messy" to "validatable".

### 🏠 **ValiChord at Home (Self-Service)**
**Private, local pre-vetting for researchers.**
Before submitting for formal validation, researchers use this tool to scan their repositories privately.
* **Static Analysis:** Identifies documentation gaps and environment friction without code execution.
* **Difficulty Prediction:** Uses a weighted rubric to estimate validation labor based on Phase 0 empirical data.
👉 **[Launch ValiChord at Home](https://topeuph-ai.github.io/ValiChord/at-home.html)**

### 🔍 **Assisted Correction**
**Automated reproducibility hygiene.**
ValiChord generates proposed corrections—such as drafted READMEs and pinned dependencies—for researcher review and approval, ensuring studies pass triage without manual toil.

---


## 🛠️ Technical Specifications
The ValiChord engine is specified in `Rust` to ensure memory safety and zero-cost abstractions for high-stakes validation.

* 🛠️ **[Architecture Scaffold v10 (Rust)](https://github.com/topeuph-ai/ValiChord/blob/main/docs/4_ValiChord_RUST_Scaffold.rs)** — *Type-level spec for the 4-DNA model.*
* 📚 **[Technical Reference v12](https://github.com/topeuph-ai/ValiChord/blob/main/docs/3_ValiChord_Technical_Reference.md)** — *Full architectural narrative and engineering sketches.*

### **The Commit-Reveal Protocol**
To prevent "last-mover advantage," ValiChord utilizes Holochain's native countersigning sessions. Validators seal findings as private source chain entries (**Commit**) before a simultaneous, atomic reveal session (**Reveal**).

---

## 📊 Roadmap: The Path to Scale

| Phase | Focus | Status |
| :--- | :--- | :--- |
| **Phase 0** | **Workload Discovery:** Empirical study to quantify the "Price of Truth" (£150k FEC). | **[Proposed: UKRI Metascience 2]** |
| **Phase 1** | **Core Infrastructure:** Building the functional Rust/Holochain 4-DNA MVP. | **[Architecture Validated]** |
| **Phase 2** | **Integration:** Journal and funder API deployments via HTTP Gateway. | **[In Planning]** |

---

> ### *“Every initiative assumes verification is feasible at a reasonable cost. That assumption has never been tested. ValiChord is the test.”*

---
**Author:** Ceri John &nbsp;•&nbsp; **Technical Validation:** Arthur Brock (Holochain), Joel Marcey (Rust Foundation), Paul D'Aoust (Holochain Foundation)  
**Contact:** [topeuph@gmail.com](mailto:topeuph@gmail.com)
