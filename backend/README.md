# ValiChord backend

This directory contains **two separate Flask applications** for two separate tools
that happen to share infrastructure. They are intentionally kept separate because
they answer different questions and are used by different audiences.

---

## app_protocol.py — ValiChord Protocol API

**Question it answers:** *Did an independent party get the same result as the researcher?*

This is the core of ValiChord. It runs the Holochain blind commit-reveal protocol
and returns a **HarmonyRecord** — a cryptographically tamper-evident proof of the
reproducibility verdict.

**Who uses it:** AI validators (PI, Feynman) and human validators.

**Endpoints:** `/attest`, `/health`, `/openapi.yaml`, `/docs`

**Key design decision:** validators pass `data_hash` (SHA-256 of the deposit, computed
locally) — no upload needed. The Holochain protocol only needs the hash.

```bash
# Run in Codespace (requires demo/serve.mjs + Holochain conductor)
python backend/app_protocol.py          # port 5001
PORT=5001 gunicorn --workers 1 --threads 4 app_protocol:app
```

**Requirements:** `requirements_protocol.txt` (just Flask, gunicorn, requests)

**Does NOT import from valichord_at_home.**

---

## app.py — valichord_at_home API

**Question it answers:** *Does this deposit look like someone could run it?*

This is the valichord_at_home researcher prep tool. It runs 100+ static checks on a
research deposit (missing README, hardcoded paths, no requirements file, etc.) and
returns a structured report of issues.

**Who uses it:** researchers checking their own deposits before publication.

**Endpoints:** `/validate`, `/upload-chunk`, `/result`, `/download`, `/status`, `/health`, `/attest`*

**Deployment:** Render (`valichord.onrender.com`). The demo at
[topeuph-ai.github.io/ValiChord/valichord-at-home.html](https://topeuph-ai.github.io/ValiChord/valichord-at-home.html)
calls this deployment.

```bash
# Render runs this automatically via render.yaml:
gunicorn --timeout 120 --workers 1 --threads 4 app:app     # port from $PORT
```

**Requirements:** `requirements.txt` (includes rarfile, py7zr, python-docx, etc.)

*`/attest` is present in app.py for backward compatibility. On Render it degrades
gracefully (harmony_record_hash is always null — no conductor). The canonical
`/attest` implementation is in `app_protocol.py`.

---

## Which one should PI / Feynman point to?

`app_protocol.py` — the protocol API running in the Codespace.

Default URL: `http://localhost:5001` (or whatever `PORT` is set to).

```bash
export VALICHORD_BASE_URL=http://localhost:5001
```

---

## How to undo the split

The split is additive:
- `app_protocol.py`, `openapi_protocol.yaml`, `requirements_protocol.txt`, `README.md` are new files.
- `app.py` has one added comment line at the top.

To undo: delete the four new files and remove the comment from `app.py`.
`app.py` itself and the Render deployment are unchanged.
