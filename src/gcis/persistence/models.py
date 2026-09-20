from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, Integer, Numeric, DateTime, Boolean, Text, JSON, UniqueConstraint, Index, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from gcis.persistence.db import Base
import uuid

def utcnow():
    return datetime.now(timezone.utc)

class Candle(Base):
    __tablename__ = "candles"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol: Mapped[str] = mapped_column(String, index=True)
    timeframe: Mapped[str] = mapped_column(String, index=True)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    open: Mapped[Decimal] = mapped_column(Numeric(38,18))
    high: Mapped[Decimal] = mapped_column(Numeric(38,18))
    low: Mapped[Decimal] = mapped_column(Numeric(38,18))
    close: Mapped[Decimal] = mapped_column(Numeric(38,18))
    volume: Mapped[Decimal] = mapped_column(Numeric(38,18))
    quote_volume: Mapped[Decimal] = mapped_column(Numeric(38,18), nullable=True)
    trade_count: Mapped[int] = mapped_column(Integer, nullable=True)
    taker_buy_volume: Mapped[Decimal] = mapped_column(Numeric(38,18), nullable=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String, default="binance")
    ingestion_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("symbol","timeframe","open_time", name="uq_candle_symbol_tf_open"), Index("ix_candle_symbol_tf_close","symbol","timeframe","close_time"))

class LatestQuote(Base):
    __tablename__ = "latest_quotes"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    price: Mapped[Decimal] = mapped_column(Numeric(38,18))
    bid: Mapped[Decimal] = mapped_column(Numeric(38,18), nullable=True)
    ask: Mapped[Decimal] = mapped_column(Numeric(38,18), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source: Mapped[str] = mapped_column(String, default="binance")

class UniverseRegistry(Base):
    __tablename__ = "universe_registry"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    base: Mapped[str] = mapped_column(String)
    quote: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    tick_size: Mapped[Decimal] = mapped_column(Numeric(38,18), nullable=True)
    step_size: Mapped[Decimal] = mapped_column(Numeric(38,18), nullable=True)
    min_notional: Mapped[Decimal] = mapped_column(Numeric(38,18), nullable=True)
    market_type: Mapped[str] = mapped_column(String, default="SPOT")
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class ProviderStatus(Base):
    __tablename__ = "provider_status"
    provider: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, default="UNKNOWN")
    last_success: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    throttled_requests: Mapped[int] = mapped_column(Integer, default=0)
    data_age_s: Mapped[int] = mapped_column(Integer, nullable=True)

class SystemHealth(Base):
    __tablename__ = "system_health"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    verdict: Mapped[str] = mapped_column(String)  # HEALTHY DEGRADED UNHEALTHY
    details: Mapped[dict] = mapped_column(JSON, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class WorkerState(Base):
    __tablename__ = "worker_state"
    process: Mapped[str] = mapped_column(String, primary_key=True)
    pid: Mapped[int] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[str] = mapped_column(String, default="UNKNOWN")
    last_error: Mapped[str] = mapped_column(Text, nullable=True)
    queue_depth: Mapped[int] = mapped_column(Integer, nullable=True)
    lag_ms: Mapped[int] = mapped_column(Integer, nullable=True)

class EventOutbox(Base):
    __tablename__ = "event_outbox"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str] = mapped_column(String, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)

class ConsumerCursor(Base):
    __tablename__ = "consumer_cursors"
    consumer: Mapped[str] = mapped_column(String, primary_key=True)
    last_event_id: Mapped[int] = mapped_column(Integer, default=0)

class Command(Base):
    __tablename__ = "commands"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String, unique=True)
    type: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class CommandResult(Base):
    __tablename__ = "command_results"
    command_id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String)
    result: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Signal(Base):
    __tablename__ = "signals"
    signal_id: Mapped[str] = mapped_column(String, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    market_type: Mapped[str] = mapped_column(String, default="SPOT")
    exchange: Mapped[str] = mapped_column(String, default="binance")
    direction: Mapped[str] = mapped_column(String)
    primary_timeframe: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[str] = mapped_column(String, default="DISCOVERED")
    setup_score: Mapped[int] = mapped_column(Integer, nullable=True)
    setup_quality: Mapped[str] = mapped_column(String, nullable=True)
    probability: Mapped[Decimal] = mapped_column(Numeric(38,18), nullable=True)
    probability_status: Mapped[str] = mapped_column(String, nullable=True)
    expected_r: Mapped[Decimal] = mapped_column(Numeric(38,18), nullable=True)
    entry: Mapped[Decimal] = mapped_column(Numeric(38,18), nullable=True)
    stop: Mapped[Decimal] = mapped_column(Numeric(38,18), nullable=True)
    target_1: Mapped[Decimal] = mapped_column(Numeric(38,18), nullable=True)
    target_2: Mapped[Decimal] = mapped_column(Numeric(38,18), nullable=True)
    regime: Mapped[str] = mapped_column(String, nullable=True)
    session: Mapped[str] = mapped_column(String, nullable=True)
    strategy: Mapped[str] = mapped_column(String)
    evidence_hash: Mapped[str] = mapped_column(String, nullable=True)
    analysis_version: Mapped[str] = mapped_column(String, nullable=True)
    config_version: Mapped[str] = mapped_column(String, nullable=True)

class SignalEvent(Base):
    __tablename__ = "signal_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[str] = mapped_column(String, index=True)
    previous_state: Mapped[str] = mapped_column(String, nullable=True)
    new_state: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class SignalOutcome(Base):
    __tablename__ = "signal_outcomes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[str] = mapped_column(String, index=True, unique=True)
    symbol: Mapped[str] = mapped_column(String)
    outcome: Mapped[str] = mapped_column(String)  # WIN LOSS TIMEOUT INVALIDATED NO_FILL AMBIGUOUS
    net_r: Mapped[Decimal] = mapped_column(Numeric(38,18), nullable=True)
    would_be_blocked_by_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class DailyRiskState(Base):
    __tablename__ = "daily_risk_state"
    risk_day: Mapped[str] = mapped_column(String, primary_key=True)  # YYYY-MM-DD
    starting_equity: Mapped[Decimal] = mapped_column(Numeric(38,18))
    current_equity: Mapped[Decimal] = mapped_column(Numeric(38,18))
    daily_loss: Mapped[Decimal] = mapped_column(Numeric(38,18), default=0)
    daily_realized_pnl: Mapped[Decimal] = mapped_column(Numeric(38,18), default=0)
    trades_today: Mapped[int] = mapped_column(Integer, default=0)
    risk_lock: Mapped[str] = mapped_column(String, default="ACTIVE")  # ACTIVE BLOCK_NEW_TRADES
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class RiskEvent(Base):
    __tablename__ = "risk_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String)
    details: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class KillSwitchState(Base):
    __tablename__ = "kill_switch_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    mode: Mapped[str] = mapped_column(String, default="BLOCK_NEW_TRADES")
    reason: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class PaperAccount(Base):
    __tablename__ = "paper_accounts"
    id: Mapped[str] = mapped_column(String, primary_key=True, default="paper_main")
    equity: Mapped[Decimal] = mapped_column(Numeric(38,18), default=10000)
    cash: Mapped[Decimal] = mapped_column(Numeric(38,18), default=10000)
    peak_equity: Mapped[Decimal] = mapped_column(Numeric(38,18), default=10000)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(38,18), default=0)
    fees_paid: Mapped[Decimal] = mapped_column(Numeric(38,18), default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class ExecutionIntent(Base):
    __tablename__ = "execution_intents"
    intent_id: Mapped[str] = mapped_column(String, primary_key=True)
    signal_id: Mapped[str] = mapped_column(String)
    symbol: Mapped[str] = mapped_column(String)
    direction: Mapped[str] = mapped_column(String)
    quantity: Mapped[Decimal] = mapped_column(Numeric(38,18))
    entry: Mapped[Decimal] = mapped_column(Numeric(38,18))
    stop: Mapped[Decimal] = mapped_column(Numeric(38,18))
    status: Mapped[str] = mapped_column(String, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Position(Base):
    __tablename__ = "positions"
    position_id: Mapped[str] = mapped_column(String, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    direction: Mapped[str] = mapped_column(String)
    quantity: Mapped[Decimal] = mapped_column(Numeric(38,18))
    entry_price: Mapped[Decimal] = mapped_column(Numeric(38,18))
    current_price: Mapped[Decimal] = mapped_column(Numeric(38,18), nullable=True)
    stop_loss: Mapped[Decimal] = mapped_column(Numeric(38,18), nullable=True)
    take_profit_1: Mapped[Decimal] = mapped_column(Numeric(38,18), nullable=True)
    take_profit_2: Mapped[Decimal] = mapped_column(Numeric(38,18), nullable=True)
    state: Mapped[str] = mapped_column(String, default="OPEN")
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(38,18), default=0)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(38,18), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

class SystemMetrics(Base):
    __tablename__ = "system_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric: Mapped[str] = mapped_column(String, index=True)
    value: Mapped[int] = mapped_column(Integer, default=0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class ConfigVersion(Base):
    __tablename__ = "config_versions"
    hash: Mapped[str] = mapped_column(String, primary_key=True)
    config: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class ScanJob(Base):
    __tablename__ = "scan_jobs"
    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, default="PENDING")
    checkpoint: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
