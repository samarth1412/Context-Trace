from contexttrace.verify.judges import (
    CachedJudge,
    JsonJudgeCache,
    OllamaJudge,
    OpenAICompatibleJudge,
    build_judge_provider,
    is_local_base_url,
)
from contexttrace.verify.schema import TraceContext


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"verdict":"supported","confidence":0.93,'
                            '"reason":"Evidence directly supports it.",'
                            '"matched_facts":["refunds within 30 days"]}'
                        )
                    }
                }
            ]
        }


class FakeClient:
    def __init__(self):
        self.requests = []
        self.closed = False

    def post(self, url, *, headers=None, json):
        self.requests.append({"url": url, "headers": headers, "json": json})
        return FakeResponse()

    def close(self):
        self.closed = True


def test_openai_compatible_judge_parses_structured_verdict():
    client = FakeClient()
    judge = OpenAICompatibleJudge(
        api_key="test-key",
        base_url="http://judge.test/v1",
        model="judge-model",
        client=client,
    )

    verdict = judge.verify_claim(
        query="What is the refund policy?",
        claim="Refunds are available within 30 days.",
        contexts=[
            TraceContext(
                id="policy",
                text="Customers may request refunds within 30 days.",
            )
        ],
    )

    assert verdict.verdict == "supported"
    assert verdict.confidence == 0.93
    assert verdict.matched_facts == ["refunds within 30 days"]
    assert verdict.provider == "openai_compatible"
    assert verdict.model == "judge-model"
    assert client.requests[0]["url"] == "http://judge.test/v1/chat/completions"
    assert client.requests[0]["headers"]["Authorization"] == "Bearer test-key"
    assert client.requests[0]["json"]["response_format"] == {"type": "json_object"}


def test_openai_compatible_judge_allows_local_servers_without_api_key():
    client = FakeClient()
    judge = OpenAICompatibleJudge(
        api_key="",
        base_url="http://localhost:8000/v1",
        model="local-model",
        client=client,
        provider="local_openai",
    )

    verdict = judge.verify_claim(
        query="What is the refund policy?",
        claim="Refunds are available within 30 days.",
        contexts=[TraceContext(id="policy", text="Customers may request refunds within 30 days.")],
    )

    assert verdict.provider == "local_openai"
    assert client.requests[0]["url"] == "http://localhost:8000/v1/chat/completions"
    assert client.requests[0]["headers"] == {}


class FakeOllamaResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "message": {
                "content": (
                    '{"verdict":"contradicted","confidence":0.88,'
                    '"reason":"Evidence says the opposite.",'
                    '"conflicting_facts":["refunds are not available"]}'
                )
            }
        }


class FakeOllamaClient:
    def __init__(self):
        self.requests = []
        self.closed = False

    def post(self, url, *, json):
        self.requests.append({"url": url, "json": json})
        return FakeOllamaResponse()

    def close(self):
        self.closed = True


def test_ollama_judge_uses_native_local_chat_api():
    client = FakeOllamaClient()
    judge = OllamaJudge(
        base_url="http://localhost:11434",
        model="llama3.1",
        client=client,
    )

    verdict = judge.verify_claim(
        query="What is the refund policy?",
        claim="Refunds are available.",
        contexts=[TraceContext(id="policy", text="Refunds are not available.")],
    )

    assert verdict.verdict == "contradicted"
    assert verdict.confidence == 0.88
    assert verdict.conflicting_facts == ["refunds are not available"]
    assert verdict.provider == "ollama"
    assert client.requests[0]["url"] == "http://localhost:11434/api/chat"
    assert client.requests[0]["json"]["stream"] is False
    assert client.requests[0]["json"]["format"] == "json"
    assert client.requests[0]["json"]["options"] == {"temperature": 0}


def test_build_judge_provider_prefers_local_provider_defaults(monkeypatch):
    monkeypatch.delenv("CONTEXTTRACE_JUDGE_PROVIDER", raising=False)
    monkeypatch.delenv("CONTEXTTRACE_JUDGE_BASE_URL", raising=False)
    monkeypatch.delenv("CONTEXTTRACE_JUDGE_API_KEY", raising=False)
    monkeypatch.delenv("CONTEXTTRACE_JUDGE_MODEL", raising=False)

    ollama = build_judge_provider(provider="ollama")
    local_openai = build_judge_provider(provider="local_openai")
    lmstudio = build_judge_provider(provider="lmstudio")

    assert isinstance(ollama, OllamaJudge)
    assert ollama.base_url == "http://localhost:11434"
    assert ollama.model == "llama3.1"
    assert isinstance(local_openai, OpenAICompatibleJudge)
    assert local_openai.base_url == "http://localhost:8000/v1"
    assert local_openai.api_key == ""
    assert isinstance(lmstudio, OpenAICompatibleJudge)
    assert lmstudio.base_url == "http://localhost:1234/v1"


def test_build_judge_provider_can_wrap_local_judge_with_cache(monkeypatch, tmp_path):
    monkeypatch.delenv("CONTEXTTRACE_JUDGE_CACHE", raising=False)

    judge = build_judge_provider(
        provider="local_openai",
        model="local-model",
        cache_enabled=True,
        cache_path=str(tmp_path / "judge_cache.json"),
    )

    assert isinstance(judge, CachedJudge)
    assert judge.cache.path == tmp_path / "judge_cache.json"


def test_cached_judge_reuses_local_verdict(tmp_path):
    client = FakeClient()
    judge = CachedJudge(
        OpenAICompatibleJudge(
            api_key="",
            base_url="http://localhost:8000/v1",
            model="local-model",
            client=client,
            provider="local_openai",
        ),
        cache=JsonJudgeCache(tmp_path / "judge_cache.json"),
    )
    kwargs = {
        "query": "What is the refund policy?",
        "claim": "Refunds are available within 30 days.",
        "contexts": [TraceContext(id="policy", text="Customers may request refunds within 30 days.")],
    }

    first = judge.verify_claim(**kwargs)
    second = judge.verify_claim(**kwargs)

    assert first.verdict == "supported"
    assert second.verdict == "supported"
    assert second.raw["cached"] is True
    assert len(client.requests) == 1
    assert judge.stats()["hits"] == 1
    assert judge.stats()["writes"] == 1


def test_offline_strict_blocks_remote_judge_url():
    try:
        build_judge_provider(
            provider="openai",
            api_key="test-key",
            offline_strict=True,
        )
    except ValueError as exc:
        assert "only allows localhost judge URLs" in str(exc)
    else:
        raise AssertionError("offline_strict should block remote OpenAI URL")


def test_local_base_url_detection():
    assert is_local_base_url("http://localhost:11434")
    assert is_local_base_url("http://127.0.0.1:8000/v1")
    assert is_local_base_url("http://api.localhost:1234/v1")
    assert not is_local_base_url("https://api.openai.com/v1")


def test_build_judge_provider_requires_key_only_for_openai(monkeypatch):
    monkeypatch.delenv("CONTEXTTRACE_JUDGE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    try:
        build_judge_provider(provider="openai")
    except ValueError as exc:
        assert "requires CONTEXTTRACE_JUDGE_API_KEY" in str(exc)
    else:
        raise AssertionError("openai provider should require an API key")


def test_build_judge_provider_returns_none_for_local_provider(monkeypatch):
    monkeypatch.setenv("CONTEXTTRACE_JUDGE_PROVIDER", "local")

    assert build_judge_provider() is None
