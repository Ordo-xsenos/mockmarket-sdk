from __future__ import annotations

from typing import Any
from uuid import UUID

from mockmarket._base import BaseClient
from mockmarket.schemas import (
    Candle,
    StockHistoryItem,
    StockProfile,
    StockQuote,
    StockSearchResult,
    Tick,
)


def _extract_list(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                return v
    return []


class MarketDataClient(BaseClient):
    async def get_ticks(
        self,
        sandbox_id: UUID,
        symbol: str,
        limit: int = 100,
    ) -> list[Tick]:
        data = await self._request(
            "GET",
            f"/api/v1/market-data/{sandbox_id}/ticks",
            params={"symbol": symbol, "limit": limit},
        )
        return [Tick.model_validate(item) for item in _extract_list(data)]

    async def get_candles(
        self,
        sandbox_id: UUID,
        symbol: str,
        interval: str = "1h",
        limit: int = 100,
    ) -> list[Candle]:
        data = await self._request(
            "GET",
            f"/api/v1/market-data/{sandbox_id}/candles",
            params={"symbol": symbol, "interval": interval, "limit": limit},
        )
        return [Candle.model_validate(item) for item in _extract_list(data)]

    async def get_universe(self) -> list[str]:
        data = await self._request("GET", "/api/v1/market-data/stocks/universe")
        return _extract_list(data)

    async def search_stocks(self, query: str) -> list[StockSearchResult]:
        data = await self._request(
            "GET",
            "/api/v1/market-data/stocks/search",
            params={"query": query},
        )
        return [StockSearchResult.model_validate(item) for item in _extract_list(data)]

    async def get_quote(self, symbol: str) -> StockQuote:
        data = await self._request("GET", f"/api/v1/market-data/stocks/{symbol}")
        return StockQuote.model_validate(data)

    async def get_history(self, symbol: str, period: str = "1M") -> list[StockHistoryItem]:
        data = await self._request(
            "GET",
            f"/api/v1/market-data/stocks/{symbol}/history",
            params={"period": period},
        )
        return [StockHistoryItem.model_validate(item) for item in _extract_list(data)]

    async def get_profile(self, symbol: str) -> StockProfile:
        data = await self._request("GET", f"/api/v1/market-data/stocks/{symbol}/profile")
        return StockProfile.model_validate(data)
