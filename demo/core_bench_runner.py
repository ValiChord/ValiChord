"""Orchestrates the CORE-Bench commit-reveal demo: researcher claim -> three
mixed-model validators -> commit-reveal via the existing demo node HTTP APIs ->
HarmonyRecord -> recomputable numeric panel.

Reuses demo_runner's node HTTP helpers and agreement.py so the displayed
outcome matches the on-chain HarmonyRecord by construction."""
import hashlib
import os

from inspect_evals.core_bench.dataset import CAPSULE_CHECKSUMS

# provider env var expected per model-string prefix
_PROVIDER_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
}


def claim_to_metrics(claim: dict) -> list:
    """Encode the committed claim as a MetricResult list for /lock-result.
    The interval is sealed in expected_value (string) so it is committed
    on-chain and any third party can read the bounds the match was judged
    against."""
    metrics = []
    for q, spec in claim.items():
        metrics.append({
            "metric_name": q,
            "produced_value": repr(spec["value"]),
            "expected_value": f"[{spec['lower']!r}, {spec['upper']!r}] ({spec['basis']})",
            "within_tolerance": True,
        })
    return metrics


def compute_capsule_data_hash(capsule_id: str, salt: bytes) -> str:
    """data_hash = SHA-256(capsule_tarball_checksum_bytes || salt). Binds the
    claim to the exact verified capsule; salt makes each run a fresh identity."""
    checksum_hex = CAPSULE_CHECKSUMS[capsule_id]
    return hashlib.sha256(bytes.fromhex(checksum_hex) + salt).hexdigest()


def validate_model_keys(models: list) -> None:
    """Fail fast if any required provider key is missing, naming the offender."""
    missing = []
    for model in models:
        provider = model.split("/", 1)[0]
        env = _PROVIDER_KEY_ENV.get(provider)
        if env is None:
            raise RuntimeError(f"Unknown model provider in '{model}' (expected one of {list(_PROVIDER_KEY_ENV)})")
        if not os.environ.get(env):
            missing.append(f"{env} (needed for validator model '{model}')")
    if missing:
        raise RuntimeError("Missing required provider API keys:\n  - " + "\n  - ".join(missing))
