# Running the demo on local models

No API key. No cost. The validators run on your own machine.

This covers the **CLI demo** (`ai_validator_cma.py`). The public web demo at
`/demo` still needs an Anthropic key — see [What this does not
cover](#what-this-does-not-cover) for why that is a harder problem than it
looks.

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

## Running it

Use whatever the server lists, in order:

```bash
python3 demo/ai_validator_cma.py --mode decentralised --local
```

Or name them yourself:

```bash
python3 demo/ai_validator_cma.py --mode decentralised --local --local-models alice,bob,carol
```

Point somewhere other than the default server:

```bash
python3 demo/ai_validator_cma.py --mode decentralised --local --api-base http://127.0.0.1:8080/v1
```

| Flag | Environment variable | Default |
|---|---|---|
| `--local` | — | off |
| `--local-models` | `VALICHORD_LOCAL_MODELS` | whatever `/v1/models` lists first |
| `--api-base` | `VALICHORD_LOCAL_API_BASE` | `http://127.0.0.1:11435/v1` |

The protocol nodes are separate and unchanged. They default to
`localhost:3001–3004`, so if you are running the Docker stack locally there is
nothing else to set; otherwise point `VALICHORD_RESEARCHER_URL` and the three
`VALICHORD_VALIDATOR_N_URL` variables at the Oracle host as usual.

## What this proves, and what it does not

**It does prove** that three independent validators committed a verdict to the
DHT before any of them could see another's, and that the reveal matched the
commitment. That is the ValiChord invariant, and it holds regardless of what
produced the verdicts — the protocol never learns what model answered.

**It does not prove** that the validators reproduced anything. They are handed
the study brief and the execution output and asked to judge whether the
methodology supports the claim. They do not re-run the study independently.
That gap is real and predates this change.

**One model three times is not three validators.** If fewer than three distinct
models are given, the run prints a warning saying so. The count on screen would
otherwise imply an independence that repeated sampling does not provide.

A local model is also, unlike a hosted one, a validator you can re-run. Pin the
model file and the temperature and you can ask for the same verdict again.
Expect agreement rather than identity: inference is not bit-reproducible across
different hardware, engines or quantisations.

## What this does not cover

The public web demo (`app.py` → `custom_runner.py`) cannot simply be pointed at
a local model. Its validators are given `web_search` and `web_fetch` and asked
to go and find evidence for a free-text claim; the verdict rubric is written
entirely in terms of what they retrieved. Remove search and the prompt
contradicts itself, and a rubric-obedient offline validator has a legal path to
refuting everything put to it.

The dangerous part is that this failure is invisible. The pipeline still runs,
the record is still written, the page still renders a confident headline. The
cryptography stays sound — it would faithfully prove that three validators
committed opinions before revealing them. It just would not be proving what the
page says it is proving.

Deciding what a validator *does* when it cannot look anything up is a product
decision, not an engineering one, and it has to come first.
