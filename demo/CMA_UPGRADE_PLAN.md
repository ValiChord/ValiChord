# CMA Upgrade Plan — Smarter AI Validators

**What this is:** A plan to upgrade the AI validators in the demo from quick one-shot answers to proper, thorough multi-step analysis using Anthropic's Claude Managed Agents (CMA).

**What stays the same:** Everything in Holochain. The four DNAs, the commit-reveal protocol, HarmonyRecords, badges — none of that changes. This is purely an upgrade to the AI layer that sits on top.

**What changes:** One file — `demo/ai_validator.py`. We'll create a new version called `demo/ai_validator_cma.py` alongside it. The old one stays as a fallback.

---

## In plain English

Right now each AI validator reads the study once and gives an immediate verdict. With CMA, each validator becomes a proper agent that can search the web, run code, go back and forth, and won't submit its verdict until it's done a thorough job. There's also a built-in quality check that rejects shallow verdicts.

The three validators still work independently — they still can't see each other's answers. The Holochain protocol still enforces all the trust guarantees. CMA just makes the validators much smarter.

---

## Prerequisites before starting

1. **CMA API access** — the `managed-agents-2026-04-01` beta must be enabled on the Anthropic account. Check at platform.claude.ai or ask Anthropic support. **Run the Step 1 access check first. If it fails, stop — nothing else works without it.**
2. **Set a budget ceiling** — CMA sessions cost ~$1–2 per demo run (multi-turn, tool use). For a public demo, set a monthly ceiling of ~$20 (≈10–15 runs). Set billing alerts in the Anthropic console at $20 and $50. Also add a run counter in the code that falls back to simple mode when the estimated monthly spend exceeds the ceiling.
3. **The demo stack** — Oracle nodes must be running (they're on `restart: unless-stopped`, so they should be up).

---

## What we'll build

### New file: `demo/ai_validator_cma.py`

This replaces the orchestration logic in `ai_validator.py` but calls the exact same Node.js bridge HTTP APIs that already exist.

**Structure:**

```
1. Set up 3 validator agents (done once, agents are reusable)
2. Create a shared sandbox environment
3. For each demo run:
   a. Researcher submits study to Holochain (same as now)
   b. Spin up 3 validator sessions IN PARALLEL — each gets its own context
   c. Each validator session:
      - Reads the study
      - Searches web / checks methodology / analyses the claim
      - Quality check rejects it if the analysis is too shallow
      - Calls seal_attestation tool → hits validator-node.mjs → commits to DHT
   d. Wait for Holochain to open the reveal phase
   e. Each validator reveals
   f. HarmonyRecord lands on DHT — done
```

### The 3 validator agents

Each gets a system prompt like:
> "You are an independent scientific reproducibility evaluator. You will be given a study and asked whether you can reproduce the result. Check the methodology, verify the claim, run the numbers. You have 3 minutes and a maximum of 3 web searches. Do not submit your verdict until you are confident. You cannot see what other validators conclude."

Each gets these tools:
- `web_search` — limited to 3 calls per session, for methodology lookup only
- `seal_attestation(verdict, confidence, notes)` — custom tool that calls `validator-node.mjs`
- `submit_reveal()` — custom tool that fires once the reveal phase opens

**Time limit:** 3 minutes (180 seconds) per validator session. If a session exceeds this, fall back to a simple one-shot verdict and log the timeout.

**Note on environment isolation:** Validators share one CMA environment — this is fine and is how Anthropic's own multi-agent cookbook works. Isolation between validators is at the session/context level (each session has its own conversation history). ValiChord's validators don't use the shared file system at all — they call external HTTP endpoints — so there is nothing to leak between them.

### The quality rubric (Outcomes API)

Before a validator's verdict counts, an automated grader checks:
- Did it state a clear Reproduced / NotReproduced / Partial decision?
- Did it give a confidence level?
- Did it explain its reasoning (at least 2 sentences)?
- Did it call `seal_attestation`?

If not, the validator is sent back to do more work. Also handle the separate case where the agent produces malformed tool arguments — retry once, then fall back to simple mode.

---

## Files to create / change

| File | Action | Notes |
|---|---|---|
| `demo/ai_validator_cma.py` | **Create new** | New orchestrator using CMA |
| `demo/ai_validator.py` | **Leave alone** | Kept as fallback |
| `demo/app.py` | **Small change** | Add `?mode=cma` query param to use new validator |
| `demo/requirements.txt` | **Small change** | `anthropic` version must be ≥ the CMA beta release |

---

## Step-by-step for the session

When picking this up, run these steps in order:

### Step 1 — Check CMA access
```python
import anthropic
client = anthropic.Anthropic()
# Try creating a test agent
agent = client.beta.agents.create(
    name="test",
    model="claude-haiku-4-5-20251001",
    system="test",
    betas=["managed-agents-2026-04-01"]
)
print(agent.id)  # Should print an agent ID, not raise an error
```
If this raises a 403 or beta-not-enabled error, stop — CMA access isn't live on the account yet.

### Step 2 — Study the CMA cookbooks
The two key notebooks are already cloned at `/tmp/claude-cookbooks/` (or re-clone):
```bash
git clone --depth 1 https://github.com/anthropics/claude-cookbooks /tmp/claude-cookbooks
```
Read:
- `managed_agents/CMA_coordinate_specialist_team.ipynb` — the multiagent coordinator pattern
- `managed_agents/CMA_verify_with_outcome_grader.ipynb` — the Outcomes/rubric quality gate

### Step 3 — Write `ai_validator_cma.py`

Key API shapes to use (from the cookbooks):

```python
BETAS = ["managed-agents-2026-04-01"]

# Create environment (once per run)
env = client.beta.environments.create(
    name="valichord-run",
    config={"type": "anthropic_cloud", "networking": {"type": "unrestricted"}},
    betas=BETAS,
)

# Create a validator agent (once, reusable across runs)
validator = client.beta.agents.create(
    name="validator-1",
    model="claude-haiku-4-5-20251001",  # Haiku is fast and cheap for validators
    system=VALIDATOR_SYSTEM_PROMPT,
    tools=[web_search_tool, seal_attestation_tool, submit_reveal_tool],
    betas=BETAS,
)

# Start a session for this validator
session = client.beta.sessions.create(
    agent_id=validator.id,
    environment_id=env.id,
    betas=BETAS,
)

# Send the study to the validator
client.beta.sessions.events.send(
    session.id,
    betas=BETAS,
    events=[{"type": "user.message", "content": study_prompt}],
)

# Stream until idle (verdict submitted)
with client.beta.sessions.events.stream(session.id, betas=BETAS) as stream:
    for event in stream:
        # handle tool calls, messages, completion
        pass
```

The `seal_attestation_tool` is a custom tool whose handler calls:
```python
requests.post(f"{validator_url}/seal_attestation", json={
    "task_hash": task_hash,
    "verdict": verdict,      # "Reproduced" / "NotReproduced" / "PartiallyReproduced"
    "confidence": confidence, # "High" / "Medium" / "Low"
    "notes": notes,
})
```
This is the same HTTP call `ai_validator.py` already makes — just now the AI decides when to make it.

### Step 4 — Run 3 validators in parallel

Use Python's `concurrent.futures.ThreadPoolExecutor` (same pattern as current code) to run all 3 validator sessions simultaneously.

### Step 5 — Wire the Outcomes rubric

```python
client.beta.sessions.events.send(
    session.id,
    betas=BETAS,
    events=[{
        "type": "user.define_outcome",
        "description": "A complete reproducibility verdict for the study",
        "rubric": """
        The verdict must:
        1. State clearly: Reproduced, NotReproduced, or PartiallyReproduced
        2. Give a confidence level: High, Medium, or Low
        3. Explain the methodology check (at least 2 sentences)
        4. Have called seal_attestation before finishing
        Reject if any of these are missing.
        """
    }],
)
```

### Step 5.5 — Add rate limiting + spend tracking to `app.py`

The public demo needs two guards:

```python
# In app.py — add alongside the existing _demo_running lock

import time
from collections import defaultdict

_ip_last_run = defaultdict(float)   # ip → timestamp of last CMA run
_cma_run_count = 0                  # estimate-based spend tracking
CMA_RUN_COST_ESTIMATE = 1.50        # dollars per run
CMA_MONTHLY_BUDGET = 20.00

def cma_allowed(ip: str) -> tuple[bool, str]:
    now = time.time()
    if now - _ip_last_run[ip] < 3600:
        return False, "CMA mode is limited to once per hour per visitor. Try again later."
    estimated_spend = _cma_run_count * CMA_RUN_COST_ESTIMATE
    if estimated_spend >= CMA_MONTHLY_BUDGET:
        return False, "CMA mode has reached its monthly demo budget. Standard mode is still available."
    return True, ""
```

When CMA is rate-limited or budget-capped, the endpoint returns a clear user-facing message and falls back to standard mode automatically.

**Note:** Spend tracking is estimate-based (run count × fixed cost). The Anthropic API does not expose per-request cost in real time.

### Step 5.75 — Add session observability logging

Log the following for every CMA run (to stdout / Render logs):

```python
{
  "cma_run_id": run_id,
  "validator": 1,           # 1, 2, or 3
  "session_id": session.id,
  "duration_s": elapsed,
  "tool_calls": n_tool_calls,
  "verdict": verdict,
  "estimated_cost_usd": token_count * cost_per_token,
}
```

This gives visibility into runtime, cost, and tool usage per validator without needing an admin UI.

### Step 6 — Test end-to-end
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export VALICHORD_RESEARCHER_URL=http://132.145.34.27:3001
export VALICHORD_VALIDATOR_1_URL=http://132.145.34.27:3002
export VALICHORD_VALIDATOR_2_URL=http://132.145.34.27:3003
export VALICHORD_VALIDATOR_3_URL=http://132.145.34.27:3004
python3 demo/ai_validator_cma.py --mode decentralised
```

---

## What success looks like

Same output as the current demo — 7 steps, HarmonyRecord hash, shareable URL — but with richer per-validator notes in the output showing the actual analysis each validator did, not just "Reproduced (High)".

---

## If CMA isn't available yet

The current `ai_validator.py` stays working. Nothing breaks. Pick this up whenever the tokens and beta access are ready.
