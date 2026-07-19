from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from mockmarket._base import BaseClient
from mockmarket._sandbox import Sandbox
from mockmarket.schemas import (
    Account,
    ApiKey,
    LeaderboardEntry,
    Order,
    OrderBook,
    OrderCreate,
    SandboxCreate,
    SandboxInfo,
    StreamMessage,
    Trade,
)


class MockMarketAsyncClient(BaseClient):
    """Async client for the MockMarket reactive exchange simulator (``/v1``).

    Orders trade against a live limit order book with background liquidity, so a
    market order *moves the price* and a limit order joins the queue. Business
    rejects (e.g. exceeding the notional cap) are returned as a normal
    :class:`~mockmarket.schemas.Order` with ``status == "rejected"`` — not an
    exception.

    Example::

        async with MockMarketAsyncClient("mk_...", base_url="http://localhost") as mm:
            sb = await mm.create_sandbox(
                SandboxCreate(challenge_preset="sprint_v1", agent_name="bot")
            )
            await sb.start()
            await sb.market_buy(10)      # moves the mid
            print(await sb.account())
            await sb.stop()
    """

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
        super().__init__(self._client, api_key)

    async def __aenter__(self) -> MockMarketAsyncClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------- top-level
    async def health(self) -> dict[str, str]:
        data = await self._request("GET", "/v1/health")
        return dict(data)

    async def create_key(self, name: str = "default") -> ApiKey:
        data = await self._request("POST", "/v1/keys", json_body={"name": name})
        return ApiKey.model_validate(data)

    async def create_sandbox(self, params: SandboxCreate | None = None) -> Sandbox:
        body = (params or SandboxCreate()).model_dump(mode="json", exclude_none=True)
        data = await self._request("POST", "/v1/sandboxes", json_body=body)
        return Sandbox(self, SandboxInfo.model_validate(data))

    async def get_sandbox(self, sandbox_id: str) -> Sandbox:
        info = await self._get_sandbox(sandbox_id)
        return Sandbox(self, info)

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
    # (Prefer the Sandbox handle returned by create_sandbox/get_sandbox.)
    async def _get_sandbox(self, sandbox_id: str) -> SandboxInfo:
        data = await self._request("GET", f"/v1/sandboxes/{sandbox_id}")
        return SandboxInfo.model_validate(data)

    async def start(self, sandbox_id: str) -> SandboxInfo:
        data = await self._request("POST", f"/v1/sandboxes/{sandbox_id}/start")
        return SandboxInfo.model_validate(data)

    async def pause(self, sandbox_id: str) -> SandboxInfo:
        data = await self._request("POST", f"/v1/sandboxes/{sandbox_id}/pause")
        return SandboxInfo.model_validate(data)

    async def stop(self, sandbox_id: str) -> SandboxInfo:
        data = await self._request("POST", f"/v1/sandboxes/{sandbox_id}/stop")
        return SandboxInfo.model_validate(data)

    async def delete(self, sandbox_id: str) -> None:
        await self._request("DELETE", f"/v1/sandboxes/{sandbox_id}")

    async def orderbook(self, sandbox_id: str, depth: int = 10) -> OrderBook:
        data = await self._request(
            "GET", f"/v1/sandboxes/{sandbox_id}/orderbook", params={"depth": depth}
        )
        return OrderBook.model_validate(data)

    async def account(self, sandbox_id: str) -> Account:
        data = await self._request("GET", f"/v1/sandboxes/{sandbox_id}/account")
        return Account.model_validate(data)

    async def trades(self, sandbox_id: str, limit: int = 100) -> list[Trade]:
        data = await self._request(
            "GET", f"/v1/sandboxes/{sandbox_id}/trades", params={"limit": limit}
        )
        return [Trade.model_validate(item) for item in data]

    async def submit_order(self, sandbox_id: str, params: OrderCreate) -> Order:
        body = params.model_dump(mode="json", exclude_none=True)
        data = await self._request("POST", f"/v1/sandboxes/{sandbox_id}/orders", json_body=body)
        return Order.model_validate(data)

    async def list_orders(self, sandbox_id: str) -> list[Order]:
        data = await self._request("GET", f"/v1/sandboxes/{sandbox_id}/orders")
        return [Order.model_validate(item) for item in data]

    async def cancel_order(self, sandbox_id: str, order_id: str) -> bool:
        data = await self._request("DELETE", f"/v1/sandboxes/{sandbox_id}/orders/{order_id}")
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

        ws_base = self._base_url.replace("https://", "wss://").replace("http://", "ws://")
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
