"""
Holochain bridge — thin Python wrapper around the /holochain/* endpoints
served by demo/serve.mjs.

serve.mjs must be running on localhost:8888 (i.e. the ValiChord demo stack
is up) for these calls to succeed.  All functions degrade gracefully: if the
bridge is unreachable they return None and log a warning rather than raising,
so the analysis pipeline always completes even without a live conductor.
"""

import logging
import requests

BRIDGE_BASE = 'http://localhost:8888'
BRIDGE_TIMEOUT = 120   # seconds — allow time for WASM JIT + DHT operations

log = logging.getLogger(__name__)


def run_validation_round(
    data_hash_hex: str,
    outcome: dict,
    discipline: dict | None = None,
    confidence: str | None = None,
) -> dict | None:
    """Run the full single-agent commit-reveal round via the Node bridge.

    Parameters
    ----------
    data_hash_hex : str
        64-character lowercase hex string — SHA-256 of the deposit ZIP.
    outcome : dict
        AttestationOutcome in adjacent-tag form, e.g.
          {"type": "Reproduced"}
          {"type": "PartiallyReproduced", "content": {"details": "..."}}
    discipline : dict, optional
        Discipline in adjacent-tag form, e.g. {"type": "ComputationalBiology"}.
        Defaults to ComputationalBiology when omitted.
    confidence : str, optional
        "High" | "Medium" | "Low".  Defaults to "Medium".

    Returns
    -------
    dict or None
        {"harmony_record_hash": <{"__bytes": "base64"} or None>}
        Returns None if the bridge is unreachable or the round fails.
    """
    payload = {
        'data_hash_hex': data_hash_hex,
        'outcome':       outcome,
        'discipline':    discipline or {'type': 'ComputationalBiology'},
        'confidence':    confidence or 'Medium',
    }
    try:
        r = requests.post(
            f'{BRIDGE_BASE}/holochain/validate-round',
            json=payload,
            timeout=BRIDGE_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        log.warning('Holochain bridge not reachable (serve.mjs not running) — skipping')
        return None
    except Exception as exc:
        log.warning('Holochain validate-round failed: %s', exc)
        return None
