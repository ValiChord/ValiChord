# Notes for next email to Tiberius

## Things to mention

### The bg_device repo
- Found the Breathing Games hardware repo: https://gitlab.com/breathinggames/bg_device
- 13 device iterations, Arduino/ESP32, 3D-printed enclosures, Bluetooth
- Clinically validated at CHU Sainte-Justine with 158 children — published in JMIR Serious Games (2021)
- This is the most concrete NDO I've seen — hardware + firmware + docs + institutional partners + validation study, all in one place
- ValiChord at Home could be run against it (hardware reproducibility = same logic as research reproducibility)
- Offer to do this and share the output, same non-judgmental framing as the CSV

### Hardware reproducibility — new use case now documented
- Added as section 10 in docs/12_Other_potential_use_cases.md
- The key framing: validation splits into two claims — buildability (can a third party assemble it?) and performance (does it meet spec?)
- The concrete sentence for the email: "three validators in three countries building the same PEP Master device and recording the result in a Harmony Record"
- Also flags that bg_device scores well on most hardware reproducibility criteria but has no root licence file and unpinned Arduino library versions — real findings, gently stated
- CERN-OHL-S 2.0 is the right hardware licence (bg_device already uses it) — relevant to the licence conversation

### The CSV — now fully understood
- The clinical connection (Sainte-Justine, 158 children) explains why the [HS] detector fired
- Tiberius's explanation was correct — contributor ledger, not patient data
- The tool did exactly what it should: flagged, deferred to the human

### License conversation — useful data point
- PEP Master / bg_device uses THREE licences simultaneously, not OVN:
  - AGPL-3.0 for source code
  - CC-BY-SA 4.0 for documents
  - CERN-OHL-S 2.0 for hardware designs
- This is relevant to the OVN vs AGPL question — their own flagship project uses AGPL
- Worth asking Tiberius why OVN rather than the stack they already use

### The nondominium_integration folder
- Created in the ValiChord repo after reading both codebases properly
- README.md: concrete 6-step integration path using actual function names from their code
- NONDOMINIUM_ARCHITECTURE.md: shows we read their code in detail
- Key hook: there's a commented-out cross-zome call in zome_resource → zome_gouvernance
  that ValiChord's commit-reveal is shaped to fill — worth mentioning to Sacha specifically

### Scheduling
- Tiberius suggested a conversation on AI-assisted development methodology
- Worth suggesting a three-way call: Ceri + Tiberius + Sacha
- Sacha is the programmer — the integration folder is aimed at him

## Things NOT to mention yet
- Licensing changes (stay Apache 2.0 for now, don't commit to OVN)
- Timelines or roadmaps
- Formal partnership terms
