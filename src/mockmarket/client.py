from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx

from mockmarket._analytics import AnalyticsClient
from mockmarket._base import BaseClient
from mockmarket._market import MarketDataClient
from mockmarket._orders import OrdersClient
from mockmarket._risk import RiskClient
from mockmarket._sandboxes import SandboxesClient
from mockmarket.schemas import OrderCreate


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

    async def get_sandbox_info(self, sandbox_id: str) -> dict[str, Any]:
        sb = await self.sandboxes.get(UUID(sandbox_id))
        return {
            "budget": sb.budget,
            "status": sb.status,
            "fee_structure": sb.fee_structure,
            "base_slippage_pct": sb.base_slippage_pct,
            "commission_fee_pct": sb.commission_fee_pct,
            "exchange_type": sb.exchange_type,
        }

    async def get_portfolio(self, sandbox_id: str) -> list[dict[str, Any]]:
        positions = await self.risk.get_positions(UUID(sandbox_id))
        return [
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "unrealized_pnl": p.unrealized_pnl,
            }
            for p in positions
        ]

    async def get_price(self, symbol: str) -> float:
        quote = await self.market.get_quote(symbol)
        return quote.price

    async def place_order(
        self, sandbox_id: str, symbol: str, side: str, quantity: int
    ) -> dict[str, Any]:
        order = await self.orders.create(OrderCreate(
            sandbox_id=UUID(sandbox_id),
            symbol=symbol,
            side=side,
            order_type="market",
            quantity=float(quantity),
        ))
        return {
            "order_id": str(order.id),
            "status": order.status,
            "side": order.side,
            "symbol": order.symbol,
            "quantity": order.quantity,
            "filled_price": order.filled_price,
            "reject_reason": order.reject_reason,
        }

    async def __aenter__(self) -> MockMarketAsyncClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()
