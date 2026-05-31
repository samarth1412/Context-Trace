def test_trace_lifecycle_logs_and_fetches_trace(client, auth_headers):
    start = client.post(
        "/v1/traces/start",
        headers=auth_headers,
        json={
            "project": "support-rag",
            "query": "What is the refund policy?",
            "metadata": {"env": "test"},
        },
    )
    assert start.status_code == 201
    trace_id = start.json()["trace_id"]

    retrieval = client.post(
        f"/v1/traces/{trace_id}/retrieval",
        headers=auth_headers,
        json={
            "retriever_name": "unit-test-retriever",
            "chunks": [
                {
                    "chunk_id": "chunk_12",
                    "content": "Customers can request refunds within 30 days of purchase.",
                    "source": "refund-policy.md",
                    "relevance_score": 0.93,
                },
                {
                    "chunk_id": "chunk_13",
                    "content": "Shipping time depends on the destination.",
                    "source": "shipping.md",
                    "relevance_score": 0.41,
                },
            ],
        },
    )
    assert retrieval.status_code == 200
    assert retrieval.json()["accepted"] == 2

    context = client.post(
        f"/v1/traces/{trace_id}/context",
        headers=auth_headers,
        json={"chunk_ids": ["chunk_12"]},
    )
    assert context.status_code == 200
    assert context.json()["accepted"] == 1

    answer = client.post(
        f"/v1/traces/{trace_id}/answer",
        headers=auth_headers,
        json={
            "answer": "Refunds are available within 30 days and processed in two days.",
            "model": "gpt-4.1-mini",
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 200,
                "total_tokens": 1200,
            },
        },
    )
    assert answer.status_code == 200

    citations = client.post(
        f"/v1/traces/{trace_id}/citations",
        headers=auth_headers,
        json={
            "citations": [
                {
                    "claim": "Refunds are available within 30 days.",
                    "source_chunk_id": "chunk_12",
                },
                {
                    "claim": "Refunds are processed in two days.",
                    "source_chunk_id": "chunk_12",
                },
            ]
        },
    )
    assert citations.status_code == 200
    assert citations.json()["accepted"] == 2

    fetched = client.get(f"/v1/traces/{trace_id}", headers=auth_headers)
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["project"] == "support-rag"
    assert len(fetched_body["citation_checks"]) == 2
    assert fetched_body["citation_checks"][0]["support_status"] == "pending"
    assert fetched_body["chunks"][0]["selected"] is True


def test_agent_events_are_logged_listed_and_included_in_trace(client, auth_headers):
    start = client.post(
        "/v1/traces/start",
        headers=auth_headers,
        json={
            "project": "agent-support",
            "query": "Resolve the refund ticket.",
            "metadata": {"trace_kind": "agent"},
        },
    )
    assert start.status_code == 201
    trace_id = start.json()["trace_id"]

    planner = client.post(
        f"/v1/traces/{trace_id}/agent-events",
        headers=auth_headers,
        json={
            "event_type": "planner_step",
            "name": "plan_refund_lookup",
            "input_json": {"query": "Resolve the refund ticket."},
            "output_json": {"next": "lookup_policy"},
            "metadata_json": {"agent": "support-agent"},
            "latency_ms": 12.5,
        },
    )
    assert planner.status_code == 200
    assert planner.json()["accepted"] == 1

    error = client.post(
        f"/v1/traces/{trace_id}/agent-events",
        headers=auth_headers,
        json={
            "event_type": "error",
            "name": "lookup_policy",
            "input_json": {"tool": "policy_search"},
            "output_json": {},
            "metadata_json": {"failure_label": "tool_error"},
            "latency_ms": 42,
            "error_message": "Policy search timed out.",
        },
    )
    assert error.status_code == 200

    listed = client.get(f"/v1/traces/{trace_id}/agent-events", headers=auth_headers)
    assert listed.status_code == 200
    events = listed.json()["events"]
    assert [event["event_type"] for event in events] == ["planner_step", "error"]
    assert events[0]["output_json"] == {"next": "lookup_policy"}
    assert events[1]["error_message"] == "Policy search timed out."

    fetched = client.get(f"/v1/traces/{trace_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["agent_events"][1]["metadata_json"]["failure_label"] == "tool_error"


def test_evaluate_supported_citation_retries_invalid_json_once(
    client,
    auth_headers,
    judge_provider,
):
    trace_id = _create_evaluable_trace(client, auth_headers)
    judge_provider.citation_responses.extend(
        [
            "not json",
            {
                "verdict": "directly_supported",
                "support_score": 0.98,
                "reason": "The source explicitly states the 30-day refund window.",
            },
        ]
    )
    judge_provider.failure_responses.append(_failure("no_failure_detected", "none"))

    response = client.post(f"/v1/traces/{trace_id}/evaluate", headers=auth_headers, json={})

    assert response.status_code == 200
    body = response.json()
    assert body["citation_checks"][0]["verdict"] == "directly_supported"
    assert body["citation_checks"][0]["support_score"] == 0.98
    assert [call["task"] for call in judge_provider.calls[:2]] == [
        "citation_verification",
        "citation_verification",
    ]


def test_evaluate_unsupported_citation(client, auth_headers, judge_provider):
    trace_id = _create_evaluable_trace(client, auth_headers)
    judge_provider.citation_responses.append(
        {
            "verdict": "unsupported",
            "support_score": 0.05,
            "reason": "The source does not mention processing time.",
        }
    )
    judge_provider.failure_responses.append(_failure("citation_mismatch", "medium"))

    response = client.post(f"/v1/traces/{trace_id}/evaluate", headers=auth_headers, json={})

    assert response.status_code == 200
    assert response.json()["citation_checks"][0]["verdict"] == "unsupported"


def test_evaluate_contradicted_citation(client, auth_headers, judge_provider):
    trace_id = _create_evaluable_trace(
        client,
        auth_headers,
        claim="Final sale items are refundable.",
        chunk_text="Final sale items are not refundable.",
    )
    judge_provider.citation_responses.append(
        {
            "verdict": "contradicted",
            "support_score": 0.0,
            "reason": "The source says the opposite of the claim.",
        }
    )
    judge_provider.failure_responses.append(_failure("contradicted_answer", "high"))

    response = client.post(f"/v1/traces/{trace_id}/evaluate", headers=auth_headers, json={})

    assert response.status_code == 200
    assert response.json()["citation_checks"][0]["verdict"] == "contradicted"


def test_evaluate_citation_mismatch_failure(client, auth_headers, judge_provider):
    trace_id = _create_evaluable_trace(
        client,
        auth_headers,
        citations=[
            {
                "claim": "Refunds are available within 30 days.",
                "source_chunk_id": "chunk_12",
            },
            {
                "claim": "Refunds are processed in two days.",
                "source_chunk_id": "chunk_12",
            },
        ],
    )
    judge_provider.citation_responses.extend(
        [
            {
                "verdict": "directly_supported",
                "support_score": 0.95,
                "reason": "The source states the eligibility window.",
            },
            {
                "verdict": "unsupported",
                "support_score": 0.1,
                "reason": "The source does not state processing time.",
            },
        ]
    )
    judge_provider.failure_responses.append(_failure("citation_mismatch", "medium"))

    response = client.post(f"/v1/traces/{trace_id}/evaluate", headers=auth_headers, json={})

    assert response.status_code == 200
    assert response.json()["failure"]["failure_type"] == "citation_mismatch"


def test_evaluate_unsupported_answer_failure(client, auth_headers, judge_provider):
    trace_id = _create_evaluable_trace(client, auth_headers, citations=[])
    judge_provider.failure_responses.append(_failure("unsupported_answer", "high"))

    response = client.post(f"/v1/traces/{trace_id}/evaluate", headers=auth_headers, json={})

    assert response.status_code == 200
    assert response.json()["citation_checks"] == []
    assert response.json()["failure"]["failure_type"] == "unsupported_answer"


def test_evaluate_no_failure_detected(client, auth_headers, judge_provider):
    trace_id = _create_evaluable_trace(client, auth_headers)
    judge_provider.citation_responses.append(
        {
            "verdict": "directly_supported",
            "support_score": 0.99,
            "reason": "The source directly supports the claim.",
        }
    )
    judge_provider.failure_responses.append(_failure("no_failure_detected", "none"))

    response = client.post(f"/v1/traces/{trace_id}/evaluate", headers=auth_headers, json={})

    assert response.status_code == 200
    assert response.json()["failure"]["failure_type"] == "no_failure_detected"

    fetched = client.get(f"/v1/traces/{trace_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["evaluation"]["failure"]["failure_type"] == "no_failure_detected"


def test_invalid_failure_json_falls_back_to_unknown(client, auth_headers, judge_provider):
    trace_id = _create_evaluable_trace(client, auth_headers, citations=[])
    judge_provider.failure_responses.extend(["not json", "still not json"])

    response = client.post(f"/v1/traces/{trace_id}/evaluate", headers=auth_headers, json={})

    assert response.status_code == 200
    assert response.json()["failure"]["failure_type"] == "unknown"


def test_eval_set_summary_aggregates_existing_traces(client, auth_headers, judge_provider):
    good_trace_id = _create_evaluable_trace(client, auth_headers)
    judge_provider.citation_responses.append(
        {
            "verdict": "directly_supported",
            "support_score": 0.95,
            "reason": "The source directly supports the claim.",
        }
    )
    judge_provider.failure_responses.append(_failure("no_failure_detected", "none"))
    assert client.post(
        f"/v1/traces/{good_trace_id}/evaluate",
        headers=auth_headers,
        json={},
    ).status_code == 200

    mismatch_trace_id = _create_evaluable_trace(
        client,
        auth_headers,
        claim="Refunds are processed in two days.",
    )
    judge_provider.citation_responses.append(
        {
            "verdict": "unsupported",
            "support_score": 0.4,
            "reason": "The source does not support the processing-time claim.",
        }
    )
    judge_provider.failure_responses.append(_failure("citation_mismatch", "medium"))
    assert client.post(
        f"/v1/traces/{mismatch_trace_id}/evaluate",
        headers=auth_headers,
        json={},
    ).status_code == 200

    unsupported_trace_id = _create_evaluable_trace(client, auth_headers, citations=[])
    judge_provider.failure_responses.append(_failure("unsupported_answer", "high"))
    assert client.post(
        f"/v1/traces/{unsupported_trace_id}/evaluate",
        headers=auth_headers,
        json={},
    ).status_code == 200

    eval_set = client.post(
        "/v1/eval-sets",
        headers=auth_headers,
        json={"name": "refund-policy-regression"},
    )
    assert eval_set.status_code == 201
    eval_set_id = eval_set.json()["eval_set_id"]

    questions = client.post(
        f"/v1/eval-sets/{eval_set_id}/questions",
        headers=auth_headers,
        json={
            "questions": [
                {
                    "question": "What is the refund policy?",
                    "trace_id": good_trace_id,
                },
                {
                    "question": "How fast are refunds processed?",
                    "trace_id": mismatch_trace_id,
                },
                {
                    "question": "What unsupported claim did the answer make?",
                    "trace_id": unsupported_trace_id,
                },
            ]
        },
    )
    assert questions.status_code == 200
    assert questions.json()["accepted"] == 3

    run = client.post(
        f"/v1/eval-sets/{eval_set_id}/runs",
        headers=auth_headers,
        json={},
    )
    assert run.status_code == 200
    summary = run.json()
    assert summary["total_questions"] == 3
    assert summary["linked_trace_count"] == 3
    assert summary["evaluated_trace_count"] == 3
    assert summary["unevaluated_trace_count"] == 0
    assert summary["avg_citation_support"] == 0.45
    assert summary["unsupported_claim_rate"] == 0.667
    assert summary["failure_type_distribution"] == {
        "no_failure_detected": 1,
        "citation_mismatch": 1,
        "unsupported_answer": 1,
    }
    assert summary["worst_traces"][0]["trace_id"] == unsupported_trace_id
    assert summary["worst_traces"][0]["severity"] == "high"

    fetched_summary = client.get(
        f"/v1/eval-sets/{eval_set_id}/summary",
        headers=auth_headers,
    )
    assert fetched_summary.status_code == 200
    assert fetched_summary.json() == summary


def test_auth_required(client):
    response = client.post(
        "/v1/traces/start",
        json={"project": "support-rag", "query": "What is the refund policy?"},
    )
    assert response.status_code == 401


def _create_evaluable_trace(
    client,
    auth_headers,
    *,
    claim="Refunds are available within 30 days.",
    chunk_text="Customers can request refunds within 30 days of purchase.",
    citations=None,
):
    start = client.post(
        "/v1/traces/start",
        headers=auth_headers,
        json={
            "project": "support-rag",
            "query": "What is the refund policy?",
        },
    )
    assert start.status_code == 201
    trace_id = start.json()["trace_id"]

    retrieval = client.post(
        f"/v1/traces/{trace_id}/retrieval",
        headers=auth_headers,
        json={
            "chunks": [
                {
                    "chunk_id": "chunk_12",
                    "content": chunk_text,
                    "source": "refund-policy.md",
                    "relevance_score": 0.93,
                }
            ]
        },
    )
    assert retrieval.status_code == 200

    context = client.post(
        f"/v1/traces/{trace_id}/context",
        headers=auth_headers,
        json={"chunk_ids": ["chunk_12"]},
    )
    assert context.status_code == 200

    answer = client.post(
        f"/v1/traces/{trace_id}/answer",
        headers=auth_headers,
        json={
            "answer": "Refunds are available within 30 days.",
            "model": "gpt-4.1-mini",
            "usage": {"total_tokens": 1200},
        },
    )
    assert answer.status_code == 200

    if citations is None:
        citations = [{"claim": claim, "source_chunk_id": "chunk_12"}]
    citation_response = client.post(
        f"/v1/traces/{trace_id}/citations",
        headers=auth_headers,
        json={"citations": citations},
    )
    assert citation_response.status_code == 200
    return trace_id


def _failure(failure_type, severity):
    return {
        "failure_type": failure_type,
        "severity": severity,
        "root_cause": "Mocked root cause.",
        "suggested_fix": "Mocked suggested fix.",
    }
