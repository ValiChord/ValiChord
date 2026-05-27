"""W&B (Weights & Biases) Run → Valichord Bundle adapter.

Converts a finished wandb Run (fetched via the public wandb API) into a
Valichord Bundle suitable for cryptographic attestation and commit-reveal
submission.

Field mapping (wandb Run → Valichord Bundle):

    run.config[model_id_key]          → Bundle.model_id
    run.config[task_id_key]           → Bundle.task_id   (None → "overall")
    run.summary (numeric, non-_)      → Bundle.metrics
    run.metadata["git"]["commit"]     → Bundle.repo_commit
    run.metadata["program"] + args    → Bundle.command
    run.created_at                    → Bundle.generated_at
    eval_log_samples                  → Bundle.outputs_merkle_root
    run.entity / project / id / name  → Bundle.meta["wandb_*"] (provenance)

Model ID resolution (first match wins):
    1. run.config[model_id_key]    (default key: "model")
    2. run.config["model_name"]
    3. run.config["model_id"]
    4. run.name                    (wandb run display name — last resort)

Task ID resolution (first match wins):
    1. run.config[task_id_key]     (default key: "task")
    2. run.config["dataset"]
    3. run.config["benchmark"]
    4. run.config["task_name"]
    5. None → "overall"

Metrics:
    All numeric (int/float) values in run.summary whose keys do not begin
    with "_" (wandb internal fields: _runtime, _step, _timestamp, etc.).
    Pass metric_keys= to select a specific subset.
    Non-finite values (NaN, Inf) are silently dropped; if any are dropped
    they are listed in meta["filtered_non_finite_metrics"]. If all candidate
    metrics are non-finite, ValueError is raised.

Per-sample outputs (Merkle root):
    wandb does not auto-capture per-sample outputs. Pass eval_log_samples
    explicitly as a list of dicts (e.g. from a logged wandb.Table, an
    artifact file, or WandbRunAdapter.history_samples(run)).

    Obtaining samples from run history:
        samples = WandbRunAdapter.history_samples(run)  # one dict per step
        bundle  = adapter.to_bundle(run, samples)

Fetching a run:
    Use WandbRunAdapter.fetch_run("entity/project/run_id") to retrieve a run
    from the wandb API, then pass it to to_bundle(). This two-step design
    keeps all wandb API calls out of to_bundle() so tests can inject plain
    mock objects without touching the wandb package.

        run    = WandbRunAdapter.fetch_run("my-org/evals/run123")
        bundle = WandbRunAdapter().to_bundle(run, samples)

Requires wandb: pip install 'valichord-attestation[wandb]'
"""

from __future__ import annotations

import math
from typing import Optional

from ..adapters.base import AdapterBase
from ..builder import build_bundle
from ..bundle import Bundle

# Keys wandb injects into run.summary that are not user metrics.
_WANDB_INTERNAL_PREFIX = "_"


def _resolve_model_id(config: dict, model_id_key: str, run_name: str) -> str:
    for key in (model_id_key, "model_name", "model_id"):
        val = config.get(key)
        if val:
            return str(val)
    if run_name:
        return run_name
    raise ValueError(
        f"Cannot determine model_id: config has no '{model_id_key}', 'model_name', "
        "or 'model_id' key, and run.name is empty. "
        f"Pass model_id_key= to specify the config key that holds the model identifier."
    )


def _resolve_task_id(config: dict, task_id_key: str) -> str:
    for key in (task_id_key, "dataset", "benchmark", "task_name"):
        val = config.get(key)
        if val:
            return str(val)
    return "overall"


def _extract_metrics(
    summary: dict,
    metric_keys: Optional[list[str]],
) -> tuple[list[dict], list[str]]:
    """Return (raw_metrics_list, list_of_dropped_non_finite_keys)."""
    raw: list[dict] = []
    dropped: list[str] = []

    if metric_keys is not None:
        missing = [k for k in metric_keys if k not in summary]
        if missing:
            raise ValueError(
                f"metric_keys not found in run.summary: {missing}"
            )
        for key in metric_keys:
            val = summary[key]
            if not isinstance(val, (int, float)):
                raise ValueError(
                    f"metric_keys['{key}'] value is not numeric: "
                    f"{type(val).__name__!r} — only int/float are supported"
                )
            fval = float(val)
            if not math.isfinite(fval):
                dropped.append(key)
            else:
                raw.append({"key": key, "value": fval})
    else:
        for key, val in summary.items():
            if key.startswith(_WANDB_INTERNAL_PREFIX):
                continue
            if not isinstance(val, (int, float)):
                continue
            fval = float(val)
            if not math.isfinite(fval):
                dropped.append(key)
            else:
                raw.append({"key": key, "value": fval})

    return raw, dropped


def _build_command(metadata: dict) -> Optional[str]:
    program = metadata.get("program") or ""
    if not program:
        return None
    args = metadata.get("args") or []
    if args:
        return f"{program} {' '.join(str(a) for a in args)}"
    return program


class WandbRunAdapter(AdapterBase):
    """Adapter: wandb Run → Valichord Bundle."""

    @staticmethod
    def fetch_run(run_path: str):
        """Fetch a wandb Run by path (``"entity/project/run_id"``).

        Requires wandb: ``pip install 'valichord-attestation[wandb]'``
        """
        try:
            import wandb
        except ImportError as exc:
            raise ImportError(
                "wandb is required for WandbRunAdapter: "
                "pip install 'valichord-attestation[wandb]'"
            ) from exc
        return wandb.Api().run(run_path)

    @staticmethod
    def history_samples(run, *, max_rows: int = 5000) -> list[dict]:
        """Return run history rows as eval_log_samples for the Merkle root.

        Each history row (one per logged step) becomes one sample dict.
        Useful when no explicit per-sample prediction table was logged.

        Args:
            run:      wandb public API Run object.
            max_rows: upper bound on rows fetched (default 5 000).
        """
        return [dict(row) for row in run.scan_history(max_rows=max_rows)]

    def to_bundle(
        self,
        run,
        eval_log_samples: list[dict],
        *,
        model_id_key: str = "model",
        task_id_key: str = "task",
        metric_keys: Optional[list[str]] = None,
    ) -> Bundle:
        """Convert a finished wandb Run to a Valichord Bundle.

        Args:
            run:              wandb public API Run object (from ``fetch_run``
                              or ``wandb.Api().run(...)``).
            eval_log_samples: per-sample output dicts for the Merkle root.
                              Use ``history_samples(run)`` to derive these
                              from the run's step history when no explicit
                              prediction table was logged.
            model_id_key:     config key used to look up the model identifier
                              (default ``"model"``).  Falls back through
                              ``"model_name"``, ``"model_id"``, then ``run.name``.
            task_id_key:      config key used to look up the task/eval name
                              (default ``"task"``).  Falls back through
                              ``"dataset"``, ``"benchmark"``, ``"task_name"``,
                              then ``"overall"``.
            metric_keys:      explicit list of run.summary keys to include as
                              metrics.  When None, all numeric non-internal
                              summary keys are used.

        Returns:
            A Valichord Bundle ready for canonicalisation and hashing.

        Raises:
            ValueError:          if model_id cannot be resolved, if metric_keys
                                 names are absent from summary, or if no finite
                                 numeric metrics remain after filtering.
            MalformedBundleError: propagated from build_bundle().
        """
        config = dict(run.config) if run.config else {}
        summary = dict(run.summary) if run.summary else {}
        metadata = dict(run.metadata) if run.metadata else {}

        model_id = _resolve_model_id(config, model_id_key, getattr(run, "name", "") or "")
        task_id = _resolve_task_id(config, task_id_key)

        raw_metrics, dropped = _extract_metrics(summary, metric_keys)
        if not raw_metrics:
            raise ValueError(
                "run.summary contains no usable numeric metrics "
                "(all values were non-numeric, wandb-internal, or non-finite). "
                "Pass metric_keys= to select specific keys."
            )

        # Provenance fields → meta (excluded from content_hash).
        meta: dict = {}

        # wandb run identity
        for attr, meta_key in (
            ("entity", "wandb_entity"),
            ("project", "wandb_project"),
            ("id", "wandb_run_id"),
            ("name", "wandb_run_name"),
            ("url", "wandb_run_url"),
        ):
            val = getattr(run, attr, None)
            if val:
                meta[meta_key] = str(val)

        tags = getattr(run, "tags", None) or []
        if tags:
            meta["tags"] = list(tags)

        notes = getattr(run, "notes", None)
        if notes:
            meta["notes"] = str(notes)

        if dropped:
            meta["filtered_non_finite_metrics"] = dropped

        repo_commit = metadata.get("git", {}).get("commit") or None
        command = _build_command(metadata)

        return build_bundle(
            model_id=model_id,
            task_id=task_id,
            raw_metrics=raw_metrics,
            samples=eval_log_samples,
            repo_commit=repo_commit,
            command=command,
            generated_at=getattr(run, "created_at", None) or None,
            meta=meta or None,
        )
