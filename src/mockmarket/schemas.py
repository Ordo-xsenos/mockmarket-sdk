"""Pydantic schemas for the MockMarket reactive engine (``/v1``).

Prices/quantities/money are :class:`~decimal.Decimal` so the SDK inherits the
engine's exact arithmetic; they cross the wire as strings via
``model_dump(mode="json")``.
"""

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class ReferenceConfig(BaseModel):
    type: Literal["stochastic", "replay", "external_feed"] = "stochastic"
    model: Literal["gbm", "ou"] = "gbm"
    initial_price: Decimal = Decimal("100")
    volatility: Decimal = Decimal("0.3")
    drift: Decimal = Decimal("0.0")
    mean: Decimal | None = None
    kappa: Decimal = Decimal("1.0")
    replay_prices: list[Decimal] = Field(default_factory=list)


class MarketMakerConfig(BaseModel):
    depth_levels: int = Field(default=10, ge=1, le=100)
    base_spread: Decimal = Decimal("0.10")
    size_per_level: Decimal = Decimal("50")
    replenish_rate: Decimal = Decimal("0.25")
    reprice_threshold: Decimal = Decimal("0.20")


class NoiseConfig(BaseModel):
    intensity: Decimal = Decimal("2.0")
    max_size: Decimal = Decimal("10")
    limit_ratio: Decimal = Field(default=Decimal("0.5"), ge=0, le=1)


class SandboxConfig(BaseModel):
    """Free-form market config (ignored when a ``challenge_preset`` is set)."""

    tick_size: Decimal = Decimal("0.01")
    lot_size: Decimal = Decimal("1")
    initial_balance: Decimal = Decimal("100000")
    max_notional: Decimal | None = Decimal("1000000")
    maker_fee_bps: Decimal = Decimal("1.0")
    taker_fee_bps: Decimal = Decimal("5.0")
    tick_ms: int = Field(default=100, ge=10, le=10000)
    speed: Decimal = Decimal("1.0")
    max_duration_s: int | None = Field(default=3600, ge=1)
    idle_timeout_s: int | None = Field(default=None, ge=1)
    latency_ms: int = Field(default=0, ge=0)
    reject_on_empty: bool = False
    snapshot_every_ticks: int = Field(default=10, ge=1)
    reference: ReferenceConfig = Field(default_factory=ReferenceConfig)
    market_maker: MarketMakerConfig = Field(default_factory=MarketMakerConfig)
    noise: NoiseConfig = Field(default_factory=NoiseConfig)


class SandboxCreate(BaseModel):
    name: str = Field(default="sandbox", max_length=100)
    symbol: str = Field(default="AAPL", max_length=20)
    seed: int | None = None
    challenge_preset: str | None = Field(default=None, max_length=50)
    agent_name: str | None = Field(default=None, max_length=100)
    config: SandboxConfig | None = None


class SandboxInfo(BaseModel):
    """Server view of a sandbox (see :class:`mockmarket.Sandbox` for the stateful
    handle you actually trade with)."""

    id: str
    name: str
    symbol: str
    seed: int
    status: str
    is_challenge: bool
    challenge_preset: str | None = None
    sim_time: float
    tick_ms: int
    speed: Decimal


class OrderCreate(BaseModel):
    side: Literal["buy", "sell"]
    type: Literal["market", "limit"] = "market"
    qty: Decimal = Field(gt=0)
    price: Decimal | None = None
    client_order_id: str | None = Field(default=None, max_length=64)


class Order(BaseModel):
    order_id: str
    side: str
    type: str
    qty: Decimal
    price: Decimal | None = None
    filled_qty: Decimal
    avg_fill_price: Decimal | None = None
    status: str
    reject_reason: str | None = None
    client_order_id: str | None = None

    @property
    def is_rejected(self) -> bool:
        return self.status == "rejected"


class BookLevel(BaseModel):
    price: Decimal
    size: Decimal
    orders: int


class OrderBook(BaseModel):
    bids: list[BookLevel]
    asks: list[BookLevel]
    mid: Decimal | None = None

    @property
    def best_bid(self) -> Decimal | None:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Decimal | None:
        return self.asks[0].price if self.asks else None

    @property
    def spread(self) -> Decimal | None:
        if self.bids and self.asks:
            return self.asks[0].price - self.bids[0].price
        return None


class Account(BaseModel):
    quote_balance: Decimal
    position: Decimal
    avg_entry_price: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    equity: Decimal
    fees_paid: Decimal
    mid: Decimal


class Trade(BaseModel):
    price: Decimal
    qty: Decimal
    taker_side: str
    ts: float
    seq: int


class LeaderboardEntry(BaseModel):
    sandbox_id: str
    agent_name: str
    challenge_preset: str
    return_pct: Decimal
    max_drawdown: Decimal
    sharpe: Decimal
    num_trades: int
    duration_s: Decimal
    final_equity: Decimal


class ApiKey(BaseModel):
    id: str
    name: str
    key_prefix: str
    api_key: str  # full secret — returned only once


class StreamMessage(BaseModel):
    """A single WebSocket event (status/orderbook/trade/fill/account/order)."""

    type: str
    data: dict[str, Any]
