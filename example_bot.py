import asyncio
from uuid import UUID

from mockmarket import MockMarketAsyncClient, OrderCreate, SandboxCreate


async def main() -> None:
    api_key = "YOUR_API_KEY_HERE"
    sandbox_id: UUID

    async with MockMarketAsyncClient(api_key, base_url="http://localhost:8000") as client:
        sandboxes = await client.sandboxes.list()
        if sandboxes:
            sandbox_id = sandboxes[0].id
            print(f"Using existing sandbox: {sandbox_id}")
        else:
            sandbox = await client.sandboxes.create(
                SandboxCreate(
                    name="My Trading Bot",
                    fee_structure="standard",
                    base_slippage_pct=0.1,
                    latency_ms=50,
                )
            )
            sandbox_id = sandbox.id
            print(f"Created sandbox: {sandbox_id}")

        candles = await client.market.get_candles(
            sandbox_id=sandbox_id,
            symbol="AAPL",
            interval="1h",
            limit=10,
        )
        print(f"Fetched {len(candles)} candles for AAPL")
        for c in candles[:3]:
            print(f"  {c.timestamp} | O={c.open} H={c.high} L={c.low} C={c.close} V={c.volume}")

        order = await client.orders.create(
            OrderCreate(
                sandbox_id=sandbox_id,
                symbol="AAPL",
                side="buy",
                order_type="limit",
                quantity=10.0,
                price=150.0,
            )
        )
        print(f"Order {order.id} created: status={order.status}")

        positions = await client.risk.get_positions(sandbox_id)
        print(f"Open positions: {len(positions)}")

        balance = await client.risk.get_balance(sandbox_id)
        print(f"Balance: {balance.balance} | Maintenance margin: {balance.maintenance_margin}")

        pnl = await client.analytics.get_pnl(sandbox_id)
        print(f"PnL: {pnl.total_pnl} | Win rate: {pnl.win_rate:.1f}%")

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
