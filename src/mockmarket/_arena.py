from __future__ import annotations

import json
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import TYPE_CHECKING

from mockmarket._base import BaseClient
from mockmarket.schemas import (
    EngineAccount,
    EngineApiKey,
    EngineOrder,
    EngineOrderCreate,
    EngineSandbox,
    EngineSandboxCreate,
    EngineTrade,
    LeaderboardEntry,
    OrderBook,
    StreamMessage,
)

if TYPE_CHECKING:
    import httpx

Number = Decimal | int | float | str


class ArenaClient(BaseClient):
    """Client for the reactive-engine API (``/v1``).

    Orders trade against a live limit order book with background liquidity, so a
    market order moves the price and a limit order joins the queue. Business
    rejects (e.g. exceeding the notional cap) are returned as a normal
    :class:`~mockmarket.schemas.EngineOrder` with ``status == "rejected"`` — not
    an exception.
    """

    def __init__(self, client: httpx.AsyncClient, api_key: str) -> None:
        super().__init__(client, api_key)

    # ------------------------------------------------------------- top-level
    async def health(self) -> dict[str, str]:
        data = await self._request("GET", "/v1/health")
        return dict(data)

    async def create_key(self, name: str = "default") -> EngineApiKey:
        data = await self._request("POST", "/v1/keys", json_body={"name": name})
        return EngineApiKey.model_validate(data)

    async def create_sandbox(self, params: EngineSandboxCreate | None = None) -> Sandbox:
        body = (params or EngineSandboxCreate()).model_dump(mode="json", exclude_none=True)
        data = await self._request("POST", "/v1/sandboxes", json_body=body)
        return Sandbox(self, EngineSandbox.model_validate(data))

    async def get_sandbox(self, sandbox_id: str) -> Sandbox:
        data = await self._request("GET", f"/v1/sandboxes/{sandbox_id}")
        return Sandbox(self, EngineSandbox.model_validate(data))

    async def leaderboard(
        self,
        preset: str | None = None,
        metric: str = "return_pct",
        limit: int = 50,
    ) -> list[LeaderboardEntry]:
        params: dict[str, str | int] = {"metric": metric, "limit": limit}
        if preset is not None:
            params["preset"] = preset
        data = await self._request("GET", "/v1/leaderboard", params=params)
        return [LeaderboardEntry.model_validate(item) for item in data]

    # --------------------------------------------------------- id-based ops
    async def _sandbox(self, sandbox_id: str) -> EngineSandbox:
        data = await self._request("GET", f"/v1/sandboxes/{sandbox_id}")
        return EngineSandbox.model_validate(data)

    async def start(self, sandbox_id: str) -> EngineSandbox:
        data = await self._request("POST", f"/v1/sandboxes/{sandbox_id}/start")
        return EngineSandbox.model_validate(data)

    async def pause(self, sandbox_id: str) -> EngineSandbox:
        data = await self._request("POST", f"/v1/sandboxes/{sandbox_id}/pause")
        return EngineSandbox.model_validate(data)

    async def stop(self, sandbox_id: str) -> EngineSandbox:
        data = await self._request("POST", f"/v1/sandboxes/{sandbox_id}/stop")
        return EngineSandbox.model_validate(data)

    async def delete(self, sandbox_id: str) -> None:
        await self._request("DELETE", f"/v1/sandboxes/{sandbox_id}")

    async def orderbook(self, sandbox_id: str, depth: int = 10) -> OrderBook:
        data = await self._request(
            "GET", f"/v1/sandboxes/{sandbox_id}/orderbook", params={"depth": depth}
        )
        return OrderBook.model_validate(data)

    async def account(self, sandbox_id: str) -> EngineAccount:
        data = await self._request("GET", f"/v1/sandboxes/{sandbox_id}/account")
        return EngineAccount.model_validate(data)

    async def trades(self, sandbox_id: str, limit: int = 100) -> list[EngineTrade]:
        data = await self._request(
            "GET", f"/v1/sandboxes/{sandbox_id}/trades", params={"limit": limit}
        )
        return [EngineTrade.model_validate(item) for item in data]

    async def submit_order(self, sandbox_id: str, params: EngineOrderCreate) -> EngineOrder:
        body = params.model_dump(mode="json", exclude_none=True)
        data = await self._request("POST", f"/v1/sandboxes/{sandbox_id}/orders", json_body=body)
        return EngineOrder.model_validate(data)

    async def list_orders(self, sandbox_id: str) -> list[EngineOrder]:
        data = await self._request("GET", f"/v1/sandboxes/{sandbox_id}/orders")
        return [EngineOrder.model_validate(item) for item in data]

    async def cancel_order(self, sandbox_id: str, order_id: str) -> bool:
        data = await self._request(
            "DELETE", f"/v1/sandboxes/{sandbox_id}/orders/{order_id}"
        )
        return bool(data.get("cancelled", False))

    # ------------------------------------------------------------- streaming
    async def stream(
        self, sandbox_id: str, channels: list[str] | None = None
    ) -> AsyncIterator[StreamMessage]:
        """Yield live WebSocket events. Requires the optional ``websockets`` extra."""
        try:
            import websockets
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "stream() requires the 'websockets' package (install mockmarket[ws])"
            ) from exc

        base = str(self._client.base_url).rstrip("/")
        ws_base = base.replace("https://", "wss://").replace("http://", "ws://")
        url = f"{ws_base}/v1/sandboxes/{sandbox_id}/stream?api_key={self._api_key}"

        async with websockets.connect(url) as ws:
            if channels:
                await ws.send(json.dumps({"op": "subscribe", "channels": channels}))
            async for raw in ws:
                text = raw if isinstance(raw, str) else raw.decode()
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:  # pragma: no cover
                    continue
                yield StreamMessage(type=payload.get("type", "unknown"), data=payload)


class Sandbox:
    """Stateful handle to one engine sandbox — the ergonomic entry point.

    Returned by :meth:`ArenaClient.create_sandbox` / :meth:`ArenaClient.get_sandbox`.
    """

    def __init__(self, arena: ArenaClient, info: EngineSandbox) -> None:
        self._arena = arena
        self.info = info
        self.id = info.id

    def __repr__(self) -> str:
        return f"<Sandbox {self.id} status={self.info.status}>"

    async def refresh(self) -> Sandbox:
        self.info = await self._arena._sandbox(self.id)
        return self

    async def start(self) -> EngineSandbox:
        self.info = await self._arena.start(self.id)
        return self.info

    async def pause(self) -> EngineSandbox:
        self.info = await self._arena.pause(self.id)
        return self.info

    async def stop(self) -> EngineSandbox:
        self.info = await self._arena.stop(self.id)
        return self.info

    async def delete(self) -> None:
        await self._arena.delete(self.id)

    async def orderbook(self, depth: int = 10) -> OrderBook:
        return await self._arena.orderbook(self.id, depth)

    async def account(self) -> EngineAccount:
        return await self._arena.account(self.id)

    async def trades(self, limit: int = 100) -> list[EngineTrade]:
        return await self._arena.trades(self.id, limit)

    async def submit_order(
        self,
        side: str,
        qty: Number,
        *,
        type: str = "market",
        price: Number | None = None,
        client_order_id: str | None = None,
    ) -> EngineOrder:
        params = EngineOrderCreate(
            side=side,  # type: ignore[arg-type]
            type=type,  # type: ignore[arg-type]
            qty=Decimal(str(qty)),
            price=Decimal(str(price)) if price is not None else None,
            client_order_id=client_order_id,
        )
        return await self._arena.submit_order(self.id, params)

    async def market_buy(self, qty: Number, **kw: str | None) -> EngineOrder:
        return await self.submit_order("buy", qty, type="market", **kw)

    async def market_sell(self, qty: Number, **kw: str | None) -> EngineOrder:
        return await self.submit_order("sell", qty, type="market", **kw)

    async def limit_buy(self, qty: Number, price: Number, **kw: str | None) -> EngineOrder:
        return await self.submit_order("buy", qty, type="limit", price=price, **kw)

    async def limit_sell(self, qty: Number, price: Number, **kw: str | None) -> EngineOrder:
        return await self.submit_order("sell", qty, type="limit", price=price, **kw)

    async def orders(self) -> list[EngineOrder]:
        return await self._arena.list_orders(self.id)

    async def cancel_order(self, order_id: str) -> bool:
        return await self._arena.cancel_order(self.id, order_id)

    def stream(self, channels: list[str] | None = None) -> AsyncIterator[StreamMessage]:
        return self._arena.stream(self.id, channels)
