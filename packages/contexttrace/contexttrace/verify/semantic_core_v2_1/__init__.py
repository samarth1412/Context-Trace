"""Safety-guarded, schema-compatible product profile for semantic_core_v2."""

from .profile import SELECTIVE_V2_1_PROFILE, V21Profile
from .runner import (
    verify_trace_file_v2_1,
    verify_trace_v2_1,
    verify_traces_v2_1,
)

__all__ = [
    "SELECTIVE_V2_1_PROFILE",
    "V21Profile",
    "verify_trace_file_v2_1",
    "verify_trace_v2_1",
    "verify_traces_v2_1",
]
