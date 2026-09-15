"""Schema loader for hybrid_v2 outputs."""

from __future__ import annotations

from typing import Any

from contexttrace.contracts import load_json_schema


def load_output_schema() -> dict[str, Any]:
    return load_json_schema("ClaimVerificationHybridV2")
