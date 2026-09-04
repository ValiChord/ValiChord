"""Unit tests for the local-model path of the custom (web) demo.

Two things are being protected here.

The first is that local mode is *additive*. With VALICHORD_LOCAL unset the
hosted Anthropic path must behave exactly as it did, because that is what the
Render deployment runs. Several tests below assert the "off" case explicitly
rather than only testing the new behaviour.

The second is the submit button. Local mode swaps the API-key field for a
sources field, and the readiness check reads both. If the key field were
removed from the DOM instead of hidden, that check would throw and the button
would stay disabled forever — with no error anywhere. The page-render tests
assert both modes produce a usable form.

Everything is offline: litellm and the model server are faked.

    python3 -m pytest demo/test_local_mode.py
"""
import importlib
import json
import sys
from types import SimpleNamespace

import pytest

import local_mode


# ── helpers ────────────────────────────────────────────────────────────────────

def _resp(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class _FakeLiteLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def completion(self, **kwargs):
        self.calls.append(kwargs)
        return _resp(self.replies.pop(0))


SOURCE_A = "Aerobic exercise lowered resting heart rate by 6 bpm over 12 weeks."
SOURCE_B = "No change in resting heart rate was observed in the control group."


# ── local mode is off by default ───────────────────────────────────────────────

def test_local_config_is_none_when_the_flag_is_unset(monkeypatch):
    # The hosted path depends on this: None is what makes it take its own branch.
    monkeypatch.delenv("VALICHORD_LOCAL", raising=False)
    assert local_mode.LocalConfig.from_env() is None


def test_local_config_is_none_for_a_falsy_flag(monkeypatch):
    monkeypatch.setenv("VALICHORD_LOCAL", "0")
    assert local_mode.LocalConfig.from_env() is None


def test_local_config_reads_models_and_base(monkeypatch):
    monkeypatch.setenv("VALICHORD_LOCAL", "1")
    monkeypatch.setenv("VALICHORD_LOCAL_MODELS", "alice,bob,carol")
    monkeypatch.setenv("VALICHORD_LOCAL_API_BASE", "http://example.test/v1")
    cfg = local_mode.LocalConfig.from_env()
    assert cfg.api_base == "http://example.test/v1"
    assert cfg.models == ["openai/alice", "openai/bob", "openai/carol"]
    assert cfg.distinct_models == 3


def test_model_for_is_one_based_and_wraps():
    cfg = local_mode.LocalConfig(api_base="x", models=["a", "b", "c"])
    assert cfg.model_for(1) == "a"
    assert cfg.model_for(3) == "c"
    assert cfg.model_for(4) == "a"


# ── sources ────────────────────────────────────────────────────────────────────

def test_a_single_source_is_hashed():
    got = local_mode.split_sources(SOURCE_A)
    assert len(got) == 1
    assert got[0]["index"] == 1
    assert len(got[0]["sha256"]) == 64


def test_sources_split_on_a_separator_line():
    got = local_mode.split_sources(f"{SOURCE_A}\n---\n{SOURCE_B}")
    assert [s["index"] for s in got] == [1, 2]
    assert got[0]["text"] == SOURCE_A
    assert got[1]["text"] == SOURCE_B
    assert got[0]["sha256"] != got[1]["sha256"]


def test_blank_sources_give_nothing():
    assert local_mode.split_sources("") == []
    assert local_mode.split_sources("   \n  ") == []


def test_a_dash_inside_prose_is_not_a_separator():
    # Only a line that is nothing but --- splits. Otherwise em-dashes in the
    # pasted text would silently shard a source and change its hash.
    got = local_mode.split_sources("before --- after")
    assert len(got) == 1


def test_the_digest_changes_if_a_source_changes():
    a = local_mode.sources_digest(local_mode.split_sources(SOURCE_A))
    b = local_mode.sources_digest(local_mode.split_sources(SOURCE_A + "!"))
    assert a != b


def test_the_digest_changes_if_the_order_changes():
    fwd = local_mode.sources_digest(local_mode.split_sources(f"{SOURCE_A}\n---\n{SOURCE_B}"))
    rev = local_mode.sources_digest(local_mode.split_sources(f"{SOURCE_B}\n---\n{SOURCE_A}"))
    assert fwd != rev


# ── normalisation ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("said,want", [
    ("Supported",            "Reproduced"),
    ("supported",            "Reproduced"),
    ("PartiallySupported",   "PartiallyReproduced"),
    ("Partially Supported",  "PartiallyReproduced"),
    ("PARTIALLY_SUPPORTED",  "PartiallyReproduced"),
    ("NotSupported",         "NotReproduced"),
    ("not supported",        "NotReproduced"),
    ("Unsupported",          "NotReproduced"),
    # The wire words are accepted too, so a model that ignores the prompt and
    # answers in the protocol's own vocabulary still lands correctly.
    ("Reproduced",           "Reproduced"),
    ("NotReproduced",        "NotReproduced"),
])
def test_outcome_variants_normalise(said, want):
    assert local_mode.normalise_outcome(said) == want


@pytest.mark.parametrize("junk", ["", None, "maybe", "Reproducible"])
def test_unusable_outcomes_return_empty(junk):
    assert local_mode.normalise_outcome(junk) == ""


def test_confidence_normalises():
    assert local_mode.normalise_confidence("high") == "High"
    assert local_mode.normalise_confidence("LOW") == "Low"
    assert local_mode.normalise_confidence("certain") == ""


# ── evidence checking ──────────────────────────────────────────────────────────

def test_a_real_quote_is_marked_verified():
    sources = local_mode.split_sources(SOURCE_A)
    got = local_mode.clean_evidence([{"source": 1, "quote": "lowered resting heart rate by 6 bpm"}], sources)
    assert got[0]["verified"] is True
    assert got[0]["sha256"] == sources[0]["sha256"]


def test_a_fabricated_quote_is_kept_and_marked_unverified():
    # Kept, not dropped: hiding it would make a fabricating validator look
    # like a careful one.
    sources = local_mode.split_sources(SOURCE_A)
    got = local_mode.clean_evidence([{"source": 1, "quote": "raised heart rate by 40 bpm"}], sources)
    assert len(got) == 1
    assert got[0]["verified"] is False


def test_quote_matching_ignores_whitespace_and_case():
    sources = local_mode.split_sources(SOURCE_A)
    got = local_mode.clean_evidence(
        [{"source": 1, "quote": "LOWERED   resting\n heart RATE"}], sources
    )
    assert got[0]["verified"] is True


def test_a_quote_citing_a_source_that_does_not_exist_is_unverified():
    sources = local_mode.split_sources(SOURCE_A)
    got = local_mode.clean_evidence([{"source": 9, "quote": "lowered resting heart rate"}], sources)
    assert got[0]["verified"] is False


def test_malformed_evidence_is_ignored():
    assert local_mode.clean_evidence("not a list", []) == []
    assert local_mode.clean_evidence([None, 5, {}], []) == []


# ── the validator ──────────────────────────────────────────────────────────────

def _verdict_json(outcome="Supported", quote="lowered resting heart rate by 6 bpm"):
    return json.dumps({
        "outcome":    outcome,
        "confidence": "High",
        "reasoning":  "One. Two. Three.",
        "evidence":   [{"source": 1, "quote": quote}],
    })


def test_the_validator_returns_the_wire_vocabulary(monkeypatch):
    monkeypatch.setitem(sys.modules, "litellm", _FakeLiteLLM([_verdict_json()]))
    cfg = local_mode.LocalConfig(api_base="http://x/v1", models=["a", "b", "c"])

    got = local_mode.run_local_claim_validator(1, "claim", local_mode.split_sources(SOURCE_A), cfg)

    assert got["outcome"] == "Reproduced"      # asked for "Supported", stored as wire word
    assert got["confidence"] == "High"
    assert got["model"] == "a"
    assert got["evidence"][0]["verified"] is True


def test_each_validator_uses_its_own_model(monkeypatch):
    fake = _FakeLiteLLM([_verdict_json()] * 3)
    monkeypatch.setitem(sys.modules, "litellm", fake)
    cfg = local_mode.LocalConfig(api_base="http://x/v1", models=["a", "b", "c"])

    for idx in (1, 2, 3):
        local_mode.run_local_claim_validator(idx, "claim", [], cfg)

    assert [c["model"] for c in fake.calls] == ["openai/a", "openai/b", "openai/c"]


def test_the_validator_never_sends_a_real_key(monkeypatch):
    fake = _FakeLiteLLM([_verdict_json()])
    monkeypatch.setitem(sys.modules, "litellm", fake)
    cfg = local_mode.LocalConfig(api_base="http://127.0.0.1:11435/v1", models=["a"])

    local_mode.run_local_claim_validator(1, "claim", [], cfg)

    assert fake.calls[0]["api_key"] == "local-no-key"
    assert fake.calls[0]["api_base"] == "http://127.0.0.1:11435/v1"


def test_a_fabricating_validator_is_reported_not_hidden(monkeypatch):
    monkeypatch.setitem(
        sys.modules, "litellm",
        _FakeLiteLLM([_verdict_json(quote="the study found the opposite")]),
    )
    cfg = local_mode.LocalConfig(api_base="http://x/v1", models=["a"])

    got = local_mode.run_local_claim_validator(1, "claim", local_mode.split_sources(SOURCE_A), cfg)

    assert got["evidence"][0]["verified"] is False


def test_an_unusable_outcome_fails_loudly(monkeypatch):
    bad = json.dumps({"outcome": "banana", "confidence": "High", "reasoning": "x"})
    monkeypatch.setitem(sys.modules, "litellm", _FakeLiteLLM([bad]))
    cfg = local_mode.LocalConfig(api_base="http://x/v1", models=["a"])

    with pytest.raises(RuntimeError, match="unusable outcome"):
        local_mode.run_local_claim_validator(1, "claim", [], cfg)


def test_non_json_is_retried_before_giving_up(monkeypatch):
    fake = _FakeLiteLLM(["sorry, I cannot", "still prose", _verdict_json()])
    monkeypatch.setitem(sys.modules, "litellm", fake)
    cfg = local_mode.LocalConfig(api_base="http://x/v1", models=["a"])

    got = local_mode.run_local_claim_validator(1, "claim", [], cfg)

    assert got["outcome"] == "Reproduced"
    assert len(fake.calls) == 3


# ── the page renders in both modes ─────────────────────────────────────────────

def _load_app(monkeypatch, local):
    if local:
        monkeypatch.setenv("VALICHORD_LOCAL", "1")
    else:
        monkeypatch.delenv("VALICHORD_LOCAL", raising=False)
    import app as app_module
    importlib.reload(app_module)
    return app_module


@pytest.mark.parametrize("local,flag", [(False, "false"), (True, "true")])
def test_the_page_carries_the_right_mode_flag(monkeypatch, local, flag):
    mod = _load_app(monkeypatch, local)
    body = mod.app.test_client().get("/demo").get_data(as_text=True)
    assert f"const VALICHORD_LOCAL={flag};" in body
    # A placeholder left in the served page would make the whole script block a
    # syntax error, and every button on the page would stop working.
    assert "__VALICHORD_LOCAL__" not in body


@pytest.mark.parametrize("local", [False, True])
def test_both_form_fields_stay_in_the_dom(monkeypatch, local):
    # checkCustomReady() reads whichever one is not in use. Removing either
    # would throw there and leave the submit button permanently disabled.
    mod = _load_app(monkeypatch, local)
    body = mod.app.test_client().get("/demo").get_data(as_text=True)
    assert 'id="customKey"' in body
    assert 'id="customSources"' in body


def test_hosted_mode_still_demands_an_anthropic_key(monkeypatch):
    mod = _load_app(monkeypatch, local=False)
    r = mod.app.test_client().post("/demo/custom/run", json={
        "claim": "c", "user_answer": "a",
    })
    assert r.status_code == 400
    assert "Anthropic API key" in r.get_json()["error"]


def test_hosted_mode_rejects_a_non_anthropic_key(monkeypatch):
    mod = _load_app(monkeypatch, local=False)
    r = mod.app.test_client().post("/demo/custom/run", json={
        "claim": "c", "user_answer": "a", "user_api_key": "sk-proj-nope",
    })
    assert r.status_code == 400


def test_local_mode_needs_no_key_but_does_need_sources(monkeypatch):
    mod = _load_app(monkeypatch, local=True)
    r = mod.app.test_client().post("/demo/custom/run", json={
        "claim": "c", "user_answer": "a",
    })
    assert r.status_code == 400
    assert "source material is required" in r.get_json()["error"]


def test_local_mode_still_requires_a_claim(monkeypatch):
    mod = _load_app(monkeypatch, local=True)
    r = mod.app.test_client().post("/demo/custom/run", json={
        "user_answer": "a", "sources": SOURCE_A,
    })
    assert r.status_code == 400
    assert "claim is required" in r.get_json()["error"]


# ── the page's JavaScript still parses ─────────────────────────────────────────

def _open_string_lines(script):
    """Line numbers where a quoted JS string is left unterminated.

    Walks characters tracking whether we are inside a ' or " string, honouring
    backslash escapes. Deliberately naive about regex literals - `/"/g` reads as
    a string start - which is why the test below compares the two modes rather
    than demanding zero. The pre-existing esc() helper trips it in both.
    """
    bad = []
    for n, line in enumerate(script.splitlines(), 1):
        quote = None
        i = 0
        while i < len(line):
            c = line[i]
            if quote:
                if c == "\\":
                    i += 2
                    continue
                if c == quote:
                    quote = None
            elif c in "'\"":
                quote = c
            elif c == "/" and i + 1 < len(line) and line[i + 1] == "/":
                break
            i += 1
        if quote:
            bad.append(n)
    return bad


def _script_of(mod):
    body = mod.app.test_client().get("/demo").get_data(as_text=True)
    return body.split("<script>")[1].split("</script>")[0]


def test_local_mode_adds_no_unterminated_js_string(monkeypatch):
    """The failure this catches is total and silent.

    _DEMO_HTML is a Python triple-quoted string, so a \\' written for JavaScript
    is collapsed by Python to a bare ' before the browser ever sees it. That
    ends the JS string early, the script block fails to parse, and every button
    on the page stops working - with nothing in any log to say why. It happened
    once already, writing the local-mode copy.
    """
    hosted = _open_string_lines(_script_of(_load_app(monkeypatch, local=False)))
    local  = _open_string_lines(_script_of(_load_app(monkeypatch, local=True)))
    assert local == hosted, (
        f"local mode introduced unterminated JS strings at lines "
        f"{sorted(set(local) - set(hosted))}"
    )


def test_the_swapped_copy_lines_are_well_formed(monkeypatch):
    script = _script_of(_load_app(monkeypatch, local=True))
    for marker in ("hero.innerHTML", "intro.textContent"):
        line = next(l for l in script.splitlines() if marker in l)
        assert _open_string_lines(line) == [], f"{marker} line does not terminate"


# ── 0.7.0 compatibility ───────────────────────────────────────────────────────

def test_the_web_path_pins_the_round_to_the_device(monkeypatch):
    fake = _FakeLiteLLM([_verdict_json()])
    monkeypatch.setitem(sys.modules, "litellm", fake)
    cfg = local_mode.LocalConfig(api_base="http://x/v1", models=["a"])

    local_mode.run_local_claim_validator(1, "claim", [], cfg)

    assert fake.calls[0]["extra_headers"]["X-Your-Own-AI-Online-Share"] == "local"
    assert fake.calls[0]["extra_headers"]["X-Title"] == "ValiChord"


def test_local_validators_run_one_at_a_time():
    """Your Own AI holds exactly one chat model loaded.

    `current_model: Mutex<Option<String>>` — naming a different AI kills the
    llama-server and respawns it on the new file. Three concurrent calls naming
    three different models fight over one loader, each swap killing the load the
    previous one was waiting on. So the local path runs them in sequence.
    """
    import threading
    import time

    import custom_runner

    lock = threading.Lock()
    active: list = []
    peak: list = []

    def fn(idx, url):
        with lock:
            active.append(idx)
            peak.append(len(active))
        time.sleep(0.05)
        with lock:
            active.remove(idx)
        return {"outcome": "Reproduced"}

    results, errors = custom_runner._run_validators(fn, lambda i, u: (i + 1, u), workers=1)

    assert not errors
    assert len(results) == 3
    assert max(peak) == 1, f"validators overlapped: peak concurrency {max(peak)}"


def test_the_default_is_still_parallel():
    """Negative control for the test above.

    Without it, `workers=1` would keep passing against an implementation that
    had quietly gone serial everywhere — including the hosted path, where the
    concurrency is wanted. The barrier only clears if all three run at once.
    """
    import threading

    import custom_runner

    barrier = threading.Barrier(3, timeout=5)

    def fn(idx, url):
        barrier.wait()
        return {"outcome": "Reproduced"}

    results, errors = custom_runner._run_validators(fn, lambda i, u: (i + 1, u))

    assert not errors, f"the default is no longer parallel: {errors}"
    assert len(results) == 3


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
