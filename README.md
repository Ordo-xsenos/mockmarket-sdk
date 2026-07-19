# MockMarket SDK

Async Python SDK for the [MockMarket](https://mockmarket.ai) algorithmic trading sandbox.

Built with `httpx` + `pydantic` v2.

## Installation

```bash
uv add mockmarket
```

## Quick Start

```python
import asyncio
from mockmarket import MockMarketAsyncClient, OrderCreate, SandboxCreate


async def main() -> None:
    async with MockMarketAsyncClient("YOUR_API_KEY") as client:
        sandbox = await client.sandboxes.create(
            SandboxCreate(
                name="My Bot",
                fee_structure="standard",
                base_slippage_pct=0.1,
                latency_ms=50,
            )
        )
        candles = await client.market.get_candles(sandbox.id, "AAPL")
        order = await client.orders.create(
            OrderCreate(
                sandbox_id=sandbox.id,
                symbol="AAPL",
                side="buy",
                order_type="limit",
                quantity=10.0,
                price=150.0,
            )
        )
        positions = await client.risk.get_positions(sandbox.id)
        balance = await client.risk.get_balance(sandbox.id)
        pnl = await client.analytics.get_pnl(sandbox.id)


asyncio.run(main())
```

## Sub-clients

| Client | Namespace | Methods |
|---|---|---|
| Sandboxes | `client.sandboxes` | `list()`, `create()`, `get()`, `stop()`, `update()` |
| Market Data | `client.market` | `get_ticks()`, `get_candles()`, `get_universe()`, `search_stocks()`, `get_quote()`, `get_history()`, `get_profile()` |
| Orders | `client.orders` | `list()`, `create()`, `get()` |
| Risk | `client.risk` | `get_positions()`, `get_balance()`, `get_liquidations()` |
| Analytics | `client.analytics` | `get_trades()`, `get_pnl()`, `get_metrics()` |
| **Arena (reactive engine)** | `client.arena` | `create_sandbox()`, `get_sandbox()`, `start/pause/stop/delete()`, `orderbook()`, `account()`, `trades()`, `submit_order()`, `list_orders()`, `cancel_order()`, `leaderboard()`, `create_key()`, `stream()` |

## Reactive engine (`/v1`)

The **arena** sub-client talks to the reactive exchange simulator: your orders
trade against a live limit order book with background liquidity, so a market
order *moves the price* and a limit order joins the queue. `client.arena.create_sandbox()`
returns a stateful `Sandbox` handle:

```python
import asyncio
from mockmarket import MockMarketAsyncClient, EngineSandboxCreate


async def main() -> None:
    async with MockMarketAsyncClient("YOUR_API_KEY", base_url="http://localhost") as client:
        # Deterministic challenge run → lands on the public leaderboard.
        sb = await client.arena.create_sandbox(
            EngineSandboxCreate(challenge_preset="sprint_v1", agent_name="my-bot")
        )
        await sb.start()

        order = await sb.market_buy(10)          # this moves the mid
        print(order.status, order.avg_fill_price)

        acct = await sb.account()
        print("equity", acct.equity, "position", acct.position)

        book = await sb.orderbook(depth=5)
        print("best bid/ask", book.best_bid, book.best_ask)

        await sb.stop()
        for e in await client.arena.leaderboard(preset="sprint_v1"):
            print(e.agent_name, e.return_pct)


asyncio.run(main())
```

Business rejects (e.g. exceeding the notional cap) come back as a normal
`EngineOrder` with `status == "rejected"` and a `reject_reason` — not an exception.

### Live stream (WebSocket)

Install the optional extra and iterate events:

```bash
uv add "mockmarket[ws]"
```

```python
async for msg in sb.stream(channels=["orderbook", "trade", "fill"]):
    print(msg.type, msg.data)
```

### Mint an API key

```python
info = await client.arena.create_key("my-bot")
print(info.api_key)   # shown only once
```
