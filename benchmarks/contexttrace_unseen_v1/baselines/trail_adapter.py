"""Scope record for the deferred TRAIL agent-transfer experiment."""

from __future__ import annotations

from typing import NoReturn

from .contract import BaselineInputError


BASELINE_ID = "trail_paper_2505_08638"
EXECUTION_STATUS = "deferred_secondary_agent_transfer_incompatible_primary_inputs"


def prepare_input() -> NoReturn:
    raise BaselineInputError(
        "TRAIL consumes agent execution traces, not the primary RAG candidate "
        "contract. It is deferred to the preregistered secondary transfer study."
    )
