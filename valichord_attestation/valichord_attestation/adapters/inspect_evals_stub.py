"""Stub adapter: inspect_evals → Valichord Bundle.

Deferred until the inspect_evals evaluation_report schema stabilises
(merged in UKGovernmentBEIS/inspect_evals#1575, but flagged as subject
to change by maintainer Scott Simmons in review of PR #1610).

Field mapping (when implemented):
    EvaluationReport.commit              -> Bundle.repo_commit
    EvaluationReport.command             -> Bundle.command
    EvaluationReportResult.model         -> Bundle.model_id
    EvaluationReportResult.task          -> Bundle.task_id
    EvaluationReportResult.metrics[*]    -> Bundle.metrics  (key/value/stderr verbatim)

Valichord additions (no upstream equivalent):
    Bundle.outputs_merkle_root  <- merkle_root() over per-sample output dicts from .eval log
    Bundle.format_version       <- "v1"
    Bundle.harness_version      <- inspect_ai package version string

Upstream schema source:
    src/inspect_evals/metadata.py  (EvaluationReport, EvaluationReportResult,
                                    EvaluationReportMetric)
    register/hangman-bench/README.md  (worked example, PR #1593)
"""

from ..adapters.base import AdapterBase
from ..bundle import Bundle


class InspectEvalsAdapter(AdapterBase):
    def to_bundle(self, eval_yaml_block: dict, eval_log_samples: list[dict]) -> Bundle:
        raise NotImplementedError(
            "InspectEvalsAdapter is deferred until the inspect_evals API stabilises. "
            "See module docstring for the intended field mapping."
        )
