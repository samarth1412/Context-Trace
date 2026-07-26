from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from benchmarks.contexttrace_unseen_v1.collect_natural_ood import (
    AUTHORIZED_SCHEDULE_SHA256,
    BudgetLedger,
    Chunk,
    CollectionError,
    Document,
    PendingAttemptError,
    actual_openai_cost,
    bm25_scores,
    chunk_documents,
    deterministic_seed_excerpt,
    extract_citations,
    extract_openai_text,
    openai_payload,
    parse_documents,
    request_upper_cost,
    rrf_indices,
    stable_top_indices,
    validate_query,
)


def test_document_parsing_chunking_and_seed_excerpt_are_deterministic() -> None:
    source = (
        "ignored preamble\n"
        "===== FILE: first.md =====\n"
        + "alpha "
        * 800
        + "\n===== FILE: second.md =====\n"
        + "beta "
        * 500
    )
    documents = parse_documents(source)
    assert [document.path for document in documents] == ["first.md", "second.md"]

    first = deterministic_seed_excerpt(documents, case_seed=42)
    second = deterministic_seed_excerpt(documents, case_seed=42)
    assert first == second
    assert 384 <= len(first[0].split()) <= 768

    chunks = chunk_documents(
        [Document("one.md", " ".join(f"token{i}" for i in range(600)))],
        source_id="source-one",
        size=256,
        overlap=32,
    )
    assert [chunk.id for chunk in chunks] == [
        "source-one/chunk-000000",
        "source-one/chunk-000001",
        "source-one/chunk-000002",
    ]
    assert chunks[0].text.split()[-32:] == chunks[1].text.split()[:32]


def test_bm25_and_rrf_use_stable_locked_ties() -> None:
    chunks = [
        Chunk("source/chunk-000002", "unrelated", "a", 2),
        Chunk("source/chunk-000001", "alpha alpha", "a", 1),
        Chunk("source/chunk-000003", "alpha", "a", 3),
    ]
    scores = bm25_scores("alpha", chunks, k1=1.2, b=0.75)
    assert stable_top_indices(scores, chunks, 3)[0] == 1
    assert rrf_indices([1, 2], [2, 1], chunks, rrf_k=60, limit=2) == [1, 2]


def test_openai_payload_and_text_extraction_preserve_output() -> None:
    component = {
        "model": "gpt-5-mini-2025-08-07",
        "parameters": {
            "max_output_tokens": 800,
            "reasoning": {"effort": "minimal"},
            "service_tier": "default",
            "store": False,
            "text": {"verbosity": "low"},
            "tools": [],
            "truncation": "disabled",
        },
    }
    payload = openai_payload(component, system_prompt="system", user_prompt="user")
    assert payload["store"] is False
    assert payload["model"] == "gpt-5-mini-2025-08-07"
    assert extract_openai_text(
        {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "  exact "},
                        {"type": "output_text", "text": "output\n"},
                    ],
                }
            ]
        }
    ) == "  exact output\n"


def test_query_validation_does_not_rewrite_model_output() -> None:
    assert validate_query("What is supported?") is None
    assert validate_query("What is supported?\nExtra") is not None
    assert validate_query("What is supported? ") == "query does not end in '?'"
    assert validate_query("x" * 240 + "?") == "query exceeds 240 characters"


def test_citations_are_extracted_mechanically() -> None:
    selected = [
        Chunk("source/chunk-000001", "one", "a", 1),
        Chunk("source/chunk-000002", "two", "a", 2),
    ]
    assert extract_citations(
        "Claim [2] and repeated [2].",
        citation_format="inline_numeric",
        selected=selected,
    ) == [
        {
            "source_id": "source",
            "chunk_id": "source/chunk-000002",
            "raw": "[2]",
        }
    ]
    assert extract_citations(
        "Claim [source/chunk-000001].",
        citation_format="source_id",
        selected=selected,
    )[0]["chunk_id"] == "source/chunk-000001"
    assert extract_citations(
        "No citations.", citation_format="none", selected=selected
    ) == []


def _guard(hard_limit: float = 10.0) -> dict:
    return {
        "hard_limit": hard_limit,
        "maximum_request_input_utf8_bytes": 50_000,
        "maximum_output_tokens_per_attempt": 800,
        "prices_per_million_tokens": {
            "uncached_input": 0.25,
            "cached_input": 0.025,
            "output_and_reasoning": 2.0,
        },
    }


def test_cost_guard_is_conservative_and_counts_output_once(tmp_path: Path) -> None:
    guard = _guard()
    upper = request_upper_cost({"input": "hello"}, guard)
    assert upper >= 800 * 2.0 / 1_000_000
    actual, basis = actual_openai_cost(
        {
            "input_tokens": 100,
            "input_tokens_details": {"cached_tokens": 40},
            "output_tokens": 20,
            "output_tokens_details": {"reasoning_tokens": 10},
        },
        upper_cost=upper,
        guard=guard,
    )
    assert basis == "provider_usage"
    assert actual == pytest.approx((60 * 0.25 + 40 * 0.025 + 20 * 2.0) / 1_000_000)

    ledger = BudgetLedger(
        tmp_path / "budget.json", AUTHORIZED_SCHEDULE_SHA256, _guard(0.001)
    )
    with pytest.raises(CollectionError, match="hard ceiling"):
        ledger.reserve("attempt", 0.002, "a" * 64)


def test_unsettled_budget_reservation_stops_resume(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    ledger = BudgetLedger(path, AUTHORIZED_SCHEDULE_SHA256, _guard())
    ledger.reserve("case:answer:1", 0.001, "a" * 64)
    with pytest.raises(PendingAttemptError, match="Manual reconciliation"):
        BudgetLedger(path, AUTHORIZED_SCHEDULE_SHA256, _guard())


def test_runner_module_does_not_import_verifier_packages() -> None:
    module = Path(
        "benchmarks/contexttrace_unseen_v1/collect_natural_ood.py"
    ).read_text(encoding="utf-8")
    assert "semantic_core_v2" not in module
    assert "semantic_v1_calibrated" not in module
    assert "contexttrace.verifier" not in module
