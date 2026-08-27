"""End-to-end checks of the local-model path against a REAL HTTP server.

Everything in test_local_models.py and test_local_mode.py fakes litellm by
putting a stub in `sys.modules`. That covers our logic and misses the thing
underneath it: whether litellm is *configured* correctly. If `api_base` were
passed wrongly, or the provider prefix reached the wire, every one of those
tests would still pass and the first run against a real server would fail.

So this file does not mock litellm. It stands up a minimal OpenAI-compatible
server on a loopback port, points the real client at it, and asserts on what
the server actually received.

The load-bearing assertion is `test_the_provider_prefix_is_stripped_on_the_wire`.
litellm needs `openai/<name>` to route to a custom base, but Your Own AI selects
an AI by the bare name in the `model` field, so a leaked prefix means nothing
matches. Mocks cannot see the difference; a socket can.

Skips rather than fails if litellm is unavailable — it is a heavy import that
reaches the network on first use, and a flaky download should not turn CI red
for a reason unrelated to the code.
"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

# NOT pytest.importorskip: that catches ImportError only. litellm downloads a
# tiktoken encoding during import, so on a machine that cannot reach the network
# — or, as here, one behind TLS interception — it raises SSLError and would fail
# collection instead of skipping. Observed on the author's box 2026-08-27.
try:
    import litellm  # noqa: F401
except Exception as _exc:  # noqa: BLE001 - any import-time failure means skip
    pytest.skip(f"litellm unavailable: {_exc}", allow_module_level=True)

import ai_validator_cma as av
import local_mode


RECEIVED: list = []
REPLIES: list = []


def _verdict(outcome="Supported", quote="lowered resting heart rate by 6 bpm"):
    return json.dumps({
        "outcome":    outcome,
        "confidence": "High",
        "reasoning":  "One. Two. Three.",
        "evidence":   [{"source": 1, "quote": quote}],
    })


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            self._send({"object": "list", "data": [
                {"id": "alpha"}, {"id": "beta"}, {"id": "gamma"},
            ]})
        else:
            self._send({"error": "not found"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        RECEIVED.append({
            "model": body.get("model"),
            "auth":  self.headers.get("Authorization"),
        })
        text = REPLIES.pop(0) if REPLIES else _verdict()
        self._send({
            "id": "chatcmpl-stub", "object": "chat.completion", "created": 0,
            "model": body.get("model", "stub"),
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": text}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })


@pytest.fixture(scope="module")
def base_url():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/v1"
    srv.shutdown()


@pytest.fixture(autouse=True)
def _reset():
    RECEIVED.clear()
    REPLIES.clear()
    yield


SOURCE = "Aerobic exercise lowered resting heart rate by 6 bpm over 12 weeks."


# ── discovery ──────────────────────────────────────────────────────────────────

def test_discovery_reads_a_real_models_endpoint(base_url):
    assert av.discover_local_models(base_url) == [
        "openai/alpha", "openai/beta", "openai/gamma",
    ]


# ── the wire ───────────────────────────────────────────────────────────────────

def test_the_provider_prefix_is_stripped_on_the_wire(base_url):
    """The one a mock cannot check.

    We hand litellm `openai/alpha` so it routes to our base. Your Own AI reads
    the `model` field as the name of one of the user's AIs, so if the prefix
    survived to the request body no AI would match and every run would fail.
    """
    REPLIES.extend([_verdict("Reproduced")] * 3)
    av.form_verdicts_simple(
        "brief", "output", "",
        ["openai/alpha", "openai/beta", "openai/gamma"], api_base=base_url,
    )
    assert [r["model"] for r in RECEIVED] == ["alpha", "beta", "gamma"]


def test_each_validator_reaches_the_server_on_its_own_model(base_url):
    REPLIES.extend([_verdict("Reproduced")] * 3)
    av.form_verdicts_simple(
        "brief", "output", "",
        ["openai/alpha", "openai/beta", "openai/gamma"], api_base=base_url,
    )
    assert len(RECEIVED) == 3
    assert len({r["model"] for r in RECEIVED}) == 3


def test_an_authorization_header_is_sent(base_url):
    # A local server authenticates nobody, but one that expects the header at
    # all must receive something rather than nothing.
    REPLIES.append(_verdict("Reproduced"))
    cfg = local_mode.LocalConfig(api_base=base_url, models=["alpha"])
    local_mode.run_local_claim_validator(1, "claim", [], cfg)
    assert RECEIVED[0]["auth"] == "Bearer local-no-key"


# ── the claim validator ────────────────────────────────────────────────────────

def test_validator_index_selects_the_model(base_url):
    REPLIES.append(_verdict())
    cfg = local_mode.LocalConfig(api_base=base_url, models=["alpha", "beta", "gamma"])
    local_mode.run_local_claim_validator(2, "claim", [], cfg)
    assert RECEIVED[0]["model"] == "beta"


@pytest.mark.parametrize("label,reply,want", [
    ("plain",          _verdict(),                                              "Reproduced"),
    ("think block",    "<think>weighing it up</think>\n" + _verdict(),          "Reproduced"),
    ("prose preamble", "Sure! Here you go:\n\n" + _verdict() + "\n\nCheers.",   "Reproduced"),
    ("fenced json",    "```json\n" + _verdict() + "\n```",                      "Reproduced"),
    ("lowercase enum", _verdict(outcome="not supported"),                       "NotReproduced"),
])
def test_messy_replies_survive_a_real_round_trip(base_url, label, reply, want):
    # These are the shapes small local models actually return, exercised through
    # HTTP and the real client rather than handed straight to the parser.
    REPLIES.append(reply)
    cfg = local_mode.LocalConfig(api_base=base_url, models=["alpha"])
    got = local_mode.run_local_claim_validator(1, "claim", local_mode.split_sources(SOURCE), cfg)
    assert got["outcome"] == want, label


def test_a_quote_that_is_in_the_source_is_verified(base_url):
    REPLIES.append(_verdict())
    cfg = local_mode.LocalConfig(api_base=base_url, models=["alpha"])
    got = local_mode.run_local_claim_validator(1, "claim", local_mode.split_sources(SOURCE), cfg)
    assert got["evidence"][0]["verified"] is True


def test_a_fabricated_quote_is_reported_not_hidden(base_url):
    REPLIES.append(_verdict(quote="the study found the opposite"))
    cfg = local_mode.LocalConfig(api_base=base_url, models=["alpha"])
    got = local_mode.run_local_claim_validator(1, "claim", local_mode.split_sources(SOURCE), cfg)
    assert got["evidence"][0]["verified"] is False


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
