from __future__ import annotations

from uuid import UUID

from mockmarket_sdk._base import BaseClient
from mockmarket_sdk.schemas import (
    Candle,
    StockHistoryItem,
    StockProfile,
    StockQuote,
    StockSearchResult,
    Tick,
)


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
        return [Tick.model_validate(item) for item in data]

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
        return [Candle.model_validate(item) for item in data]

    async def get_universe(self) -> list[str]:
        data = await self._request("GET", "/api/v1/market-data/stocks/universe")
        return data if isinstance(data, list) else list(data)

    async def search_stocks(self, query: str) -> list[StockSearchResult]:
        data = await self._request(
            "GET",
            "/api/v1/market-data/stocks/search",
            params={"query": query},
        )
        return [StockSearchResult.model_validate(item) for item in data]

    async def get_quote(self, symbol: str) -> StockQuote:
        data = await self._request("GET", f"/api/v1/market-data/stocks/{symbol}")
        return StockQuote.model_validate(data)

    async def get_history(self, symbol: str, period: str = "1M") -> list[StockHistoryItem]:
        data = await self._request(
            "GET",
            f"/api/v1/market-data/stocks/{symbol}/history",
            params={"period": period},
        )
        return [StockHistoryItem.model_validate(item) for item in data]

    async def get_profile(self, symbol: str) -> StockProfile:
        data = await self._request("GET", f"/api/v1/market-data/stocks/{symbol}/profile")
        return StockProfile.model_validate(data)
