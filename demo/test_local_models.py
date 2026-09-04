"""Unit tests for the local-model validator path in demo/ai_validator_cma.py.

These cover the pieces that let the demo run with no API key and no cost:
model discovery against an OpenAI-compatible server, one model per validator,
and the looser JSON that local models actually return.

Everything here is offline - litellm and the HTTP call are both faked, so this
runs in CI with no model, no server and no key:

    python3 -m pytest demo/test_local_models.py
"""
import json
import sys
from types import SimpleNamespace

import pytest

import ai_validator_cma as av


# ── helpers ──

def _resp(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class _FakeLiteLLM:
    """Records the kwargs it was called with, replays canned replies."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls   = []

    def completion(self, **kwargs):
        self.calls.append(kwargs)
        return _resp(self.replies.pop(0))


class _FakeHTTPResponse:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


GOOD = json.dumps({
    "outcome":    "Reproduced",
    "confidence": "High",
    "reasoning":  "One. Two. Three.",
})


# ── model naming ──

def test_bare_name_gets_a_provider_prefix():
    # litellm needs the prefix to route a bare AI name to an OpenAI-compatible base.
    assert av._normalise_local_model("alice") == "openai/alice"


def test_existing_prefix_is_left_alone():
    assert av._normalise_local_model("ollama/llama3") == "ollama/llama3"


# ── resolving one model per validator ──

def test_three_names_give_three_validators():
    got = av.resolve_local_models("alice,bob,carol", "http://x/v1")
    assert got == ["openai/alice", "openai/bob", "openai/carol"]


def test_one_name_is_cycled_to_fill_the_slots():
    # Allowed, but main() warns - one reader sampled three times.
    assert av.resolve_local_models("alice", "http://x/v1") == ["openai/alice"] * 3


def test_extra_names_are_ignored():
    got = av.resolve_local_models("a,b,c,d", "http://x/v1")
    assert got == ["openai/a", "openai/b", "openai/c"]


def test_blank_spec_falls_back_to_discovery(monkeypatch):
    monkeypatch.setattr(
        av.urllib.request, "urlopen",
        lambda *a, **k: _FakeHTTPResponse({"data": [{"id": "x"}, {"id": "y"}, {"id": "z"}]}),
    )
    assert av.resolve_local_models("", "http://x/v1") == ["openai/x", "openai/y", "openai/z"]


# ── discovery ──

def test_discovery_cycles_when_the_server_serves_fewer_than_three(monkeypatch):
    monkeypatch.setattr(
        av.urllib.request, "urlopen",
        lambda *a, **k: _FakeHTTPResponse({"data": [{"id": "solo"}]}),
    )
    assert av.discover_local_models("http://x/v1") == ["openai/solo"] * 3


def test_discovery_rejects_an_empty_catalogue(monkeypatch):
    monkeypatch.setattr(
        av.urllib.request, "urlopen",
        lambda *a, **k: _FakeHTTPResponse({"data": []}),
    )
    with pytest.raises(RuntimeError, match="no models"):
        av.discover_local_models("http://x/v1")


def test_unreachable_server_names_the_url(monkeypatch):
    def boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(av.urllib.request, "urlopen", boom)
    with pytest.raises(RuntimeError, match="Could not reach a local model server"):
        av.discover_local_models("http://127.0.0.1:11435/v1")


# ── verdict parsing ──

def test_plain_json():
    assert av.extract_verdict_json(GOOD)["outcome"] == "Reproduced"


def test_fenced_json():
    assert av.extract_verdict_json("```json\n" + GOOD + "\n```")["confidence"] == "High"


def test_reasoning_block_is_stripped():
    # Reasoning models emit <think>; it must not reach the parser.
    text = "<think>Let me weigh this up.</think>\n" + GOOD
    assert av.extract_verdict_json(text)["outcome"] == "Reproduced"


def test_prose_preamble_before_the_object():
    text = "Sure! Here is my verdict:\n\n" + GOOD + "\n\nHope that helps."
    assert av.extract_verdict_json(text)["outcome"] == "Reproduced"


def test_braces_inside_reasoning_do_not_truncate_the_object():
    nested = json.dumps({
        "outcome":    "FailedToReproduce",
        "confidence": "Low",
        "reasoning":  "The dict {a: 1} was not defined. Two. Three.",
    })
    got = av.extract_verdict_json("noise " + nested + " trailing")
    assert got["outcome"] == "FailedToReproduce"
    assert "{a: 1}" in got["reasoning"]


def test_no_object_at_all_is_an_error():
    with pytest.raises(ValueError, match="no JSON object"):
        av.extract_verdict_json("I could not reach a conclusion.")


# ── form_verdicts_simple wiring ──

def test_each_validator_gets_its_own_model(monkeypatch):
    fake = _FakeLiteLLM([GOOD, GOOD, GOOD])
    monkeypatch.setitem(sys.modules, "litellm", fake)

    verdicts = av.form_verdicts_simple(
        "brief", "output", "", ["openai/a", "openai/b", "openai/c"],
        api_base="http://127.0.0.1:11435/v1",
    )

    assert len(verdicts) == 3
    assert [c["model"] for c in fake.calls] == ["openai/a", "openai/b", "openai/c"]


def test_local_calls_carry_the_api_base_and_a_placeholder_key(monkeypatch):
    fake = _FakeLiteLLM([GOOD] * 3)
    monkeypatch.setitem(sys.modules, "litellm", fake)

    av.form_verdicts_simple(
        "brief", "output", "", ["openai/a"] * 3,
        api_base="http://127.0.0.1:11435/v1",
    )

    for call in fake.calls:
        assert call["api_base"] == "http://127.0.0.1:11435/v1"
        # A local server authenticates nobody, but the header must be present.
        assert call["api_key"] == "local-no-key"


def test_local_calls_pin_the_round_to_the_device(monkeypatch):
    # Your Own AI 0.7.0 flipped "Auto Online-and-Offline" AIs to frontier-first
    # and made the default difficulty one that can never stay local. Without this
    # header a validator can be answered by a paid online model — the prompt
    # leaves the machine, or the run 401s. See LOCAL_HEADERS in ai_validator_cma.
    fake = _FakeLiteLLM([GOOD] * 3)
    monkeypatch.setitem(sys.modules, "litellm", fake)

    av.form_verdicts_simple("brief", "output", "", ["openai/a"] * 3, api_base="http://x/v1")

    for call in fake.calls:
        assert call["extra_headers"]["X-Your-Own-AI-Online-Share"] == "local"
        assert call["extra_headers"]["X-Title"] == "ValiChord"


def test_hosted_calls_carry_none_of_the_local_headers(monkeypatch):
    # Keeps local mode additive: the hosted Anthropic path must not grow vendor
    # headers for a different product.
    fake = _FakeLiteLLM([GOOD] * 3)
    monkeypatch.setitem(sys.modules, "litellm", fake)

    av.form_verdicts_simple("brief", "output", "sk-real", ["gpt-4o-mini"] * 3)

    for call in fake.calls:
        assert "extra_headers" not in call
        assert "response_format" not in call


def test_the_placeholder_key_is_never_the_bare_word_local(monkeypatch):
    # `Authorization: Bearer local` in agent mode is how Your Own AI recognises
    # its own internal harness, and it stops recording the exchange. A tidy-up
    # of this placeholder would silently cost us the signed record.
    fake = _FakeLiteLLM([GOOD] * 3)
    monkeypatch.setitem(sys.modules, "litellm", fake)

    av.form_verdicts_simple("brief", "output", "", ["openai/a"] * 3, api_base="http://x/v1")

    for call in fake.calls:
        assert call["api_key"].strip().lower() != "local"


def test_hosted_calls_send_the_real_key_and_no_api_base(monkeypatch):
    fake = _FakeLiteLLM([GOOD] * 3)
    monkeypatch.setitem(sys.modules, "litellm", fake)

    av.form_verdicts_simple("brief", "output", "sk-real", ["gpt-4o-mini"] * 3)

    for call in fake.calls:
        assert "api_base" not in call
        assert call["api_key"] == "sk-real"


def test_a_bad_reply_is_retried(monkeypatch):
    fake = _FakeLiteLLM(["not json at all", GOOD, GOOD, GOOD])
    monkeypatch.setitem(sys.modules, "litellm", fake)

    verdicts = av.form_verdicts_simple("brief", "output", "", ["openai/a"] * 3, api_base="http://x/v1")

    assert len(verdicts) == 3
    assert len(fake.calls) == 4  # one wasted attempt, then three good ones


def test_a_wrong_enum_is_rejected(monkeypatch):
    wrong = json.dumps({"outcome": "Supported", "confidence": "High", "reasoning": "x"})
    fake = _FakeLiteLLM([wrong] * 5)
    monkeypatch.setitem(sys.modules, "litellm", fake)

    with pytest.raises(RuntimeError, match="failed after 5 attempts"):
        av.form_verdicts_simple("brief", "output", "", ["openai/a"] * 3, api_base="http://x/v1")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
