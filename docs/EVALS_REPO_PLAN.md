# Plan: ValiChord/valichord-evals — Repo Extraction

**Status:** Planned  
**Estimated effort:** Half a day  
**Do before:** TerraCommons repo creation (TerraCommons will depend on this library)

---

## Purpose

Extract `valichord_attestation` from the main ValiChord repo into a standalone public library repo at `github.com/ValiChord/valichord-evals`. This makes the attestation library independently referenceable by partners (lm-eval-harness, AILuminate, inspect_evals) and separately publishable to PyPI, without requiring them to clone the full Holochain protocol repo.

The main repo (`ValiChord/ValiChord`) becomes Holochain-only. The attestation library becomes the *client-side on-ramp* it was always intended to be — a clean, focused tool.

---

## Repo identity

| Field | Value |
|---|---|
| GitHub repo | `ValiChord/valichord-evals` |
| PyPI package name | `valichord-evals` |
| Python import name | `valichord_attestation` (unchanged — no breaking change for existing users) |
| Visibility | Public |

---

## What moves out of the main repo

| Path (current) | Destination |
|---|---|
| `valichord_attestation/` | New repo root → `valichord_attestation/` |
| `valichord_attestation/tests/` | Travels with the package |
| `valichord_attestation/examples/` | Travels with the package |
| `valichord_attestation/spec/` | Travels with the package |
| `.claude/skills/generate-attestation-bundle/` | New repo → `.claude/skills/generate-attestation-bundle/` |

---

## What stays in the main repo

| Path | Reason |
|---|---|
| `demo/core_bench_bundle.py` | Demo orchestration code, not library code |
| `demo/oetp_bridge.py` | Demo integration layer |
| `backend/` | Protocol REST API |
| All Holochain / Rust code | Protocol, not evals |

Demo code that imports `valichord_attestation` will pip-install it from PyPI (or from the new repo during development).

---

## Steps

### 1. Create the new repo
```bash
gh repo create ValiChord/valichord-evals --public --description "Cryptographic attestation bundles for AI evaluation runs — client on-ramp to the ValiChord reproducibility protocol"
```

### 2. Extract with git history preserved
Use `git subtree split` to carry commit history for `valichord_attestation/`:
```bash
# In a temp clone of ValiChord/ValiChord
git subtree split --prefix=valichord_attestation -b evals-extract
git push https://github.com/ValiChord/valichord-evals.git evals-extract:main
```

### 3. Set up the new repo
- Move `pyproject.toml` to repo root (already exists inside `valichord_attestation/`) — adjust paths
- Add `README.md` (draw from existing `valichord_attestation/README.md` if present, else write fresh)
- Copy `.claude/skills/generate-attestation-bundle/` to new repo
- Add MIT licence file (or match whatever licence decision is made for the org)
- Set up CI: `pytest --cov` on push + PR

### 4. PyPI publishing workflow
Add `.github/workflows/publish.yml`:
- Triggers on version tag (`v*`)
- Builds with `python -m build`
- Publishes to PyPI via `pypa/gh-action-pypi-publish`
- Requires `PYPI_API_TOKEN` secret in the new repo's settings

### 5. Update the main repo
- Delete `valichord_attestation/` directory
- Delete `.claude/skills/generate-attestation-bundle/`
- Update `CLAUDE.md`: change `valichord_attestation` path references; note it is now a separate repo
- Update `PROJECT_STATUS.md`: point to new repo for adapter status
- Update `demo/requirements.txt` (or equivalent): `valichord-evals>=1.2` instead of local path install
- Update any `pip install -e ".[dev]"` instructions in CLAUDE.md → point to new repo
- Commit: `chore: extract valichord_attestation to ValiChord/valichord-evals`

### 6. Verify
- Fresh clone of new repo → `pip install -e ".[dev]"` → `pytest` → all 537 tests pass
- Main repo demo code → `pip install valichord-evals` → imports resolve → demo runs end-to-end

---

## Also consider at the same time

**`topeuph-ai/lm-evaluation-harness` fork** — this is a personal fork carrying the `ValiChordLogger` PR. Consider transferring to `ValiChord/lm-evaluation-harness` so it sits alongside the library it extends. Low urgency; do it when the upstream PR lands or if a partner asks to see it.

---

## Post-extraction repo structure (new repo)

```
valichord-evals/
├── valichord_attestation/
│   ├── __init__.py
│   ├── builder.py
│   ├── canonical.py
│   ├── merkle.py
│   ├── challenge.py
│   ├── response.py
│   └── adapters/
│       ├── base.py
│       ├── inspect_ai_adapter.py
│       ├── inspect_evals_adapter.py
│       ├── pi_session_adapter.py
│       ├── lm_eval_adapter.py
│       └── ailuminate_adapter.py
├── tests/
├── examples/
├── spec/
├── .claude/skills/generate-attestation-bundle/
├── pyproject.toml
├── README.md
└── .github/workflows/
    ├── test.yml
    └── publish.yml
```
