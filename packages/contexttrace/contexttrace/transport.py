from __future__ import annotations

from typing import Any, Protocol

import httpx


class Transport(Protocol):
    def post(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        ...

    def get(self, path: str) -> dict[str, Any]:
        ...


class HttpTransport:
    def __init__(self, *, base_url: str, api_key: str, timeout: float = 30.0) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "contexttrace-python/0.1.0",
            },
        )

    def post(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self._client.post(path, json=payload or {})
        response.raise_for_status()
        return response.json()

    def get(self, path: str) -> dict[str, Any]:
        response = self._client.get(path)
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()
