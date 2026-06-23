"""MLCommons AILuminate / modelbench report → Valichord Bundle adapter.

Reads the JSON report produced by ``modelbench``'s ``dump_json()`` function
(the file typically named ``benchmark_run_*.json``) and an optional per-item
annotation list from ``BenchmarkRun.compile_annotations()``, and converts them
into a canonical Valichord Bundle.

Field mapping (modelbench report → Valichord Bundle):

    scores[i].sut.uid                     → Bundle.model_id
    benchmark.uid                         → Bundle.task_id  (override with task_id_override=)
    scores[i].hazard_scores[j]:
        hazard_definition.uid short-code  → metric key prefix  (e.g. "cse", "dfm")
        score.estimate                    → "{code}_safe_rate" metric value
        numeric_grade (1–5)               → "{code}_numeric_grade" (when include_numeric_grade=True)
    scores[i].score                       → "overall_safe_rate" metric (overall benchmark score)
    scores[i].end_time                    → Bundle.generated_at
    _metadata.code.source.code_version    → Bundle.repo_commit (git describe)
    compile_annotations() list            → Bundle.outputs_merkle_root (per-item dicts)

Hazard short-code extraction:
    The last ``-``-delimited segment of the hazard UID is used as the metric key
    prefix — ``"safe_hazard-1_0-cse"`` → ``"cse"``.  For UIDs that don't follow
    this pattern, the full UID is normalised (non-alphanumeric → ``_``).

Multiple SUTs:
    A modelbench report may contain scores for several models.  When ``scores``
    has more than one entry, ``sut_uid=`` is required to select one.  A single-SUT
    report uses that SUT automatically.

Metrics:
    Primary (always included):
        ``{code}_safe_rate``      — fraction of prompts graded safe (0–1) per hazard
        ``overall_safe_rate``     — top-level benchmark score (fraction safe)
    Optional (default on):
        ``{code}_numeric_grade``  — ordinal grade 1 (poor) – 5 (excellent)

Per-item annotation dict format (from compile_annotations):
    {
        "hazard":    str  — hazard short name (e.g. ``"safe_cse"``)
        "prompt":    str  — prompt text
        "response":  str  — model response
        "is_safe":   bool — grader ensemble verdict
        "is_valid":  bool — whether the annotation is valid
    }
    The full dict is used as the Merkle leaf — it commits to the response and
    verdict together, which is exactly what an independent validator must reproduce.

Fallback when no annotations are provided:
    One summary leaf per hazard is synthesised from the aggregate hazard scores,
    containing ``hazard_uid``, ``num_scored_items``, ``num_safe_items``, and
    ``safe_rate``.  This gives the adapter a usable Merkle root even when
    per-item annotations are unavailable, at the cost of coarser granularity.

Producing the required files:
    # Run modelbench (AILuminate v1.0 example):
    modelbench run --benchmark ailuminate-1.0 --sut gpt-4o \\
                   --output-dir ./benchmark_output
    # Produces: benchmark_output/benchmark_run_*.json (main report)
    #           benchmark_output/annotations_*.json   (per-item, when --annotations flag used)
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Optional

from ..adapters.base import AdapterBase
from ..builder import build_bundle
from ..bundle import Bundle


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _hazard_short_code(uid: str) -> str:
    """Extract a short metric-key-safe code from a modelbench hazard UID.

    ``"safe_hazard-1_0-cse"`` → ``"cse"``
    ``"safe_hazard-1_0-ssh"`` → ``"ssh"``
    Falls back to a normalised form of the full UID for non-standard patterns.
    """
    parts = uid.rsplit("-", 1)
    if len(parts) == 2:
        code = parts[1]
        # Accept short alphabetic codes (2–5 chars) as-is
        if 2 <= len(code) <= 5 and code.isalpha():
            return code.lower()
    # Fall back: normalise the full UID
    return re.sub(r"[^a-z0-9]+", "_", uid.lower()).strip("_")


def _select_sut_score(scores: list, sut_uid: Optional[str]) -> dict:
    """Return the single SUT score dict to bundle, or raise.

    Args:
        scores:  list of score dicts from ``report["scores"]``.
        sut_uid: UID of the desired SUT.  Required when ``len(scores) > 1``.
    """
    if not scores:
        raise ValueError("report['scores'] is empty — no SUT scores to bundle.")

    if sut_uid is None:
        if len(scores) > 1:
            uids = [s.get("sut", {}).get("uid", "?") for s in scores]
            raise ValueError(
                f"Report contains {len(scores)} SUT scores: {uids}. "
                "Pass sut_uid= to select one."
            )
        return scores[0]

    for score in scores:
        if score.get("sut", {}).get("uid") == sut_uid:
            return score
    available = [s.get("sut", {}).get("uid", "?") for s in scores]
    raise ValueError(
        f"sut_uid={sut_uid!r} not found in report scores. "
        f"Available: {available}"
    )


def _extract_metrics(
    sut_score: dict,
    include_numeric_grade: bool,
) -> list[dict]:
    """Extract per-hazard safe rates (and optional numeric grades) as metric dicts."""
    raw: list[dict] = []
    for hs in sut_score.get("hazard_scores") or []:
        hdef = hs.get("hazard_definition") or {}
        uid = hdef.get("uid") or ""
        code = _hazard_short_code(uid) if uid else None
        if not code:
            continue

        # Primary: fraction safe (0–1)
        score_block = hs.get("score") or {}
        estimate = score_block.get("estimate")
        if estimate is not None:
            try:
                fval = float(estimate)
                if math.isfinite(fval):
                    raw.append({"key": f"{code}_safe_rate", "value": fval})
            except (TypeError, ValueError):
                pass

        # Optional: ordinal grade 1–5
        if include_numeric_grade:
            grade = hs.get("numeric_grade")
            if grade is not None:
                try:
                    gval = float(grade)
                    if math.isfinite(gval):
                        raw.append({"key": f"{code}_numeric_grade", "value": gval})
                except (TypeError, ValueError):
                    pass

    # Overall benchmark score
    overall = sut_score.get("score")
    if overall is not None:
        try:
            oval = float(overall)
            if math.isfinite(oval) and oval > 0.0:  # 0.0 is the uninitialised default
                raw.append({"key": "overall_safe_rate", "value": oval})
        except (TypeError, ValueError):
            pass

    return raw


def _build_sample_list(
    annotations: Optional[list],
    sut_score: dict,
) -> list[dict]:
    """Return a flat list of per-item dicts for the Merkle root.

    When ``annotations`` are provided (from ``compile_annotations()``), each
    item dict is used as-is as a Merkle leaf.  When absent, one summary leaf
    per hazard is synthesised from the aggregate hazard scores.
    """
    if annotations is not None:
        # Each annotation is already a canonical dict: hazard, prompt, response,
        # is_safe, is_valid.  Use directly.
        return [dict(a) for a in annotations if isinstance(a, dict)]

    # Fallback: one aggregate leaf per hazard
    leaves: list[dict] = []
    for hs in sut_score.get("hazard_scores") or []:
        hdef = hs.get("hazard_definition") or {}
        uid = hdef.get("uid") or ""
        score_block = hs.get("score") or {}
        leaf: dict = {"hazard_uid": uid}
        for field in ("num_scored_items", "num_safe_items"):
            val = hs.get(field)
            if val is not None:
                leaf[field] = val
        estimate = score_block.get("estimate")
        if estimate is not None:
            leaf["safe_rate"] = estimate
        leaves.append(leaf)
    return leaves


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class AiluminateAdapter(AdapterBase):
    """Adapter: MLCommons AILuminate / modelbench report → Valichord attestation Bundle.

    Reads the main ``benchmark_run_*.json`` report produced by ``modelbench``.
    Optionally accepts per-item annotation dicts from ``compile_annotations()``
    to build a per-prediction Merkle root.

    See module docstring for field mapping, hazard code extraction, and
    per-item annotation format.
    """

    def to_bundle(
        self,
        report: "dict | str | Path",
        annotations: "Optional[list[dict]]" = None,
        *,
        sut_uid: Optional[str] = None,
        task_id_override: Optional[str] = None,
        include_numeric_grade: bool = True,
        samples_total: Optional[int] = None,
        meta_extras: Optional[dict] = None,
    ) -> Bundle:
        """Convert a modelbench report to a Valichord attestation Bundle.

        Args:
            report: modelbench ``benchmark_run_*.json`` dict or path to that file.
            annotations: per-item dicts from ``compile_annotations()`` — list of
                         ``{hazard, prompt, response, is_safe, is_valid}`` dicts.
                         When None, summary leaves are synthesised from the
                         aggregate hazard scores.
            sut_uid: UID of the SUT (model) to bundle.  Required when the report
                     contains scores for more than one model.
            task_id_override: explicit Bundle.task_id, overriding the auto-derived
                              ``benchmark.uid``.
            include_numeric_grade: when True (default), ``{code}_numeric_grade``
                                   metrics (1–5) are included alongside safe rates.
            samples_total: declared total prompt count for sample-omission detection
                           (threat model §10(d)).
            meta_extras: extra key/value pairs merged last into Bundle.meta.

        Returns:
            A Valichord Bundle ready for canonicalisation and hashing.

        Raises:
            ValueError:          if the report is malformed, has no SUT scores, or
                                 no finite numeric metrics can be extracted.
            MalformedBundleError: propagated from build_bundle().
        """
        # ---- load from file or use dict directly ----------------------------
        if isinstance(report, (str, Path)):
            with open(report, encoding="utf-8") as f:
                report = json.load(f)

        if not isinstance(report, dict):
            raise ValueError(
                f"report must be a dict or path to a JSON file, got {type(report).__name__!r}"
            )

        scores: list = report.get("scores") or []
        sut_score = _select_sut_score(scores, sut_uid)

        # ---- model and task IDs ---------------------------------------------
        model_id: str = str((sut_score.get("sut") or {}).get("uid") or "")
        if not model_id:
            raise ValueError(
                "Cannot determine model_id: report scores[i].sut.uid is missing."
            )

        benchmark: dict = report.get("benchmark") or {}
        task_id = task_id_override or str(benchmark.get("uid") or "ailuminate")

        # ---- metrics --------------------------------------------------------
        raw_metrics = _extract_metrics(sut_score, include_numeric_grade)
        if not raw_metrics:
            raise ValueError(
                "No finite numeric metrics found in the report. "
                "Check that modelbench scored at least one hazard category."
            )

        # ---- samples → Merkle root ------------------------------------------
        sample_list = _build_sample_list(annotations, sut_score)
        if not sample_list:
            raise ValueError(
                "No samples or hazard scores available for Merkle root. "
                "The report appears to have no hazard scores and no annotations."
            )

        # ---- generated_at ---------------------------------------------------
        generated_at: Optional[str] = None
        end_time = sut_score.get("end_time")
        if end_time:
            generated_at = str(end_time)
        else:
            # Fall back to _metadata.run.timestamp
            run_meta = (report.get("_metadata") or {}).get("run") or {}
            ts = run_meta.get("timestamp")
            if ts:
                generated_at = str(ts)

        # ---- repo_commit from code_version ----------------------------------
        repo_commit: Optional[str] = None
        code_info = (
            (report.get("_metadata") or {}).get("code") or {}
        ).get("source") or {}
        code_version = code_info.get("code_version")
        if code_version:
            repo_commit = str(code_version)

        # ---- meta -----------------------------------------------------------
        meta: dict = {}

        run_uid = report.get("run_uid")
        if run_uid:
            meta["run_uid"] = str(run_uid)

        run_info = (report.get("_metadata") or {}).get("run") or {}
        if run_info.get("python"):
            meta["python"] = run_info["python"]

        exceptions = sum(
            hs.get("exceptions", 0)
            for hs in sut_score.get("hazard_scores") or []
        )
        if exceptions:
            meta["exceptions"] = exceptions

        overall_numeric_grade = sut_score.get("numeric_grade")
        if overall_numeric_grade is not None:
            meta["overall_numeric_grade"] = overall_numeric_grade
            meta["overall_text_grade"] = sut_score.get("text_grade", "")

        if meta_extras:
            meta.update(meta_extras)

        return build_bundle(
            model_id=model_id,
            task_id=task_id,
            raw_metrics=raw_metrics,
            samples=sample_list,
            samples_total=samples_total,
            repo_commit=repo_commit,
            harness_version="modelbench",
            generated_at=generated_at,
            meta=meta or None,
        )
