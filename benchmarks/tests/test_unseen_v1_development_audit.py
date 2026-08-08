import pytest
from contexttrace.verify.schema import TraceContext

from benchmarks.product_safety.run_unseen_v1_development_audit import (
    _exclusive_output_lock,
    _observable_safety_reasons,
    prepare_trace,
)


def test_prepare_trace_preserves_selected_order_and_source_metadata() -> None:
    case = {
        "case_id": "case-1",
        "track": "natural_ood",
        "source_family": "family-1",
        "domain_group": "software_product",
        "publication_window": "2026-H2",
        "citation_format": "source_id",
        "retrieval": {"family": "bm25"},
        "reranking": {"enabled": False},
        "chunking": {"size": 512},
    }
    payload = {
        "case_id": "case-1",
        "query": "What is supported?",
        "answer": "The value is 10 [source/chunk-2].",
        "retrieved_chunks": [
            {"id": "source/chunk-1", "source_id": "source", "text": "Noise."},
            {
                "id": "source/chunk-2",
                "source_id": "source",
                "text": "The value is 10.",
            },
        ],
        "selected_context_ids": ["source/chunk-2", "source/chunk-1"],
        "citations": [
            {
                "chunk_id": "source/chunk-2",
                "source_id": "source",
                "raw": "[source/chunk-2]",
            }
        ],
    }
    trace = prepare_trace(
        case,
        payload,
        {
            "source": {
                "source_id": "source",
                "source_condition": "current_canonical",
            }
        },
    )

    assert [context.id for context in trace.contexts] == [
        "source/chunk-2",
        "source/chunk-1",
    ]
    assert trace.contexts[0].metadata["source_condition"] == "current_canonical"
    assert trace.citations[0].source_id == "source/chunk-2"
    assert trace.metadata["citation_required"] is True


def test_observable_safety_reasons_reject_inconsistent_green_claim() -> None:
    claim = {
        "green": True,
        "claim_verdict": "supported",
        "diagnostic_abstention": False,
        "qualification_required": False,
        "abstention_requirement": "must_answer",
        "failure_label": "none",
        "primary_root_cause": "none",
        "source_condition": "stale",
        "citation_state": "missing",
        "evidence_spans": [
            {
                "context_id": "c1",
                "start_char": 0,
                "end_char": 4,
                "text": "wrong",
            }
        ],
    }

    reasons = _observable_safety_reasons(
        claim,
        context_by_id={"c1": TraceContext(id="c1", text="right")},
        citation_required=True,
    )

    assert reasons == [
        "green_invalid_required_citation",
        "green_non_exact_evidence_span",
        "green_risky_source_condition",
    ]


def test_observable_safety_reasons_accept_consistent_green_claim() -> None:
    claim = {
        "green": True,
        "claim_verdict": "supported",
        "diagnostic_abstention": False,
        "qualification_required": False,
        "abstention_requirement": "must_answer",
        "failure_label": "none",
        "primary_root_cause": "none",
        "source_condition": "current_canonical",
        "citation_state": "correct",
        "evidence_spans": [
            {
                "context_id": "c1",
                "start_char": 0,
                "end_char": 5,
                "text": "right",
            }
        ],
    }

    assert (
        _observable_safety_reasons(
            claim,
            context_by_id={"c1": TraceContext(id="c1", text="right")},
            citation_required=True,
        )
        == []
    )


def test_exclusive_output_lock_rejects_concurrent_writer(tmp_path) -> None:
    output = tmp_path / "audit.json"

    with (
        _exclusive_output_lock(output),
        pytest.raises(RuntimeError, match="Another audit process"),
        _exclusive_output_lock(output),
    ):
        pass

    assert not output.with_suffix(".json.lock").exists()
