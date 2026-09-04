# Running the demo on local models

No API key. No cost. The validators run on your own machine.

There are two of these: the **CLI demo**, which executes a study and asks
validators to judge the output, and the **web demo**, which takes a claim you
type and judges it against sources you supply. Both are covered below.

## What you need

An OpenAI-compatible model server running on this machine. [Your Own
AI](https://yourownai.net/download/) serves one at `127.0.0.1:11435` with
nothing to configure — install it, create some AIs, and it is running.

**Use three different models, one per validator.** Three AIs each bound to a
different model file is three genuinely different readers, with different
weights, different training data and different failure modes. Budget roughly
2–4 GB of disk per model.

Check the server can see them:

```bash
curl http://127.0.0.1:11435/v1/models
```

Each AI you created appears there as an id. Those ids are the model names below.

## Settings

Both demos read the same three:

| Flag (CLI) | Environment variable | Default |
|---|---|---|
| `--local` | `VALICHORD_LOCAL` | off |
| `--local-models` | `VALICHORD_LOCAL_MODELS` | whatever `/v1/models` lists first |
| `--api-base` | `VALICHORD_LOCAL_API_BASE` | `http://127.0.0.1:11435/v1` |
| — | `VALICHORD_LOCAL_JSON_SCHEMA=off` | on |

### Two things sent on every local request

**`X-Your-Own-AI-Online-Share: local`.** Your Own AI 0.7.0 changed the default
for "Auto Online-and-Offline" AIs to prefer a *frontier online* model, and made
the default difficulty one that can never choose to stay local. Without this
header a validator can be answered by a paid online model — your prompt leaves
the machine, or the run stops with a 401 asking you to sign in. The header pins
the round to the device.

**A JSON schema.** The verdict request carries an OpenAI-style `response_format`
naming a schema. Your Own AI forwards the body to the bundled llama.cpp
untouched apart from the messages and the model, and llama.cpp compiles that
schema into a grammar the sampler cannot leave. A small model is not being asked
nicely to return valid JSON — the malformed answer stops being representable.
This is the same mechanism the app uses on its own helper model.

If a server refuses the field, the call is retried once without it rather than
failing, and parsing falls back to the tolerant reader. `VALICHORD_LOCAL_JSON_SCHEMA=off`
disables it outright.

The protocol nodes are separate and unchanged. They default to
`localhost:3001–3004`, so if you are running the Docker stack locally there is
nothing else to set; otherwise point `VALICHORD_RESEARCHER_URL` and the three
`VALICHORD_VALIDATOR_N_URL` variables at the Oracle host as usual.

## The CLI demo

```bash
python3 demo/ai_validator_cma.py --mode decentralised --local
```

Or name the models yourself:

```bash
python3 demo/ai_validator_cma.py --mode decentralised --local --local-models alice,bob,carol
```

It runs the synthetic study, then gives each validator the study brief and the
actual execution output and asks whether the methodology supports the claim.

## The web demo

```bash
export VALICHORD_LOCAL=1
export VALICHORD_LOCAL_MODELS=alice,bob,carol
python3 demo/app.py
```

Then open `http://127.0.0.1:5000/demo`.

The page swaps the API-key box for a **source material** box. You type a claim,
paste the evidence, and write your own answer. Your answer *and the sources* are
hashed and sealed before the validators start, so neither can be swapped
afterwards. Each validator is a different local model, and each one is asked to
quote the passages it relied on.

**Every quote comes back checked.** The page shows each quote against the
SHA-256 of the source it cites, and marks it if the passage is not actually
there. A validator that invents a supporting quote is exactly the failure this
demo exists to expose, so a fabricated quote is displayed and flagged rather
than quietly dropped.

Separate multiple sources with a line containing only `---`.

### Why the web validators were given a different job

The hosted validators are handed `web_search` and told to go and find evidence.
Their rubric is written entirely in terms of what they retrieved —
`NotReproduced` means "weak, **absent**, or contradictory evidence".

Point that same prompt at an offline model and evidence is absent by
construction, so a rule-following validator can refute everything put to it. The
dangerous part is that nothing would look wrong: the pipeline runs, the record
is written, the page shows a confident headline, and the cryptography faithfully
proves that three validators committed before revealing. It would just not be
proving what the page says.

So the local validator judges supplied sources instead of searching. "Absent
evidence" then means something checkable — the passage is either in the document
with that hash, or it is not.

## The hosted demo is untouched

Local mode is off unless `VALICHORD_LOCAL` is set. The Render deployment keeps
running the Anthropic path exactly as before, and the tests assert the "off"
case explicitly rather than only covering the new behaviour.

## What this proves, and what it does not

**It does prove** that three independent validators committed a verdict to the
DHT before any of them could see another's, and that the reveal matched the
commitment. That is the ValiChord invariant, and it holds regardless of what
produced the verdicts — the protocol never learns what model answered.

**It does not prove** that the validators reproduced anything. In the CLI demo
they judge one execution's output rather than re-running the study. In the web
demo they read documents. Neither is independent reproduction, and the word
"Reproduced" is doing work here that it should not be asked to do — it survives
because the protocol and `agreement.py` already speak that vocabulary, not
because it describes what happened.

**One model three times is not three validators.** If fewer than three distinct
models are given, the CLI run prints a warning saying so. The count on screen
would otherwise imply an independence that repeated sampling does not provide.

A local model is also, unlike a hosted one, a validator you can re-run. Pin the
model file and the temperature and you can ask for the same verdict again.
Expect agreement rather than identity: inference is not bit-reproducible across
different hardware, engines or quantisations.
