from contexttrace.storage import SQLiteTraceStore


def test_sqlite_store_creates_db_and_round_trips_trace(tmp_path):
    path = tmp_path / "contexttrace.db"
    store = SQLiteTraceStore(str(path))

    trace = store.create_trace(project="support-rag", query="What is the refund policy?", metadata={"env": "test"})
    store.upsert_chunks(
        trace["id"],
        [{"chunk_id": "chunk_1", "content": "Refunds are available within 30 days."}],
        selected=False,
    )
    store.mark_context(trace["id"], ["chunk_1"])
    store.save_answer(trace["id"], {"answer": "Refunds are available within 30 days."})
    store.save_citations(
        trace["id"],
        [{"claim": "Refunds are available within 30 days.", "source_chunk_id": "chunk_1"}],
    )
    store.save_evaluation(
        trace["id"],
        {
            "scores": {"citation_support": 1.0, "unsupported_claim_rate": 0.0},
            "citation_checks": [
                {
                    "claim": "Refunds are available within 30 days.",
                    "source_chunk_id": "chunk_1",
                    "verdict": "directly_supported",
                    "support_score": 1.0,
                    "reason": "Supported.",
                }
            ],
            "failure": {
                "failure_type": "no_failure_detected",
                "severity": "none",
                "root_cause": "No failure.",
                "suggested_fix": "No fix needed.",
            },
        },
    )

    fetched = store.get_trace(trace["id"])
    assert path.exists()
    assert fetched["query"] == "What is the refund policy?"
    assert fetched["chunks"][0]["selected"] is True
    assert fetched["citation_checks"][0]["support_status"] == "directly_supported"
    assert fetched["evaluation"]["failure"]["failure_type"] == "no_failure_detected"
