# CMA Upgrade Plan — Smarter AI Validators

**What this is:** A plan to upgrade the AI validators in the demo from quick one-shot answers to proper, thorough multi-step analysis using Anthropic's Claude Managed Agents (CMA).

**What stays the same:** Everything in Holochain. The four DNAs, the commit-reveal protocol, HarmonyRecords, badges — none of that changes. This is purely an upgrade to the AI layer that sits on top.

**What changes:** One file — `demo/ai_validator.py`. We'll create a new version called `demo/ai_validator_cma.py` alongside it. The old one stays as a fallback.

---

## In plain English

Right now each AI validator reads the study once and gives an immediate verdict. With CMA, each validator becomes a proper agent that can search the web, go back and forth, and won't submit its verdict until it's done a thorough job.

The three validators still work independently — they still can't see each other's answers. The Holochain protocol still enforces all the trust guarantees. CMA just makes the validators much smarter.

---

## User-provided API keys

To protect the demo budget, users can bring their own API key. The key is sent over HTTPS, used only for that run, and never logged or stored.

**Behaviour by key type:**

| Key format | Provider | Mode |
|---|---|---|
| `sk-ant-...` | Anthropic | Full CMA mode — agents, web search, quality check |
| `sk-proj-...` or `sk-...` | OpenAI | Simple one-shot mode via litellm |
| `AIzaSy...` | Google Gemini | Simple one-shot mode via litellm |
| `gsk_...` | Groq | Simple one-shot mode via litellm |
| anything else | Unknown | Attempted as OpenAI-compatible via litellm |
| nothing provided | — | Server's key, Anthropic CMA, with per-IP rate limiting |

**Simple one-shot mode** means the validator still gets the full 5-step analysis prompt and gives a reasoned verdict — it just doesn't do live web searches or the iterative quality check. The Holochain commit-reveal protocol is identical either way.

**UI change:** The demo page gets an optional "Your API key" text field and a "Provider / model" hint line (e.g. `openai/gpt-4o`, `gemini/gemini-1.5-pro`). Both are optional — leaving them blank uses the server's key.

---

## Prerequisites before starting

1. **CMA API access** — the `managed-agents-2026-04-01` beta must be enabled on the Anthropic account. ✓ Confirmed working.
2. **litellm** — add to `demo/requirements.txt` for non-Anthropic key support.
3. **The demo stack** — Oracle nodes must be running (they're on `restart: unless-stopped`, so they should be up).

---

## What we'll build

### New file: `demo/ai_validator_cma.py`

This replaces the orchestration logic in `ai_validator.py` but calls the exact same Node.js bridge HTTP APIs that already exist.

**Structure:**

```
1. Check key type → decide CMA mode or simple mode
2. Researcher submits study to Holochain (same as now)
3. Spin up 3 validator sessions IN PARALLEL — each gets its own context
4. Each validator session:
   a. Reads the study
   b. (CMA only) Searches web to verify methodology
   c. Writes verdict to scratchpad file
   d. (CMA only) Quality check reviews scratchpad — rejects if reasoning is shallow
   e. Once quality check passes, calls seal_attestation → hits validator-node.mjs → commits to DHT
5. Wait for Holochain to open the reveal phase
6. Each validator reveals
7. HarmonyRecord lands on DHT — done
```

### The validator system prompt

Each validator gets this prompt, regardless of mode:

```
You are an independent scientific reproducibility evaluator. Your job is to assess
whether a research result can be independently reproduced.

Work through these steps in order:
1. Read the claim being made and identify exactly what result is asserted.
2. Identify what would need to be true for that result to hold — the key assumptions
   and dependencies.
3. Check whether the methodology described is capable of producing that result. Look
   for gaps, ambiguities, or steps that couldn't be replicated without missing information.
4. Search for any known issues with the methodology, dataset, or statistical approach.
5. Based on steps 1–4, reach a verdict: Reproduced, PartiallyReproduced, or
   NotReproduced. State your confidence (High / Medium / Low) and explain your
   reasoning in at least 3 sentences, showing your working.

You cannot see what the other validators conclude. Do not submit your verdict until
you are confident.
```

### The quality check (CMA mode only)

Before calling `seal_attestation`, the agent writes its draft verdict to `/mnt/session/verdict.md`. An independent grader then checks that file. This keeps the quality check separate from the irreversible DHT write — the agent can revise its verdict file as many times as needed, but `seal_attestation` is only called once the grader is satisfied.

Rubric the grader checks:
- Does it state a clear verdict (Reproduced / PartiallyReproduced / NotReproduced)?
- Does it give a confidence level (High / Medium / Low)?
- Does it explain the reasoning in at least 3 sentences showing actual analysis?
- Does it identify at least one specific thing it checked (a method, a dataset, a statistic)?

If any of these fail, the grader sends the agent back to revise the verdict file. Once all pass, the agent calls `seal_attestation`.

### Tool execution — how seal_attestation works

`seal_attestation` is a custom tool that the agent calls but the Python code actually executes. The flow:

1. Agent decides it's ready, calls `seal_attestation(verdict, confidence, notes)`
2. Python code intercepts this in the event stream
3. Python calls the validator-node.mjs HTTP endpoint (same as current code)
4. Python sends the result back to the agent session
5. Agent receives confirmation and finishes

This is why the quality check runs before the seal — once Python sends that HTTP call to validator-node.mjs, it's written to the DHT and cannot be undone.

---

## Files to create / change

| File | Action | Notes |
|---|---|---|
| `demo/ai_validator_cma.py` | **Create new** | New orchestrator using CMA |
| `demo/ai_validator.py` | **Leave alone** | Kept as fallback |
| `demo/app.py` | **Small change** | Add API key field + `?mode=cma` param |
| `demo/requirements.txt` | **Small change** | Add `litellm`; `anthropic` already present |
| `demo/templates/demo.html` | **Small change** | Add optional API key + model hint fields |

---

## Correct API shapes (from cookbook verification)

```python
BETAS = ["managed-agents-2026-04-01"]

# Create environment
env = client.beta.environments.create(
    name="valichord-run",
    config={"type": "anthropic_cloud", "networking": {"type": "unrestricted"}},
)

# Create a validator agent
validator = client.beta.agents.create(
    name="validator-1",
    model="claude-haiku-4-5-20251001",
    system=VALIDATOR_SYSTEM_PROMPT,
    tools=[
        {
            "type": "agent_toolset_20260401",
            "configs": [{"name": "web_search"}, {"name": "web_fetch"},
                        {"name": "read"}, {"name": "write"}],
        },
        # Custom tool — executed client-side
        {
            "name": "seal_attestation",
            "description": "Submit your reproducibility verdict. Call this only after your verdict file has been approved.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "verdict":    {"type": "string", "enum": ["Reproduced", "NotReproduced", "PartiallyReproduced"]},
                    "confidence": {"type": "string", "enum": ["High", "Medium", "Low"]},
                    "notes":      {"type": "string"},
                },
                "required": ["verdict", "confidence", "notes"],
            },
        },
    ],
    betas=BETAS,
)

# Create session — NOTE: agent= dict, not agent_id=
session = client.beta.sessions.create(
    agent={"type": "agent", "id": validator.id, "version": validator.version},
    environment_id=env.id,
    betas=BETAS,
)

# Define outcome — NOTE: rubric is a dict, not a plain string
client.beta.sessions.events.send(
    session.id,
    betas=BETAS,
    events=[{
        "type": "user.define_outcome",
        "description": "A complete, reasoned reproducibility verdict written to /mnt/session/verdict.md",
        "rubric": {"type": "text", "content": QUALITY_RUBRIC},
        "max_iterations": 3,
    }],
)

# Stream events — handle custom tool calls client-side
with client.beta.sessions.events.stream(session.id, betas=BETAS) as stream:
    for ev in stream:
        if ev.type == "agent.tool_use" and ev.name == "seal_attestation":
            result = call_validator_node(validator_url, task_hash, ev.input)
            client.beta.sessions.events.send(
                session.id, betas=BETAS,
                events=[{"type": "agent.tool_result", "tool_use_id": ev.id, "content": result}],
            )
        elif ev.type == "session.status_idle":
            break
```

---

## Rate limiting (server key only)

When no user key is provided, the server's key is used with these guards:

```python
import time
from collections import defaultdict

_ip_last_run   = defaultdict(float)
_cma_run_count = 0
CMA_RUN_COST_ESTIMATE = 1.50   # dollars per run
CMA_MONTHLY_BUDGET    = 20.00

def cma_allowed(ip: str) -> tuple[bool, str]:
    now = time.time()
    if now - _ip_last_run[ip] < 3600:
        return False, "CMA mode is limited to once per hour per visitor."
    if _cma_run_count * CMA_RUN_COST_ESTIMATE >= CMA_MONTHLY_BUDGET:
        return False, "CMA mode has reached its monthly demo budget. Standard mode is still available."
    return True, ""
```

Rate limiting is skipped when the user provides their own key.

---

## Observability logging

Log the following for every CMA run (stdout → Render logs):

```python
{
  "cma_run_id":          run_id,
  "validator":           1,        # 1, 2, or 3
  "session_id":          session.id,
  "duration_s":          elapsed,
  "tool_calls":          n_tool_calls,
  "verdict":             verdict,
  "quality_iterations":  n_grader_passes,
  "user_key":            bool,     # True/False — never log the key itself
}
```

---

## Step-by-step for the session

1. ~~Check CMA access~~ — ✓ confirmed working
2. ~~Read cookbooks~~ — ✓ done; API shapes corrected above
3. Write `ai_validator_cma.py`
4. Update `app.py` — add key field, mode param, rate limiting
5. Update `demo.html` — add optional key + model hint fields
6. Test end-to-end against Oracle nodes

```bash
export ANTHROPICAPIKEY=sk-ant-...
export VALICHORD_RESEARCHER_URL=http://132.145.34.27:3001
export VALICHORD_VALIDATOR_1_URL=http://132.145.34.27:3002
export VALICHORD_VALIDATOR_2_URL=http://132.145.34.27:3003
export VALICHORD_VALIDATOR_3_URL=http://132.145.34.27:3004
python3 demo/ai_validator_cma.py --mode decentralised
```

---

## What success looks like

Same output as the current demo — 7 steps, HarmonyRecord hash, shareable URL — but with richer per-validator notes showing the actual analysis each validator did.

---

## If CMA isn't available

The current `ai_validator.py` stays working. Nothing breaks.
