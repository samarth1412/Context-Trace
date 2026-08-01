"""Safety-guarded, schema-compatible product profile for semantic_core_v2."""

from .checker import (
    OBSERVABLE_CONFLICT_GUARD_VERSION,
    ObservableConflict,
    ObservableConflictGuard,
    observable_conflicts,
)
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
    "OBSERVABLE_CONFLICT_GUARD_VERSION",
    "SELECTIVE_V2_1_PROFILE",
    "ObservableConflict",
    "ObservableConflictGuard",
    "V21Profile",
    "observable_conflicts",
    "unitize_atomic_claims",
    "verify_trace_file_v2_1",
    "verify_trace_v2_1",
    "verify_traces_v2_1",
]
