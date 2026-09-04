"""
Custom hypothesis demo — researcher (user) commits their answer blind,
three CMA validators independently research the claim, then the user
manually triggers the reveal once all validators have committed.
"""
import hashlib
import json
import logging
import threading
import time
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import os

import anthropic

from ai_validator_cma import (
    _node_post, _node_get, BETAS, MODEL_CMA, MAX_TOOL_CALLS, SESSION_DEADLINE_S,
    _find_named, _idle_stop_reason,
)
from agreement import derive_agreement_level, derive_majority_outcome
import local_mode

RESEARCHER_URL = os.environ.get("VALICHORD_RESEARCHER_URL",  "http://localhost:3001")
VALIDATOR_URLS = [
    os.environ.get("VALICHORD_VALIDATOR_1_URL", "http://localhost:3002"),
    os.environ.get("VALICHORD_VALIDATOR_2_URL", "http://localhost:3003"),
    os.environ.get("VALICHORD_VALIDATOR_3_URL", "http://localhost:3004"),
]

log = logging.getLogger(__name__)

_MAX_ATTEMPTS = 2

# The three validators run in a thread pool and all bump the same counter.
# Read-modify-write from three threads can lose an update, which would strand
# the run at 2/3 forever, since the phase transition is driven separately.
_COMMIT_COUNT_LOCK = threading.Lock()


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


_CLAIM_AGENT_ENV_CACHE: dict = {}
_CLAIM_AGENT_ENV_LOCK  = threading.Lock()
_CLAIM_AGENT_ENV_CACHE_MAX = 32  # visitor keys are one-shot; bound the cache

# Stable names for the persistent control-plane objects. Distinct from the
# reproducibility validator's — this agent carries a different system prompt.
CMA_CLAIM_AGENT_NAME = "valichord-claim-validator"
CMA_CLAIM_ENV_NAME   = "valichord-claim-validator-env"


def _commit_verdict(idx, validator_url, external_hash_b64, verdict, discipline, job):
    """Post one validator's verdict to its node, then count it.

    Shared by the hosted CMA path and the local-model path so the two cannot
    drift in what they actually write to the DHT.
    """
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

    with _COMMIT_COUNT_LOCK:
        job["validators_committed"] = job.get("validators_committed", 0) + 1


def _run_validators(fn, args_for, workers: int = 3):
    """Run the three validators and collect results and failures.

    All-or-nothing is preserved: the caller raises if any validator failed.

    `workers=1` runs them one after another. That is required for local models,
    not a preference - see the call site.
    """
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(fn, *args_for(idx, url)): idx
            for idx, url in enumerate(VALIDATOR_URLS)
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
    return results, errors


def _run_local_claim_session(idx, validator_url, external_hash_b64, discipline,
                             claim, sources, job, cfg):
    """The local-model equivalent of _run_cma_claim_session.

    No sandbox, no agent, no event stream: the verdict comes back from a plain
    completion. Everything the protocol sees afterwards is identical.
    """
    t0 = time.time()
    verdict = local_mode.run_local_claim_validator(idx, claim, sources, cfg)

    _commit_verdict(idx, validator_url, external_hash_b64, verdict, discipline, job)

    log.info(json.dumps({
        "event":      "local_claim_session_done",
        "validator":  idx,
        "model":      verdict.get("model", ""),
        "duration_s": round(time.time() - t0, 1),
        "verdict":    verdict["outcome"],
        "quotes":     len(verdict.get("evidence", [])),
        "unverified": sum(1 for e in verdict.get("evidence", []) if not e.get("verified")),
    }))

    return verdict


def _get_or_create_agent_env(api_key: str) -> tuple:
    """Return (agent_id, agent_version, env_id) for the claim-evaluation validator
    config — shared by all 3 validators. Each session still provisions its own
    isolated container.

    Agents and environments are persistent, VERSIONED control-plane objects, not
    per-run resources: minting a pair per run accumulates orphans, pays the create
    latency in the request path, and discards the version pinning that makes a run
    reproducible. Resolution order, cheapest first:
      1. process cache — keyed by SHA-256 of the API key, since raw visitor keys
         must not persist in process memory, and size-capped so one-shot visitor
         keys don't accumulate
      2. VALICHORD_CMA_CLAIM_AGENT_ID / VALICHORD_CMA_CLAIM_ENV_ID — provision once
         out of band and the request path never touches the control plane at all
      3. lookup by stable name
      4. create — first run for a given key only
    """
    cache_key = hashlib.sha256(api_key.encode()).hexdigest()
    with _CLAIM_AGENT_ENV_LOCK:
        cached = _CLAIM_AGENT_ENV_CACHE.get(cache_key)
        if cached is not None:
            return cached

        client = anthropic.Anthropic(api_key=api_key)

        # -- Environment ------------------------------------------------------
        env_id = os.environ.get("VALICHORD_CMA_CLAIM_ENV_ID", "").strip()
        if not env_id:
            env = _find_named(client.beta.environments.list(), CMA_CLAIM_ENV_NAME)
            if env is None:
                try:
                    env = client.beta.environments.create(
                        name=CMA_CLAIM_ENV_NAME,
                        config={"type": "cloud", "networking": {"type": "unrestricted"}},
                    )
                except Exception:
                    # Environment names are unique (409 on collision) — another
                    # process won the race. Re-scan rather than fail the run.
                    env = _find_named(client.beta.environments.list(), CMA_CLAIM_ENV_NAME)
                    if env is None:
                        raise
            env_id = env.id

        # -- Agent ------------------------------------------------------------
        agent_id = os.environ.get("VALICHORD_CMA_CLAIM_AGENT_ID", "").strip()
        if agent_id:
            agent = client.beta.agents.retrieve(agent_id)
        else:
            found = _find_named(client.beta.agents.list(), CMA_CLAIM_AGENT_NAME)
            if found is not None:
                # Retrieve the canonical object — don't assume the list item carries
                # `version`, which sessions.create needs in order to pin.
                agent = client.beta.agents.retrieve(found.id)
            else:
                agent = client.beta.agents.create(
                    name=CMA_CLAIM_AGENT_NAME,
                    model=MODEL_CMA,
                    system=VALIDATOR_CLAIM_SYSTEM,
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
        while len(_CLAIM_AGENT_ENV_CACHE) >= _CLAIM_AGENT_ENV_CACHE_MAX:
            _CLAIM_AGENT_ENV_CACHE.pop(next(iter(_CLAIM_AGENT_ENV_CACHE)))
        _CLAIM_AGENT_ENV_CACHE[cache_key] = result
        return result


def _run_cma_claim_session(
    idx: int,
    validator_url: str,
    external_hash_b64: str,
    discipline: dict,
    claim: str,
    api_key: str,
    job: dict,
    agent_id: str,
    agent_version,
    env_id: str,
) -> dict:
    """Run one CMA validator session for a free-text claim (shared agent + environment,
    own session/container). Commits to DHT when done."""
    client = anthropic.Anthropic(api_key=api_key)

    time.sleep((idx - 1) * 8)

    last_error = ""
    t0 = time.time()
    v = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        session = client.beta.sessions.create(
            agent={"type": "agent", "id": agent_id, "version": agent_version},
            environment_id=env_id,
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
        stop_reason  = ""
        stream_start = time.monotonic()
        with client.beta.sessions.events.stream(session.id, betas=BETAS) as stream:
            for ev in stream:
                # Runs FIRST so it still fires on iterations that `continue` below.
                # Per-chunk read timeout isn't a total deadline; enforce one here.
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

        # Cut short → interrupt so the agent stops running/billing server-side.
        if stop_reason:
            try:
                client.beta.sessions.events.send(
                    session.id, betas=BETAS, events=[{"type": "user.interrupt"}],
                )
            except Exception:
                pass

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
            detail = f", {stop_reason}" if stop_reason else ""
            last_error = (
                f"Validator {idx} session ended without writing verdict.json "
                f"(attempt={attempt}/{_MAX_ATTEMPTS}, tool_calls={n_tool_calls}, "
                f"duration={elapsed:.0f}s{detail})"
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

    _commit_verdict(idx, validator_url, external_hash_b64, verdict, discipline, job)

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


def classify_discipline(claim: str, api_key: str, local=None) -> dict:
    """Return a Discipline struct for the DHT — {"type": "Other", "content": "<name>"}."""
    if local is not None:
        try:
            raw = local_mode.complete_json(
                local, local.model_for(1),
                _DISCIPLINE_PROMPT.format(claim=claim), max_tokens=64,
                schema=local_mode.DISCIPLINE_SCHEMA, schema_name="valichord_discipline",
            )
            name = str(raw.get("discipline", "") or "").strip() or "General Science"
        except Exception as exc:
            # Same posture as the hosted path: a discipline label is not worth
            # failing a run over.
            log.warning(f"classify_discipline (local) fell back to General Science: {exc}")
            name = "General Science"
        return {"type": "Other", "content": name}

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
    local=None,
) -> dict:
    """Compare researcher's sealed answer against validator findings. One short call."""
    client = None if local is not None else anthropic.Anthropic(api_key=api_key)

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

    if local is not None:
        # Only the prose summary comes from here — outcome and agreement_level
        # are derived from the verdicts by shared logic downstream — so a weak
        # local model degrades one sentence of copy, not the verdict.
        try:
            result = local_mode.complete_json(
                local, local.model_for(1), prompt, max_tokens=512,
                schema=local_mode.COMPARISON_SCHEMA, schema_name="valichord_comparison",
            )
        except Exception as exc:
            log.warning(f"compare_answers (local) failed, using fallback: {exc}")
            return {
                "outcome":         "PartiallyReproduced",
                "agreement_level": "DirectionalMatch",
                "summary":         "Automated comparison unavailable. Review individual validator verdicts above.",
            }
        return {
            "outcome":         local_mode.normalise_outcome(result.get("outcome")) or "NotReproduced",
            "agreement_level": result.get("agreement_level", "DirectionalMatch"),
            "summary":         result.get("summary", ""),
        }

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


def _claim_headline(outcomes: list, comparison_outcome: str) -> str:
    """Human headline for the claim demo: a verdict on the hypothesis + how
    unanimous the validators were + whether the researcher's sealed answer aligned.

    The reproducibility-framed outcome/agreement_level are kept for the record but
    read confusingly for a free-text claim — a *unanimous refutation* scores zero
    'reproduction', so the agreement scale bottoms out at "UnableToAssess" even
    though the validators assessed it clearly and agreed. This headline speaks the
    claim vocabulary instead.
    """
    from collections import Counter

    def _bucket(o: str) -> str:
        if o == "Reproduced":          return "Supported"
        if o == "PartiallyReproduced": return "Partially supported"
        if o in ("NotReproduced", "FailedToReproduce"): return "Refuted"
        return "Inconclusive"

    total = len(outcomes) or 1
    verdict, top_n = Counter(_bucket(o) for o in outcomes).most_common(1)[0]
    if top_n >= total:
        agreement = "validators unanimous"
    elif top_n <= 1:
        agreement = "validators split"
    else:
        agreement = f"{top_n} of {total} validators agree"

    align = {
        "Reproduced":          "matches your sealed answer",
        "PartiallyReproduced": "partly matches your sealed answer",
        "NotReproduced":       "diverges from your sealed answer",
    }.get(comparison_outcome, "")

    headline = f"{verdict} — {agreement}"
    return f"{headline} ({align})" if align else headline


def start_commit_phase(claim: str, user_answer: str, api_key: str, job: dict,
                       sources_raw: str = "", local=None) -> None:
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

    # Sources are sealed alongside the claim and the answer. Without that, the
    # evidence the validators were shown could be swapped after the verdicts
    # land and the commitment would still verify.
    sources = local_mode.split_sources(sources_raw)
    job["sources"] = [
        {"index": s["index"], "sha256": s["sha256"], "chars": len(s["text"])}
        for s in sources
    ]
    preimage = claim + user_answer
    if sources:
        preimage += local_mode.sources_digest(sources)

    data_hash = hashlib.sha256(preimage.encode() + run_salt).hexdigest()

    lock_resp = _node_post(f"{RESEARCHER_URL}/lock-result", {
        "data_hash_hex": data_hash,
        "metrics":       metrics,
    })
    external_hash_b64 = lock_resp["external_hash_b64"]
    job["external_hash_b64"] = external_hash_b64

    disc = classify_discipline(claim, api_key, local=local)
    _node_post(f"{RESEARCHER_URL}/submit-request", {
        "external_hash_b64":       external_hash_b64,
        "discipline":              disc,
        "num_validators_required": 3,
    })

    time.sleep(30)  # let ValidationRequest propagate via DHT gossip

    job["phase"]               = "committing"
    job["validators_committed"] = 0

    if local is not None:
        # One at a time, deliberately. Your Own AI holds exactly ONE chat model
        # loaded (`current_model: Mutex<Option<String>>`); naming a different AI
        # kills the llama-server and respawns it on the new file. Three
        # concurrent calls naming three different models would therefore fight
        # over one loader, each swap killing the load the last one was waiting
        # on. Sequential is slower and it finishes.
        #
        # Nothing about blindness depends on this: validators still cannot see
        # each other, and every commit still lands before any reveal. It also
        # makes the progress dots honest, since the UI renders the committed
        # count as an ordered prefix and the parallel version could light them
        # out of order.
        results, errors = _run_validators(
            _run_local_claim_session,
            lambda idx, url: (idx + 1, url, external_hash_b64, disc, claim, sources, job, local),
            workers=1,
        )
    else:
        # One shared agent + environment for all three validators (created once / cached).
        agent_id, agent_version, env_id = _get_or_create_agent_env(api_key)
        results, errors = _run_validators(
            _run_cma_claim_session,
            lambda idx, url: (idx + 1, url, external_hash_b64, disc, claim, api_key, job,
                              agent_id, agent_version, env_id),
        )

    if errors:
        failed_msgs = [f"Validator {i + 1}: {e}" for i, e in sorted(errors.items())]
        raise RuntimeError(
            f"{len(errors)}/{len(VALIDATOR_URLS)} validator(s) failed:\n"
            + "\n".join(failed_msgs)
        )

    verdicts = [results[i] for i in range(len(VALIDATOR_URLS))]
    job["verdicts"] = verdicts
    job["phase"]    = "awaiting_reveal"


def finish_reveal_phase(claim: str, user_answer: str, job: dict, api_key: str,
                        local=None) -> None:
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
        _reveal_with_retry(f"{vurl}/reveal", {"external_hash_b64": external_hash_b64})
        if i < len(VALIDATOR_URLS) - 1:
            time.sleep(15)

    comparison = compare_answers(claim, user_answer, verdicts, api_key, local=local)

    harmony_resp = _node_post(f"{VALIDATOR_URLS[0]}/create-harmony-record", {
        "external_hash_b64": external_hash_b64,
    })
    harmony_record_hash = harmony_resp.get("harmony_record_hash")
    if not harmony_record_hash:
        raise RuntimeError("HarmonyRecord was not written to the DHT")

    # Outcome + agreement_level are derived from the validator verdicts with the
    # same logic as the on-chain HarmonyRecord (shared_types::derive_*), NOT from
    # the free-form compare_answers adjudication — otherwise the label could
    # contradict the per-validator verdicts shown beside it (e.g. 3/3 Reproduced
    # displayed as "WithinTolerance"). compare_answers is kept only for its
    # human-readable summary.
    outcomes = [v["outcome"] for v in verdicts]
    job["result"] = {
        "harmony_record_hash":    harmony_record_hash,
        "external_hash_b64":      external_hash_b64,
        "outcome":                derive_majority_outcome(outcomes),
        "agreement_level":        derive_agreement_level(outcomes),
        "headline":               _claim_headline(outcomes, comparison["outcome"]),
        "comparison_summary":     comparison["summary"],
        "researcher_answer":      user_answer,
        "validator_count":        3,
        "researcher_reveal_hash": researcher_reveal_hash,
        "record_url":             f"{RESEARCHER_URL}/record?hash={urllib.parse.quote(external_hash_b64)}",
        "sources":                job.get("sources", []),
        "validator_verdicts": [
            {
                "validator":  i + 1,
                "outcome":    v["outcome"],
                "confidence": v["confidence"],
                "reasoning":  v["reasoning"],
                # Present only on the local path; the hosted validators search
                # the web rather than a supplied corpus, so they have no quote
                # to check against a document hash.
                "evidence":   v.get("evidence", []),
                "model":      v.get("model", ""),
            }
            for i, v in enumerate(verdicts)
        ],
    }
    job["phase"]   = "done"
    job["status"]  = "done"
