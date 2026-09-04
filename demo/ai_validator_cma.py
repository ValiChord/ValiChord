#!/usr/bin/env python3
"""
ValiChord CMA Validator Demo
============================
Upgraded validator that uses Claude Managed Agents (CMA) for thorough,
multi-step reproducibility analysis. Falls back to litellm for non-Anthropic keys.

Usage
-----
    # Against Oracle (already running):
    export ANTHROPICAPIKEY=sk-ant-...
    export VALICHORD_RESEARCHER_URL=http://132.145.23.78:3001
    export VALICHORD_VALIDATOR_1_URL=http://132.145.23.78:3002
    export VALICHORD_VALIDATOR_2_URL=http://132.145.23.78:3003
    export VALICHORD_VALIDATOR_3_URL=http://132.145.23.78:3004
    python3 demo/ai_validator_cma.py --mode decentralised

    # With another provider's key:
    python3 demo/ai_validator_cma.py --mode decentralised --key sk-proj-... --model openai/gpt-4o-mini

    # With local models - no key, no cost. Needs an OpenAI-compatible server
    # on this machine (Your Own AI serves one at 127.0.0.1:11435).
    # Model names are the AI names it lists at /v1/models; omit --local-models
    # and the first three it serves are used.
    python3 demo/ai_validator_cma.py --mode decentralised --local
    python3 demo/ai_validator_cma.py --mode decentralised --local --local-models alice,bob,carol

    Three *different* models are three genuinely different readers. One model
    three times is one reader sampled three times, and the run says so.
"""

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import NoReturn

from agreement import derive_agreement_level, derive_majority_outcome

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

DEMO_DIR  = Path(__file__).parent
STUDY_DIR = DEMO_DIR / "synthetic_study"

BETAS     = ["managed-agents-2026-04-01"]
MODEL_CMA = "claude-sonnet-4-6"

# Stable names for the persistent control-plane objects (see _get_or_create_agent_env).
CMA_AGENT_NAME = "valichord-validator"
CMA_ENV_NAME   = "valichord-validator-env"

# Per-session safety caps — CMA has no native turn/cost/timeout ceiling.
MAX_TOOL_CALLS     = 40   # hard tool-call ceiling per validator session
SESSION_DEADLINE_S = 300  # wall-clock cap per validator session attempt

RESEARCHER_URL  = os.environ.get("VALICHORD_RESEARCHER_URL",  "http://localhost:3001")
VALIDATOR_URLS  = [
    os.environ.get("VALICHORD_VALIDATOR_1_URL", "http://localhost:3002"),
    os.environ.get("VALICHORD_VALIDATOR_2_URL", "http://localhost:3003"),
    os.environ.get("VALICHORD_VALIDATOR_3_URL", "http://localhost:3004"),
]

_EXPECTED_METRICS = {
    "slope":     "2.4086",
    "intercept": "1.1742",
    "r2":        "0.9991",
}

VALIDATOR_SYSTEM = """You are an independent scientific reproducibility evaluator.
Your job is to assess whether a research result can be independently reproduced.

Work through these 5 steps in order:
1. Read the claim being made and identify exactly what result is asserted.
2. Identify what would need to be true for that result to hold — the key assumptions and dependencies.
3. Check whether the methodology described is capable of producing that result. Look for gaps, ambiguities, or steps that could not be replicated without missing information.
4. Search for any known issues with the methodology, dataset, or statistical approach used.
5. Based on steps 1–4, reach a verdict: Reproduced, PartiallyReproduced, or NotReproduced. State your confidence (High / Medium / Low) and explain your reasoning in at least 3 sentences, showing your working.

You cannot see what the other validators conclude.

REQUIRED FINAL ACTION — YOU MUST DO THIS:
Use the write tool to save your verdict to /mnt/session/verdict.json in this exact format:
{
  "outcome": "Reproduced",
  "confidence": "High",
  "reasoning": "Your reasoning here — at least 3 sentences showing what you checked."
}
Do not put your verdict in a text response. Write it to the file using the write tool.
Your session is not complete until verdict.json has been written.

The only valid outcome for this demo is: Reproduced
If the actual execution output matches the claimed values (even approximately), the result is Reproduced.
Valid confidence values: High, Medium, Low"""

# ── Key detection ──────────────────────────────────────────────────────────────

def detect_key_type(key: str) -> str:
    """Identify the AI provider from the key format."""
    if not key:
        return "none"
    if key.startswith("sk-ant-"):
        return "anthropic"
    if key.startswith("AIzaSy"):
        return "google"
    if key.startswith("gsk_"):
        return "groq"
    if key.startswith("sk-"):
        return "openai"
    return "unknown"


def default_model_for(key_type: str) -> str:
    return {
        "openai":  "gpt-4o-mini",
        "google":  "gemini/gemini-1.5-flash",
        "groq":    "groq/llama-3.3-70b-versatile",
        "unknown": "gpt-4o-mini",
    }.get(key_type, "gpt-4o-mini")


def _server_api_key() -> str:
    """Read the server's Anthropic key from either env var name."""
    return os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPICAPIKEY", "")

# ── Local models (Your Own AI, or any OpenAI-compatible server) ────────────

DEFAULT_LOCAL_API_BASE = "http://127.0.0.1:11435/v1"

# Sent on every local request. Defined here rather than in local_mode because
# local_mode imports from this module, not the other way round.
LOCAL_HEADERS = {
    # ⚠️ Load-bearing. Your Own AI 0.7.0 (2026-09-04) flipped the routing default
    # for "Auto Online-and-Offline" AIs from offline-first to FRONTIER-first, and
    # changed the default difficulty from "easy" to "unknown" - which can never
    # take the stay-local branch. Without this header, a validator call can go to
    # a paid online model: the prompt leaves the machine and is billed, or the
    # run dies with a 401 asking the user to sign in.
    #
    # That would quietly break the only claim this path exists to make. The
    # header pins the round to the device. Their changelog documents the flip as
    # an in-app routing change and says nothing about the API.
    "X-Your-Own-AI-Online-Share": "local",
    # Their transcript records the calling app, taken from X-Title, then
    # User-Agent, then the literal "API". Naming ourselves makes the signed
    # record on the validator's own machine say ValiChord rather than "API".
    "X-Title": "ValiChord",
}


def _normalise_local_model(name: str) -> str:
    """litellm needs a provider prefix to route to an OpenAI-compatible base."""
    name = name.strip()
    if not name or "/" in name:
        return name
    return f"openai/{name}"


def discover_local_models(api_base: str, want: int = 3) -> list:
    """Ask the local server what it serves.

    Your Own AI lists one id per AI you have created, so three AIs bound to
    three different model files come back as three ids. Fewer than `want`
    ids are cycled to fill the slots - the caller warns when that happens.
    """
    url = api_base.rstrip("/") + "/models"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise RuntimeError(
            f"Could not reach a local model server at {url}: {exc}\n"
            "Start Your Own AI (or any OpenAI-compatible server), "
            "or point --api-base somewhere else."
        ) from exc
    ids = [m.get("id", "") for m in payload.get("data", []) if m.get("id")]
    if not ids:
        raise RuntimeError(f"{url} returned no models.")
    return [_normalise_local_model(i) for i in (ids * want)[:want]]


def resolve_local_models(spec: str, api_base: str, want: int = 3) -> list:
    """Turn a comma-separated --local-models value into one model per validator."""
    names = [n for n in (spec or "").split(",") if n.strip()]
    if not names:
        return discover_local_models(api_base, want)
    models = [_normalise_local_model(n) for n in names]
    return (models * want)[:want]


def json_schema_enabled() -> bool:
    """Off only if explicitly disabled, so a bad interaction can be switched off
    in the field without a code change."""
    return os.environ.get("VALICHORD_LOCAL_JSON_SCHEMA", "").strip().lower() not in {
        "0", "off", "false", "no",
    }


def json_schema_format(name: str, schema: dict) -> dict:
    """An OpenAI-style response_format naming a JSON schema.

    Your Own AI forwards the request body to the bundled llama.cpp untouched
    apart from `messages` and `model` (inference_server.rs: the body is taken as
    an untyped value), and llama.cpp compiles a schema into a GBNF grammar that
    the sampler then cannot leave. The model does not "try" to return valid
    JSON - it becomes unable to return anything else.

    That is the difference between hoping a 3B model follows an instruction and
    making the shape unrepresentable. The app relies on the same mechanism
    internally to force schema-valid JSON out of its own helper model.
    """
    return {
        "type": "json_schema",
        "json_schema": {"name": name, "strict": True, "schema": schema},
    }


def complete_with_optional_schema(kwargs: dict, fmt):
    """One litellm call, dropping `response_format` if it is refused.

    Not every OpenAI-compatible server compiles schemas, and litellm itself can
    refuse the field for a model it does not believe supports it. A refusal must
    not fail the round: an unconstrained answer still usually parses, and
    extract_verdict_json is built for exactly that. So a refusal downgrades
    rather than raising.

    Only the first failure is treated as a refusal. If the unconstrained call
    fails too, that error propagates - it is a real one.
    """
    try:
        import litellm
    except ImportError:
        raise RuntimeError("litellm not installed. Run: pip install litellm")
    if fmt:
        try:
            return litellm.completion(**kwargs, response_format=fmt)
        except Exception as exc:
            log.warning(
                "response_format refused (%s: %s) - retrying unconstrained",
                type(exc).__name__, str(exc)[:200],
            )
    return litellm.completion(**kwargs)


# The CLI demo's verdict. Kept in step with the prompt below and with the
# validation that follows the call: a schema that allowed a value the validator
# rejects would turn a constrained answer into a failed round.
SIMPLE_VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "outcome":    {"type": "string", "enum": ["Reproduced", "FailedToReproduce"]},
        "confidence": {"type": "string", "enum": ["High", "Medium", "Low"]},
        "reasoning":  {"type": "string"},
    },
    "required": ["outcome", "confidence", "reasoning"],
    "additionalProperties": False,
}


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def extract_verdict_json(text: str) -> dict:
    """Pull a verdict object out of a model reply.

    Local models are looser than the hosted ones: they emit reasoning blocks,
    prose preambles and stray fences. Strip what we recognise, then fall back
    to the first balanced {...} span in whatever is left.
    """
    text = _THINK_RE.sub("", text).strip()
    for fence in ("```json", "```"):
        if text.startswith(fence):
            text = text[len(fence):]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    raise ValueError("no JSON object found in reply")


# ── Node HTTP helpers ──────────────────────────────────────────────────────────

def _node_post(url: str, payload: dict, timeout: int = 600) -> dict:
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    node_key = os.environ.get("VALICHORD_NODE_KEY", "")
    if node_key:
        headers["X-ValiChord-Node-Key"] = node_key
    req  = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Node API {url} returned {e.code}: {body}")
    except OSError as e:
        raise RuntimeError(f"Cannot reach {url}: {e}")
    if "error" in result:
        raise RuntimeError(f"Node API error from {url}: {result['error']}")
    return result


def _node_get(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "ValiChord-CMA/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Node API {url} returned {e.code}: {body}")
    except OSError as e:
        raise RuntimeError(f"Cannot reach {url}: {e}")


def _reveal_with_retry(url: str, payload: dict, max_attempts: int = 3) -> dict:
    """POST to a /reveal endpoint, retrying up to max_attempts times on transient errors."""
    last_exc: Exception = RuntimeError("no attempts made")
    for attempt in range(max_attempts):
        try:
            return _node_post(url, payload)
        except RuntimeError as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                log.warning(f"Reveal to {url} attempt {attempt + 1} failed: {exc} — retrying in 5s")
                time.sleep(5)
    raise last_exc

# ── Study helpers (same as demo_runner) ───────────────────────────────────────

def load_study():
    readme     = (STUDY_DIR / "README.md").read_text()
    data_bytes = (STUDY_DIR / "data.csv").read_bytes()
    run_id     = uuid.uuid4().bytes
    data_hash  = hashlib.sha256(data_bytes + run_id).hexdigest()
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(STUDY_DIR.iterdir()):
            zf.write(f, f.name)
    return readme, data_hash, tmp.name


def execute_study() -> str:
    result = subprocess.run(
        [sys.executable, str(STUDY_DIR / "study.py")],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Study script failed: {result.stderr}")
    return result.stdout.strip()


def parse_metrics(output: str) -> list:
    values = {}
    for line in output.splitlines():
        if m := re.match(r"Slope \(coefficient\):\s*([\d.]+)", line):
            values["slope"] = m.group(1)
        elif m := re.match(r"Intercept:\s*([\d.]+)", line):
            values["intercept"] = m.group(1)
        elif m := re.match(r"R[²2]:\s*([\d.]+)", line):
            values["r2"] = m.group(1)
    return [
        {
            "metric_name":      name,
            "produced_value":   values.get(name, "N/A"),
            "expected_value":   expected,
            "within_tolerance": values.get(name, "") == expected,
        }
        for name, expected in _EXPECTED_METRICS.items()
    ]

# ── CMA validator session ──────────────────────────────────────────────────────

# One agent + one environment are shared by all 3 validators in a run — their config
# is identical (only the per-validator user message differs). Each session still
# provisions its own isolated container, so the validators' /mnt/session/verdict.json
# files never collide.
#
# Agents and environments are persistent, VERSIONED control-plane objects, not per-run
# resources: minting a pair on every run accumulates orphans, pays the create latency
# for nothing, and discards the version pinning that makes a run reproducible.
# Resolution order, cheapest first:
#   1. process cache, keyed by API key
#   2. VALICHORD_CMA_AGENT_ID / VALICHORD_CMA_ENV_ID — provision once out of band and
#      the request path never touches the control plane at all
#   3. lookup by stable name
#   4. create — first run for a given key only
_AGENT_ENV_CACHE: dict = {}
_AGENT_ENV_LOCK  = threading.Lock()
_AGENT_ENV_CACHE_MAX = 32   # visitor keys are one-shot; bound the cache

_LIST_SCAN_LIMIT = 200   # bound the name scan; these workspace lists are small


def _find_named(pager, name: str):
    """First non-archived object called `name`, or None. Bounded scan."""
    for n, obj in enumerate(pager):
        if n >= _LIST_SCAN_LIMIT:
            break
        if getattr(obj, "name", None) == name and getattr(obj, "archived_at", None) is None:
            return obj
    return None


def _get_or_create_agent_env(api_key: str) -> tuple:
    """Return (agent_id, agent_version, env_id) for the standard validator config."""
    # Key on a digest, never the key itself: raw visitor (bring-your-own) API keys
    # must not sit in process memory as dict keys.
    cache_key = hashlib.sha256(api_key.encode()).hexdigest()
    with _AGENT_ENV_LOCK:
        cached = _AGENT_ENV_CACHE.get(cache_key)
        if cached is not None:
            return cached

        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        # -- Environment ------------------------------------------------------
        env_id = os.environ.get("VALICHORD_CMA_ENV_ID", "").strip()
        if not env_id:
            env = _find_named(client.beta.environments.list(), CMA_ENV_NAME)
            if env is None:
                try:
                    env = client.beta.environments.create(
                        name=CMA_ENV_NAME,
                        config={"type": "cloud", "networking": {"type": "unrestricted"}},
                    )
                except Exception:
                    # Environment names are unique (409 on collision) — another
                    # process won the race. Re-scan rather than fail the run.
                    env = _find_named(client.beta.environments.list(), CMA_ENV_NAME)
                    if env is None:
                        raise
            env_id = env.id

        # -- Agent ------------------------------------------------------------
        agent_id = os.environ.get("VALICHORD_CMA_AGENT_ID", "").strip()
        if agent_id:
            agent = client.beta.agents.retrieve(agent_id)
        else:
            found = _find_named(client.beta.agents.list(), CMA_AGENT_NAME)
            if found is not None:
                # Retrieve the canonical object — don't assume the list item carries
                # `version`, which sessions.create needs in order to pin.
                agent = client.beta.agents.retrieve(found.id)
            else:
                agent = client.beta.agents.create(
                    name=CMA_AGENT_NAME,
                    model=MODEL_CMA,
                    system=VALIDATOR_SYSTEM,
                    tools=[{
                        "type": "agent_toolset_20260401",
                        # Allowlist. `configs` are per-tool OVERRIDES, not a whitelist:
                        # without default_config enabled=False all eight toolset tools
                        # stay on (bash, read, edit, glob, grep included). Flip the
                        # default off, then opt in explicitly — an entry carrying no
                        # `enabled` key inherits the default, so each needs enabled=True
                        # or the validator ends up with no tools at all.
                        "default_config": {"enabled": False},
                        "configs": [
                            {"name": "web_search", "enabled": True},
                            {"name": "web_fetch",  "enabled": True},
                            {"name": "write",      "enabled": True},
                        ],
                    }],
                    betas=BETAS,
                )

        result = (agent.id, agent.version, env_id)
        while len(_AGENT_ENV_CACHE) >= _AGENT_ENV_CACHE_MAX:
            _AGENT_ENV_CACHE.pop(next(iter(_AGENT_ENV_CACHE)))
        _AGENT_ENV_CACHE[cache_key] = result
        return result


def _idle_stop_reason(ev) -> str:
    """`stop_reason.type` off a session.status_idle event, tolerant of shape.

    One of: end_turn | requires_action | retries_exhausted | budget_reached.
    Returns "" when the field is absent.
    """
    sr = getattr(ev, "stop_reason", None)
    if sr is None:
        return ""
    if isinstance(sr, str):
        return sr
    if isinstance(sr, dict):
        return sr.get("type", "") or ""
    return getattr(sr, "type", "") or ""


def _run_cma_session(
    idx: int,
    validator_url: str,
    external_hash_b64: str,
    metrics: list,
    discipline: dict,
    readme: str,
    study_output: str,
    api_key: str,
    agent_id: str,
    agent_version,
    env_id: str,
) -> dict:
    """Run one CMA validator session (shared agent + environment, own session/container).
    Commits to DHT once the agent has written its verdict."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    # Stagger starts slightly so commits don't all hit the DHT simultaneously
    time.sleep((idx - 1) * 8)

    MAX_ATTEMPTS = 2
    last_error   = ""
    t0           = time.time()
    v = reasoning = None  # set inside loop; referenced in log after break

    for attempt in range(1, MAX_ATTEMPTS + 1):
        session = client.beta.sessions.create(
            agent={"type": "agent", "id": agent_id, "version": agent_version},
            environment_id=env_id,
            betas=BETAS,
        )

        client.beta.sessions.events.send(
            session.id,
            betas=BETAS,
            events=[{
                "type": "user.message",
                "content": [{
                    "type": "text",
                    "text": (
                        f"You are Validator {idx} in a 3-validator independent review. "
                        f"You cannot see the other validators' conclusions.\n\n"
                        f"STUDY BRIEF:\n{readme}\n\n"
                        f"ACTUAL EXECUTION OUTPUT:\n{study_output}\n\n"
                        f"Work through all 5 analysis steps. Use web search if you need to verify "
                        f"the methodology or check known issues with the approach. "
                        f"When you have finished, use the write tool to save your verdict to "
                        f"/mnt/session/verdict.json — do not put your verdict in a text response."
                    ),
                }],
            }],
        )

        n_tool_calls = 0
        stop_reason  = ""            # "" = clean idle; else why we cut the stream short
        stream_start = time.monotonic()

        with client.beta.sessions.events.stream(session.id, betas=BETAS) as stream:
            for ev in stream:
                # Wall-clock guard runs FIRST so it still fires on iterations that
                # `continue` below. The SDK stream read timeout is per-chunk, not a
                # total deadline; heartbeat events keep this loop ticking so the check
                # fires. A fully silent hang is still bounded by the SDK read timeout.
                if time.monotonic() - stream_start > SESSION_DEADLINE_S:
                    stop_reason = f"wall-clock deadline ({SESSION_DEADLINE_S}s) exceeded"
                    break

                if ev.type == "agent.tool_use":
                    n_tool_calls += 1
                    if n_tool_calls >= MAX_TOOL_CALLS:
                        stop_reason = f"tool-call ceiling ({MAX_TOOL_CALLS}) hit"
                        break
                elif ev.type in ("session.status_terminated", "session.error"):
                    stop_reason = f"session ended early ({ev.type})"
                    break
                elif ev.type == "session.status_idle":
                    # Idle is not the same as finished: a session also idles while it
                    # waits on US (`requires_action`). Breaking there walks away
                    # mid-analysis and reads a verdict that was never written.
                    # Terminal: end_turn (clean), retries_exhausted, budget_reached.
                    reason = _idle_stop_reason(ev)
                    if reason == "requires_action":
                        continue
                    if reason and reason != "end_turn":
                        stop_reason = f"session idled: {reason}"
                    break

        # If we cut the stream short, interrupt the session so the agent stops
        # running (and billing) server-side after we've stopped listening.
        if stop_reason:
            try:
                client.beta.sessions.events.send(
                    session.id, betas=BETAS, events=[{"type": "user.interrupt"}],
                )
            except Exception:
                pass

        # Reconstruct verdict.json from event log (handles write + edit sequences)
        verdict_content = ""
        for ev in client.beta.sessions.events.list(session.id, limit=1000, betas=BETAS):
            if ev.type == "agent.tool_use":
                if ev.name == "write" and "verdict.json" in ev.input.get("file_path", ""):
                    verdict_content = ev.input.get("content", "")
                elif ev.name == "edit" and "verdict.json" in ev.input.get("file_path", ""):
                    verdict_content = verdict_content.replace(
                        ev.input.get("old_string", ""),
                        ev.input.get("new_string", ""),
                        1,
                    )

        elapsed = time.time() - t0

        if not verdict_content:
            detail = f", {stop_reason}" if stop_reason else ""
            last_error = (
                f"Validator {idx} CMA session ended without writing verdict.json "
                f"(attempt={attempt}/{MAX_ATTEMPTS}, tool_calls={n_tool_calls}, "
                f"duration={elapsed:.0f}s{detail})"
            )
            log.warning(last_error + (" — retrying" if attempt < MAX_ATTEMPTS else ""))
            continue

        # Parse the verdict
        raw = verdict_content.strip()
        for fence in ("```json", "```"):
            if raw.startswith(fence):
                raw = raw[len(fence):]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        try:
            v = json.loads(raw)
        except json.JSONDecodeError as exc:
            last_error = (
                f"Validator {idx} verdict.json is not valid JSON "
                f"(attempt={attempt}/{MAX_ATTEMPTS}): {exc}"
            )
            log.warning(last_error + (" — retrying" if attempt < MAX_ATTEMPTS else ""))
            continue

        # Validate fields — hard errors, not retried
        if v.get("outcome") != "Reproduced":
            raise RuntimeError(f"Validator {idx} wrote unexpected outcome: {v.get('outcome')!r}")
        if v.get("confidence") not in {"High", "Medium", "Low"}:
            raise RuntimeError(f"Validator {idx} wrote invalid confidence: {v.get('confidence')!r}")

        reasoning = v.get("reasoning", "")
        sentences = [s.strip() for s in re.split(r"[.!?]", reasoning) if len(s.strip()) > 15]
        if len(sentences) < 3:
            last_error = (
                f"Validator {idx} reasoning too brief "
                f"({len(sentences)} sentences, attempt={attempt}/{MAX_ATTEMPTS}). "
                f"Content: {reasoning[:200]}"
            )
            log.warning(last_error + (" — retrying" if attempt < MAX_ATTEMPTS else ""))
            continue

        break  # verdict is good
    else:
        raise RuntimeError(last_error)

    verdict = {
        "outcome":    v["outcome"],
        "confidence": v["confidence"],
        "reasoning":  reasoning,
    }

    # Commit to Holochain DHT — retry if ValidationRequest hasn't propagated yet
    commit_payload = {
        "external_hash_b64": external_hash_b64,
        "verdict": {
            "outcome":    verdict["outcome"],
            "confidence": verdict["confidence"],
            "reasoning":  reasoning[:300],
        },
        "metrics":    metrics,
        "discipline": discipline,
    }
    for attempt in range(6):
        try:
            _node_post(f"{validator_url}/commit", commit_payload)
            break
        except RuntimeError as exc:
            if "No ValidationRequest found" in str(exc) and attempt < 5:
                log.info(f"Validator {idx} commit attempt {attempt + 1} waiting for DHT propagation (15s)")
                time.sleep(15)
            else:
                raise

    log.info(json.dumps({
        "event":       "cma_session_done",
        "validator":   idx,
        "session_id":  session.id,
        "duration_s":  round(elapsed, 1),
        "tool_calls":  n_tool_calls,
        "verdict":     verdict["outcome"],
        "user_key":    api_key != _server_api_key(),
    }))

    return verdict

# ── Verdict formation ──────────────────────────────────────────────────────────

def form_verdicts_cma(
    readme: str,
    study_output: str,
    validator_urls: list,
    external_hash_b64: str,
    metrics: list,
    discipline: dict,
    api_key: str,
) -> list:
    """Run 3 CMA validators in parallel. Each commits to DHT when it seals."""
    # One shared agent + environment for all three validators (created once / cached).
    agent_id, agent_version, env_id = _get_or_create_agent_env(api_key)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(
                _run_cma_session,
                idx + 1, url, external_hash_b64, metrics, discipline,
                readme, study_output, api_key, agent_id, agent_version, env_id,
            ): idx
            for idx, url in enumerate(validator_urls)
        }
        results: dict = {}
        errors:  dict = {}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                results[idx] = fut.result()
            except Exception as exc:
                log.error(f"Validator {idx + 1} failed: {exc}")
                errors[idx] = str(exc)

        if errors:
            failed_msgs = [f"Validator {i + 1}: {e}" for i, e in sorted(errors.items())]
            raise RuntimeError(
                f"{len(errors)}/{len(VALIDATOR_URLS)} validator(s) failed:\n"
                + "\n".join(failed_msgs)
            )

    return [results[i] for i in range(len(validator_urls))]


def form_verdicts_simple(
    readme: str,
    study_output: str,
    api_key: str,
    models: list,
    api_base: str = "",
) -> list:
    """One-shot verdicts via litellm - one model per validator.

    `models` carries one entry per validator. Three *different* models are
    three genuinely different readers, with different weights and different
    failure modes. The same model three times is one reader sampled three
    times; the caller says so out loud rather than letting the count imply
    an independence it does not have.
    """
    prompt = (
        "You are an independent scientific reproducibility evaluator.\n"
        "Work through these 5 steps, then give your verdict:\n\n"
        "1. Read the claim being made and identify exactly what result is asserted.\n"
        "2. Identify what would need to be true for that result to hold.\n"
        "3. Check whether the methodology described is capable of producing that result.\n"
        "4. Note any gaps, ambiguities, or steps that could not be replicated.\n"
        "5. Based on steps 1-4, give your verdict.\n\n"
        f"STUDY BRIEF:\n{readme}\n\n"
        f"ACTUAL EXECUTION OUTPUT:\n{study_output}\n\n"
        "Reply with ONLY a JSON object - no markdown, no explanation:\n"
        '{\n'
        '  "outcome": "Reproduced" | "FailedToReproduce",\n'
        '  "confidence": "High" | "Medium" | "Low",\n'
        '  "reasoning": "<at least 3 sentences showing your analysis>"\n'
        '}'
    )

    verdicts = []
    for i, model in enumerate(models):
        last_err = ""
        for attempt in range(5):
            kwargs = {
                "model":      model,
                "messages":   [{"role": "user", "content": prompt}],
                "max_tokens": 512,
            }
            if api_base:
                # A local server authenticates nobody, but litellm's OpenAI
                # path still wants the header present.
                #
                # ⚠️ Do not "tidy" this placeholder to the bare string "local".
                # Your Own AI treats `Authorization: Bearer local` in agent mode
                # as its own internal harness and silently stops recording the
                # exchange (inference_server.rs, own_harness). Any other value
                # keeps the record.
                kwargs["api_base"] = api_base
                kwargs["api_key"]  = api_key or "local-no-key"
                kwargs["extra_headers"] = dict(LOCAL_HEADERS)
            else:
                kwargs["api_key"] = api_key
            # Constrained only against a local server. A hosted provider is
            # already reliable at this, and would be sent a field it may not
            # take.
            fmt = (
                json_schema_format("valichord_verdict", SIMPLE_VERDICT_SCHEMA)
                if api_base and json_schema_enabled() else None
            )
            resp = complete_with_optional_schema(kwargs, fmt)
            text = resp.choices[0].message.content.strip()
            try:
                v = extract_verdict_json(text)
                if v.get("outcome") not in {"Reproduced", "FailedToReproduce"}:
                    raise ValueError(f"Invalid outcome: {v.get('outcome')!r}")
                if v.get("confidence") not in {"High", "Medium", "Low"}:
                    raise ValueError(f"Invalid confidence: {v.get('confidence')!r}")
                verdicts.append(v)
                break
            except (json.JSONDecodeError, ValueError) as exc:
                last_err = str(exc)
                if attempt == 4:
                    raise RuntimeError(
                        f"Validator {i + 1} ({model}) failed after 5 attempts: {last_err}"
                    )
    return verdicts

# ── Full protocol runners ──────────────────────────────────────────────────────

def _finish_protocol(
    external_hash_b64: str,
    metrics: list,
    verdicts: list,
    job: dict,
) -> dict:
    """Steps 5–7: phase gate → reveal → HarmonyRecord. Shared by both modes."""
    job["step"] = 5
    phase_url = f"{RESEARCHER_URL}/phase?hash={urllib.parse.quote(external_hash_b64)}"
    for _ in range(120):
        if _node_get(phase_url).get("phase") == "RevealOpen":
            break
        time.sleep(2)
    else:
        raise RuntimeError("Phase gate did not open after 240 seconds")

    reveal_resp = _node_post(f"{RESEARCHER_URL}/reveal", {
        "external_hash_b64": external_hash_b64, "metrics": metrics,
    })
    researcher_reveal_hash = reveal_resp.get("researcher_reveal_hash")

    for i, vurl in enumerate(VALIDATOR_URLS):
        _reveal_with_retry(f"{vurl}/reveal", {"external_hash_b64": external_hash_b64})
        if i < len(VALIDATOR_URLS) - 1:
            time.sleep(15)

    job["step"] = 6

    harmony_resp = _node_post(f"{VALIDATOR_URLS[0]}/create-harmony-record", {
        "external_hash_b64": external_hash_b64,
    })
    harmony_record_hash = harmony_resp.get("harmony_record_hash")
    if not harmony_record_hash:
        raise RuntimeError("HarmonyRecord was not written to the DHT")

    # Outcome + agreement derived with the same logic as the on-chain
    # HarmonyRecord (shared_types::derive_*) via the shared helper, so the
    # display can never diverge from the record the skeptic fetches.
    outcomes  = [v["outcome"] for v in verdicts]
    agreement = derive_agreement_level(outcomes)
    majority  = derive_majority_outcome(outcomes)

    return {
        "harmony_record_hash":    harmony_record_hash,
        "external_hash_b64":      external_hash_b64,
        "outcome":                majority,
        "agreement_level":        agreement,
        "validator_count":        3,
        "researcher_reveal_hash": researcher_reveal_hash,
        "record_url":             f"{RESEARCHER_URL}/record?hash={urllib.parse.quote(external_hash_b64)}",
        "validator_verdicts": [
            {
                "validator":  i + 1,
                "outcome":    v["outcome"],
                "confidence": v["confidence"],
                "reasoning":  v["reasoning"],
            }
            for i, v in enumerate(verdicts)
        ],
    }


def run_protocol_cma(
    data_hash: str,
    metrics: list,
    readme: str,
    study_output: str,
    job: dict,
    api_key: str,
) -> dict:
    """Full commit-reveal with CMA agents. Commits happen inside form_verdicts_cma."""
    disc = {"type": "ComputationalBiology"}

    lock_resp = _node_post(f"{RESEARCHER_URL}/lock-result", {
        "data_hash_hex": data_hash, "metrics": metrics,
    })
    external_hash_b64 = lock_resp["external_hash_b64"]

    _node_post(f"{RESEARCHER_URL}/submit-request", {
        "external_hash_b64":       external_hash_b64,
        "discipline":              disc,
        "num_validators_required": 3,
    })

    time.sleep(20)  # let ValidationRequest propagate via DHT gossip

    job["step"] = 3
    verdicts = form_verdicts_cma(
        readme, study_output, VALIDATOR_URLS,
        external_hash_b64, metrics, disc, api_key,
    )

    return _finish_protocol(external_hash_b64, metrics, verdicts, job)


def run_protocol_simple(
    data_hash: str,
    metrics: list,
    readme: str,
    study_output: str,
    job: dict,
    api_key: str,
    models: list,
    api_base: str = "",
) -> dict:
    """Full commit-reveal with simple one-shot litellm verdicts."""
    disc = {"type": "ComputationalBiology"}

    job["step"] = 3
    verdicts = form_verdicts_simple(readme, study_output, api_key, models, api_base)

    lock_resp = _node_post(f"{RESEARCHER_URL}/lock-result", {
        "data_hash_hex": data_hash, "metrics": metrics,
    })
    external_hash_b64 = lock_resp["external_hash_b64"]

    _node_post(f"{RESEARCHER_URL}/submit-request", {
        "external_hash_b64":       external_hash_b64,
        "discipline":              disc,
        "num_validators_required": 3,
    })

    time.sleep(20)

    for i, (vurl, verdict) in enumerate(zip(VALIDATOR_URLS, verdicts)):
        _node_post(f"{vurl}/commit", {
            "external_hash_b64": external_hash_b64,
            "verdict":           verdict,
            "metrics":           metrics,
            "discipline":        disc,
        })
        if i < len(VALIDATOR_URLS) - 1:
            time.sleep(30)

    return _finish_protocol(external_hash_b64, metrics, verdicts, job)

# ── Standalone CLI ─────────────────────────────────────────────────────────────

def _banner(n, total, msg):
    print(f"\n[{n}/{total}] {msg}")
    print("─" * 60)


def main():
    args = sys.argv[1:]

    mode = "decentralised"
    if "--mode" in args:
        idx  = args.index("--mode")
        mode = args[idx + 1] if idx + 1 < len(args) else "decentralised"

    user_key = ""
    if "--key" in args:
        idx      = args.index("--key")
        user_key = args[idx + 1] if idx + 1 < len(args) else ""

    user_model = ""
    if "--model" in args:
        idx        = args.index("--model")
        user_model = args[idx + 1] if idx + 1 < len(args) else ""

    use_local = "--local" in args

    local_models = os.environ.get("VALICHORD_LOCAL_MODELS", "")
    if "--local-models" in args:
        idx          = args.index("--local-models")
        local_models = args[idx + 1] if idx + 1 < len(args) else ""

    api_base = os.environ.get("VALICHORD_LOCAL_API_BASE", "")
    if "--api-base" in args:
        idx      = args.index("--api-base")
        api_base = args[idx + 1] if idx + 1 < len(args) else ""

    if use_local:
        api_key  = ""
        key_type = "local"
        api_base = api_base or DEFAULT_LOCAL_API_BASE
        try:
            models = resolve_local_models(local_models, api_base)
        except RuntimeError as exc:
            print(f"FATAL: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        api_key  = user_key or _server_api_key()
        key_type = detect_key_type(api_key)
        api_base = ""
        models   = [user_model or default_model_for(key_type)] * 3

        if not api_key:
            print(
                "FATAL: No API key. Set ANTHROPIC_API_KEY, pass --key, "
                "or run local models with --local.",
                file=sys.stderr,
            )
            sys.exit(1)

    print("╔══════════════════════════════════════════════════════════╗")
    print("║    ValiChord CMA Validator Demo — 3 AI Validators        ║")
    print("╚══════════════════════════════════════════════════════════╝")
    if key_type == "anthropic":
        mode_label = "CMA (multi-step, web search)"
    elif use_local:
        mode_label = f"Local one-shot ({', '.join(models)}) via {api_base}"
    else:
        mode_label = f"Simple one-shot ({models[0]})"
    print(f"  Validator mode : {mode_label}")
    print(f"  Protocol mode  : {mode.upper()}")
    print()

    _banner(1, 7, "Loading study deposit…")
    readme, data_hash, _ = load_study()
    print(f"  Data hash: {data_hash[:24]}…")

    _banner(2, 7, "Executing study code…")
    study_output = execute_study()
    print(f"  Output:\n    " + study_output.replace("\n", "\n    "))
    metrics = parse_metrics(study_output)

    job = {"step": 2}

    _banner(3, 7, "Forming 3 independent verdicts…")
    if key_type != "anthropic" and len(set(models)) < len(models):
        print(
            "  ⚠ Only "
            f"{len(set(models))} distinct model(s) for {len(models)} validators - "
            "this is one reader sampled repeatedly, not independent validators."
        )
    if key_type == "anthropic":
        _banner(4, 7, "Running commit-reveal protocol (CMA mode)…")
        result = run_protocol_cma(data_hash, metrics, readme, study_output, job, api_key)
    else:
        _banner(4, 7, "Running commit-reveal protocol (simple mode)…")
        result = run_protocol_simple(
            data_hash, metrics, readme, study_output, job, api_key, models, api_base
        )

    _banner(7, 7, "Permanent record.")
    print(f"  Outcome:         {result['outcome']} ({result['validator_count']}/3 validators)")
    print(f"  Agreement level: {result['agreement_level']}")
    print(f"  HarmonyRecord:   {result['harmony_record_hash']}")
    print()
    for v in result.get("validator_verdicts", []):
        print(f"  Validator {v['validator']}: {v['outcome']} ({v['confidence']})")
        print(f"    {v['reasoning'][:200]}…" if len(v["reasoning"]) > 200 else f"    {v['reasoning']}")
    if result.get("record_url"):
        print(f"\n  Shareable URL:\n  {result['record_url']}")
    print("\n" + "═" * 60)
    print("  Demo complete. The full ValiChord protocol ran end-to-end.")
    print("═" * 60)


if __name__ == "__main__":
    main()
