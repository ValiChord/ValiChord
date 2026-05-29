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
    export VALICHORD_RESEARCHER_URL=http://132.145.34.27:3001
    export VALICHORD_VALIDATOR_1_URL=http://132.145.34.27:3002
    export VALICHORD_VALIDATOR_2_URL=http://132.145.34.27:3003
    export VALICHORD_VALIDATOR_3_URL=http://132.145.34.27:3004
    python3 demo/ai_validator_cma.py --mode decentralised

    # With another provider's key:
    python3 demo/ai_validator_cma.py --mode decentralised --key sk-proj-... --model openai/gpt-4o-mini
"""

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import NoReturn

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

DEMO_DIR  = Path(__file__).parent
STUDY_DIR = DEMO_DIR / "synthetic_study"

BETAS     = ["managed-agents-2026-04-01"]
MODEL_CMA = "claude-sonnet-4-6"

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

# ── Node HTTP helpers ──────────────────────────────────────────────────────────

def _node_post(url: str, payload: dict, timeout: int = 600) -> dict:
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST",
    )
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

def _run_cma_session(
    idx: int,
    validator_url: str,
    external_hash_b64: str,
    metrics: list,
    discipline: dict,
    readme: str,
    study_output: str,
    api_key: str,
) -> dict:
    """Run one CMA validator session. Commits to DHT when the agent calls seal_attestation."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    # Stagger starts slightly so commits don't all hit the DHT simultaneously
    time.sleep((idx - 1) * 8)

    env = client.beta.environments.create(
        name=f"valichord-v{idx}-{int(time.time())}",
        config={"type": "anthropic_cloud", "networking": {"type": "unrestricted"}},
    )

    agent = client.beta.agents.create(
        name=f"valichord-validator-{idx}",
        model=MODEL_CMA,
        system=VALIDATOR_SYSTEM,
        tools=[
            {
                "type": "agent_toolset_20260401",
                "configs": [
                    {"name": "web_search"},
                    {"name": "web_fetch"},
                    {"name": "write"},
                ],
            },
        ],
        betas=BETAS,
    )

    MAX_ATTEMPTS = 2
    last_error   = ""
    t0           = time.time()
    v = reasoning = None  # set inside loop; referenced in log after break

    for attempt in range(1, MAX_ATTEMPTS + 1):
        session = client.beta.sessions.create(
            agent={"type": "agent", "id": agent.id, "version": agent.version},
            environment_id=env.id,
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

        with client.beta.sessions.events.stream(session.id, betas=BETAS) as stream:
            for ev in stream:
                if ev.type == "agent.tool_use":
                    n_tool_calls += 1
                elif ev.type == "session.status_idle":
                    break

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
            last_error = (
                f"Validator {idx} CMA session ended without writing verdict.json "
                f"(attempt={attempt}/{MAX_ATTEMPTS}, tool_calls={n_tool_calls}, duration={elapsed:.0f}s)"
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
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(
                _run_cma_session,
                idx + 1, url, external_hash_b64, metrics, discipline,
                readme, study_output, api_key,
            ): idx
            for idx, url in enumerate(validator_urls)
        }
        results = {}
        for fut in as_completed(futures):
            idx = futures[fut]
            results[idx] = fut.result()

    return [results[i] for i in range(len(validator_urls))]


def form_verdicts_simple(
    readme: str,
    study_output: str,
    api_key: str,
    model: str,
) -> list:
    """One-shot verdicts via litellm — works with any AI provider key."""
    try:
        import litellm
    except ImportError:
        raise RuntimeError("litellm not installed. Run: pip install litellm")

    prompt = (
        "You are an independent scientific reproducibility evaluator.\n"
        "Work through these 5 steps, then give your verdict:\n\n"
        "1. Read the claim being made and identify exactly what result is asserted.\n"
        "2. Identify what would need to be true for that result to hold.\n"
        "3. Check whether the methodology described is capable of producing that result.\n"
        "4. Note any gaps, ambiguities, or steps that could not be replicated.\n"
        "5. Based on steps 1–4, give your verdict.\n\n"
        f"STUDY BRIEF:\n{readme}\n\n"
        f"ACTUAL EXECUTION OUTPUT:\n{study_output}\n\n"
        "Reply with ONLY a JSON object — no markdown, no explanation:\n"
        '{\n'
        '  "outcome": "Reproduced" | "FailedToReproduce",\n'
        '  "confidence": "High" | "Medium" | "Low",\n'
        '  "reasoning": "<at least 3 sentences showing your analysis>"\n'
        '}'
    )

    verdicts = []
    for i in range(3):
        last_err = ""
        for attempt in range(5):
            resp = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                api_key=api_key,
                max_tokens=512,
            )
            text = resp.choices[0].message.content.strip()
            for fence in ("```json", "```"):
                if text.startswith(fence):
                    text = text[len(fence):]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            try:
                v = json.loads(text)
                if v.get("outcome") not in {"Reproduced", "FailedToReproduce"}:
                    raise ValueError(f"Invalid outcome: {v.get('outcome')!r}")
                if v.get("confidence") not in {"High", "Medium", "Low"}:
                    raise ValueError(f"Invalid confidence: {v.get('confidence')!r}")
                verdicts.append(v)
                break
            except (json.JSONDecodeError, ValueError) as exc:
                last_err = str(exc)
                if attempt == 4:
                    raise RuntimeError(f"Validator {i + 1} failed after 5 attempts: {last_err}")
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

    outcomes  = [v["outcome"] for v in verdicts]
    n_repro   = outcomes.count("Reproduced")
    n_partial = outcomes.count("PartiallyReproduced")
    rate      = (n_repro + n_partial) / len(outcomes)
    agreement = (
        "ExactMatch"       if rate >= 0.90 else
        "WithinTolerance"  if rate >= 0.70 else
        "DirectionalMatch" if rate >= 0.50 else
        "Divergent"        if n_repro + n_partial > 0 else
        "UnableToAssess"
    )
    majority = (
        "Reproduced"          if n_repro   >= 2 else
        "PartiallyReproduced" if n_partial >= 2 else
        "FailedToReproduce"   if outcomes.count("FailedToReproduce") >= 2 else
        "UnableToAssess"
    )

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
    model: str,
) -> dict:
    """Full commit-reveal with simple one-shot litellm verdicts."""
    disc = {"type": "ComputationalBiology"}

    job["step"] = 3
    verdicts = form_verdicts_simple(readme, study_output, api_key, model)

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

    api_key  = user_key or _server_api_key()
    key_type = detect_key_type(api_key)
    model    = user_model or default_model_for(key_type)

    if not api_key:
        print("FATAL: No API key. Set ANTHROPIC_API_KEY or pass --key.", file=sys.stderr)
        sys.exit(1)

    print("╔══════════════════════════════════════════════════════════╗")
    print("║    ValiChord CMA Validator Demo — 3 AI Validators        ║")
    print("╚══════════════════════════════════════════════════════════╝")
    mode_label = "CMA (multi-step, web search)" if key_type == "anthropic" else f"Simple one-shot ({model})"
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
    if key_type == "anthropic":
        _banner(4, 7, "Running commit-reveal protocol (CMA mode)…")
        result = run_protocol_cma(data_hash, metrics, readme, study_output, job, api_key)
    else:
        _banner(4, 7, "Running commit-reveal protocol (simple mode)…")
        result = run_protocol_simple(data_hash, metrics, readme, study_output, job, api_key, model)

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
