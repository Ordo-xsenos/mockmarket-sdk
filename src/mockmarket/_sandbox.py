from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from typing import TYPE_CHECKING

from mockmarket.schemas import (
    Account,
    Order,
    OrderBook,
    OrderCreate,
    SandboxInfo,
    StreamMessage,
    Trade,
)

if TYPE_CHECKING:
    from mockmarket.client import MockMarketAsyncClient

Number = Decimal | int | float | str


class Sandbox:
    """Stateful handle to one engine sandbox — the ergonomic entry point.

    Returned by :meth:`MockMarketAsyncClient.create_sandbox` /
    :meth:`MockMarketAsyncClient.get_sandbox`.
    """

    def __init__(self, client: MockMarketAsyncClient, info: SandboxInfo) -> None:
        self._client = client
        self.info = info
        self.id = info.id

    def __repr__(self) -> str:
        return f"<Sandbox {self.id} status={self.info.status}>"

    # ---------------------------------------------------------- lifecycle
    async def refresh(self) -> Sandbox:
        self.info = await self._client._get_sandbox(self.id)
        return self

    async def start(self) -> SandboxInfo:
        self.info = await self._client.start(self.id)
        return self.info

    async def pause(self) -> SandboxInfo:
        self.info = await self._client.pause(self.id)
        return self.info

    async def stop(self) -> SandboxInfo:
        self.info = await self._client.stop(self.id)
        return self.info

    async def delete(self) -> None:
        await self._client.delete(self.id)

    # ---------------------------------------------------------- market data
    async def orderbook(self, depth: int = 10) -> OrderBook:
        return await self._client.orderbook(self.id, depth)

    async def account(self) -> Account:
        return await self._client.account(self.id)

    async def trades(self, limit: int = 100) -> list[Trade]:
        return await self._client.trades(self.id, limit)

    # ---------------------------------------------------------- orders
    async def submit_order(
        self,
        side: str,
        qty: Number,
        *,
        type: str = "market",
        price: Number | None = None,
        client_order_id: str | None = None,
    ) -> Order:
        params = OrderCreate(
            side=side,  # type: ignore[arg-type]
            type=type,  # type: ignore[arg-type]
            qty=Decimal(str(qty)),
            price=Decimal(str(price)) if price is not None else None,
            client_order_id=client_order_id,
        )
        return await self._client.submit_order(self.id, params)

    async def market_buy(self, qty: Number, **kw: str | None) -> Order:
        return await self.submit_order("buy", qty, type="market", **kw)

    async def market_sell(self, qty: Number, **kw: str | None) -> Order:
        return await self.submit_order("sell", qty, type="market", **kw)

    async def limit_buy(self, qty: Number, price: Number, **kw: str | None) -> Order:
        return await self.submit_order("buy", qty, type="limit", price=price, **kw)

    async def limit_sell(self, qty: Number, price: Number, **kw: str | None) -> Order:
        return await self.submit_order("sell", qty, type="limit", price=price, **kw)

    async def orders(self) -> list[Order]:
        return await self._client.list_orders(self.id)

    async def cancel_order(self, order_id: str) -> bool:
        return await self._client.cancel_order(self.id, order_id)

    # ---------------------------------------------------------- streaming
    def stream(self, channels: list[str] | None = None) -> AsyncIterator[StreamMessage]:
        return self._client.stream(self.id, channels)
