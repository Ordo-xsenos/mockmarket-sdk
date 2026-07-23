from __future__ import annotations

import asyncio
import email.utils
import random
from typing import Any

import httpx

from mockmarket.exceptions import (
    AuthenticationError,
    ConflictError,
    ForbiddenError,
    MockMarketAPIError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)


def _parse_retry_after(value: str | None) -> float | None:
    """Parse a ``Retry-After`` header (delta-seconds or an HTTP date)."""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (ValueError, TypeError):
        return None
    if parsed is None:
        return None
    import datetime as _dt

    now = _dt.datetime.now(_dt.UTC)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.UTC)
    return max(0.0, (parsed - now).total_seconds())


class BaseClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        *,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        backoff_max: float = 30.0,
    ) -> None:
        self._client = client
        self._api_key = api_key
        # Automatic 429 handling: retry up to ``max_retries`` times, honouring the
        # server's ``Retry-After`` header when present, else an exponential backoff
        # with full jitter capped at ``backoff_max`` seconds.
        self._max_retries = max(0, max_retries)
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max

    def _build_url(self, path: str) -> str:
        base = str(self._client.base_url).rstrip("/")
        clean_path = path.lstrip("/")
        return f"{base}/{clean_path}"

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        """Seconds to wait before retrying a 429 on ``attempt`` (0-indexed)."""
        retry_after = _parse_retry_after(response.headers.get("Retry-After"))
        if retry_after is not None:
            return min(retry_after, self._backoff_max)
        # Exponential backoff with full jitter.
        ceiling = min(self._backoff_base * (2**attempt), self._backoff_max)
        return random.uniform(0.0, ceiling)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        url = self._build_url(path)
        headers = {"X-API-Key": self._api_key}

        attempt = 0
        while True:
            try:
                response = await self._client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json_body,
                )
            except httpx.HTTPError as exc:
                raise MockMarketAPIError(0, str(exc)) from exc

            if response.status_code == 429 and attempt < self._max_retries:
                await asyncio.sleep(self._retry_delay(response, attempt))
                attempt += 1
                continue
            break

        if response.status_code == 204:
            return None

        if response.status_code == 401:
            raise AuthenticationError(response.text or None)
        if response.status_code == 403:
            raise ForbiddenError(response.text or None)
        if response.status_code == 404:
            raise NotFoundError(response.text or None)
        if response.status_code == 429:
            raise RateLimitError(
                response.text or None,
                retry_after=_parse_retry_after(response.headers.get("Retry-After")),
            )
        if 400 <= response.status_code < 500:
            detail: str | None = None
            try:
                body = response.json()
                detail = str(body.get("detail", body))
            except Exception:
                detail = response.text
            if response.status_code == 409:
                raise ConflictError(detail)
            raise ValidationError(detail)
        if response.status_code >= 500:
            raise MockMarketAPIError(response.status_code, response.text or None)

        return response.json()
