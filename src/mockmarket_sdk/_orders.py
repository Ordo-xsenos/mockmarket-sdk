from __future__ import annotations

from uuid import UUID

from mockmarket_sdk._base import BaseClient
from mockmarket_sdk.schemas import OrderCreate, OrderResponse


class OrdersClient(BaseClient):
    async def list(
        self,
        sandbox_id: UUID,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[OrderResponse]:
        params: dict[str, str | int] = {
            "sandbox_id": str(sandbox_id),
            "limit": limit,
            "offset": offset,
        }
        if status is not None:
            params["status"] = status
        data = await self._request("GET", "/api/v1/orders", params=params)
        return [OrderResponse.model_validate(item) for item in data]

    async def create(self, params: OrderCreate) -> OrderResponse:
        data = await self._request("POST", "/api/v1/orders", json_body=params.model_dump())
        return OrderResponse.model_validate(data)

    async def get(self, order_id: UUID) -> OrderResponse:
        data = await self._request("GET", f"/api/v1/orders/{order_id}")
        return OrderResponse.model_validate(data)
