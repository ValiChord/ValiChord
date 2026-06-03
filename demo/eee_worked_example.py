"""Generate the EEE worked-example bundles from EXISTING CORE-Bench artifacts.

This reproduces, fully offline (no API key, no fresh run), the same per-validator
`valichord_attestation` bundles that `core_bench_runner.py --emit-bundles` would
write after a live round -- but sourced from the real `.eval` logs and the real,
publicly-curl-able HarmonyRecord already on the Oracle DHT.

It is the worked example referenced in the EveryEvalEver (EEE) convergence thread:
several independent validators reproduce ONE capsule, each blind, all sharing one
tamper-evident `attestation_uri`. Here all three validators are claude-sonnet-4-6
(the all-Sonnet round that produced Oracle record uhC8k4j2...), so it is an honest
SAME-model example. A cross-model headline needs a real mixed-model run.

Run:  cd demo && python3 eee_worked_example.py
"""
import glob
import json
from pathlib import Path

from inspect_ai.log import read_eval_log

from report_to_verdict import derive_committed_claim
from core_bench_bundle import emit_core_bench_bundles

CAPSULE = "capsule-0851068"
RESEARCHER_MODEL = "anthropic/claude-sonnet-4-6"

# The all-Sonnet round (2026-05-31) that produced the public Oracle HarmonyRecord.
# First three are the validators; the round's researcher run is a 4th sonnet log.
VALIDATOR_LOGS = [
    ("Validator 1", "logs/2026-05-31T20-40-04-00-00_task_TjeyHpwQXzTowojg7rMCNp.eval"),
    ("Validator 2", "logs/2026-05-31T20-44-49-00-00_task_4zRarAnsfC6tVAasUMtSdn.eval"),
    ("Validator 3", "logs/2026-05-31T20-55-30-00-00_task_BzGHhj6BR*.eval"),
]
RESEARCHER_VALUE = 0.9157952669235003  # researcher --researcher-runs 1, capsule AUC

# Real, live, publicly-curl-able HarmonyRecord on the Oracle DHT for this round.
RECORD_HASH = "uhC8k4j2xO83gyCFCBMTAtx2Nyy_i_Yr4oDk-X1XJlbOZsI0-bYNT"
RESULT = {
    "record_url": f"http://132.145.34.27:3001/record?hash={RECORD_HASH}",
    "harmony_record_hash": RECORD_HASH,
    # The ValidationRequest data hash is held on the authoring node; the public
    # /record endpoint does not expose it. The verifiable anchor is the record.
    "external_hash_b64": None,
    "outcome": "Reproduced",
    "agreement_level": "ExactMatch",
}


def _report_from_log(path):
    """Lift the captured report.json out of an .eval log's capture_report score."""
    log = read_eval_log(path)
    sample = log.samples[0]
    for score in (sample.scores or {}).values():
        if score.metadata and "report" in score.metadata:
            return score.metadata["report"]
    raise ValueError(f"no captured report in {path}")


def main():
    committed_claim = derive_committed_claim(
        [{"Report the final AUC after training.": RESEARCHER_VALUE}]
    )
    RESULT["committed_claim"] = committed_claim

    model = "anthropic/claude-sonnet-4-6"
    validator_reports, validator_eval_logs, validator_models = [], [], []
    for label, pattern in VALIDATOR_LOGS:
        path = glob.glob(pattern)[0]
        validator_reports.append((label, _report_from_log(path)))
        validator_eval_logs.append(path)
        validator_models.append(model)

    # emit_core_bench_bundles now disambiguates same-model rounds by validator
    # index (bundle_<capsule>_v{n}_<model>.json), so 3 Sonnet validators no
    # longer collide onto one file.
    out_dir = Path("bundles_worked_example")
    paths = emit_core_bench_bundles(
        capsule_id=CAPSULE,
        researcher_model=RESEARCHER_MODEL,
        validator_models=validator_models,
        validator_reports=validator_reports,
        validator_eval_logs=validator_eval_logs,
        result=RESULT,
        out_dir=out_dir,
    )

    committed = committed_claim["Report the final AUC after training."]
    print(f"committed interval: [{committed['lower']}, {committed['upper']}] "
          f"(basis={committed['basis']})\n")
    for p in paths:
        w = json.loads(p.read_text())
        b = w["bundle"]
        print(f"{p.name}")
        print(f"  bundle_sha256 : {w['_source']['bundle_sha256']}")
        print(f"  metrics       : {b['metrics']}")
        print(f"  samples       : {len(w['samples'])}  -> {[s['sample_id'] for s in w['samples']]}")
        print(f"  attestation   : {b['meta']['attestation_uri']}")
    print(f"\n{len(paths)} bundles written to {out_dir}/")


if __name__ == "__main__":
    main()
