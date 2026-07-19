#!/usr/bin/env python3
"""Reactive-engine example bot (MockMarket /v1).

Unlike paper trading, orders here hit a live limit order book with background
liquidity — market orders move the price. This bot runs a deterministic challenge
preset, trades a little, prints its account, and shows the leaderboard.

Requirements:
  - Running MockMarket backend (default http://localhost)
  - MOCKMARKET_API_KEY in the environment

Usage:
    MOCKMARKET_API_KEY=mk_... python example_bot.py
"""

from __future__ import annotations

import asyncio
import os
import random

from mockmarket import MockMarketAsyncClient, SandboxCreate

BASE_URL = os.environ.get("MOCKMARKET_URL", "http://localhost")
API_KEY = os.environ.get("MOCKMARKET_API_KEY", "")
PRESET = "sprint_v1"


async def main() -> None:
    async with MockMarketAsyncClient(API_KEY, base_url=BASE_URL) as client:
        sb = await client.create_sandbox(
            SandboxCreate(challenge_preset=PRESET, agent_name="arena-example")
        )
        await sb.start()
        print(f"sandbox {sb.id} started")

        for _ in range(30):
            side = random.choice(("buy", "sell"))
            order = await sb.submit_order(side, qty=random.randint(1, 5))
            if order.is_rejected:
                print(f"  rejected: {order.reject_reason}")
            await asyncio.sleep(0.2)

        book = await sb.orderbook(depth=5)
        acct = await sb.account()
        print(f"mid={book.mid} spread={book.spread}")
        print(f"equity={acct.equity} realized={acct.realized_pnl} position={acct.position}")

        await sb.stop()

        print("\nLeaderboard (top 5 by return %):")
        for i, e in enumerate(await client.leaderboard(preset=PRESET, limit=5), 1):
            print(f"  {i}. {e.agent_name:20s} {e.return_pct:>8}%  sharpe={e.sharpe}")


if __name__ == "__main__":
    asyncio.run(main())
