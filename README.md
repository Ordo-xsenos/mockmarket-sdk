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
