"""Reference-free, identity-preserving input adapters for external RAG evaluators."""

from __future__ import annotations

from typing import Any, Mapping

from .contract import BaselineInputError


def export_ragas(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Map only reference-free RAGAS fields; do not expose sealed gold."""

    return {
        "case_id": candidate["case_id"],
        "candidate_input_sha256": candidate["candidate_input_sha256"],
        "user_input": candidate["query"],
        "response": candidate["answer"],
        "retrieved_contexts": [
            context["text"] for context in candidate["selected_contexts"]
        ],
        "reference": None,
    }


def export_deepeval(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Map only reference-free DeepEval fields; do not expose sealed gold."""

    return {
        "case_id": candidate["case_id"],
        "candidate_input_sha256": candidate["candidate_input_sha256"],
        "input": candidate["query"],
        "actual_output": candidate["answer"],
        "retrieval_context": [
            context["text"] for context in candidate["selected_contexts"]
        ],
        "expected_output": None,
    }


def export_ragchecker(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Refuse an invalid reference-free RAGChecker run."""

    raise BaselineInputError(
        "RAGChecker requires a ground-truth answer. Its adapter may run only inside "
        "the sealed scoring zone after a reference-answer policy is preregistered."
    )
