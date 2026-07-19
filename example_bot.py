"""AI trading bot (ReAct) for the MockMarket reactive engine.

Keeps the ReAct pattern of the original: an LLM (via Ollama tool-calling) reasons
over news, calls tools to gather live market state, and decides buy / sell / hold.
Rewritten for the engine-only SDK (mockmarket >= 0.2.0): the bot trades a single
symbol against a *live limit order book* — its market orders move the price — and
reads state through the account / order book / tape instead of the old portal's
portfolio + reference-price endpoints.

Run:
    MOCKMARKET_API_KEY is read from .env
    python trade_bot.py
"""

import asyncio
import json
import os
import random

from ollama import AsyncClient

from mockmarket import MockMarketAsyncClient, SandboxCreate
from mockmarket.exceptions import MockMarketAPIError

BASE_URL = "http://localhost:80"

_env = {}
with open(os.path.join(os.path.dirname(__file__), ".env")) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            _env[k.strip()] = v.strip()
API_KEY = _env.get("MOCKMARKET_API_KEY", "")

# Each entry is a fixed, named challenge preset (server-side: symbol + seed + full
# market config). Running as a challenge means every run is reproducible and lands
# on the public leaderboard. Different presets = different (independent) synthetic
# markets, so the bot trades several stocks with distinct price dynamics.
PRESETS = [
    ("sprint_v1", "AAPL"),
    ("sprint_msft", "MSFT"),
    ("sprint_nvda", "NVDA"),
]
MODEL_NAME = "qwen2.5:7b"
OLLAMA_HOST = "http://localhost:11434"
# Context window for the model. 2048 keeps qwen2.5:7b fully on a 6GB GPU
# (larger windows grow the KV cache and spill layers to the CPU).
NUM_CTX = 2048

# Symbol-agnostic headlines ({symbol} is filled in per run).
NEWS_POOL = [
    "{symbol} unveils a groundbreaking new AI chip. Analysts predict massive growth.",
    "Supply chain issues disrupt {symbol}'s production in Asia.",
    "Federal Reserve cuts interest rates, boosting tech stocks globally.",
    "{symbol} faces a massive antitrust lawsuit in the European Union.",
]

# Tools the ReAct agent may call. Note: the sandbox trades ONE symbol, so orders
# don't take a symbol — just side/quantity (and price for limits).
TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "get_account",
            "description": (
                "Get the live account: signed position (negative = short), quote "
                "balance, average entry price, realized and unrealized PnL, equity, "
                "fees paid, and the current mark (mid) price."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_orderbook",
            "description": (
                "Get the top of the live limit order book: best bid, best ask, mid "
                "and spread, plus aggregated depth. Large market orders eat depth "
                "and move the price."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "depth": {
                        "type": "integer",
                        "description": "How many price levels per side (1-10).",
                        "minimum": 1,
                        "maximum": 10,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_trades",
            "description": "Get the most recent trades on the tape (price, qty, taker side).",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "How many recent trades to return (1-50).",
                        "minimum": 1,
                        "maximum": 50,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "place_market_order",
            "description": (
                "Send a MARKET order that executes immediately against the book. "
                "Buying pushes the price up, selling pushes it down. You may go long "
                "or short. Rejected orders (e.g. risk cap) come back with a reason."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "side": {"type": "string", "enum": ["buy", "sell"]},
                    "quantity": {"type": "integer", "minimum": 1, "description": "Shares"},
                },
                "required": ["side", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "place_limit_order",
            "description": (
                "Rest a LIMIT order in the book at your price. A buy below the ask "
                "(or sell above the bid) waits in the queue until the market reaches it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "side": {"type": "string", "enum": ["buy", "sell"]},
                    "quantity": {"type": "integer", "minimum": 1, "description": "Shares"},
                    "price": {"type": "number", "description": "Limit price"},
                },
                "required": ["side", "quantity", "price"],
            },
        },
    },
]


class SandboxAIBot:
    def __init__(self, preset: str, symbol: str):
        self.preset = preset
        self.symbol = symbol
        self.api_client = MockMarketAsyncClient(api_key=API_KEY, base_url=BASE_URL)
        self.ollama_client = AsyncClient(host=OLLAMA_HOST)
        self.sb = None  # mockmarket.Sandbox handle

    async def init_sandbox(self):
        print(f"🏗️ [{self.symbol}] Создание challenge-песочницы (пресет {self.preset})...")
        # A challenge preset pins the whole market (symbol + seed + config) server-side:
        # the run is reproducible, auto-expires on the preset's max_duration_s, and is
        # then finalised onto the public leaderboard. No client config override — the
        # preset is authoritative.
        self.sb = await self.api_client.create_sandbox(
            SandboxCreate(
                name=f"AI-{MODEL_NAME}-{self.symbol}",
                symbol=self.symbol,
                challenge_preset=self.preset,
                agent_name=f"AI-{MODEL_NAME}",
            )
        )
        await self.sb.start()
        book = await self.sb.orderbook(depth=1)
        print(f"✅ [{self.symbol}] Песочница {self.sb.id} запущена | mid={book.mid}")

    async def _dispatch_tool(self, name: str, args: dict) -> str:
        try:
            match name:
                case "get_account":
                    a = await self.sb.account()
                    print(
                        f"📊 Счёт: позиция={a.position} equity={a.equity} "
                        f"realized={a.realized_pnl} unrealized={a.unrealized_pnl}"
                    )
                    return json.dumps({
                        "position": str(a.position),
                        "quote_balance": str(a.quote_balance),
                        "avg_entry_price": str(a.avg_entry_price),
                        "realized_pnl": str(a.realized_pnl),
                        "unrealized_pnl": str(a.unrealized_pnl),
                        "equity": str(a.equity),
                        "fees_paid": str(a.fees_paid),
                        "mid": str(a.mid),
                        "hint": (
                            "position is signed: >0 long, <0 short, 0 flat. "
                            "You may buy (increase/cover) or sell (reduce/short)."
                        ),
                    })

                case "get_orderbook":
                    depth = int(args.get("depth", 5))
                    book = await self.sb.orderbook(depth=depth)
                    print(f"📈 Стакан: bid={book.best_bid} ask={book.best_ask} mid={book.mid}")
                    return json.dumps({
                        "best_bid": str(book.best_bid) if book.best_bid is not None else None,
                        "best_ask": str(book.best_ask) if book.best_ask is not None else None,
                        "mid": str(book.mid) if book.mid is not None else None,
                        "spread": str(book.spread) if book.spread is not None else None,
                        "bids": [{"price": str(l.price), "size": str(l.size)} for l in book.bids],
                        "asks": [{"price": str(l.price), "size": str(l.size)} for l in book.asks],
                    })

                case "get_recent_trades":
                    limit = int(args.get("limit", 10))
                    trades = await self.sb.trades(limit=limit)
                    print(f"🧾 Лента: {len(trades)} сделок")
                    return json.dumps({
                        "trades": [
                            {"price": str(t.price), "qty": str(t.qty), "taker_side": t.taker_side}
                            for t in trades
                        ]
                    })

                case "place_market_order":
                    side = args["side"]
                    qty = int(args["quantity"])
                    order = await self.sb.submit_order(side, qty, type="market")
                    return self._order_result(side, qty, order, kind="MARKET")

                case "place_limit_order":
                    side = args["side"]
                    qty = int(args["quantity"])
                    price = float(args["price"])
                    order = await self.sb.submit_order(side, qty, type="limit", price=price)
                    return self._order_result(side, qty, order, kind=f"LIMIT @ {price}")

                case _:
                    return json.dumps({"error": f"Unknown tool: {name}"})
        except MockMarketAPIError as exc:
            print(f"⚠️ Ошибка API в {name}: {exc}")
            return json.dumps({"error": str(exc)})

    def _order_result(self, side: str, qty: int, order, kind: str) -> str:
        if order.is_rejected:
            print(f"⛔ ОРДЕР {side.upper()} {qty} ({kind}) отклонён: {order.reject_reason}")
            return json.dumps({"status": "rejected", "reason": order.reject_reason})
        print(
            f"🚀 ОРДЕР {side.upper()} {qty} ({kind}) — {order.status}, "
            f"исполнено {order.filled_qty} @ {order.avg_fill_price}"
        )
        return json.dumps({
            "status": order.status,
            "filled_qty": str(order.filled_qty),
            "avg_fill_price": str(order.avg_fill_price) if order.avg_fill_price is not None else None,
        })

    async def agent_loop(self):
        await self.init_sandbox()
        print(f"🧠 Запуск агента {MODEL_NAME} (ReAct) для {self.symbol}\n")

        system_prompt = (
            "You are an elite AI trading bot on a reactive exchange simulator.\n"
            f"You trade a single symbol: {self.symbol}.\n\n"
            "This is NOT paper trading: your orders hit a live limit order book with "
            "background liquidity. A market BUY lifts the price, a market SELL drops "
            "it, and large orders slip through several levels. You can go long "
            "(positive position) or short (negative position).\n\n"
            "Your workflow MUST be:\n"
            "1. Gather context: call get_account and get_orderbook (and optionally "
            "get_recent_trades).\n"
            "2. Analyze the news together with the live data.\n"
            "3. Decide: place_market_order / place_limit_order, or explain a HOLD.\n\n"
            "Rules:\n"
            "- Keep order sizes modest (1-20 shares) to manage market impact and risk.\n"
            "- Check get_account before trading; equity and PnL tell you how you're doing.\n"
            "- A rejected order returns a reason (e.g. risk cap) — respect it.\n"
            "- Make your final decision (BUY/SELL/HOLD) within 3-4 tool calls."
        )

        while True:
            try:
                news = random.choice(NEWS_POOL).format(symbol=self.symbol)
                print("\n" + "=" * 60)
                print(f"📰 [{self.symbol}] Сигнал: {news}")
                print("=" * 60)

                messages = [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Latest news for {self.symbol}: '{news}'\n\n"
                            f"Analyze the situation using your tools and decide: "
                            f"buy, sell, or hold. Provide a short reason."
                        ),
                    },
                ]

                step = 0
                while True:
                    step += 1
                    if step > 4:
                        print("🔴 Превышен лимит шагов ReAct. Принудительно HOLD.")
                        break

                    resp = await self.ollama_client.chat(
                        model=MODEL_NAME,
                        messages=messages,
                        tools=TOOL_DEFS,
                        options={"temperature": 0.1, "num_ctx": NUM_CTX},
                    )

                    msg = resp["message"]

                    if msg.get("content"):
                        print(f"🤔 {MODEL_NAME} думает: {msg['content']}")

                    if msg.get("tool_calls"):
                        # Echo the assistant turn so tool results attach to it.
                        messages.append(msg)
                        for tc in msg["tool_calls"]:
                            name = tc["function"]["name"]
                            args = tc["function"]["arguments"]
                            print(f"🔧 {MODEL_NAME} вызывает: {name}({args})")
                            result_str = await self._dispatch_tool(name, args)
                            messages.append({
                                "role": "tool",
                                "content": result_str,
                                "tool_name": name,
                            })
                    else:
                        content = msg.get("content", "")
                        if content:
                            print(f"🤖 {MODEL_NAME} говорит: {content}")
                        break

            except Exception as e:
                print(f"🔴 Ошибка в цикле бота: {e}")

            await asyncio.sleep(5)

            # A challenge run auto-expires on the preset's max_duration_s; once it is
            # no longer running the engine has finalised it onto the leaderboard, so
            # stop the loop cleanly.
            try:
                await self.sb.refresh()
                if self.sb.info.status != "running":
                    print(f"🏁 [{self.symbol}] Прогон завершён (статус {self.sb.info.status}) → лидерборд.")
                    break
            except MockMarketAPIError:
                pass

    async def close(self):
        if self.sb is not None:
            try:
                await self.sb.stop()
            except MockMarketAPIError:
                pass
        await self.api_client.close()


async def main():
    # Trade a single stock (the first preset) to keep the output focused. To run
    # several stocks concurrently, gather a bot per entry in PRESETS instead.
    preset, symbol = PRESETS[0]
    bot = SandboxAIBot(preset=preset, symbol=symbol)
    try:
        await bot.agent_loop()
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
