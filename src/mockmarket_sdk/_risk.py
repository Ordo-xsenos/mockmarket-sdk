from __future__ import annotations

from uuid import UUID

from mockmarket_sdk._base import BaseClient
from mockmarket_sdk.schemas import BalanceResponse, LiquidationResponse, PositionResponse


class RiskClient(BaseClient):
    async def get_positions(self, sandbox_id: UUID) -> list[PositionResponse]:
        data = await self._request("GET", f"/api/v1/risk/{sandbox_id}/positions")
        return [PositionResponse.model_validate(item) for item in data]

    async def get_balance(self, sandbox_id: UUID) -> BalanceResponse:
        data = await self._request("GET", f"/api/v1/risk/{sandbox_id}/balance")
        return BalanceResponse.model_validate(data)

    async def get_liquidations(self, sandbox_id: UUID) -> list[LiquidationResponse]:
        data = await self._request("GET", f"/api/v1/risk/{sandbox_id}/liquidations")
        return [LiquidationResponse.model_validate(item) for item in data]
