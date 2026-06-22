"""
OETP Bridge — embed a ValiChord HarmonyRecord into an Open Ethics
Transparency Protocol disclosure.

OETP schema: https://github.com/OpenEthicsAI/OETP
Integration point: snapshot.processing.source[] — an array of
{type, url, comments} pointers to external evidence.

Usage (inject into an existing disclosure):
    from oetp_bridge import inject_into_disclosure
    enriched = inject_into_disclosure(existing_oetp_dict, round_result)

Usage (generate a minimal disclosure from scratch):
    from oetp_bridge import minimal_disclosure
    disclosure = minimal_disclosure("https://example.com/mymodel", round_result)

`round_result` is the dict returned by demo_runner.run_round() or
ai_validator.run_decentralised_protocol(). Both are accepted; the bridge
handles the key difference ('outcome' vs 'outcome_type').
"""

import copy
import time


def valichord_source_entry(round_result: dict) -> dict:
    """Build an OETP processing.source item from a ValiChord round result."""
    outcome = round_result.get('outcome_type') or round_result.get('outcome', 'Unknown')
    agreement = round_result.get('agreement_level', 'Unknown')
    count = round_result.get('validator_count', '?')
    record_url = round_result.get('record_url', '')
    harmony_hash = round_result.get('harmony_record_hash', '')

    return {
        "type": "ValiChord Reproducibility Attestation",
        "url": record_url,
        "comments": (
            f"{outcome} ({agreement}, {count}/{count} validators). "
            f"Independent blind commit-reveal verification on Holochain DHT. "
            f"Record: {harmony_hash}"
        ),
    }


def inject_into_disclosure(disclosure: dict, round_result: dict) -> dict:
    """Return a copy of *disclosure* with a ValiChord source entry appended.

    Creates snapshot.processing.source if absent. Does not mutate the input.
    """
    disclosure = copy.deepcopy(disclosure)
    processing = disclosure.setdefault('snapshot', {}).setdefault('processing', {})
    processing.setdefault('source', []).append(valichord_source_entry(round_result))
    return disclosure


def minimal_disclosure(product_url: str, round_result: dict) -> dict:
    """Minimal valid OETP disclosure anchored to a single ValiChord round.

    For systems with no existing disclosure that want to generate one from
    the ValiChord attestation record alone. The label fields (data/source/
    decision) are left with empty practice strings — fill them in for a
    production disclosure.
    """
    return {
        "schema": {
            "name": "Open Ethics Transparency Protocol",
            "version": "0.9.3 RFC",
            "integrity": "",
        },
        "snapshot": {
            "product": {"url": product_url},
            "timestamp": int(time.time()),
            "generator": {
                "name": "ValiChord",
                "alias": "valichord",
                "type": "third-party",
                "website": "https://valichord-demo.onrender.com",
            },
            "label": {
                "data":     {"type": "proprietary", "practice": ""},
                "source":   {"type": "open",        "practice": ""},
                "decision": {"type": "automated",   "practice": ""},
            },
            "processing": {
                "source": [valichord_source_entry(round_result)],
            },
        },
    }
