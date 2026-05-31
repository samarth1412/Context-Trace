import asyncio

import httpx

from app.services import external_endpoints as external_endpoint_module
from app.services.external_endpoints import (
    call_external_endpoint,
    extract_json_path,
    map_external_response,
    render_body_template,
)


def test_jsonpath_mapping_normalizes_external_response():
    raw = {
        "answer": "Refunds are available within 30 days.",
        "sources": [
            {
                "id": "chunk_1",
                "text": "Refunds are available within 30 days.",
                "source": "policy.md",
                "score": 0.94,
            }
        ],
    }

    mapped = map_external_response(
        raw,
        {
            "answer": "$.answer",
            "retrieved_chunks": "$.sources",
            "citations": "$.sources",
        },
    )

    assert extract_json_path(raw, "$.sources[0].text") == "Refunds are available within 30 days."
    assert mapped.answer == "Refunds are available within 30 days."
    assert mapped.retrieved_chunks[0].chunk_id == "chunk_1"
    assert mapped.retrieved_chunks[0].content == "Refunds are available within 30 days."
    assert mapped.citations[0].claim == "Refunds are available within 30 days."
    assert mapped.citations[0].source_chunk_id == "chunk_1"


def test_body_template_renders_query_metadata_and_expected_answer():
    rendered = render_body_template(
        {
            "question": "{{query}}",
            "tenant": "{{metadata.tenant}}",
            "expected": "{{expected_answer}}",
            "static": ["rag", "{{query}}"],
        },
        query="What is the refund policy?",
        metadata={"tenant": "support"},
        expected_answer="Refunds are documented.",
    )

    assert rendered == {
        "question": "What is the refund policy?",
        "tenant": "support",
        "expected": "Refunds are documented.",
        "static": ["rag", "What is the refund policy?"],
    }


def test_external_http_call_uses_configured_method_headers_and_body(monkeypatch):
    requests = []
    real_async_client = external_endpoint_module.httpx.AsyncClient

    def handler(request):
        requests.append(request)
        assert request.headers["X-Test"] == "1"
        assert request.content == b'{"question":"What is the refund policy?"}'
        return httpx.Response(200, json={"answer": "Refunds are available within 30 days."})

    def fake_async_client(**kwargs):
        return real_async_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(external_endpoint_module.httpx, "AsyncClient", fake_async_client)

    response = asyncio.run(
        call_external_endpoint(
            url="https://rag.example/query",
            method="POST",
            headers={"X-Test": "1"},
            body={"question": "What is the refund policy?"},
        )
    )

    assert response["answer"] == "Refunds are available within 30 days."
    assert requests[0].method == "POST"
    assert str(requests[0].url) == "https://rag.example/query"


def test_external_endpoint_test_creates_trace_from_mapped_response(
    client,
    auth_headers,
    monkeypatch,
):
    project_id = _create_project(client, auth_headers)
    endpoint_id = _register_endpoint(client, auth_headers, project_id)
    calls = []

    async def fake_call_external_endpoint(**kwargs):
        calls.append(kwargs)
        return {
            "answer": "Refunds are available within 30 days.",
            "contexts": [
                {
                    "id": "chunk_1",
                    "content": "Refunds are available within 30 days.",
                    "source": "policy.md",
                }
            ],
            "sources": [{"claim": "Refunds are available within 30 days.", "chunk_id": "chunk_1"}],
        }

    monkeypatch.setattr(
        "app.services.external_endpoints.call_external_endpoint",
        fake_call_external_endpoint,
    )

    response = client.post(
        f"/v1/external-endpoints/{endpoint_id}/test",
        headers=auth_headers,
        json={"query": "What is the refund policy?", "metadata": {"tenant": "support"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mapped"]["answer"] == "Refunds are available within 30 days."
    assert body["mapped"]["retrieved_chunks"][0]["chunk_id"] == "chunk_1"
    assert calls[0]["body"]["question"] == "What is the refund policy?"
    assert calls[0]["headers"]["X-Test"] == "1"

    trace = client.get(f"/v1/traces/{body['trace_id']}", headers=auth_headers)
    assert trace.status_code == 200
    trace_body = trace.json()
    assert trace_body["answer"]["answer"] == "Refunds are available within 30 days."
    assert trace_body["chunks"][0]["selected"] is True
    assert trace_body["citation_checks"][0]["source_chunk_id"] == "chunk_1"


def test_external_endpoint_run_eval_links_and_evaluates_traces(
    client,
    auth_headers,
    monkeypatch,
    judge_provider,
):
    project_id = _create_project(client, auth_headers)
    endpoint_id = _register_endpoint(client, auth_headers, project_id)
    eval_set = client.post(
        "/v1/eval-sets",
        headers=auth_headers,
        json={"name": "external-rag-regression"},
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
                    "expected_answer": "Refunds are available within 30 days.",
                }
            ]
        },
    )
    assert questions.status_code == 200

    async def fake_call_external_endpoint(**kwargs):
        return {
            "answer": "Refunds are available within 30 days.",
            "contexts": [
                {
                    "id": "chunk_1",
                    "content": "Refunds are available within 30 days.",
                    "source": "policy.md",
                }
            ],
            "sources": [{"claim": "Refunds are available within 30 days.", "chunk_id": "chunk_1"}],
        }

    monkeypatch.setattr(
        "app.services.external_endpoints.call_external_endpoint",
        fake_call_external_endpoint,
    )
    judge_provider.citation_responses.append(
        {
            "verdict": "directly_supported",
            "support_score": 0.99,
            "reason": "The source directly supports the claim.",
        }
    )
    judge_provider.failure_responses.append(
        {
            "failure_type": "no_failure_detected",
            "severity": "none",
            "root_cause": "All claims are supported.",
            "suggested_fix": "No fix required.",
        }
    )

    run = client.post(
        f"/v1/external-endpoints/{endpoint_id}/run-eval",
        headers=auth_headers,
        json={"eval_set_id": eval_set_id},
    )

    assert run.status_code == 200
    body = run.json()
    assert body["summary"]["evaluated_trace_count"] == 1
    assert body["summary"]["avg_citation_support"] == 0.99
    assert body["traces"][0]["evaluation"]["failure"]["failure_type"] == "no_failure_detected"

    summary = client.get(f"/v1/eval-sets/{eval_set_id}/summary", headers=auth_headers)
    assert summary.status_code == 200
    assert summary.json()["linked_trace_count"] == 1


def _create_project(client, auth_headers):
    response = client.post(
        "/v1/traces/start",
        headers=auth_headers,
        json={"project": "support-rag", "query": "seed project"},
    )
    assert response.status_code == 201
    return response.json()["project_id"]


def _register_endpoint(client, auth_headers, project_id):
    response = client.post(
        f"/v1/projects/{project_id}/external-endpoints",
        headers=auth_headers,
        json={
            "name": "support-api",
            "url": "https://my-rag-app.com/query",
            "method": "POST",
            "headers": {"X-Test": "1"},
            "body_template": {"question": "{{query}}"},
            "response_mapping": {
                "answer": "$.answer",
                "citations": "$.sources",
                "retrieved_chunks": "$.contexts",
            },
        },
    )
    assert response.status_code == 201
    return response.json()["id"]
