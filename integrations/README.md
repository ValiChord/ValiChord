# ValiChord — Integrations

ValiChord exposes a REST API that any AI agent, tool, or service can call to participate in the commit-reveal protocol.

---

## Integration API

Two endpoints, two roles:

| Endpoint | Role | What it does |
|---|---|---|
| `POST /attest` | **Validator** | Submit a replication verdict; runs commit-reveal; returns HarmonyRecord synchronously (~60 s) |
| `POST /validate` | **Researcher** (via valichord_at_home) | Deposit quality check — 100+ structural detectors. Async; poll `GET /result/<job_id>`. Lives in [valichord_at_home](https://github.com/topeuph-ai/valichord_at_home). |

The protocol API (`app_protocol.py`) runs on port 5001. It does not run the structural analysis pipeline. Any tool that can make an HTTP request can act as a ValiChord validator.

---

## Active integrations

| Integration | Status | Doc |
|---|---|---|
| [PI](https://github.com/badlogic/pi-mono) — AI coding agent | PR pending upstream | [PI_INTEGRATION.md](PI_INTEGRATION.md) |

---

## Quick start — acting as a validator

```bash
# 1. Compute the SHA-256 of the deposit locally (no upload needed)
DATA_HASH=$(sha256sum deposit.zip | cut -d' ' -f1)

# 2. Run the research code and form a verdict, then attest
curl -X POST http://localhost:5001/attest \
  -F "data_hash=$DATA_HASH" \
  -F "outcome=Reproduced" \
  -F "notes=Code ran without errors. Outputs matched to 4 decimal places." \
  -F "confidence=High"
```

Returns synchronously:
```json
{
  "data_hash": "<64-char hex>",
  "outcome": "Reproduced",
  "validator_attested": true,
  "harmony_record_hash": "<uhCkk... or null>",
  "harmony_record_url": "<gateway URL or null>"
}
```

`harmony_record_hash` is null only when the Holochain conductor is offline — the response always succeeds.

---

## Guides

- [What ValiChord Does](WHAT_VALICHORD_DOES.md) — plain-English state of the protocol for integrators
- [AI Validator Guide](AI_VALIDATOR_GUIDE.md) — workflow and prompt template for AI agents acting as validators
- [PI Integration](PI_INTEGRATION.md) — full details of the PI coding agent integration
