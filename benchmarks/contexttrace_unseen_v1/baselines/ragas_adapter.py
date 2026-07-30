"""Frozen reference-free adapter boundary for RAGAS 0.4.3."""

from __future__ import annotations

from typing import Any, Mapping

from .reference_free_exports import export_ragas


BASELINE_ID = "ragas_0_4_3"
PACKAGE_VERSION = "0.4.3"
EXECUTION_STATUS = "not_run_judge_model_and_budget_not_authorized"


def prepare_input(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return export_ragas(candidate)
