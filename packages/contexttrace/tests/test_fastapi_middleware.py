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
    json.loads(request["body"].decode("utf-8"))
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


def test_fastapi_middleware_tees_streaming_response_before_logging():
    order = []

    class OrderedTransport(FakeTransport):
        def post(self, path, payload=None):
            order.append(("log", path))
            return super().post(path, payload)

    async def streaming_app(scope, receive, send):
        await receive()
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": b'{"answer":"streamed ', "more_body": True})
        await send({"type": "http.response.body", "body": b'answer"}', "more_body": False})

    transport = OrderedTransport()
    middleware = ContextTraceFastAPIMiddleware(streaming_app, client=ContextTrace(transport=transport))
    sent = []

    async def receive():
        return {"type": "http.request", "body": b'{"query":"q"}', "more_body": False}

    async def send(message):
        order.append(("send", message["type"]))
        sent.append(message)

    asyncio.run(middleware({"type": "http", "method": "POST", "path": "/query", "headers": []}, receive, send))

    assert [item["body"] for item in sent if item["type"] == "http.response.body"] == [
        b'{"answer":"streamed ',
        b'answer"}',
    ]
    assert max(index for index, item in enumerate(order) if item[0] == "send") < min(
        index for index, item in enumerate(order) if item[0] == "log"
    )
    assert transport.calls[-1][2]["answer"] == "streamed answer"


def test_fastapi_middleware_bounds_capture_and_skips_sse_and_disallowed_routes():
    transport = FakeTransport()

    async def sse_app(scope, receive, send):
        await receive()
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/event-stream")]})
        await send({"type": "http.response.body", "body": b"data: secret\n\n", "more_body": False})

    middleware = ContextTraceFastAPIMiddleware(
        sse_app,
        client=ContextTrace(transport=transport),
        max_capture_bytes=8,
        route_allowlist=("/events",),
    )

    async def receive():
        return {"type": "http.request", "body": b'{"query":"a long secret"}', "more_body": False}

    async def send(message):
        return None

    asyncio.run(middleware({"type": "http", "method": "POST", "path": "/events", "headers": []}, receive, send))
    assert middleware.metrics["request_capture_truncated"] == 1
    assert middleware.metrics["streaming_responses_skipped"] == 1
    assert not any(call[1].endswith("/answer") for call in transport.calls)

    before = len(transport.calls)
    asyncio.run(middleware({"type": "http", "method": "POST", "path": "/health", "headers": []}, receive, send))
    assert len(transport.calls) == before


def test_fastapi_middleware_reassembles_json_across_adversarial_chunk_boundaries():
    transport = FakeTransport()

    async def chunked_app(scope, receive, send):
        request_parts = []
        while True:
            message = await receive()
            request_parts.append(message.get("body", b""))
            if not message.get("more_body"):
                break
        assert json.loads(b"".join(request_parts))["query"] == "split request"
        response = json.dumps({"answer": "split response"}).encode("utf-8")
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"application/json")]})
        for index, byte in enumerate(response):
            await send(
                {
                    "type": "http.response.body",
                    "body": bytes([byte]),
                    "more_body": index < len(response) - 1,
                }
            )

    request = b'{"query":"split request"}'
    messages = [
        {"type": "http.request", "body": request[:1], "more_body": True},
        {"type": "http.request", "body": request[1:9], "more_body": True},
        {"type": "http.request", "body": request[9:], "more_body": False},
    ]

    async def receive():
        return messages.pop(0)

    async def send(message):
        return None

    middleware = ContextTraceFastAPIMiddleware(chunked_app, client=ContextTrace(transport=transport))
    asyncio.run(middleware({"type": "http", "method": "POST", "path": "/query", "headers": []}, receive, send))

    assert transport.calls[0][2]["query"] == "split request"
    assert next(payload for _, path, payload in transport.calls if path.endswith("/answer"))["answer"] == "split response"
    assert middleware.metrics["request_capture_truncated"] == 0
    assert middleware.metrics["response_capture_truncated"] == 0


def test_fastapi_middleware_drops_background_log_when_queue_is_saturated():
    transport = FakeTransport()

    async def minimal_app(scope, receive, send):
        await receive()
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": b'{"answer":"ok"}', "more_body": False})

    async def scenario():
        release = asyncio.Event()
        extractor_started = asyncio.Event()

        async def blocked_request_extractor(request):
            extractor_started.set()
            await release.wait()
            return {"query": request["json"]["query"]}

        middleware = ContextTraceFastAPIMiddleware(
            minimal_app,
            client=ContextTrace(transport=transport),
            request_extractor=blocked_request_extractor,
            background_logging=True,
            max_pending_logs=1,
        )

        async def invoke(query):
            used = False

            async def receive():
                nonlocal used
                assert not used
                used = True
                return {
                    "type": "http.request",
                    "body": json.dumps({"query": query}).encode("utf-8"),
                    "more_body": False,
                }

            async def send(message):
                return None

            await middleware(
                {"type": "http", "method": "POST", "path": "/query", "headers": []},
                receive,
                send,
            )

        await invoke("first")
        await extractor_started.wait()
        await invoke("second")
        assert middleware.metrics["logging_dropped"] == 1
        assert len(middleware._pending_logs) == 1
        release.set()
        await middleware.drain()
        return middleware

    middleware = asyncio.run(scenario())
    assert middleware.metrics["traces_attempted"] == 2
    assert middleware.metrics["logging_failures"] == 0
    assert len([call for call in transport.calls if call[1] == "/v1/traces/start"]) == 1


def test_fastapi_middleware_truncates_oversized_request_and_response_independently():
    transport = FakeTransport()

    async def oversized_app(scope, receive, send):
        await receive()
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"application/json")]})
        await send(
            {
                "type": "http.response.body",
                "body": json.dumps({"answer": "x" * 1024}).encode("utf-8"),
                "more_body": False,
            }
        )

    async def receive():
        return {
            "type": "http.request",
            "body": json.dumps({"query": "y" * 1024}).encode("utf-8"),
            "more_body": False,
        }

    async def send(message):
        return None

    middleware = ContextTraceFastAPIMiddleware(
        oversized_app,
        client=ContextTrace(transport=transport),
        max_capture_bytes=32,
    )
    asyncio.run(middleware({"type": "http", "method": "POST", "path": "/oversized", "headers": []}, receive, send))

    assert middleware.metrics["request_capture_truncated"] == 1
    assert middleware.metrics["response_capture_truncated"] == 1
    assert transport.calls[0][2]["query"] == "/oversized"
    assert not any(path.endswith("/answer") for _, path, _ in transport.calls)
