import asyncio
import json

from contexttrace import ContextTrace
from contexttrace.integrations.fastapi import ContextTraceFastAPIMiddleware


class FakeTransport:
    def __init__(self):
        self.calls = []

    def post(self, path, payload=None):
        self.calls.append(("POST", path, payload or {}))
        if path == "/v1/traces/start":
            return {"trace_id": "trace_fastapi", "project_id": "project_123"}
        return {"trace_id": "trace_fastapi", "accepted": 1}

    def get(self, path):
        self.calls.append(("GET", path, {}))
        return {"id": "trace_fastapi"}


async def rag_app(scope, receive, send):
    request = await receive()
    body = json.loads(request["body"].decode("utf-8"))
    response = {
        "answer": "Refunds are available within 30 days.",
        "retrieved_chunks": [
            {
                "chunk_id": "chunk_12",
                "content": "Customers may request refunds within 30 days.",
                "source": "refund_policy.md",
            }
        ],
        "selected_context": [
            {
                "chunk_id": "chunk_12",
                "content": "Customers may request refunds within 30 days.",
                "source": "refund_policy.md",
            }
        ],
        "citations": [
            {
                "claim": "Refunds are available within 30 days.",
                "source_chunk_id": "chunk_12",
            }
        ],
        "usage": {"total_tokens": 120},
        "model": "gpt-4.1-mini",
        "metadata": {"route": "query"},
    }
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": json.dumps(response).encode("utf-8"),
            "more_body": False,
        }
    )


def test_fastapi_middleware_traces_async_rag_endpoint():
    transport = FakeTransport()
    client = ContextTrace(api_key="ctx_test", project="support-rag", transport=transport)
    middleware = ContextTraceFastAPIMiddleware(
        rag_app,
        client=client,
        should_trace=lambda request: request["path"] == "/query",
    )
    sent = []

    async def receive():
        return {
            "type": "http.request",
            "body": json.dumps({"query": "What is the refund policy?"}).encode("utf-8"),
            "more_body": False,
        }

    async def send(message):
        sent.append(message)

    asyncio.run(
        middleware(
            {"type": "http", "method": "POST", "path": "/query", "headers": []},
            receive,
            send,
        )
    )

    assert sent[0]["status"] == 200
    assert transport.calls[0][1] == "/v1/traces/start"
    assert transport.calls[0][2]["query"] == "What is the refund policy?"
    assert transport.calls[1][1] == "/v1/traces/trace_fastapi/retrieval"
    assert transport.calls[2][1] == "/v1/traces/trace_fastapi/context"
    assert transport.calls[3][1] == "/v1/traces/trace_fastapi/answer"
    assert transport.calls[3][2]["usage"]["total_tokens"] == 120
    assert transport.calls[4][1] == "/v1/traces/trace_fastapi/citations"


def test_fastapi_middleware_supports_custom_extractors():
    transport = FakeTransport()
    client = ContextTrace(api_key="ctx_test", project="support-rag", transport=transport)

    async def request_extractor(request):
        return {"query": request["json"]["messages"][-1]["content"], "metadata": {"custom": True}}

    def response_extractor(response, request):
        body = response["json"]
        return {
            "answer": body["data"]["text"],
            "retrieved_chunks": body["data"]["contexts"],
        }

    async def custom_app(scope, receive, send):
        await receive()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send(
            {
                "type": "http.response.body",
                "body": json.dumps(
                    {
                        "data": {
                            "text": "Custom answer.",
                            "contexts": [{"chunk_id": "c1", "content": "Custom context."}],
                        }
                    }
                ).encode("utf-8"),
                "more_body": False,
            }
        )

    middleware = ContextTraceFastAPIMiddleware(
        custom_app,
        client=client,
        request_extractor=request_extractor,
        response_extractor=response_extractor,
    )

    async def receive():
        return {
            "type": "http.request",
            "body": json.dumps({"messages": [{"content": "Custom query?"}]}).encode("utf-8"),
            "more_body": False,
        }

    async def send(message):
        return None

    asyncio.run(
        middleware(
            {"type": "http", "method": "POST", "path": "/custom-query", "headers": []},
            receive,
            send,
        )
    )

    assert transport.calls[0][2]["query"] == "Custom query?"
    assert transport.calls[0][2]["metadata"]["custom"] is True
    assert transport.calls[2][2]["answer"] == "Custom answer."

