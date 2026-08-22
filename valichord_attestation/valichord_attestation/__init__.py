from .adapters.inspect_ai_log_adapter import InspectAILogAdapter
from .adapters.inspect_evals_stub import InspectEvalsAdapter
from .adapters.pi_session_adapter import PiSessionAdapter
from .bundle import Bundle, Metric, MalformedBundleError
from .builder import build_bundle
from .canonical import (
    bundle_to_dict,
    canonicalise,
    content_hash,
    content_preimage,
    hash_bundle,
    pre_round,
)
from .challenge import Challenge, compute_challenge_hash, derive_seed, generate_indices
from .merkle import (
    UnknownFormatVersion,
    leaf_hash,
    merkle_proof,
    merkle_root,
    root_from_path,
    verify_faithfulness,
)
from .protocol import (
    data_hash,
    data_hash_b64,
    decode_holo_hash,
    encode_holo_hash,
    reproduction_bundle_hash,
    submission_bytes,
)
from .response import ChallengeResponse, ResponseSample, build_response, verify_response

__all__ = [
    "Bundle",
    "Metric",
    "MalformedBundleError",
    "build_bundle",
    "bundle_to_dict",
    "canonicalise",
    "content_hash",
    "content_preimage",
    "hash_bundle",
    "pre_round",
    "leaf_hash",
    "merkle_root",
    "merkle_proof",
    "root_from_path",
    "UnknownFormatVersion",
    "verify_faithfulness",
    "Challenge",
    "compute_challenge_hash",
    "derive_seed",
    "generate_indices",
    "ChallengeResponse",
    "ResponseSample",
    "build_response",
    "verify_response",
    # Protocol bridge - see docs/PROTOCOL_INTEGRATION_BOUNDARY.md
    "submission_bytes",
    "data_hash",
    "data_hash_b64",
    "reproduction_bundle_hash",
    "encode_holo_hash",
    "decode_holo_hash",
    "InspectAILogAdapter",
    "InspectEvalsAdapter",
    "PiSessionAdapter",
]
