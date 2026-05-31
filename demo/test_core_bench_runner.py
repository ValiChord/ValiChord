import pytest

# core_bench_runner imports CAPSULE_CHECKSUMS from inspect_evals at module load.
pytest.importorskip("inspect_evals")
import core_bench_runner as cbr


def test_claim_to_metrics_encodes_committed_interval():
    claim = {"Q": {"value": 96.125, "lower": 96.0, "upper": 96.25, "basis": "explicit_tolerance"}}
    metrics = cbr.claim_to_metrics(claim)
    assert metrics[0]["metric_name"] == "Q"
    assert metrics[0]["produced_value"] == repr(96.125)
    # the committed interval is sealed in expected_value, on-chain & inspectable
    assert "96.0" in metrics[0]["expected_value"] and "96.25" in metrics[0]["expected_value"]
    assert metrics[0]["within_tolerance"] is True


def test_data_hash_binds_to_capsule_checksum():
    h1 = cbr.compute_capsule_data_hash("capsule-5507257", salt=b"\x00" * 16)
    h2 = cbr.compute_capsule_data_hash("capsule-5507257", salt=b"\x01" * 16)
    assert len(h1) == 64 and h1 != h2  # salted, fresh per run


def test_validate_model_keys_fails_fast_when_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    with pytest.raises(RuntimeError) as exc:
        cbr.validate_model_keys(["anthropic/claude-opus-4-8", "openai/gpt-4o", "google/gemini-1.5-pro"])
    assert "OPENAI_API_KEY" in str(exc.value)


def test_validate_model_keys_passes_when_all_present(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    cbr.validate_model_keys(["anthropic/claude-opus-4-8", "openai/gpt-4o", "google/gemini-1.5-pro"])


def test_run_protocol_drives_full_sequence(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("GOOGLE_API_KEY", "x")

    posts = []

    def fake_post(url, payload, timeout=600):
        posts.append((url, payload))
        if url.endswith("/lock-result"):
            return {"external_hash_b64": "uhC8kEXT"}
        if url.endswith("/reveal"):
            return {"researcher_reveal_hash": "uhCkkREV"}
        if url.endswith("/create-harmony-record"):
            return {"harmony_record_hash": "uhC8kHARM"}
        return {}

    def fake_get(url, timeout=30):
        return {"phase": "RevealOpen"}

    monkeypatch.setattr(cbr, "_node_post", fake_post)
    monkeypatch.setattr(cbr, "_node_get", fake_get)
    monkeypatch.setattr(cbr, "run_researcher_claim",
                        lambda cid, model, n_runs, rel_tolerance:
                        {"Q": {"value": 96.125, "lower": 96.0, "upper": 96.25, "basis": "explicit_tolerance"}})
    monkeypatch.setattr(cbr, "run_validator_eval", lambda cid, model: {"Q": 96.125})
    monkeypatch.setattr(cbr, "_sleep", lambda s: None)

    result = cbr.run_core_bench_protocol(
        capsule_id="capsule-5507257",
        researcher_model="anthropic/claude-opus-4-8",
        validator_models=["anthropic/claude-opus-4-8", "openai/gpt-4o", "google/gemini-1.5-pro"],
    )

    urls = [u for u, _ in posts]
    assert any(u.endswith("/lock-result") for u in urls)
    assert any(u.endswith("/submit-request") for u in urls)
    assert sum(u.endswith("/commit") for u in urls) == 3
    assert sum(u.endswith("/reveal") for u in urls) == 4  # researcher + 3 validators
    assert any(u.endswith("/create-harmony-record") for u in urls)
    assert result["harmony_record_hash"] == "uhC8kHARM"
    assert result["agreement_level"] == "ExactMatch"  # 3/3 Reproduced
    assert all(row["match"] for v in result["numeric_panel"] for row in v["rows"])


def test_run_protocol_aborts_when_a_validator_fails(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("GOOGLE_API_KEY", "x")

    monkeypatch.setattr(cbr, "_node_post", lambda url, payload, timeout=600: {"external_hash_b64": "uhC8kEXT"})
    monkeypatch.setattr(cbr, "_node_get", lambda url, timeout=30: {"phase": "RevealOpen"})
    monkeypatch.setattr(cbr, "run_researcher_claim",
                        lambda cid, model, n_runs, rel_tolerance:
                        {"Q": {"value": 96.125, "lower": 96.0, "upper": 96.25, "basis": "explicit_tolerance"}})
    monkeypatch.setattr(cbr, "_sleep", lambda s: None)

    def flaky_eval(cid, model):
        if model == "openai/gpt-4o":
            raise RuntimeError("sandbox build failed")
        return {"Q": 96.125}

    monkeypatch.setattr(cbr, "run_validator_eval", flaky_eval)

    with pytest.raises(RuntimeError) as exc:
        cbr.run_core_bench_protocol(
            capsule_id="capsule-5507257",
            researcher_model="anthropic/claude-opus-4-8",
            validator_models=["anthropic/claude-opus-4-8", "openai/gpt-4o", "google/gemini-1.5-pro"],
        )
    msg = str(exc.value)
    assert "aborted" in msg.lower()
    assert "openai/gpt-4o" in msg  # names the failed model
