from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SandboxCreate(BaseModel):
    name: str = Field(max_length=100, min_length=1)
    fee_structure: str
    base_slippage_pct: float = Field(ge=0.0, le=100.0)
    latency_ms: int = Field(ge=0, le=10000)
    commission_fee_pct: float = Field(default=0.0, ge=0.0, le=100.0)


class SandboxUpdate(BaseModel):
    latency_ms: int | None = Field(default=None, ge=0, le=10000)
    base_slippage_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    commission_fee_pct: float | None = Field(default=None, ge=0.0, le=100.0)


class SandboxResponse(BaseModel):
    id: UUID
    name: str
    exchange_type: str
    fee_structure: str
    budget: float
    base_slippage_pct: float
    latency_ms: int
    commission_fee_pct: float
    status: str
    created_at: datetime


class OrderCreate(BaseModel):
    sandbox_id: UUID
    symbol: str = Field(max_length=20, min_length=1)
    side: str = Field(pattern=r"^(buy|sell)$")
    order_type: str = Field(pattern=r"^(market|limit)$")
    quantity: float
    price: float | None = None


class OrderResponse(BaseModel):
    id: UUID
    sandbox_id: UUID
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: float | None = None
    filled_price: float | None = None
    status: str
    slippage_applied: float | None = None
    latency_ms: int
    reject_reason: str | None = None
    created_at: datetime
    filled_at: datetime | None = None


class PositionResponse(BaseModel):
    id: UUID
    sandbox_id: UUID
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    created_at: datetime
    updated_at: datetime


class BalanceResponse(BaseModel):
    id: UUID
    sandbox_id: UUID
    balance: float
    maintenance_margin: float
    created_at: datetime
    updated_at: datetime


class LiquidationResponse(BaseModel):
    sandbox_id: UUID
    symbol: str
    liquidation_price: float
    reason: str


class TradeHistoryItem(BaseModel):
    id: UUID
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: float | None = None
    filled_price: float | None = None
    slippage_applied: float | None = None
    status: str
    created_at: datetime
    filled_at: datetime | None = None


class PnLSummary(BaseModel):
    sandbox_id: UUID
    total_pnl: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_buy_volume: float
    total_sell_volume: float


class PerformanceMetrics(BaseModel):
    sandbox_id: UUID
    sharpe_ratio: float
    max_drawdown: float
    total_return_pct: float


class Tick(BaseModel):
    timestamp: datetime
    price: float
    volume: float
    symbol: str


class Candle(BaseModel):
    timestamp: datetime = Field(alias="open_time")
    open: float
    high: float
    low: float
    close: float
    volume: float
    model_config = {"populate_by_name": True}


class StockQuote(BaseModel):
    symbol: str
    price: float = Field(alias="current_price")
    change: float
    change_pct: float = Field(alias="percent_change")
    volume: float = 0
    model_config = {"populate_by_name": True}


class StockSearchResult(BaseModel):
    symbol: str
    name: str
    exchange: str | None = None


class StockProfile(BaseModel):
    symbol: str
    name: str
    sector: str | None = None
    industry: str | None = None
    market_cap: float | None = None


class StockHistoryItem(BaseModel):
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


# ---------------------------------------------------------------------------
# Reactive engine (/v1) — a live limit order book with background liquidity.
# Prices/quantities are Decimal so the SDK inherits the engine's exact
# arithmetic; they cross the wire as strings (``model_dump(mode="json")``).
# ---------------------------------------------------------------------------


class EngineReferenceConfig(BaseModel):
    type: Literal["stochastic", "replay", "external_feed"] = "stochastic"
    model: Literal["gbm", "ou"] = "gbm"
    initial_price: Decimal = Decimal("100")
    volatility: Decimal = Decimal("0.3")
    drift: Decimal = Decimal("0.0")
    mean: Decimal | None = None
    kappa: Decimal = Decimal("1.0")
    replay_prices: list[Decimal] = Field(default_factory=list)


class EngineMarketMakerConfig(BaseModel):
    depth_levels: int = Field(default=10, ge=1, le=100)
    base_spread: Decimal = Decimal("0.10")
    size_per_level: Decimal = Decimal("50")
    replenish_rate: Decimal = Decimal("0.25")
    reprice_threshold: Decimal = Decimal("0.20")


class EngineNoiseConfig(BaseModel):
    intensity: Decimal = Decimal("2.0")
    max_size: Decimal = Decimal("10")
    limit_ratio: Decimal = Field(default=Decimal("0.5"), ge=0, le=1)


class EngineSandboxConfig(BaseModel):
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
    reference: EngineReferenceConfig = Field(default_factory=EngineReferenceConfig)
    market_maker: EngineMarketMakerConfig = Field(default_factory=EngineMarketMakerConfig)
    noise: EngineNoiseConfig = Field(default_factory=EngineNoiseConfig)


class EngineSandboxCreate(BaseModel):
    name: str = Field(default="sandbox", max_length=100)
    symbol: str = Field(default="AAPL", max_length=20)
    seed: int | None = None
    challenge_preset: str | None = Field(default=None, max_length=50)
    agent_name: str | None = Field(default=None, max_length=100)
    config: EngineSandboxConfig | None = None


class EngineSandbox(BaseModel):
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


class EngineOrderCreate(BaseModel):
    side: Literal["buy", "sell"]
    type: Literal["market", "limit"] = "market"
    qty: Decimal = Field(gt=0)
    price: Decimal | None = None
    client_order_id: str | None = Field(default=None, max_length=64)


class EngineOrder(BaseModel):
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


class EngineAccount(BaseModel):
    quote_balance: Decimal
    position: Decimal
    avg_entry_price: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    equity: Decimal
    fees_paid: Decimal
    mid: Decimal


class EngineTrade(BaseModel):
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


class EngineApiKey(BaseModel):
    id: str
    name: str
    key_prefix: str
    api_key: str  # full secret — returned only once


class StreamMessage(BaseModel):
    """A single WebSocket event (status/orderbook/trade/fill/account/order)."""

    type: str
    data: dict[str, Any]
