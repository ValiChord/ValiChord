"""Inspect scorer that CAPTURES the agent's report.json into the eval log.

Unlike inspect_evals' stock evaluate_task_questions, this scorer does NOT read
the sealed ground truth stored in state metadata under the results key. It only
lifts the agent's own report.json out of the sandbox so the orchestrator can
commit it blind. Ground-truth comparison is a separate, post-reveal overlay --
never here."""
import json
from typing import Optional

from inspect_ai.scorer import CORRECT, INCORRECT, Score, Scorer, Target, accuracy, scorer
from inspect_ai.solver import TaskState
from inspect_ai.util import sandbox


async def read_report_from_sandbox(sb) -> Optional[dict]:
    """Read and parse /capsule report.json from a sandbox-like object.
    Returns the dict, or None if absent/unparseable. Pure of ground truth."""
    try:
        raw = await sb.read_file("report.json")
    except FileNotFoundError:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


@scorer(metrics=[accuracy()])
def capture_report() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        report = await read_report_from_sandbox(sandbox())
        if report is None:
            return Score(
                value=INCORRECT,
                answer="",
                explanation="report.json missing or unparseable",
                metadata={"report": None},
            )
        return Score(
            value=CORRECT,
            answer=json.dumps(report),
            explanation="captured report.json",
            metadata={"report": report},
        )
    return score
