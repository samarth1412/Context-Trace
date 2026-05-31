from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional, Protocol

import httpx

from contexttrace.errors import ContextTraceHTTPError

logger = logging.getLogger("contexttrace")


class Transport(Protocol):
    def post(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        ...

    def get(self, path: str) -> dict[str, Any]:
        ...


class HttpTransport:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
        retries: int = 2,
        debug: bool = False,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self.retries = max(0, retries)
        self.debug = debug
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "contexttrace-python/0.1.0",
            },
        )

    def post(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("POST", path, json=payload or {})

    def get(self, path: str) -> dict[str, Any]:
        return self._request("GET", path)

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        last_error: Optional[BaseException] = None
        attempts = self.retries + 1

        for attempt in range(attempts):
            try:
                if self.debug:
                    logger.debug("%s %s", method, path)
                response = self._client.request(method, path, **kwargs)
                if response.status_code >= 500 and attempt < attempts - 1:
                    last_error = _http_error(response)
                    _sleep_before_retry(attempt)
                    continue
                return _json_or_raise(response)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.TransportError) as exc:
                last_error = exc
                if attempt >= attempts - 1:
                    break
                _sleep_before_retry(attempt)

        raise ContextTraceHTTPError(
            "ContextTrace API request failed after %s attempt(s): %s %s: %s"
            % (attempts, method, path, last_error)
        )

    def close(self) -> None:
        self._client.close()


class AsyncTransport(Protocol):
    async def post(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        ...

    async def get(self, path: str) -> dict[str, Any]:
        ...


class AsyncHttpTransport:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
        retries: int = 2,
        debug: bool = False,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.retries = max(0, retries)
        self.debug = debug
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "contexttrace-python/0.1.0",
            },
        )

    async def post(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request("POST", path, json=payload or {})

    async def get(self, path: str) -> dict[str, Any]:
        return await self._request("GET", path)

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        last_error: Optional[BaseException] = None
        attempts = self.retries + 1

        for attempt in range(attempts):
            try:
                if self.debug:
                    logger.debug("%s %s", method, path)
                response = await self._client.request(method, path, **kwargs)
                if response.status_code >= 500 and attempt < attempts - 1:
                    last_error = _http_error(response)
                    await _async_sleep_before_retry(attempt)
                    continue
                return _json_or_raise(response)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.TransportError) as exc:
                last_error = exc
                if attempt >= attempts - 1:
                    break
                await _async_sleep_before_retry(attempt)

        raise ContextTraceHTTPError(
            "ContextTrace API request failed after %s attempt(s): %s %s: %s"
            % (attempts, method, path, last_error)
        )

    async def close(self) -> None:
        await self._client.aclose()


def _json_or_raise(response: httpx.Response) -> dict[str, Any]:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise _http_error(response) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise ContextTraceHTTPError(
            "ContextTrace API returned invalid JSON for %s %s."
            % (response.request.method, response.request.url)
        ) from exc

    if not isinstance(data, dict):
        raise ContextTraceHTTPError("ContextTrace API returned a non-object JSON response.")
    return data


def _http_error(response: httpx.Response) -> ContextTraceHTTPError:
    detail = response.text
    try:
        body = response.json()
        if isinstance(body, dict):
            detail = str(body.get("detail") or body.get("error") or body)
    except ValueError:
        pass
    return ContextTraceHTTPError(
        "ContextTrace API request failed with HTTP %s for %s %s: %s"
        % (response.status_code, response.request.method, response.request.url, detail)
    )


def _sleep_before_retry(attempt: int) -> None:
    time.sleep(min(0.5, 0.1 * (2 ** attempt)))


async def _async_sleep_before_retry(attempt: int) -> None:
    await asyncio.sleep(min(0.5, 0.1 * (2 ** attempt)))
