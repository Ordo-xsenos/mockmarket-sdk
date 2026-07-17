from datetime import datetime
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
