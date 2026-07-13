from __future__ import annotations

from typing import Any

import httpx

from mockmarket_sdk.exceptions import (
    AuthenticationError,
    MockMarketAPIError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)


class BaseClient:
    def __init__(self, client: httpx.AsyncClient, api_key: str) -> None:
        self._client = client
        self._api_key = api_key

    def _build_url(self, path: str) -> str:
        return f"{self._client.base_url}{path}".rstrip("/")

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

        if response.status_code == 204:
            return None

        if response.status_code == 401:
            raise AuthenticationError(response.text or None)
        if response.status_code == 403:
            raise AuthenticationError(response.text or None)
        if response.status_code == 404:
            raise NotFoundError(response.text or None)
        if response.status_code == 429:
            raise RateLimitError(response.text or None)
        if 400 <= response.status_code < 500:
            detail: str | None = None
            try:
                body = response.json()
                detail = str(body.get("detail", body))
            except Exception:
                detail = response.text
            raise ValidationError(detail)
        if response.status_code >= 500:
            raise MockMarketAPIError(response.status_code, response.text or None)

        return response.json()
