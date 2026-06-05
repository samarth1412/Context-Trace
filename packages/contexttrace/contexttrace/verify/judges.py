from __future__ import annotations

import json
import os
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from contexttrace.verify.schema import TraceContext


SUPPORTED = "supported"
PARTIALLY_SUPPORTED = "partially_supported"
UNSUPPORTED = "unsupported"
CONTRADICTED = "contradicted"
UNVERIFIABLE = "unverifiable"
ALLOWED_VERDICTS = {
    SUPPORTED,
    PARTIALLY_SUPPORTED,
    UNSUPPORTED,
    CONTRADICTED,
    UNVERIFIABLE,
}
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.1"
DEFAULT_LOCAL_OPENAI_BASE_URL = "http://localhost:8000/v1"
DEFAULT_LMSTUDIO_BASE_URL = "http://localhost:1234/v1"
DEFAULT_LOCAL_OPENAI_MODEL = "local-model"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_JUDGE_CACHE_PATH = ".contexttrace/judge_cache.json"
JUDGE_SYSTEM_PROMPT = (
    "You are a strict RAG evidence judge. Given a user query, one generated claim, "
    "and selected evidence spans, return only JSON with this schema: "
    "{\"verdict\":\"supported|partially_supported|unsupported|contradicted|unverifiable\","
    "\"confidence\":0.0,\"reason\":\"brief explanation\","
    "\"matched_facts\":[],\"missing_facts\":[],\"conflicting_facts\":[]}. "
    "Use supported only when the evidence directly entails every material part of the claim. "
    "Treat supplied contexts as minimal evidence spans, not the full source document. "
    "Do not infer support from omitted surrounding context or from fluent answer wording. "
    "Use contradicted when the evidence conflicts with the claim, including wrong entities, "
    "wrong dates, wrong numbers, negation conflicts, or reversed causal/attribution roles. "
    "Use partially_supported when some material facts are supported but others are missing. "
    "Use unsupported when the evidence is related but does not support the claim. "
    "Use unverifiable when the evidence is too ambiguous to decide."
)


class JudgeError(RuntimeError):
    """Raised when a judge provider cannot produce a valid verdict."""


class ClaimJudge(Protocol):
    def verify_claim(
        self,
        *,
        query: str,
        claim: str,
        contexts: list[TraceContext],
    ) -> "JudgeVerdict":
        """Return a claim-level support verdict for the supplied evidence."""


@dataclass(frozen=True)
class JudgeVerdict:
    verdict: str
    confidence: float
    reason: str
    matched_facts: list[str] = field(default_factory=list)
    missing_facts: list[str] = field(default_factory=list)
    conflicting_facts: list[str] = field(default_factory=list)
    provider: str = "judge"
    model: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any],
        *,
        provider: str,
        model: str | None = None,
    ) -> "JudgeVerdict":
        verdict = _normalize_verdict(payload.get("verdict"))
        return cls(
            verdict=verdict,
            confidence=_confidence(payload.get("confidence", payload.get("support_score"))),
            reason=str(payload.get("reason") or payload.get("rationale") or "Judge returned no rationale."),
            matched_facts=_string_list(payload.get("matched_facts")),
            missing_facts=_string_list(payload.get("missing_facts")),
            conflicting_facts=_string_list(payload.get("conflicting_facts")),
            provider=provider,
            model=model,
            raw=dict(payload),
        )


class OpenAICompatibleJudge:
    """Synchronous OpenAI-compatible claim verifier for SDK and CLI use."""

    system_prompt = JUDGE_SYSTEM_PROMPT

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str,
        base_url: str = DEFAULT_LOCAL_OPENAI_BASE_URL,
        timeout: float = 60.0,
        client: httpx.Client | None = None,
        provider: str = "openai_compatible",
    ) -> None:
        if not model:
            raise ValueError("model is required for OpenAICompatibleJudge.")
        self.api_key = api_key or ""
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client
        self.provider = provider

    def verify_claim(
        self,
        *,
        query: str,
        claim: str,
        contexts: list[TraceContext],
    ) -> JudgeVerdict:
        payload = _claim_payload(query=query, claim=claim, contexts=contexts)
        body = self._complete_json(payload)
        return JudgeVerdict.from_payload(body, provider=self.provider, model=self.model)

    def _complete_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        client = self._client or httpx.Client(timeout=self.timeout)
        close_client = self._client is None
        headers = {}
        if self.api_key:
            headers["Authorization"] = "Bearer %s" % self.api_key
        try:
            response = client.post(
                "%s/chat/completions" % self.base_url,
                headers=headers,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
                    ],
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            data = response.json()
        finally:
            if close_client:
                client.close()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise JudgeError("Judge response did not include choices[0].message.content.") from exc
        return _parse_json_object(content, "Judge response")


class OllamaJudge:
    """Local Ollama-backed claim verifier using the native /api/chat endpoint."""

    system_prompt = JUDGE_SYSTEM_PROMPT

    def __init__(
        self,
        *,
        model: str = DEFAULT_OLLAMA_MODEL,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        timeout: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not model:
            raise ValueError("model is required for OllamaJudge.")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client

    def verify_claim(
        self,
        *,
        query: str,
        claim: str,
        contexts: list[TraceContext],
    ) -> JudgeVerdict:
        payload = _claim_payload(query=query, claim=claim, contexts=contexts)
        body = self._complete_json(payload)
        return JudgeVerdict.from_payload(body, provider="ollama", model=self.model)

    def _complete_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        client = self._client or httpx.Client(timeout=self.timeout)
        close_client = self._client is None
        try:
            response = client.post(
                "%s/api/chat" % self.base_url,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0},
                },
            )
            response.raise_for_status()
            data = response.json()
        finally:
            if close_client:
                client.close()

        try:
            content = data["message"]["content"]
        except (KeyError, TypeError):
            content = data.get("response") if isinstance(data, dict) else None
        if content is None:
            raise JudgeError("Ollama response did not include message.content.")
        return _parse_json_object(content, "Ollama judge response")


class JsonJudgeCache:
    """Small local JSON cache for deterministic judge calls."""

    def __init__(self, path: str | Path = DEFAULT_JUDGE_CACHE_PATH) -> None:
        self.path = Path(path)
        self.hits = 0
        self.misses = 0
        self.writes = 0
        self._entries: dict[str, dict[str, Any]] | None = None

    def get(self, key: str) -> dict[str, Any] | None:
        entries = self._load()
        cached = entries.get(key)
        if cached is None:
            self.misses += 1
            return None
        self.hits += 1
        return dict(cached)

    def set(self, key: str, payload: dict[str, Any]) -> None:
        entries = self._load()
        entries[key] = dict(payload)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(entries, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self.path)
        self.writes += 1

    def stats(self) -> dict[str, int | str]:
        return {
            "path": str(self.path),
            "entries": len(self._load()),
            "hits": self.hits,
            "misses": self.misses,
            "writes": self.writes,
        }

    def _load(self) -> dict[str, dict[str, Any]]:
        if self._entries is not None:
            return self._entries
        if not self.path.exists():
            self._entries = {}
            return self._entries
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise JudgeError("Judge cache could not be read: %s" % exc) from exc
        if not isinstance(payload, dict):
            raise JudgeError("Judge cache must contain a JSON object.")
        self._entries = {
            str(key): dict(value)
            for key, value in payload.items()
            if isinstance(value, dict)
        }
        return self._entries


class CachedJudge:
    """ClaimJudge wrapper that caches verdicts on disk."""

    def __init__(
        self,
        judge: ClaimJudge,
        *,
        cache: JsonJudgeCache | None = None,
        cache_path: str | Path = DEFAULT_JUDGE_CACHE_PATH,
    ) -> None:
        self.judge = judge
        self.cache = cache or JsonJudgeCache(cache_path)
        self.provider = getattr(judge, "provider", judge.__class__.__name__)
        self.model = getattr(judge, "model", None)

    def verify_claim(
        self,
        *,
        query: str,
        claim: str,
        contexts: list[TraceContext],
    ) -> JudgeVerdict:
        payload = _claim_payload(query=query, claim=claim, contexts=contexts)
        key = judge_cache_key(
            provider=str(self.provider),
            model=self.model,
            payload=payload,
        )
        cached = self.cache.get(key)
        if cached is not None:
            return _cached_verdict(cached)
        verdict = self.judge.verify_claim(query=query, claim=claim, contexts=contexts)
        self.cache.set(key, _verdict_payload(verdict))
        return verdict

    def stats(self) -> dict[str, Any]:
        return self.cache.stats()


def judge_cache_key(
    *,
    provider: str,
    model: str | None,
    payload: dict[str, Any],
) -> str:
    cache_payload = {
        "version": 2,
        "provider": provider,
        "model": model or "",
        "system_prompt": JUDGE_SYSTEM_PROMPT,
        "payload": payload,
    }
    encoded = json.dumps(cache_payload, ensure_ascii=True, sort_keys=True, default=str).encode("utf-8")
    return "sha256:%s" % hashlib.sha256(encoded).hexdigest()


def build_judge_provider(
    *,
    provider: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    timeout: float = 60.0,
    offline_strict: bool = False,
    cache_enabled: bool = False,
    cache_path: str | None = None,
) -> ClaimJudge | None:
    resolved_provider = _normalize_provider(provider or os.getenv("CONTEXTTRACE_JUDGE_PROVIDER") or "local")
    if resolved_provider in {"", "local", "heuristic", "none", "off"}:
        return None
    if resolved_provider == "ollama":
        resolved_base_url = base_url or os.getenv("CONTEXTTRACE_JUDGE_BASE_URL") or DEFAULT_OLLAMA_BASE_URL
        _ensure_allowed_base_url(resolved_base_url, offline_strict=offline_strict, provider=resolved_provider)
        return _with_cache(
            OllamaJudge(
                base_url=resolved_base_url,
                model=model or os.getenv("CONTEXTTRACE_JUDGE_MODEL") or DEFAULT_OLLAMA_MODEL,
                timeout=timeout,
            ),
            cache_enabled=cache_enabled,
            cache_path=cache_path,
        )
    if resolved_provider == "openai":
        resolved_base_url = base_url or os.getenv("CONTEXTTRACE_JUDGE_BASE_URL") or DEFAULT_OPENAI_BASE_URL
        _ensure_allowed_base_url(resolved_base_url, offline_strict=offline_strict, provider=resolved_provider)
        resolved_api_key = api_key or os.getenv("CONTEXTTRACE_JUDGE_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        if not resolved_api_key:
            raise ValueError("Provider 'openai' requires CONTEXTTRACE_JUDGE_API_KEY or OPENAI_API_KEY.")
        return _with_cache(
            OpenAICompatibleJudge(
                api_key=resolved_api_key,
                base_url=resolved_base_url,
                model=model or os.getenv("CONTEXTTRACE_JUDGE_MODEL") or DEFAULT_OPENAI_MODEL,
                timeout=timeout,
                provider="openai",
            ),
            cache_enabled=cache_enabled,
            cache_path=cache_path,
        )
    if resolved_provider in {"openai_compatible", "local_openai", "local_openai_compatible", "vllm"}:
        resolved_base_url = base_url or os.getenv("CONTEXTTRACE_JUDGE_BASE_URL") or DEFAULT_LOCAL_OPENAI_BASE_URL
        _ensure_allowed_base_url(resolved_base_url, offline_strict=offline_strict, provider=resolved_provider)
        return _with_cache(
            OpenAICompatibleJudge(
                api_key=api_key or os.getenv("CONTEXTTRACE_JUDGE_API_KEY") or "",
                base_url=resolved_base_url,
                model=model or os.getenv("CONTEXTTRACE_JUDGE_MODEL") or DEFAULT_LOCAL_OPENAI_MODEL,
                timeout=timeout,
                provider=resolved_provider,
            ),
            cache_enabled=cache_enabled,
            cache_path=cache_path,
        )
    if resolved_provider in {"lmstudio", "lm_studio"}:
        resolved_base_url = base_url or os.getenv("CONTEXTTRACE_JUDGE_BASE_URL") or DEFAULT_LMSTUDIO_BASE_URL
        _ensure_allowed_base_url(resolved_base_url, offline_strict=offline_strict, provider=resolved_provider)
        return _with_cache(
            OpenAICompatibleJudge(
                api_key=api_key or os.getenv("CONTEXTTRACE_JUDGE_API_KEY") or "",
                base_url=resolved_base_url,
                model=model or os.getenv("CONTEXTTRACE_JUDGE_MODEL") or DEFAULT_LOCAL_OPENAI_MODEL,
                timeout=timeout,
                provider="lmstudio",
            ),
            cache_enabled=cache_enabled,
            cache_path=cache_path,
        )
    raise ValueError("Unsupported judge provider: %s" % provider)


def _claim_payload(*, query: str, claim: str, contexts: list[TraceContext]) -> dict[str, Any]:
    return {
        "evidence_scope": "selected_evidence_spans_only",
        "query": query,
        "claim": claim,
        "contexts": [
            {
                "id": context.id,
                "text": context.text,
                "metadata": _jsonable(dict(context.metadata)),
            }
            for context in contexts
        ],
    }


def _with_cache(
    judge: ClaimJudge,
    *,
    cache_enabled: bool,
    cache_path: str | None,
) -> ClaimJudge:
    enabled = cache_enabled or _env_bool("CONTEXTTRACE_JUDGE_CACHE", default=False)
    if not enabled:
        return judge
    return CachedJudge(
        judge,
        cache_path=cache_path or os.getenv("CONTEXTTRACE_JUDGE_CACHE_PATH") or DEFAULT_JUDGE_CACHE_PATH,
    )


def _ensure_allowed_base_url(base_url: str, *, offline_strict: bool, provider: str) -> None:
    if offline_strict and not is_local_base_url(base_url):
        raise ValueError(
            "Provider '%s' is blocked because local_only/offline strict mode only allows localhost judge URLs. "
            "Use ollama/local_openai/lmstudio/vllm locally, or set local_only=false to allow %s."
            % (provider, base_url)
        )


def is_local_base_url(base_url: str) -> bool:
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").strip().lower()
    if host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
        return True
    if host.endswith(".localhost"):
        return True
    if host.startswith("127."):
        return True
    return False


def _verdict_payload(verdict: JudgeVerdict) -> dict[str, Any]:
    return {
        "verdict": verdict.verdict,
        "confidence": verdict.confidence,
        "reason": verdict.reason,
        "matched_facts": list(verdict.matched_facts),
        "missing_facts": list(verdict.missing_facts),
        "conflicting_facts": list(verdict.conflicting_facts),
        "provider": verdict.provider,
        "model": verdict.model,
        "raw": dict(verdict.raw),
    }


def _cached_verdict(payload: dict[str, Any]) -> JudgeVerdict:
    raw = dict(payload.get("raw") or {})
    raw["cached"] = True
    return JudgeVerdict(
        verdict=_normalize_verdict(payload.get("verdict")),
        confidence=_confidence(payload.get("confidence")),
        reason=str(payload.get("reason") or "Cached judge verdict."),
        matched_facts=_string_list(payload.get("matched_facts")),
        missing_facts=_string_list(payload.get("missing_facts")),
        conflicting_facts=_string_list(payload.get("conflicting_facts")),
        provider=str(payload.get("provider") or "judge"),
        model=str(payload.get("model")) if payload.get("model") is not None else None,
        raw=raw,
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _env_bool(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_provider(value: str | None) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _normalize_verdict(value: Any) -> str:
    verdict = str(value or "").strip().lower().replace("-", "_")
    if verdict in {"directly_supported", "fully_supported"}:
        verdict = SUPPORTED
    if verdict in {"not_enough_info", "unknown"}:
        verdict = UNVERIFIABLE
    if verdict not in ALLOWED_VERDICTS:
        raise JudgeError("Judge verdict must be one of %s, got %r." % (sorted(ALLOWED_VERDICTS), value))
    return verdict


def _confidence(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = 0.5
    return round(max(0.0, min(1.0, score)), 3)


def _string_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _parse_json_object(content: Any, label: str) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
    text = str(content or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise JudgeError("%s was not valid JSON." % label)
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise JudgeError("%s was not valid JSON: %s" % (label, exc)) from exc
    if not isinstance(parsed, dict):
        raise JudgeError("%s JSON must be an object." % label)
    return parsed
