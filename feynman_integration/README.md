# ValiChord × Feynman — Integration Notes

**Status:** Phase 1 complete. PR #15 in progress (Feynman as genuine validator).
**Authors:** Ceri John (ValiChord), in dialogue with Advait Paliwal (Feynman)
**Last updated:** March 2026

---

## What is done

| Item | Status | Detail |
|---|---|---|
| ValiChord REST API | **Live** | `POST /validate`, `GET /result/<job_id>`, `GET /health` |
| `validator_outcome` + `validator_notes` on `POST /validate` | **Live** | Feynman can now submit its real replication verdict |
| `validator_attested` flag in responses | **Live** | Distinguishes real attestations from proxy outcomes |
| Holochain bridge | **Live** | HarmonyRecords written to DHT when conductor is running |
| `harmony_record_draft` in responses | **Live** | Outcome, data hash, findings summary, hash + URL when available |
| Feynman skill — PR #13 | **Merged** | Cherry-picked into Feynman 0.2.15 by @advaitpaliwal |
| Feynman prompt update — PR #14 | **Open** | Migrates prompt to single-shot API, documents `harmony_record_draft` |
| Feynman `/replicate`-first prompt — PR #15 | **Open** | Makes Feynman a genuine validator; see `valichord_prompt_v2.md` |
| Demo endpoint (Codespace) | **Live** | `https://improved-space-couscous-5gjwpp546jrg27p5q-5000.app.github.dev` |

## What is not done yet

| Item | Priority | Notes |
|---|---|---|
| Always-on deployment | High | Codespace sleeps; Render free tier can't handle the conductor |
| HTTP Gateway for HarmonyRecord URLs | High | `harmony_record_url` is always null until a gateway is deployed |
| API authentication | Medium | API is currently open — no rate limiting or keys |
| Webhook / push notifications | Low | Feynman polls; a webhook would be cleaner for long jobs |
| Feynman as a persistent AI validator | Long-term | Feynman joining the ValiChord Holochain network directly |
| Multi-agent round support | Long-term | Currently dev bypass uses `minimum_validators=1` |

Read `INTEGRATION_VISION.md` for the full picture and open decisions.

---

## The one-line description

Feynman runs `/replicate` on a research deposit, forms its own verdict, submits
it to `POST /validate` with `validator_outcome`, and gets back a cryptographic
Harmony Record — a permanent record of what actually happened when the code was
run. ValiChord provides the integrity layer; Feynman provides the AI replication.
