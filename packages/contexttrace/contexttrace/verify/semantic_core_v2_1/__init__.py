"""Safety-guarded, schema-compatible product profile for semantic_core_v2."""

from .claims import ATOMIC_CLAIM_UNITIZER_VERSION, unitize_atomic_claims
from .profile import (
    DETERMINISTIC_ONLY_V2_1_PROFILE,
    SELECTIVE_V2_1_PROFILE,
    V21Profile,
)
from .runner import (
    verify_trace_file_v2_1,
    verify_trace_v2_1,
    verify_traces_v2_1,
)

__all__ = [
    "ATOMIC_CLAIM_UNITIZER_VERSION",
    "DETERMINISTIC_ONLY_V2_1_PROFILE",
    "SELECTIVE_V2_1_PROFILE",
    "V21Profile",
    "unitize_atomic_claims",
    "verify_trace_file_v2_1",
    "verify_trace_v2_1",
    "verify_traces_v2_1",
]
