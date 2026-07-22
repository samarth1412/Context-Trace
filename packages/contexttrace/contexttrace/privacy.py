from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


class TextCipher(Protocol):
    """Optional application-provided encryption-at-rest integration."""

    def encrypt(self, plaintext: str) -> str:
        ...

    def decrypt(self, ciphertext: str) -> str:
        ...


Redactor = Callable[[str], str]


@dataclass(frozen=True)
class PrivacyPolicy:
    """Sanitize trace payloads before they reach local or hosted persistence."""

    profile: str = "standard"
    metadata_allowlist: frozenset[str] | None = None
    redaction_patterns: tuple[str, ...] = ()
    custom_redactors: tuple[Redactor, ...] = ()
    hash_only: bool = False
    hash_salt: str = ""
    cipher: TextCipher | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.profile not in {"standard", "strict"}:
            raise ValueError("Privacy profile must be 'standard' or 'strict'.")
        for pattern in self.redaction_patterns:
            re.compile(pattern)

    @classmethod
    def strict(
        cls,
        *,
        hash_only: bool = False,
        hash_salt: str = "",
        metadata_allowlist: frozenset[str] | None = None,
        redaction_patterns: tuple[str, ...] = (),
        custom_redactors: tuple[Redactor, ...] = (),
        cipher: TextCipher | None = None,
    ) -> "PrivacyPolicy":
        return cls(
            profile="strict",
            metadata_allowlist=frozenset() if metadata_allowlist is None else metadata_allowlist,
            redaction_patterns=redaction_patterns,
            custom_redactors=custom_redactors,
            hash_only=hash_only,
            hash_salt=hash_salt,
            cipher=cipher,
        )

    def sanitize(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        value = _copy(payload)
        if path == "/v1/traces/start":
            value["query"] = self.protect_text(value.get("query"), field="query")
            value["metadata"] = self.protect_metadata(value.get("metadata"))
            return value

        action = path.rstrip("/").rsplit("/", 1)[-1]
        if action in {"retrieval", "context"}:
            value["metadata"] = self.protect_metadata(value.get("metadata"))
            if value.get("chunk_ids") is not None:
                value["chunk_ids"] = [self.protect_identifier(item) for item in value.get("chunk_ids") or []]
            for chunk in value.get("chunks") or []:
                if not isinstance(chunk, dict):
                    continue
                for identifier_key in ("chunk_id", "id", "source_chunk_id"):
                    if identifier_key in chunk:
                        chunk[identifier_key] = self.protect_identifier(chunk.get(identifier_key))
                chunk["content"] = self.protect_text(
                    chunk.get("content") or chunk.get("text") or chunk.get("page_content"),
                    field="chunk text",
                )
                if "source" in chunk:
                    chunk["source"] = self.protect_text(chunk.get("source"), field="source")
                chunk["metadata"] = self.protect_metadata(chunk.get("metadata"))
        elif action == "answer":
            value["answer"] = self.protect_text(value.get("answer"), field="answer text")
            value["metadata"] = self.protect_metadata(value.get("metadata"))
        elif action == "citations":
            for citation in value.get("citations") or []:
                if not isinstance(citation, dict):
                    continue
                citation["claim"] = self.protect_text(citation.get("claim"), field="citation claim")
                for identifier_key in ("source_chunk_id", "source_id", "chunk_id"):
                    if identifier_key in citation:
                        citation[identifier_key] = self.protect_identifier(citation.get(identifier_key))
                if "metadata" in citation:
                    citation["metadata"] = self.protect_metadata(citation.get("metadata"))
        elif action == "agent-events":
            value["name"] = self.protect_text(value.get("name"), field="agent event name")
            value["input_json"] = self.protect_value(value.get("input_json"), field="tool input")
            value["output_json"] = self.protect_value(value.get("output_json"), field="tool output")
            value["error_message"] = self.protect_text(value.get("error_message"), field="agent error")
            if "metadata" in value:
                value["metadata"] = self.protect_metadata(value.get("metadata"))
            if "metadata_json" in value:
                value["metadata_json"] = self.protect_metadata(value.get("metadata_json"))
        return value

    def protect_text(self, value: Any, *, field: str) -> Any:
        if value is None:
            return None
        text = str(value)
        if self.hash_only:
            digest = hashlib.sha256((self.hash_salt + text).encode("utf-8")).hexdigest()
            return "[sha256:%s]" % digest
        if self.profile == "strict":
            text = "[%s redacted]" % field
        else:
            for pattern in self.redaction_patterns:
                text = re.sub(pattern, "[redacted]", text)
            for redactor in self.custom_redactors:
                text = str(redactor(text))
        if self.cipher is not None:
            return "enc:" + self.cipher.encrypt(text)
        return text

    def protect_identifier(self, value: Any) -> Any:
        if value is None or self.profile != "strict":
            return value
        digest = hashlib.sha256((self.hash_salt + str(value)).encode("utf-8")).hexdigest()
        return "id_sha256_%s" % digest

    def protect_value(self, value: Any, *, field: str) -> Any:
        if isinstance(value, dict):
            return {str(key): self.protect_value(item, field=field) for key, item in value.items()}
        if isinstance(value, list):
            return [self.protect_value(item, field=field) for item in value]
        if isinstance(value, tuple):
            return [self.protect_value(item, field=field) for item in value]
        if isinstance(value, str):
            return self.protect_text(value, field=field)
        return value

    def protect_metadata(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        allowed = self.metadata_allowlist
        result: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            if allowed is not None and name not in allowed:
                continue
            result[name] = self.protect_value(item, field="metadata")
        return result

    def restore(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self.restore(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.restore(item) for item in value]
        if isinstance(value, str) and value.startswith("enc:") and self.cipher is not None:
            return self.cipher.decrypt(value[4:])
        return value


class PrivacyTransport:
    def __init__(self, transport: Any, policy: PrivacyPolicy) -> None:
        self.transport = transport
        self.policy = policy
        _attach_restorer(transport, policy)

    def post(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self.transport.post(path, self.policy.sanitize(path, payload or {}))
        return self.policy.restore(result)

    def get(self, path: str) -> dict[str, Any]:
        return self.policy.restore(self.transport.get(path))

    def close(self) -> Any:
        close = getattr(self.transport, "close", None)
        return close() if close else None


class AsyncPrivacyTransport:
    def __init__(self, transport: Any, policy: PrivacyPolicy) -> None:
        self.transport = transport
        self.policy = policy
        _attach_restorer(transport, policy)

    async def post(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        result = await self.transport.post(path, self.policy.sanitize(path, payload or {}))
        return self.policy.restore(result)

    async def get(self, path: str) -> dict[str, Any]:
        return self.policy.restore(await self.transport.get(path))

    async def close(self) -> Any:
        close = getattr(self.transport, "close", None)
        if close is None:
            return None
        result = close()
        if hasattr(result, "__await__"):
            return await result
        return result


def _copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy(item) for item in value]
    if isinstance(value, tuple):
        return [_copy(item) for item in value]
    return value


def _attach_restorer(transport: Any, policy: PrivacyPolicy) -> None:
    target = getattr(transport, "_transport", transport)
    if hasattr(target, "trace_restorer"):
        target.trace_restorer = policy.restore
