"""
Custom hypothesis demo — researcher (user) commits their answer blind,
three CMA validators independently research the claim, then the user
manually triggers the reveal once all validators have committed.
"""
import hashlib
import json
import logging
import time
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import os

import anthropic

from ai_validator_cma import _node_post, _node_get, BETAS, MODEL_CMA

RESEARCHER_URL = os.environ.get("VALICHORD_RESEARCHER_URL",  "http://132.145.34.27:3001")
VALIDATOR_URLS = [
    os.environ.get("VALICHORD_VALIDATOR_1_URL", "http://132.145.34.27:3002"),
    os.environ.get("VALICHORD_VALIDATOR_2_URL", "http://132.145.34.27:3003"),
    os.environ.get("VALICHORD_VALIDATOR_3_URL", "http://132.145.34.27:3004"),
]

log = logging.getLogger(__name__)

_MAX_ATTEMPTS = 2

VALIDATOR_CLAIM_SYSTEM = """You are an independent evaluator assessing whether a hypothesis is supported by evidence.

Work through these 5 steps in order:
1. Identify the precise claim — what exactly is being asserted?
2. Determine what evidence would convincingly support or refute it.
3. Search for that evidence using web_search and web_fetch.
4. Assess the quality, consistency, and relevance of what you found.
5. Reach your verdict: Reproduced (well-supported by evidence), PartiallyReproduced (mixed or limited evidence), or NotReproduced (weak, absent, or contradictory evidence).

You cannot see what the other validators have concluded — they are working simultaneously and independently.

REQUIRED FINAL ACTION — YOU MUST DO THIS:
Use the write tool to save your verdict to /mnt/session/verdict.json in this exact format:
{
  "outcome": "Reproduced" | "PartiallyReproduced" | "NotReproduced",
  "confidence": "High" | "Medium" | "Low",
  "reasoning": "At least 3 sentences describing what you found and why you reached this verdict."
}
Do not put your verdict in a text response. Write it to the file using the write tool.
Your session is not complete until verdict.json has been written."""

_COMPARE_TEMPLATE = """\
A researcher assessed a hypothesis and sealed their answer as a cryptographic commitment before three \
independent validators started their research. The validators worked in parallel without seeing the \
researcher's answer or each other's verdicts. Now compare them.

HYPOTHESIS: {claim}

RESEARCHER'S ANSWER (sealed before validators started, revealed only now):
{user_answer}

INDEPENDENT VALIDATOR FINDINGS:
Validator 1 ({v1_outcome}, {v1_confidence}): {v1_reasoning}
Validator 2 ({v2_outcome}, {v2_confidence}): {v2_reasoning}
Validator 3 ({v3_outcome}, {v3_confidence}): {v3_reasoning}

Assess whether the researcher's answer aligns with what the validators independently found.
Consider: overall stance, evidence cited, quality of reasoning, significant discrepancies.

Reply with ONLY valid JSON — no markdown fences, no explanation:
{{
  "outcome": "Reproduced" | "PartiallyReproduced" | "NotReproduced",
  "agreement_level": "ExactMatch" | "WithinTolerance" | "DirectionalMatch" | "Divergent",
  "summary": "One or two sentences explaining the comparison."
}}"""


def _run_cma_claim_session(
    idx: int,
    validator_url: str,
    external_hash_b64: str,
    discipline: dict,
    claim: str,
    api_key: str,
    job: dict,
) -> dict:
    """Run one CMA validator session for a free-text claim. Commits to DHT when done."""
    client = anthropic.Anthropic(api_key=api_key)

    time.sleep((idx - 1) * 8)

    env = client.beta.environments.create(
        name=f"valichord-claim-v{idx}-{int(time.time())}",
        config={"type": "anthropic_cloud", "networking": {"type": "unrestricted"}},
    )
    agent = client.beta.agents.create(
        name=f"valichord-claim-validator-{idx}",
        model=MODEL_CMA,
        system=VALIDATOR_CLAIM_SYSTEM,
        tools=[{
            "type": "agent_toolset_20260401",
            "configs": [{"name": "web_search"}, {"name": "web_fetch"}, {"name": "write"}],
        }],
        betas=BETAS,
    )

    last_error = ""
    t0 = time.time()
    v = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        session = client.beta.sessions.create(
            agent={"type": "agent", "id": agent.id, "version": agent.version},
            environment_id=env.id,
            betas=BETAS,
        )

        client.beta.sessions.events.send(
            session.id,
            betas=BETAS,
            events=[{"type": "user.message", "content": [{"type": "text", "text": (
                f"You are Validator {idx} in a 3-validator independent review. "
                f"The other validators are working simultaneously and you cannot see their conclusions.\n\n"
                f"HYPOTHESIS TO EVALUATE:\n{claim}\n\n"
                f"Research this hypothesis independently. Use web_search to find supporting or refuting evidence. "
                f"Work through all 5 steps. When done, use the write tool to save your verdict to "
                f"/mnt/session/verdict.json — do not put your verdict in a text response."
            )}]}],
        )

        n_tool_calls = 0
        with client.beta.sessions.events.stream(session.id, betas=BETAS) as stream:
            for ev in stream:
                if ev.type == "agent.tool_use":
                    n_tool_calls += 1
                elif ev.type == "session.status_idle":
                    break

        verdict_content = ""
        for ev in client.beta.sessions.events.list(session.id, limit=1000, betas=BETAS):
            if ev.type == "agent.tool_use":
                path = ev.input.get("file_path", "").lower()
                if ev.name == "write" and "verdict" in path:
                    verdict_content = ev.input.get("content", "")
                elif ev.name == "edit" and "verdict" in path:
                    verdict_content = verdict_content.replace(
                        ev.input.get("old_string", ""),
                        ev.input.get("new_string", ""),
                        1,
                    )

        elapsed = time.time() - t0

        if not verdict_content:
            last_error = (
                f"Validator {idx} session ended without writing verdict.json "
                f"(attempt={attempt}/{_MAX_ATTEMPTS}, tool_calls={n_tool_calls}, duration={elapsed:.0f}s)"
            )
            log.warning(last_error + (" — retrying with fresh session" if attempt < _MAX_ATTEMPTS else ""))
            continue

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
                f"(attempt={attempt}/{_MAX_ATTEMPTS}): {exc}"
            )
            log.warning(last_error + (" — retrying" if attempt < _MAX_ATTEMPTS else ""))
            continue

        if v.get("outcome") not in {"Reproduced", "PartiallyReproduced", "NotReproduced"}:
            raise RuntimeError(f"Validator {idx} wrote invalid outcome: {v.get('outcome')!r}")
        if v.get("confidence") not in {"High", "Medium", "Low"}:
            raise RuntimeError(f"Validator {idx} wrote invalid confidence: {v.get('confidence')!r}")

        break  # verdict is good
    else:
        raise RuntimeError(last_error)

    verdict = {
        "outcome":    v["outcome"],
        "confidence": v["confidence"],
        "reasoning":  v.get("reasoning", ""),
    }

    commit_payload = {
        "external_hash_b64": external_hash_b64,
        "verdict": {
            "outcome":    verdict["outcome"],
            "confidence": verdict["confidence"],
            "reasoning":  verdict["reasoning"][:300],
        },
        "metrics": [{
            "metric_name":      "claim_assessment",
            "produced_value":   verdict["outcome"],
            "expected_value":   "see_researcher_reveal",
            "within_tolerance": True,
        }],
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

    job["validators_committed"] = job.get("validators_committed", 0) + 1

    log.info(json.dumps({
        "event":      "cma_claim_session_done",
        "validator":  idx,
        "session_id": session.id,
        "duration_s": round(elapsed, 1),
        "tool_calls": n_tool_calls,
        "verdict":    verdict["outcome"],
    }))

    return verdict


_DISCIPLINE_PROMPT = """\
Classify the following hypothesis or question into an academic discipline.

HYPOTHESIS: {claim}

Reply with ONLY valid JSON — no markdown fences, no explanation:
{{
  "discipline": "2-4 word discipline name (e.g. Social Psychology, Behavioural Economics, Exercise Science)"
}}"""


def classify_discipline(claim: str, api_key: str) -> dict:
    """Return a Discipline struct for the DHT — {"type": "Other", "content": "<name>"}."""
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=MODEL_CMA,
        max_tokens=64,
        messages=[{"role": "user", "content": _DISCIPLINE_PROMPT.format(claim=claim)}],
    )
    text = resp.content[0].text.strip()
    for fence in ("```json", "```"):
        if text.startswith(fence):
            text = text[len(fence):]
    if text.endswith("```"):
        text = text[:-3]
    try:
        name = json.loads(text.strip()).get("discipline", "General Science")
    except Exception:
        name = "General Science"
    return {"type": "Other", "content": name}


def compare_answers(
    claim: str,
    user_answer: str,
    validator_verdicts: list,
    api_key: str,
) -> dict:
    """Compare researcher's sealed answer against validator findings. One short Claude call."""
    client = anthropic.Anthropic(api_key=api_key)

    def _v(i):
        vd = validator_verdicts[i]
        return vd["outcome"], vd["confidence"], vd["reasoning"]

    v1o, v1c, v1r = _v(0)
    v2o, v2c, v2r = _v(1)
    v3o, v3c, v3r = _v(2)

    prompt = _COMPARE_TEMPLATE.format(
        claim=claim,
        user_answer=user_answer,
        v1_outcome=v1o, v1_confidence=v1c, v1_reasoning=v1r,
        v2_outcome=v2o, v2_confidence=v2c, v2_reasoning=v2r,
        v3_outcome=v3o, v3_confidence=v3c, v3_reasoning=v3r,
    )

    resp = client.messages.create(
        model=MODEL_CMA,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    for fence in ("```json", "```"):
        if text.startswith(fence):
            text = text[len(fence):]
    if text.endswith("```"):
        text = text[:-3]

    try:
        result = json.loads(text.strip())
    except json.JSONDecodeError:
        log.warning("compare_answers: Claude returned non-JSON; using fallback comparison result")
        return {
            "outcome":         "PartiallyReproduced",
            "agreement_level": "DirectionalMatch",
            "summary":         "Automated comparison unavailable. Review individual validator verdicts above.",
        }
    return {
        "outcome":         result.get("outcome",         "NotReproduced"),
        "agreement_level": result.get("agreement_level", "DirectionalMatch"),
        "summary":         result.get("summary",         ""),
    }


def start_commit_phase(claim: str, user_answer: str, api_key: str, job: dict) -> None:
    """
    Phase 1 — called in a background thread.

    Hashes the researcher's answer and commits it to the DHT, then runs 3 CMA
    validators in parallel. Each validator calls /commit when it finishes, which
    increments job['validators_committed']. Sets job['phase'] = 'awaiting_reveal'
    when all 3 have committed. Does NOT release _custom_running — that lock is
    held until finish_reveal_phase completes (or an error occurs here).
    """
    run_salt = uuid.uuid4().bytes

    # Metrics stored at lock time and reused verbatim at reveal time
    metrics = [{
        "metric_name":      "researcher_assessment",
        "produced_value":   user_answer[:500],
        "expected_value":   "validated_by_panel",
        "within_tolerance": True,
    }]
    job["metrics"] = metrics

    data_hash = hashlib.sha256((claim + user_answer).encode() + run_salt).hexdigest()

    lock_resp = _node_post(f"{RESEARCHER_URL}/lock-result", {
        "data_hash_hex": data_hash,
        "metrics":       metrics,
    })
    external_hash_b64 = lock_resp["external_hash_b64"]
    job["external_hash_b64"] = external_hash_b64

    disc = classify_discipline(claim, api_key)
    _node_post(f"{RESEARCHER_URL}/submit-request", {
        "external_hash_b64":       external_hash_b64,
        "discipline":              disc,
        "num_validators_required": 3,
    })

    time.sleep(30)  # let ValidationRequest propagate via DHT gossip

    job["phase"]               = "committing"
    job["validators_committed"] = 0

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(
                _run_cma_claim_session,
                idx + 1, url, external_hash_b64, disc, claim, api_key, job,
            ): idx
            for idx, url in enumerate(VALIDATOR_URLS)
        }
        results = {}
        for fut in as_completed(futures):
            idx = futures[fut]
            results[idx] = fut.result()

    verdicts = [results[i] for i in range(len(VALIDATOR_URLS))]
    job["verdicts"] = verdicts
    job["phase"]    = "awaiting_reveal"


def finish_reveal_phase(claim: str, user_answer: str, job: dict, api_key: str) -> None:
    """
    Phase 2 — triggered by the user clicking Reveal.

    Waits for the DHT phase gate, then researcher reveals → validators reveal →
    comparison step → HarmonyRecord. Sets job['phase'] = 'done' on success.
    """
    external_hash_b64 = job["external_hash_b64"]
    verdicts          = job["verdicts"]
    metrics           = job["metrics"]

    job["phase"] = "revealing"

    phase_url = f"{RESEARCHER_URL}/phase?hash={urllib.parse.quote(external_hash_b64)}"
    for _ in range(120):
        if _node_get(phase_url).get("phase") == "RevealOpen":
            break
        time.sleep(2)
    else:
        raise RuntimeError("Phase gate did not open after 240 seconds")

    reveal_resp = _node_post(f"{RESEARCHER_URL}/reveal", {
        "external_hash_b64": external_hash_b64,
        "metrics":           metrics,
    })
    researcher_reveal_hash = reveal_resp.get("researcher_reveal_hash")

    for i, vurl in enumerate(VALIDATOR_URLS):
        _node_post(f"{vurl}/reveal", {"external_hash_b64": external_hash_b64})
        if i < len(VALIDATOR_URLS) - 1:
            time.sleep(15)

    comparison = compare_answers(claim, user_answer, verdicts, api_key)

    harmony_resp = _node_post(f"{VALIDATOR_URLS[0]}/create-harmony-record", {
        "external_hash_b64": external_hash_b64,
    })
    harmony_record_hash = harmony_resp.get("harmony_record_hash")
    if not harmony_record_hash:
        raise RuntimeError("HarmonyRecord was not written to the DHT")

    job["result"] = {
        "harmony_record_hash":    harmony_record_hash,
        "external_hash_b64":      external_hash_b64,
        "outcome":                comparison["outcome"],
        "agreement_level":        comparison["agreement_level"],
        "comparison_summary":     comparison["summary"],
        "researcher_answer":      user_answer,
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
    job["phase"]   = "done"
    job["status"]  = "done"
