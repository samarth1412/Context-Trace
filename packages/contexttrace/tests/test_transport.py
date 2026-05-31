import httpx

from contexttrace.transport import HttpTransport


def test_http_transport_retries_transient_server_errors(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503, json={"detail": "busy"})
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr("contexttrace.transport.time.sleep", lambda delay: None)

    client = httpx.Client(
        base_url="http://contexttrace.test",
        transport=httpx.MockTransport(handler),
    )
    transport = HttpTransport(
        base_url="http://contexttrace.test",
        api_key="ctx_test",
        retries=1,
        client=client,
    )

    assert transport.get("/v1/health") == {"ok": True}
    assert len(calls) == 2
