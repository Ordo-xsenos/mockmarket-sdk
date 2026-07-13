from __future__ import annotations

from typing import Any

import httpx

from mockmarket_sdk._analytics import AnalyticsClient
from mockmarket_sdk._base import BaseClient
from mockmarket_sdk._market import MarketDataClient
from mockmarket_sdk._orders import OrdersClient
from mockmarket_sdk._risk import RiskClient
from mockmarket_sdk._sandboxes import SandboxesClient


class MockMarketAsyncClient(BaseClient):
    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8000",
        *,
        httpx_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        client_kwargs: dict[str, Any] = {
            "base_url": self._base_url,
            "headers": {"X-API-Key": api_key},
            "timeout": httpx.Timeout(30.0),
        }
        if httpx_kwargs:
            client_kwargs.update(httpx_kwargs)
        self._client: httpx.AsyncClient = httpx.AsyncClient(**client_kwargs)

        self.sandboxes = SandboxesClient(self._client, api_key)
        self.market = MarketDataClient(self._client, api_key)
        self.orders = OrdersClient(self._client, api_key)
        self.risk = RiskClient(self._client, api_key)
        self.analytics = AnalyticsClient(self._client, api_key)

    async def __aenter__(self) -> MockMarketAsyncClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()
