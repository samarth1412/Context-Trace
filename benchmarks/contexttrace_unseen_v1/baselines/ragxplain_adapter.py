"""Availability record for RAGXplain."""

from __future__ import annotations

from typing import NoReturn

from .contract import BaselineInputError


BASELINE_ID = "ragxplain_paper_2505_13538"
EXECUTION_STATUS = "not_available_no_reproducible_artifact_identity_locked"


def prepare_input() -> NoReturn:
    raise BaselineInputError(
        "RAGXplain is paper-only in this lock: no reproducible package or source "
        "artifact identity was established. No substitute implementation is allowed."
    )
