"""SQLAlchemy ORM models for Meridian."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Asset(Base):
    """Stellar asset registry."""

    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(12), nullable=False)
    issuer: Mapped[str | None] = mapped_column(String(56), nullable=True)  # None = XLM native
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)  # native, credit_alphanum4, credit_alphanum12
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    total_trustlines: Mapped[int] = mapped_column(BigInteger, default=0)
    total_volume_24h: Mapped[float] = mapped_column(Float, default=0.0)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint("code", "issuer", name="uq_asset_code_issuer"),
        Index("ix_asset_code", "code"),
        Index("ix_asset_volume", "total_volume_24h"),
    )


class LiquidityPool(Base):
    """Stellar AMM liquidity pool state."""

    __tablename__ = "liquidity_pools"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pool_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    asset_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    asset_b_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    reserve_a: Mapped[float] = mapped_column(Numeric(20, 7), nullable=False)
    reserve_b: Mapped[float] = mapped_column(Numeric(20, 7), nullable=False)
    total_shares: Mapped[float] = mapped_column(Numeric(20, 7), nullable=False)
    fee_bp: Mapped[int] = mapped_column(Integer, default=30)  # basis points
    total_trustlines: Mapped[int] = mapped_column(BigInteger, default=0)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    asset_a: Mapped[Asset] = relationship("Asset", foreign_keys=[asset_a_id], lazy="joined")
    asset_b: Mapped[Asset] = relationship("Asset", foreign_keys=[asset_b_id], lazy="joined")

    __table_args__ = (
        Index("ix_pool_assets", "asset_a_id", "asset_b_id"),
    )


class OrderbookSnapshot(Base):
    """Current orderbook state. TimescaleDB hypertable."""

    __tablename__ = "orderbook_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    base_asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    counter_asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    bids: Mapped[dict] = mapped_column(JSONB, nullable=False)  # [{price, amount}]
    asks: Mapped[dict] = mapped_column(JSONB, nullable=False)  # [{price, amount}]
    bid_depth: Mapped[float] = mapped_column(Numeric(20, 7), nullable=False)
    ask_depth: Mapped[float] = mapped_column(Numeric(20, 7), nullable=False)
    spread: Mapped[float] = mapped_column(Float, nullable=False)
    mid_price: Mapped[float] = mapped_column(Float, nullable=False)

    base_asset: Mapped[Asset] = relationship("Asset", foreign_keys=[base_asset_id], lazy="joined")
    counter_asset: Mapped[Asset] = relationship("Asset", foreign_keys=[counter_asset_id], lazy="joined")

    __table_args__ = (
        Index("ix_orderbook_pair_time", "base_asset_id", "counter_asset_id", "timestamp"),
    )


class Trade(Base):
    """Executed trades on Stellar. TimescaleDB hypertable."""

    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stellar_trade_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    base_asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    counter_asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    base_amount: Mapped[float] = mapped_column(Numeric(20, 7), nullable=False)
    counter_amount: Mapped[float] = mapped_column(Numeric(20, 7), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    base_is_seller: Mapped[bool] = mapped_column(Boolean, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ledger_close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trade_type: Mapped[str] = mapped_column(String(20), nullable=False)  # orderbook, liquidity_pool
    liquidity_pool_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    base_asset: Mapped[Asset] = relationship("Asset", foreign_keys=[base_asset_id], lazy="joined")
    counter_asset: Mapped[Asset] = relationship("Asset", foreign_keys=[counter_asset_id], lazy="joined")

    __table_args__ = (
        Index("ix_trade_pair_time", "base_asset_id", "counter_asset_id", "timestamp"),
        Index("ix_trade_time", "timestamp"),
    )


class Route(Base):
    """Discovered routes with metadata."""

    __tablename__ = "routes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source_asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    destination_asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    path: Mapped[dict] = mapped_column(JSONB, nullable=False)  # [{asset_id, code, issuer}]
    hop_count: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_rate: Mapped[float] = mapped_column(Float, nullable=True)
    estimated_slippage: Mapped[float] = mapped_column(Float, nullable=True)
    total_liquidity: Mapped[float] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_validated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    source_asset: Mapped[Asset] = relationship("Asset", foreign_keys=[source_asset_id], lazy="joined")
    destination_asset: Mapped[Asset] = relationship("Asset", foreign_keys=[destination_asset_id], lazy="joined")

    __table_args__ = (
        Index("ix_route_pair", "source_asset_id", "destination_asset_id"),
        Index("ix_route_active", "is_active"),
    )


class RouteExecution(Base):
    """Route execution outcomes for quality tracking."""

    __tablename__ = "route_executions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("routes.id"), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_amount: Mapped[float] = mapped_column(Numeric(20, 7), nullable=False)
    expected_output: Mapped[float] = mapped_column(Numeric(20, 7), nullable=False)
    actual_output: Mapped[float] = mapped_column(Numeric(20, 7), nullable=True)
    slippage: Mapped[float] = mapped_column(Float, nullable=True)
    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success, failed, timeout
    stellar_tx_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    route: Mapped[Route] = relationship("Route", lazy="joined")

    __table_args__ = (
        Index("ix_execution_route_time", "route_id", "executed_at"),
    )


class RouteQualityScore(Base):
    """Route Quality Oracle scoring results."""

    __tablename__ = "route_quality_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("routes.id"), nullable=False)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    composite_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 - 1.0
    liquidity_score: Mapped[float] = mapped_column(Float, nullable=False)
    reliability_score: Mapped[float] = mapped_column(Float, nullable=False)
    speed_score: Mapped[float] = mapped_column(Float, nullable=False)
    cost_score: Mapped[float] = mapped_column(Float, nullable=False)
    slippage_score: Mapped[float] = mapped_column(Float, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 - 1.0
    breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    route: Mapped[Route] = relationship("Route", lazy="joined")

    __table_args__ = (
        Index("ix_quality_route_time", "route_id", "scored_at"),
    )


class RegisteredRoute(Base):
    """Routes published to Soroban routing registry."""

    __tablename__ = "registered_routes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("routes.id"), nullable=False)
    contract_id: Mapped[str] = mapped_column(String(56), nullable=False)
    soroban_tx_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    on_chain_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    route: Mapped[Route] = relationship("Route", lazy="joined")

    __table_args__ = (
        Index("ix_registered_contract", "contract_id"),
    )


class IngestionCursor(Base):
    """Track streaming cursor positions for resumable ingestion."""

    __tablename__ = "ingestion_cursors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stream_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    cursor_value: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
