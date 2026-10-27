# Archived documents

Documents kept for the record but no longer current. Each carries a dated note at the top saying
what superseded it. Do not treat them as a description of how ValiChord works today: the code
in `valichord/` is the source of truth.

| Document | What it was | Archived |
|---|---|---|
| [19 — Test Scenarios](19_ValiChord_Test_Scenarios.md) | Tryorama (TypeScript) scenario specifications, Feb 2026. Tryorama was retired 2026-08-03; integration tests are sweettest (see [doc 14](../14_ValiChord_Integration_Tests.md)). | 2026-10-19 |
| [20 — Holochain Scaffolding Plan](20_Holochain_Scaffolding_Plan.md) | The pre-build engineering plan, March 2026. Superseded by the code itself. | 2026-10-19 |
| [`backend/`](backend/README.md) | The protocol REST API (`app_protocol.py`, `POST /attest`) and its OpenAPI spec. It could not start: it imports `holochain_bridge`, which left with valichord_at_home on 2026-04-22. Kept for the API design; it is code, but nothing runs it. | 2026-10-27 |
