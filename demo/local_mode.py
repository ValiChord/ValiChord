"""Local-model path for the custom (web) demo.

Additive by design. With `VALICHORD_LOCAL` unset, `LocalConfig.from_env()`
returns None, nothing in this module runs, and the hosted Anthropic + web-search
path is untouched. The Render deployment keeps working exactly as before.

Why this is not simply "the same demo, cheaper models"
------------------------------------------------------
The hosted validators are given `web_search` and told to go and find evidence
for the claim. Their whole rubric is written in terms of what they retrieved -
NotReproduced is defined as "weak, absent, or contradictory evidence". Point
that prompt at an offline model and evidence is absent by construction, so a
rule-following validator can refute everything put to it while the pipeline
still runs green and mints a real, permanent record.

So the local validator is given a different job, not a smaller model for the
same one: it judges the claim **only against source material the visitor
supplies**, quotes the passages it relied on, and is told plainly that if the
sources do not address the claim, that is an answer rather than a gap to fill
from memory. "Absent evidence" means something checkable here, which is what
made the swap safe to make at all.
"""
import hashlib
import json
import os
import re
from dataclasses import dataclass

from ai_validator_cma import _normalise_local_model, extract_verdict_json

DEFAULT_LOCAL_API_BASE = "http://127.0.0.1:11435/v1"

# The wire vocabulary the protocol and agreement.py already speak. The model is
# asked for the Supported/... words instead, because "Reproduced" is a poor
# description of reading a document and small models follow a prompt that means
# what it says. Both vocabularies are accepted on the way back in.
WIRE_OUTCOMES = ("Reproduced", "PartiallyReproduced", "NotReproduced")

_OUTCOME_ALIASES = {
    "supported":           "Reproduced",
    "partiallysupported":  "PartiallyReproduced",
    "notsupported":        "NotReproduced",
    "unsupported":         "NotReproduced",
    "reproduced":          "Reproduced",
    "partiallyreproduced": "PartiallyReproduced",
    "notreproduced":       "NotReproduced",
}

_CONFIDENCES = ("High", "Medium", "Low")


@dataclass
class LocalConfig:
    """Where the local models live, and which one each validator gets."""

    api_base: str
    models:   list

    @classmethod
    def from_env(cls):
        """Return a config, or None when local mode is off.

        None is the signal the rest of the demo branches on, so the hosted path
        needs no flag of its own and cannot be switched by accident.
        """
        flag = os.environ.get("VALICHORD_LOCAL", "").strip().lower()
        if flag not in {"1", "true", "yes", "on"}:
            return None
        api_base = os.environ.get("VALICHORD_LOCAL_API_BASE", "").strip() or DEFAULT_LOCAL_API_BASE
        spec = os.environ.get("VALICHORD_LOCAL_MODELS", "").strip()
        from ai_validator_cma import resolve_local_models
        return cls(api_base=api_base, models=resolve_local_models(spec, api_base))

    def model_for(self, idx: int) -> str:
        """idx is 1-based, matching the validator numbering shown to the user."""
        return self.models[(idx - 1) % len(self.models)]

    @property
    def distinct_models(self) -> int:
        return len(set(self.models))


# ── sources ────────────────────────────────────────────────────────────────────

SOURCE_SEPARATOR = "---"


def split_sources(raw: str) -> list:
    """Split pasted source material on a line containing only `---`.

    Each source is hashed so the page can show exactly what was judged. The
    hash is what makes a verdict checkable afterwards: a quote either appears
    in the document with that digest, or it does not.
    """
    if not (raw or "").strip():
        return []
    chunks = re.split(r"^\s*" + re.escape(SOURCE_SEPARATOR) + r"\s*$", raw, flags=re.MULTILINE)
    sources = []
    for chunk in chunks:
        text = chunk.strip()
        if not text:
            continue
        sources.append({
            "index":  len(sources) + 1,
            "text":   text,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        })
    return sources


def sources_digest(sources: list) -> str:
    """One digest over all supplied sources, for the sealed commitment.

    Sealing this alongside the claim and the answer means the evidence the
    validators were given cannot be swapped after the verdicts land.
    """
    return hashlib.sha256(
        "".join(s["sha256"] for s in sources).encode("utf-8")
    ).hexdigest()


def render_sources(sources: list) -> str:
    return "\n\n".join(
        f"[SOURCE {s['index']}] (sha256 {s['sha256'][:12]})\n{s['text']}"
        for s in sources
    )


# ── normalisation ──────────────────────────────────────────────────────────────

def normalise_outcome(value) -> str:
    """Map whatever the model said onto the wire vocabulary, or return ''.

    Small models produce case and spacing variants constantly ("not supported",
    "PARTIALLY_SUPPORTED"). The hosted path raises on an unrecognised enum with
    no retry at all, which would turn a correct verdict into a failed run.
    """
    key = re.sub(r"[^a-z]", "", str(value or "").lower())
    return _OUTCOME_ALIASES.get(key, "")


def normalise_confidence(value) -> str:
    key = re.sub(r"[^a-z]", "", str(value or "").lower())
    for c in _CONFIDENCES:
        if c.lower() == key:
            return c
    return ""


# ── completions ────────────────────────────────────────────────────────────────

def complete_text(cfg: "LocalConfig", model: str, prompt: str, max_tokens: int = 700) -> str:
    try:
        import litellm
    except ImportError:
        raise RuntimeError("litellm not installed. Run: pip install litellm")
    resp = litellm.completion(
        model=_normalise_local_model(model),
        messages=[{"role": "user", "content": prompt}],
        api_key="local-no-key",
        api_base=cfg.api_base,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()


def complete_json(cfg: "LocalConfig", model: str, prompt: str, max_tokens: int = 700,
                  attempts: int = 3) -> dict:
    """A completion that has to come back as an object. Retries a bad shape."""
    last = ""
    for _ in range(attempts):
        text = complete_text(cfg, model, prompt, max_tokens)
        try:
            return extract_verdict_json(text)
        except (json.JSONDecodeError, ValueError) as exc:
            last = str(exc)
    raise RuntimeError(f"{model} did not return JSON after {attempts} attempts: {last}")


# ── the validator ──────────────────────────────────────────────────────────────

VALIDATOR_SOURCES_SYSTEM = """You are an independent evaluator. You have no internet access.

Judge the claim ONLY against the source material provided below. Do not use
recollection, background knowledge, or anything you believe you know about the
subject. If it is not in the sources, you do not have it.

Work through these steps in order:
1. Identify the precise claim - what exactly is being asserted?
2. Read every source and find each passage that bears on the claim.
3. Quote those passages verbatim. A quote you cannot find in the sources is a
   mistake, not a paraphrase.
4. Decide whether the sources establish the claim.

Your verdict must be one of:
- Supported: the sources clearly establish the claim
- PartiallySupported: the sources bear on the claim but are mixed, partial or
  qualified
- NotSupported: the sources contradict the claim, OR do not address it

If the sources simply do not address the claim, that is NotSupported and you
should say so plainly. It is a real answer, not a failure - do not fill the gap
from memory."""

_VALIDATOR_TEMPLATE = """{system}

You are Validator {idx} of 3, working independently. You cannot see the other
validators' conclusions.

CLAIM TO EVALUATE:
{claim}

SOURCE MATERIAL:
{sources}

Reply with ONLY a JSON object - no markdown, no explanation:
{{
  "outcome": "Supported" | "PartiallySupported" | "NotSupported",
  "confidence": "High" | "Medium" | "Low",
  "reasoning": "At least 3 sentences on what the sources do and do not establish.",
  "evidence": [
    {{"source": 1, "quote": "verbatim passage you relied on"}}
  ]
}}"""


def run_local_claim_validator(idx: int, claim: str, sources: list, cfg: "LocalConfig") -> dict:
    """One validator's verdict, judged against the supplied sources.

    Returns the three-key shape the CMA path returns, plus `evidence` and the
    model that produced it, so everything downstream is unchanged.
    """
    model = cfg.model_for(idx)
    prompt = _VALIDATOR_TEMPLATE.format(
        system=VALIDATOR_SOURCES_SYSTEM,
        idx=idx,
        claim=claim,
        sources=render_sources(sources) if sources else "(no sources were supplied)",
    )

    raw = complete_json(cfg, model, prompt)

    outcome = normalise_outcome(raw.get("outcome"))
    if not outcome:
        raise RuntimeError(
            f"Validator {idx} ({model}) returned an unusable outcome: {raw.get('outcome')!r}"
        )

    return {
        "outcome":    outcome,
        "confidence": normalise_confidence(raw.get("confidence")) or "Low",
        "reasoning":  str(raw.get("reasoning", "")).strip(),
        "evidence":   clean_evidence(raw.get("evidence"), sources),
        "model":      model,
    }


def clean_evidence(raw, sources: list) -> list:
    """Check each quote against the source it cites.

    A quote the validator invented is precisely the failure this demo exists to
    expose, so it is kept and marked `verified: False` rather than silently
    dropped - hiding it would make a fabricating validator look like a careful
    one.
    """
    if not isinstance(raw, list):
        return []
    by_index = {s["index"]: s["text"] for s in sources}
    by_hash = {s["index"]: s["sha256"] for s in sources}
    cleaned = []
    for item in raw[:5]:
        if not isinstance(item, dict):
            continue
        quote = str(item.get("quote", "")).strip()
        if not quote:
            continue
        try:
            src_idx = int(item.get("source", 0))
        except (TypeError, ValueError):
            src_idx = 0
        body = by_index.get(src_idx, "")
        cleaned.append({
            "source":   src_idx,
            "quote":    quote,
            "verified": bool(body) and _normalise_ws(quote) in _normalise_ws(body),
            "sha256":   by_hash.get(src_idx, ""),
        })
    return cleaned


def _normalise_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()
