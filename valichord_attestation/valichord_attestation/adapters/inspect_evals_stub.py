"""inspect_evals → Valichord Bundle adapter.

Converts the ``evaluation_report`` block from an inspect_evals ``eval.yaml``
register entry, paired with per-sample output dicts, into a Valichord Bundle.

Schema reference (stable as of UKGovernmentBEIS/inspect_evals PR #1575,
confirmed unchanged through PRs #1604 and #1636):

.. code-block:: yaml

    evaluation_report:
      commit:    str          # Required: upstream git SHA
      command:   str | None   # Optional: invocation command
      timestamp: str | None   # Optional: ISO 8601 run timestamp → Bundle.generated_at
      version:   str | None   # Optional: eval version tag   → meta["eval_version"]
      notes:     list[str] | None  # Optional: notes         → meta["notes"]
      results:                # Required: min 1
        - model:    str       # Required: model identifier   → Bundle.model_id
          metrics:  list      # Required: min 1
            - key:   str      # Required
              value: float    # Required
          task:     str | None  # Optional: None → "overall" → Bundle.task_id
          provider: str | None  # Optional                   → meta["provider"]
          time:     str | None  # Optional: execution time   → meta["run_time"]
          date:     str | None  # Optional: run date         → meta["run_date"]

Field mapping (inspect_evals → Valichord Bundle):

    EvaluationReport.commit     → Bundle.repo_commit
    EvaluationReport.command    → Bundle.command
    EvaluationReport.timestamp  → Bundle.generated_at
    EvaluationReportResult.model   → Bundle.model_id
    EvaluationReportResult.task    → Bundle.task_id  (None → "overall")
    EvaluationReportResult.metrics → Bundle.metrics  (key/value pairs, verbatim)

Valichord additions (no upstream equivalent):
    Bundle.outputs_merkle_root ← merkle_root() over eval_log_samples
    Bundle.format_version      ← "v1.2"

Stderr convention:
    inspect_evals represents stderr as a standalone metric entry::

        {"key": "stderr", "value": 0.032}

    in the same metrics list as the accuracy entry.  This adapter passes all
    metrics through verbatim — each entry becomes a Metric(key, value) with
    no Metric.stderr pairing.  The "stderr" entry becomes its own Metric with
    key="stderr" in the Bundle.  Callers who want paired accuracy+stderr can
    reconstruct the pairing from Bundle.metrics by name convention.

Multi-result reports:
    ``EvaluationReport.results`` is a list — one entry per model/configuration.
    Use ``result_index=`` to select a single result (default: 0).  For
    multi-model comparison reports, call ``to_bundle()`` once per model.
"""

from ..adapters.base import AdapterBase
from ..builder import build_bundle
from ..bundle import Bundle


class InspectEvalsAdapter(AdapterBase):
    """Adapter: inspect_evals eval.yaml evaluation_report block → Valichord Bundle."""

    def to_bundle(
        self,
        eval_yaml_block: dict,
        eval_log_samples: list[dict],
        *,
        result_index: int = 0,
    ) -> Bundle:
        """Convert an inspect_evals evaluation_report block to a Valichord Bundle.

        Args:
            eval_yaml_block:  dict parsed from the ``evaluation_report:`` YAML block.
            eval_log_samples: per-sample output dicts for the Merkle root.
                              See ``build_bundle()`` for the expected dict shape.
            result_index:     which ``EvaluationReportResult`` to use (default: 0).

        Returns:
            A Valichord Bundle ready for canonicalisation and hashing.

        Raises:
            ValueError:        if ``results`` is absent/empty or has no valid metrics.
            IndexError:        if ``result_index`` is out of range.
            MalformedBundleError: propagated from ``build_bundle()`` on bad metric values.
        """
        results = eval_yaml_block.get("results") or []
        if not results:
            raise ValueError(
                "eval_yaml_block must contain a non-empty 'results' list"
            )
        if result_index >= len(results):
            raise IndexError(
                f"result_index={result_index} out of range "
                f"for report with {len(results)} result(s)"
            )
        result = results[result_index]

        # Pass all metric entries verbatim — stderr is a standalone entry in inspect_evals.
        raw_metrics = [
            {"key": m["key"], "value": float(m["value"])}
            for m in (result.get("metrics") or [])
            if "key" in m and "value" in m
        ]
        if not raw_metrics:
            raise ValueError(
                f"result[{result_index}] contains no valid metrics "
                "(each entry must have 'key' and 'value')"
            )

        # Provenance fields that have no top-level Bundle slot go into meta.
        meta: dict = {}
        if eval_yaml_block.get("version"):
            meta["eval_version"] = eval_yaml_block["version"]
        if eval_yaml_block.get("notes"):
            meta["notes"] = eval_yaml_block["notes"]
        if result.get("provider"):
            meta["provider"] = result["provider"]
        if result.get("time"):
            meta["run_time"] = result["time"]
        if result.get("date"):
            meta["run_date"] = result["date"]

        return build_bundle(
            model_id=result["model"],
            task_id=result.get("task") or "overall",
            raw_metrics=raw_metrics,
            samples=eval_log_samples,
            repo_commit=eval_yaml_block.get("commit"),
            command=eval_yaml_block.get("command"),
            generated_at=eval_yaml_block.get("timestamp"),
            meta=meta or None,
        )
