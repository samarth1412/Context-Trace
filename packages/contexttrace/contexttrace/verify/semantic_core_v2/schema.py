"""Access to the frozen semantic_core_v2 candidate-output schema."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any


OUTPUT_SCHEMA_RESOURCE = "claim-verification-v2.schema.json"


def load_output_schema() -> dict[str, Any]:
    return json.loads(
        resources.files("contexttrace.schemas")
        .joinpath(OUTPUT_SCHEMA_RESOURCE)
        .read_text(encoding="utf-8")
    )
