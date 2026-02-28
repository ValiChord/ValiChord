ValiChord: Distributed Integrity Infrastructure for Computational Science

Independent, tamper-evident verification to solve the $200B/year reproducibility crisis.
🌐 The ValiChord Ecosystem

    Official Project Site: https://topeuph-ai.github.io/ValiChord

    The ValiChord at Home Pilot: https://topeuph-ai.github.io/ValiChord/demo.html

🛠 Repository Readiness Check (Live Demo)

The embryo of "ValiChord at Home."
Before a study can be validated, it must be "validation-ready." We have developed a browser-native diagnostic tool that allows researchers to upload their research repositories and receive an instant, actionable report on how to improve their computational reproducibility.

    Self-Diagnostic: Check your code against FAIR and Turing Way standards.

    Privacy-First: Works entirely in your browser. Your code and data are never uploaded to a server.

    Actionable: Identifies documentation gaps, dependency conflicts, and environment friction before you submit for peer review.
    👉 Try the Repository Readiness Check

What is ValiChord?

ValiChord is an 8-layer distributed framework that coordinates multiple independent validators to reproduce published analyses. Instead of a binary "Pass/Fail," it produces Harmony Records—comprehensive reports that preserve the full texture of agreement and disagreement, revealing the specific boundary conditions where a methodology might be fragile.
🏗 The 8-Layer Architecture

Built on Holochain, an agent-centric distributed computing framework, ValiChord ensures that data privacy (GDPR) and institutional IP are protected while providing absolute cryptographic proof of results.
Layer	Component	Purpose
0	Data Foundation	Content-addressed, tamper-evident snapshots of code and data.
1	Analysis Intake	Time-locked analysis plans and pre-commitment protocols.
2	Validation Engine	Distributed coordination using a blinded Commit-Reveal protocol.
3	Governance	"Brutality Commitments" to resist institutional capture.
4	Audit Trail	Tamper-evident event logs and provenance graphs for every event.
5	Certification	Issuance of Harmony Records and reproducibility credentials.
6	Reputation	Multi-dimensional scoring for validators based on rigor, not status.
7	Integration	APIs for seamless inclusion in journal and funder workflows.
📅 Roadmap & Current Status

Currently seeking a Principal Investigator and Institutional Home for the UKRI Metascience Round 2 application.

    Phase 0 (2026): Validation Workload Discovery

        Goal: Empirically measure the time and expertise required to validate 75+ computational studies.

        Status: Proposed for UKRI Metascience Round 2 (£150K).

    Phase 1: Core Infrastructure Build

        Goal: Implementation of the 8-layer Rust scaffold into a functional MVP.

📂 Repository Contents

    /scaffold: The full 1,488-line Rust Type Specification defining the architecture.

    /docs: Technical references, governance frameworks, and project vision.

    ValiChord_Vision.md: The 50,000-word core documentation set.

Contact & Collaboration

Author: Ceri John (Independent Researcher, Originator)

Technical Validation: Holochain Foundation (Jan 2026)

Email: topeuph@gmail.com

"Every initiative assumes verification is feasible at a reasonable cost. That assumption has never been tested. ValiChord is the test."
