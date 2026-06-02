from unittest import mock
import pytest

pytest.importorskip("inspect_ai")
pytest.importorskip("inspect_evals")
import core_bench_validator as cbv


def test_build_validator_task_uses_hard_blind_filters():
    """Blinding guard: hard difficulty (deletes results/) + no-vision + the one
    capsule. GPU filtering is intentionally OFF — its substring check on
    REPRODUCING.md false-positives on the boilerplate `--gpus all` template and
    would empty the dataset; CPU-fitness is handled by capsule pre-screening."""
    captured = {}

    def fake_read(**kwargs):
        captured.update(kwargs)
        return "DATASET"

    with mock.patch.object(cbv, "read_core_bench_dataset", fake_read), \
         mock.patch.object(cbv, "default_solver", lambda **k: "SOLVER"), \
         mock.patch.object(cbv, "capture_report", lambda: "SCORER"), \
         mock.patch.object(cbv, "Task", lambda **k: k) as _:
        task = cbv.build_validator_task("capsule-5507257")

    assert captured["difficulty"] == "hard"
    assert captured["capsule_ids"] == ["capsule-5507257"]
    assert captured["filter_out_gpu"] is False  # crude filter disabled (see docstring)
    assert captured["filter_out_vision"] is True
    assert task["scorer"] == "SCORER"


def test_extract_report_from_log_reads_score_metadata():
    fake_score = mock.Mock(metadata={"report": {"Q": 1.0}})
    fake_sample = mock.Mock(scores={"capture_report": fake_score})
    fake_log = mock.Mock(samples=[fake_sample])
    assert cbv.extract_report_from_log([fake_log]) == {"Q": 1.0}


def test_extract_report_from_log_handles_no_samples():
    fake_log = mock.Mock(samples=[])
    assert cbv.extract_report_from_log([fake_log]) is None


def test_run_validator_eval_returns_report_and_log_path():
    good = mock.Mock(status="success", location="/logs/run.eval")
    with mock.patch.object(cbv, "build_validator_task", lambda cid: "TASK"), \
         mock.patch.object(cbv, "inspect_eval", lambda *a, **k: [good]), \
         mock.patch.object(cbv, "extract_report_from_log", lambda logs: {"Q": 2.0}):
        report, path = cbv.run_validator_eval("capsule-5507257", "anthropic/claude-opus-4-8")
    assert report == {"Q": 2.0}
    assert path == "/logs/run.eval"


def test_run_validator_eval_passes_log_dir_to_inspect_eval():
    captured = {}

    def fake_eval(task, model=None, log_dir=None):
        captured["log_dir"] = log_dir
        return [mock.Mock(status="success", location="/l/x.eval")]

    with mock.patch.object(cbv, "build_validator_task", lambda cid: "TASK"), \
         mock.patch.object(cbv, "inspect_eval", fake_eval), \
         mock.patch.object(cbv, "extract_report_from_log", lambda logs: {"Q": 1.0}):
        cbv.run_validator_eval("capsule-5507257", "m", log_dir="/l")
    assert captured["log_dir"] == "/l"


def test_run_validator_eval_raises_on_non_success_eval():
    """An infra failure (rate limit, quota, auth, interruption) yields a
    non-success eval log with no samples. It must raise so the round aborts with
    the real error -- never be silently returned as None and then recorded as a
    bogus FailedToReproduce verdict."""
    err = mock.Mock(message="Error code: 429 - insufficient_quota")
    bad_log = mock.Mock(status="error", error=err, samples=[])
    with mock.patch.object(cbv, "build_validator_task", lambda cid: "TASK"), \
         mock.patch.object(cbv, "inspect_eval", lambda *a, **k: [bad_log]):
        with pytest.raises(RuntimeError) as exc:
            cbv.run_validator_eval("capsule-5507257", "openai/gpt-4o")
    assert "429" in str(exc.value) and "status=error" in str(exc.value)


def test_run_validator_eval_returns_none_when_success_but_no_report():
    """A *successful* eval that produced no report.json is a genuine
    no-reproduction (-> FailedToReproduce later), distinct from an infra
    failure -- so report is None rather than raising."""
    good_log = mock.Mock(status="success", samples=[], location="/l/x.eval")
    with mock.patch.object(cbv, "build_validator_task", lambda cid: "TASK"), \
         mock.patch.object(cbv, "inspect_eval", lambda *a, **k: [good_log]):
        report, _ = cbv.run_validator_eval("capsule-5507257", "anthropic/claude-opus-4-8")
    assert report is None


def test_run_researcher_claim_runs_n_times_and_derives():
    calls = []

    def fake_eval(cid, model):
        calls.append(model)
        return {"Q": 96.125}, None

    with mock.patch.object(cbv, "run_validator_eval", fake_eval):
        claim = cbv.run_researcher_claim("capsule-5507257", "anthropic/claude-opus-4-8", n_runs=3)
    assert len(calls) == 3
    assert claim["Q"]["value"] == pytest.approx(96.125)


def test_run_researcher_claim_raises_on_failed_run():
    with mock.patch.object(cbv, "run_validator_eval", lambda c, m: (None, None)):
        with pytest.raises(RuntimeError):
            cbv.run_researcher_claim("capsule-5507257", "m", n_runs=2)
