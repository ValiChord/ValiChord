Want to add a ValiChord extension + skill to `examples/`.

ValiChord answers one question: can an independent party run the same research code and get the same result? Multiple validators each run the code in isolation, seal verdicts via a blind commit-reveal protocol, and the majority outcome is written as a permanent HarmonyRecord on a Holochain peer-to-peer network. No central server can alter it after the fact.

pi's role is AI validator: read the README, run the code via `bash`, compare outputs to the researcher's claims, submit a verdict. The extension adds:

- `valichord_validate` — computes deposit SHA-256 locally, calls `POST /attest`, returns the HarmonyRecord (~60 s, synchronous)
- `valichord_health` — pre-flight connectivity check
- `/valichord` command + `SKILL.md` workflow prompt

Nothing touches core. Branch: `topeuph-ai:main`
