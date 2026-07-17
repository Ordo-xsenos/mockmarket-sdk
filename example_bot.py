#!/usr/bin/env python3
"""MockMarket Trading Bot — reference implementation for SDK integration.

This bot demonstrates how to connect to the MockMarket API
using the official Python SDK. Use this as a template for
your own automated trading strategies.

Features demonstrated:
  - Sandbox lifecycle (reuse / create)
  - Market data (candles, real-time quotes)
  - Order placement (market & limit, buy & sell)
  - Risk management (positions, balance)
  - Analytics (PnL, trade history, performance metrics)

Requirements:
  - Running MockMarket backend at http://localhost:8000
  - A valid API key in the .env file:

        MOCKMARKET_API_KEY=your-api-key-here

Usage:
    python trade_bot.py                        # comprehensive demo (default)
    python trade_bot.py --mode minimal          # quick smoke-test
    python trade_bot.py --mode full             # orders + risk + analytics
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime
from uuid import UUID

import httpx
from dotenv import load_dotenv

from mockmarket import (
    BalanceResponse,
    Candle,
    MockMarketAPIError,
    MockMarketAsyncClient,
    OrderCreate,
    OrderResponse,
    PerformanceMetrics,
    PnLSummary,
    PositionResponse,
    SandboxCreate,
    SandboxResponse,
)

BASE_URL = "http://localhost:80"
DEMO_SYMBOL = "AAPL"


# ═══════════════════════════════════════════════════════════════════════════
# CLI & configuration
# ═══════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="MockMarket Trading Bot — SDK integration example",
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["minimal", "full", "comprehensive"],
        default="comprehensive",
        help="Demo scenario to run (default: comprehensive)",
    )
    parser.add_argument(
        "--sandbox-name",
        default="Trading Bot Demo",
        help="Name for the sandbox (default: 'Trading Bot Demo')",
    )
    return parser.parse_args()


def get_api_key() -> str:
    """Read the MockMarket API key from .env or environment."""
    load_dotenv()
    key = os.getenv("MOCKMARKET_API_KEY")
    if not key:
        print(
            "  MOCKMARKET_API_KEY not found.\n"
            "  Add it to the .env file:\n\n"
            "      MOCKMARKET_API_KEY=your-api-key-here\n"
        )
        sys.exit(1)
    return key


# ═══════════════════════════════════════════════════════════════════════════
# Terminal formatting
# ═══════════════════════════════════════════════════════════════════════════

def _b(s: str) -> str:
    return f"\033[1m{s}\033[0m"

def _g(s: str) -> str:
    return f"\033[32m{s}\033[0m"

def _y(s: str) -> str:
    return f"\033[33m{s}\033[0m"

def _r(s: str) -> str:
    return f"\033[31m{s}\033[0m"

def _bl(s: str) -> str:
    return f"\033[34m{s}\033[0m"

def _ok(msg: str) -> str:
    return f"  {_g('\u2713')} {msg}"

def _info(msg: str) -> str:
    return f"  {_bl('\u2139')} {msg}"

def _warn(msg: str) -> str:
    return f"  {_y('\u26a0')} {msg}"

def _fail(msg: str) -> str:
    return f"  {_r('\u2717')} {msg}"

def _step(n: int, text: str) -> None:
    print(f"\n  {_b(f'Step {n}:')} {text}")

def _price(p: float | None) -> str:
    return f"${p:,.2f}" if p is not None else "\u2014"


# ═══════════════════════════════════════════════════════════════════════════
# Domain helpers
# ═══════════════════════════════════════════════════════════════════════════

async def check_server_health() -> None:
    """Ensure the MockMarket backend is reachable before proceeding."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{BASE_URL}/api/health", timeout=5)
            r.raise_for_status()
            print(_ok(f"Server is healthy ({BASE_URL})"))
    except httpx.HTTPError as exc:
        print(_fail(f"Cannot reach server at {BASE_URL}"))
        print(f"     {exc}")
        print("     Make sure the backend is running:\n")
        print("         docker compose up\n")
        sys.exit(1)


async def get_or_create_sandbox(
    client: MockMarketAsyncClient,
    name: str,
) -> SandboxResponse:
    """Reuse an active nyse sandbox with data or create a new one."""
    sandboxes = await client.sandboxes.list()
    active = [s for s in sandboxes if s.status == "active" and s.fee_structure == "nyse"]
    if active:
        sb = active[0]
        candles = await client.market.get_candles(
            sandbox_id=sb.id, symbol=DEMO_SYMBOL, interval="1h", limit=1,
        )
        if candles:
            print(_ok(f"Using existing sandbox: {_b(sb.name)} ({sb.id})"))
            return sb
        print(_warn(f"Sandbox {sb.name} ({sb.id}) has no market data — creating a fresh one"))

    sb = await client.sandboxes.create(
        SandboxCreate(
            name=name,
            fee_structure="nyse",
            base_slippage_pct=0.1,
            latency_ms=50,
        )
    )
    print(_ok(f"Sandbox created: {_b(sb.name)} ({sb.id})"))
    return sb


def _candle_row(c: Candle) -> str:
    return (
        f"    {c.timestamp.strftime('%Y-%m-%d %H:%M')}  "
        f"O={_price(c.open)}  H={_price(c.high)}  "
        f"L={_price(c.low)}  C={_price(c.close)}  "
        f"V={c.volume:,.0f}"
    )


def _order_row(o: OrderResponse, prefix: str = "") -> str:
    side_col = _g if o.side == "buy" else _r
    status = o.status
    status_display = status
    if status == "pending" and o.reject_reason == "limit_price_not_met":
        status_display = "pending (price not met)"

    p = _price(o.price)
    fp = _price(o.filled_price)
    extra = ""
    if o.filled_price:
        extra = f" @ {fp}"
    if o.reject_reason and o.reject_reason != "limit_price_not_met":
        extra = f" [{o.reject_reason}]"

    return (
        f"    {prefix}"
        f"{side_col(o.side.upper())} {o.quantity:.1f} {o.symbol}  "
        f"{o.order_type:6s}  {p:>8s}  "
        f"\u2192 {status_display}{extra}"
    )


async def latest_price(
    client: MockMarketAsyncClient,
    sandbox_id: UUID,
    symbol: str = DEMO_SYMBOL,
) -> float:
    """Fetch the most recent closing price from the sandbox candles."""
    candles = await client.market.get_candles(
        sandbox_id=sandbox_id,
        symbol=symbol,
        interval="1h",
        limit=1,
    )
    if not candles:
        raise RuntimeError(f"No candles returned for {symbol}")
    return candles[-1].close


# ═══════════════════════════════════════════════════════════════════════════
# Demo step functions
# ═══════════════════════════════════════════════════════════════════════════

async def step_market_data(
    client: MockMarketAsyncClient,
    sandbox_id: UUID,
    show_quote: bool = True,
) -> float:
    """Fetch and display market data for the demo symbol."""
    _step(3, "Market data")

    candles = await client.market.get_candles(
        sandbox_id=sandbox_id,
        symbol=DEMO_SYMBOL,
        interval="1h",
        limit=10,
    )
    print(_ok(f"Fetched {len(candles)} hourly candles for {DEMO_SYMBOL}"))
    if not candles:
        print(_fail("No market data available for AAPL — sandbox may be empty"))
        sys.exit(1)
    for c in candles[:5]:
        print(_candle_row(c))
    if len(candles) > 5:
        print(f"    ... and {len(candles) - 5} more")

    last_close = candles[-1].close

    if show_quote:
        try:
            quote = await client.market.get_quote(DEMO_SYMBOL)
            direction = "+" if quote.change >= 0 else ""
            print(_ok(
                f"Real-time quote: {_price(quote.price)} "
                f"({direction}{quote.change_pct:.2f}%)"
            ))
        except MockMarketAPIError:
            print(_info("Real-time quote unavailable (Finnhub may not be configured)"))

    return last_close


async def step_orders_minimal(
    client: MockMarketAsyncClient,
    sandbox_id: UUID,
    last_price: float,
) -> float:
    """Place a single market buy order (used in minimal mode)."""
    _step(4, "Orders")

    order = await client.orders.create(
        OrderCreate(
            sandbox_id=sandbox_id,
            symbol=DEMO_SYMBOL,
            side="buy",
            order_type="market",
            quantity=10.0,
        )
    )
    print(_order_row(order))
    return float(order.filled_price or last_price)


async def step_orders_full(
    client: MockMarketAsyncClient,
    sandbox_id: UUID,
    last_price: float,
) -> float:
    """Place market buy and sell orders (used in full mode)."""
    _step(4, "Orders")

    # Market BUY
    buy = await client.orders.create(
        OrderCreate(
            sandbox_id=sandbox_id,
            symbol=DEMO_SYMBOL,
            side="buy",
            order_type="market",
            quantity=10.0,
        )
    )
    print(_order_row(buy, prefix="Market BUY:    "))

    # Market SELL (partial)
    sell = await client.orders.create(
        OrderCreate(
            sandbox_id=sandbox_id,
            symbol=DEMO_SYMBOL,
            side="sell",
            order_type="market",
            quantity=4.0,
        )
    )
    print(_order_row(sell, prefix="Market SELL:   "))

    return float(sell.filled_price or last_price)


async def step_orders_comprehensive(
    client: MockMarketAsyncClient,
    sandbox_id: UUID,
    last_price: float,
) -> None:
    """Place multiple order types and list results (comprehensive mode)."""
    _step(4, "Orders")

    # 4a — Market BUY
    buy = await client.orders.create(
        OrderCreate(
            sandbox_id=sandbox_id,
            symbol=DEMO_SYMBOL,
            side="buy",
            order_type="market",
            quantity=10.0,
        )
    )
    print(_order_row(buy, prefix="Market BUY:    "))

    # 4b — Market SELL (partial)
    sell = await client.orders.create(
        OrderCreate(
            sandbox_id=sandbox_id,
            symbol=DEMO_SYMBOL,
            side="sell",
            order_type="market",
            quantity=4.0,
        )
    )
    print(_order_row(sell, prefix="Market SELL:   "))

    # 4c — Limit BUY (below market to demonstrate pending status)
    limit_price = round(last_price * 0.97, 2)
    limit = await client.orders.create(
        OrderCreate(
            sandbox_id=sandbox_id,
            symbol=DEMO_SYMBOL,
            side="buy",
            order_type="limit",
            quantity=5.0,
            price=limit_price,
        )
    )
    print(_order_row(limit, prefix="Limit BUY:     "))

    # 4d — List all orders
    all_orders = await client.orders.list(sandbox_id)
    print(_ok(f"Total orders in sandbox: {len(all_orders)}"))
    print(f"    {'SIDE':4s}  {'QTY':>5s}  {'TYPE':6s}  {'PRICE':>8s}  {'STATUS':>14s}")
    print(f"    {'----':4s}  {'---':>5s}  {'----':6s}  {'-----':>8s}  {'------':>14s}")
    for o in all_orders[-5:]:
        print(f"    {o.side.upper():4s}  {o.quantity:>5.1f}  {o.order_type:6s}  {_price(o.price):>8s}  {o.status:>14s}")


async def step_positions(
    client: MockMarketAsyncClient,
    sandbox_id: UUID,
) -> None:
    """Display open positions."""
    _step(5, "Positions")
    positions = await client.risk.get_positions(sandbox_id)
    if not positions:
        print(_info("No open positions"))
        return
    print(_ok(f"{len(positions)} open position(s)"))
    for p in positions:
        pnl_col = _g if p.unrealized_pnl >= 0 else _r
        print(
            f"    {p.symbol}  "
            f"Qty: {p.quantity:.2f}  "
            f"Entry: {_price(p.entry_price)}  "
            f"Current: {_price(p.current_price)}  "
            f"PnL: {pnl_col(_price(p.unrealized_pnl))}"
        )


async def step_balance(
    client: MockMarketAsyncClient,
    sandbox_id: UUID,
) -> None:
    """Display current account balance."""
    _step(6, "Balance")
    b = await client.risk.get_balance(sandbox_id)
    print(_ok(
        f"Balance: {_b(_price(b.balance))}  "
        f"|  Maintenance margin: {_price(b.maintenance_margin)}"
    ))


async def step_pnl(
    client: MockMarketAsyncClient,
    sandbox_id: UUID,
) -> None:
    """Display profit & loss summary."""
    _step(7, "PnL Summary")
    pnl = await client.analytics.get_pnl(sandbox_id)
    wr_col = _g if pnl.win_rate >= 50 else _r
    print(_ok(
        f"Total PnL: {_price(pnl.total_pnl)}  "
        f"| Trades: {pnl.total_trades}  "
        f"| Win rate: {wr_col(f'{pnl.win_rate:.1f}%')}"
    ))
    print(f"      Buy volume: {_price(pnl.total_buy_volume)}  "
          f"| Sell volume: {_price(pnl.total_sell_volume)}")


async def step_metrics(
    client: MockMarketAsyncClient,
    sandbox_id: UUID,
) -> None:
    """Display performance metrics (comprehensive only)."""
    _step(8, "Performance Metrics")
    m = await client.analytics.get_metrics(sandbox_id)
    print(_ok(
        f"Sharpe ratio: {m.sharpe_ratio:.2f}  "
        f"| Max drawdown: {m.max_drawdown:.2f}%  "
        f"| Total return: {m.total_return_pct:.2f}%"
    ))


async def step_trade_history(
    client: MockMarketAsyncClient,
    sandbox_id: UUID,
) -> None:
    """Display recent trade history (comprehensive only)."""
    _step(9, "Trade History")
    trades = await client.analytics.get_trades(sandbox_id)
    if not trades:
        print(_info("No trades yet"))
        return
    print(_ok(f"{len(trades)} trade(s) recorded"))
    print(f"    {'SIDE':4s}  {'QTY':>5s}  {'TYPE':6s}  {'FILLED':>8s}  {'SLIPPAGE':>10s}  {'TIME'}")
    print(f"    {'----':4s}  {'---':>5s}  {'----':6s}  {'------':>8s}  {'--------':>10s}  {'----'}")
    for t in trades[-5:]:
        ts = t.filled_at.strftime("%H:%M:%S") if t.filled_at else "\u2014"
        slip = f"{_price(t.slippage_applied)}" if t.slippage_applied else "\u2014"
        print(f"    {t.side.upper():4s}  {t.quantity:>5.1f}  {t.order_type:6s}  {_price(t.filled_price):>8s}  {slip:>10s}  {ts}")


# ═══════════════════════════════════════════════════════════════════════════
# Main demo
# ═══════════════════════════════════════════════════════════════════════════

async def run_demo(api_key: str, mode: str, sandbox_name: str) -> None:
    """Orchestrate the full demo based on the selected mode."""
    async with MockMarketAsyncClient(api_key, base_url=BASE_URL) as client:
        print(f"\n  {_b('MockMarket Trading Bot Demo')}")
        print(f"  Server: {BASE_URL}  |  Mode: {_b(mode)}\n")

        # Step 1 — verify the server is alive
        await check_server_health()

        # Step 2 — sandbox setup
        _step(2, "Sandbox")
        sandbox = await get_or_create_sandbox(client, sandbox_name)

        # Step 3 — market data
        last_price = await step_market_data(client, sandbox.id, show_quote=(mode != "minimal"))

        if mode == "minimal":
            # Step 4 — single buy order
            await step_orders_minimal(client, sandbox.id, last_price)

        elif mode == "full":
            # Step 4 — buy + sell
            await step_orders_full(client, sandbox.id, last_price)

        else:
            # Step 4 — comprehensive order demonstration
            await step_orders_comprehensive(client, sandbox.id, last_price)

        # Step 5 — positions (all modes)
        await step_positions(client, sandbox.id)

        # Step 6 — balance (all modes)
        await step_balance(client, sandbox.id)

        if mode in ("full", "comprehensive"):
            # Step 7 — PnL
            await step_pnl(client, sandbox.id)

        if mode == "comprehensive":
            # Step 8 — performance metrics
            await step_metrics(client, sandbox.id)

            # Step 9 — trade history
            await step_trade_history(client, sandbox.id)

    print(f"\n  {_b(_g('Done.'))}  Disconnected.\n")


def main() -> None:
    """Entry point."""
    args = parse_args()
    api_key = get_api_key()
    asyncio.run(run_demo(api_key, args.mode, args.sandbox_name))


if __name__ == "__main__":
    main()
