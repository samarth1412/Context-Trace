"""Frozen reference-free adapter boundary for DeepEval 4.1.4."""

from __future__ import annotations

from typing import Any, Mapping

from .reference_free_exports import export_deepeval


BASELINE_ID = "deepeval_4_1_4"
PACKAGE_VERSION = "4.1.4"
EXECUTION_STATUS = "not_run_judge_model_and_budget_not_authorized"


def prepare_input(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return export_deepeval(candidate)
