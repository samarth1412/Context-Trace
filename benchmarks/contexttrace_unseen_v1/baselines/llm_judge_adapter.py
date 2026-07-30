"""Frozen prompt contract for an optional, separately authorized LLM judge."""

from __future__ import annotations

from typing import Any, Mapping

from .contract import BaselineInputError, canonical_sha256


BASELINE_ID = "generic_llm_judge_v1"
EXECUTION_STATUS = "not_run_model_and_budget_not_authorized"
PROMPT_TEMPLATE = """Assess whether ANSWER is supported by CONTEXT for QUERY.
Return JSON only:
{"supported": true|false|"unverifiable", "confidence": number, "reason": string}
Do not use outside knowledge. Do not assign a retrieval or generation root cause.

QUERY:
{query}

ANSWER:
{answer}

CONTEXT:
{context}
"""
PROMPT_SHA256 = canonical_sha256({"template": PROMPT_TEMPLATE})


def prepare_input(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_id": candidate["case_id"],
        "candidate_input_sha256": candidate["candidate_input_sha256"],
        "prompt_sha256": PROMPT_SHA256,
        "prompt": PROMPT_TEMPLATE.format(
            query=candidate["query"],
            answer=candidate["answer"],
            context="\n\n".join(
                f"[{item['chunk_id']}]\n{item['text']}"
                for item in candidate["selected_contexts"]
            ),
        ),
    }


def execute(*_: Any, **__: Any) -> None:
    raise BaselineInputError(
        "No LLM judge model, dated API version, credentials, or budget is authorized."
    )
