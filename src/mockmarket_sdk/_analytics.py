from __future__ import annotations

from uuid import UUID

from mockmarket_sdk._base import BaseClient
from mockmarket_sdk.schemas import PerformanceMetrics, PnLSummary, TradeHistoryItem


class AnalyticsClient(BaseClient):
    async def get_trades(
        self,
        sandbox_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TradeHistoryItem]:
        data = await self._request(
            "GET",
            f"/api/v1/analytics/{sandbox_id}/trades",
            params={"limit": limit, "offset": offset},
        )
        return [TradeHistoryItem.model_validate(item) for item in data]

    async def get_pnl(self, sandbox_id: UUID) -> PnLSummary:
        data = await self._request("GET", f"/api/v1/analytics/{sandbox_id}/pnl")
        return PnLSummary.model_validate(data)

    async def get_metrics(self, sandbox_id: UUID) -> PerformanceMetrics:
        data = await self._request("GET", f"/api/v1/analytics/{sandbox_id}/metrics")
        return PerformanceMetrics.model_validate(data)
