"""Run the inspect_evals CORE-Bench task for one capsule/one model and return
the agent's report.json. Also derives the researcher's committed claim from N
runs. The Inspect eval runs in its own privileged Docker sandbox; this module
is the seam between that and ValiChord's commit-reveal."""
from typing import Optional

from inspect_ai import Task, eval as inspect_eval
from inspect_evals.core_bench.dataset import read_core_bench_dataset
from inspect_evals.core_bench.core_bench import default_solver

from core_bench_capture_scorer import capture_report
from report_to_verdict import derive_committed_claim


def build_validator_task(capsule_id: str) -> Task:
    """Build a hard-mode, blind, single-capsule CORE-Bench task whose scorer
    captures report.json instead of comparing against ground truth."""
    return Task(
        dataset=read_core_bench_dataset(
            difficulty="hard",
            language="Python",
            capsule_ids=[capsule_id],
            # filter_out_gpu uses a crude substring check on REPRODUCING.md, which
            # contains the boilerplate `docker run --gpus all` template line in
            # virtually every capsule -> it false-positives and empties the dataset.
            # We rely on capsule pre-screening (and the run itself) for CPU-fitness.
            filter_out_gpu=False,
            filter_out_vision=True,
        ),
        solver=default_solver(),
        scorer=capture_report(),
    )


def extract_report_from_log(logs) -> Optional[dict]:
    """Pull the captured report dict out of the first sample's capture_report
    score. Returns None if no sample/score/report present."""
    if not logs:
        return None
    samples = getattr(logs[0], "samples", None) or []
    if not samples:
        return None
    scores = getattr(samples[0], "scores", None) or {}
    for score in scores.values():
        md = getattr(score, "metadata", None) or {}
        if "report" in md:
            return md["report"]
    return None


def run_validator_eval(capsule_id: str, model: str) -> Optional[dict]:
    """Run one CORE-Bench eval with `model` and return the agent's report.json.

    Returns None only when the eval *succeeded* but the agent produced no
    report.json (a genuine no-reproduction). An infra failure (rate limit,
    quota, auth error, interruption) yields a non-success EvalLog with no
    samples; that must raise so the round aborts with the real error, never be
    silently turned into a FailedToReproduce verdict on a published
    HarmonyRecord."""
    task = build_validator_task(capsule_id)
    logs = inspect_eval(task, model=model)
    if logs:
        status = getattr(logs[0], "status", None)
        if status is not None and status != "success":
            err = getattr(logs[0], "error", None)
            detail = getattr(err, "message", None) or (str(err) if err else "no error detail")
            raise RuntimeError(f"eval did not complete (status={status}): {detail}")
    return extract_report_from_log(logs)


def run_researcher_claim(capsule_id: str, model: str, n_runs: int = 3,
                         rel_tolerance: float = 0.001) -> dict:
    """Run the capsule n_runs times to establish the committed claim (mean +
    95% prediction interval, or explicit tolerance for deterministic output)."""
    runs = []
    for _ in range(n_runs):
        report = run_validator_eval(capsule_id, model)
        if not report:
            raise RuntimeError(
                f"Researcher run for {capsule_id} produced no report.json -- "
                f"cannot establish a committed claim."
            )
        runs.append(report)
    return derive_committed_claim(runs, rel_tolerance=rel_tolerance)
