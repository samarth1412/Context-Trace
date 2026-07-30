"""Load and validate versioned semantic_core_v2 rule-pack metadata."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

from .constants import GENERIC_RULEPACK_VERSION, SOURCE_RULEPACK_VERSION


def load_rulepacks() -> list[dict[str, Any]]:
    package = resources.files("contexttrace.verify.semantic_core_v2")
    expected = {
        "generic_v2.json": GENERIC_RULEPACK_VERSION,
        "source_condition_v2.json": SOURCE_RULEPACK_VERSION,
    }
    records: list[dict[str, Any]] = []
    for filename, version in expected.items():
        payload = json.loads(
            package.joinpath("rulepacks", filename).read_text(encoding="utf-8")
        )
        if payload.get("version") != version:
            raise RuntimeError(f"Rule-pack version mismatch: {filename}")
        records.append(payload)
    return records
