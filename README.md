# MockMarket SDK

Async Python SDK for the [MockMarket](https://mockmarket.ai) **reactive exchange
simulator**. Unlike paper trading, your orders trade against a live limit order
book with background liquidity — a market order *moves the price* and a limit
order joins the queue.

Built with `httpx` + `pydantic` v2.

## Installation

```bash
uv add mockmarket
uv add "mockmarket[ws]"   # + WebSocket streaming
```

## Quick Start

```python
import asyncio
from mockmarket import MockMarketAsyncClient, SandboxCreate


async def main() -> None:
    async with MockMarketAsyncClient("YOUR_API_KEY", base_url="http://localhost") as client:
        # A deterministic challenge run → lands on the public leaderboard.
        sb = await client.create_sandbox(
            SandboxCreate(challenge_preset="sprint_v1", agent_name="my-bot")
        )
        await sb.start()

        order = await sb.market_buy(10)          # this moves the mid
        print(order.status, order.avg_fill_price)

        book = await sb.orderbook(depth=5)
        print("best bid/ask", book.best_bid, book.best_ask)

        acct = await sb.account()
        print("equity", acct.equity, "position", acct.position)

        await sb.stop()
        for e in await client.leaderboard(preset="sprint_v1"):
            print(e.agent_name, e.return_pct)


asyncio.run(main())
```

## The `Sandbox` handle

`create_sandbox()` / `get_sandbox()` return a stateful `Sandbox` you trade with:

| Method | Description |
|---|---|
| `start()` / `pause()` / `stop()` / `delete()` | Lifecycle |
| `orderbook(depth=10)` | Top-of-book snapshot (`OrderBook` with `best_bid`/`best_ask`/`spread`) |
| `account()` | Position, balances, realized/unrealized PnL, equity |
| `trades(limit=100)` | Recent tape |
| `market_buy(qty)` / `market_sell(qty)` | Market orders |
| `limit_buy(qty, price)` / `limit_sell(qty, price)` | Limit orders |
| `submit_order(side, qty, type=..., price=..., client_order_id=...)` | Full control |
| `orders()` / `cancel_order(order_id)` | Open orders |
| `stream(channels=...)` | Live WebSocket events (needs `mockmarket[ws]`) |

Client-level helpers: `client.create_sandbox()`, `client.get_sandbox(id)`,
`client.leaderboard(preset=..., metric=..., limit=...)`, `client.create_key(name)`,
`client.health()`.

## Business rejects vs errors

A **business reject** (e.g. exceeding the notional cap) is *not* an exception —
it comes back as a normal `Order` with `status == "rejected"` and a `reject_reason`:

```python
order = await sb.market_buy(1_000_000)
if order.is_rejected:
    print("rejected:", order.reject_reason)
```

HTTP failures raise `MockMarketAPIError` subclasses: `AuthenticationError` (401/403),
`NotFoundError` (404), `ConflictError` (409, e.g. pausing before start),
`RateLimitError` (429), `ValidationError` (422).

## Rate limiting (automatic backoff)

On HTTP `429` the client **retries automatically**, honouring the server's
`Retry-After` header when present, otherwise an exponential backoff with full
jitter. `RateLimitError` is raised only after the retries are exhausted, and it
carries `retry_after` (seconds) when the server provided it.

```python
# Defaults: retry up to 3 times. Tune or disable per client:
mm = MockMarketAsyncClient("mk_...", max_retries=5, backoff_base=0.5, backoff_max=30.0)
mm = MockMarketAsyncClient("mk_...", max_retries=0)   # disable → handle 429 yourself

try:
    await sb.market_buy(10)
except RateLimitError as e:
    print("still limited; server suggests waiting", e.retry_after, "s")
```

## Live stream (WebSocket)

```python
async for msg in sb.stream(channels=["orderbook", "trade", "fill", "account"]):
    print(msg.type, msg.data)
```

## Mint an API key

```python
info = await client.create_key("my-bot")
print(info.api_key)   # shown only once
```

## Exact arithmetic

Prices, quantities and money are `Decimal` end-to-end and cross the wire as
strings, so the SDK inherits the engine's exact matching/accounting — no float drift.

See [`example_bot.py`](example_bot.py) for a runnable agent.
