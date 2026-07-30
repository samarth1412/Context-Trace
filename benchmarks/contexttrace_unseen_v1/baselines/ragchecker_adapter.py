"""Frozen adapter boundary for RAGChecker 0.1.9."""

from __future__ import annotations

from typing import Any, Mapping

from .reference_free_exports import export_ragchecker


BASELINE_ID = "ragchecker_0_1_9"
PACKAGE_VERSION = "0.1.9"
EXECUTION_STATUS = "sealed_scoring_zone_only_reference_answer_required"


def prepare_input(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return export_ragchecker(candidate)
