"""Pydantic models for API data transfer."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


# ─── Enums ───


class AssetType(str, Enum):
    NATIVE = "native"
    CREDIT_ALPHANUM4 = "credit_alphanum4"
    CREDIT_ALPHANUM12 = "credit_alphanum12"


class RouteStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"


class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SIMULATED = "simulated"


class TradeType(str, Enum):
    ORDERBOOK = "orderbook"
    LIQUIDITY_POOL = "liquidity_pool"


# ─── Asset Models ───


class AssetIdentifier(BaseModel):
    """Lightweight asset reference."""
    code: str = Field(..., max_length=12)
    issuer: str | None = Field(None, max_length=56)

    @property
    def canonical(self) -> str:
        return f"{self.code}:{self.issuer}" if self.issuer else "native"


class AssetDetail(AssetIdentifier):
    """Full asset information."""
    id: UUID
    asset_type: AssetType
    domain: str | None = None
    is_verified: bool = False
    total_trustlines: int = 0
    total_volume_24h: float = 0.0
    first_seen_at: datetime
    last_seen_at: datetime


# ─── Orderbook Models ───


class OrderbookLevel(BaseModel):
    """Single price level in an orderbook."""
    price: float
    amount: float


class OrderbookState(BaseModel):
    """Current orderbook snapshot."""
    base_asset: AssetIdentifier
    counter_asset: AssetIdentifier
    bids: list[OrderbookLevel]
    asks: list[OrderbookLevel]
    bid_depth: float
    ask_depth: float
    spread: float
    mid_price: float
    timestamp: datetime


# ─── Route Models ───


class RouteHop(BaseModel):
    """Single hop in a route."""
    asset: AssetIdentifier
    pool_id: str | None = None
    hop_type: str = "orderbook"  # orderbook | amm


class RouteExplanation(BaseModel):
    """Detailed breakdown explaining route scoring and simulation."""
    base_fee_estimate: float
    liquidity_penalty: float
    hop_penalty: float
    slippage_impact: float
    bottleneck_hop_index: int | None = None
    bottleneck_liquidity: float | None = None


class RouteResult(BaseModel):
    """Optimized route result."""
    route_hash: str
    source_asset: AssetIdentifier
    destination_asset: AssetIdentifier
    path: list[RouteHop]
    hop_count: int
    expected_output: float
    estimated_rate: float
    estimated_slippage: float
    estimated_fee: float
    total_liquidity: float
    quality_score: float | None = None
    confidence_score: float | None = None
    explanation: RouteExplanation | None = None
    discovered_at: datetime
    metadata: dict | None = None


class RouteDiscoverRequest(BaseModel):
    """Request to discover optimal routes between assets."""
    source_asset: AssetIdentifier
    destination_asset: AssetIdentifier
    amount: float = Field(..., gt=0)
    max_hops: int = Field(default=4, ge=1, le=6)
    max_routes: int = Field(default=5, ge=1, le=20)


class RouteDiscoverResponse(BaseModel):
    """Response containing Top-K discovered routes."""
    routes: list[RouteResult]
    latency_ms: int
    cache_hit: bool
    evaluated_paths_count: int


class RouteExecutionTelemetry(BaseModel):
    """Telemetry data for executed routes to optimize future pathfinding."""
    route_hash: str
    executed_at: datetime
    input_amount: float
    expected_output: float
    actual_output: float
    slippage_realized: float
    execution_latency_ms: int
    success: bool
    error_reason: str | None = None


class RouteSimulationRequest(BaseModel):
    """Request to simulate a route execution."""
    source_asset: AssetIdentifier
    destination_asset: AssetIdentifier
    amount: float = Field(..., gt=0)
    max_hops: int = Field(default=4, ge=1, le=6)
    slippage_tolerance: float = Field(default=0.01, ge=0, le=0.5)


class RouteSimulationResult(BaseModel):
    """Simulated execution result."""
    route: RouteResult
    input_amount: float
    expected_output: float
    estimated_slippage: float
    price_impact: float
    execution_probability: float
    warnings: list[str] = Field(default_factory=list)


# ─── Quality Models ───


class QualityBreakdown(BaseModel):
    """Detailed quality score breakdown."""
    liquidity_score: float = Field(..., ge=0, le=1)
    reliability_score: float = Field(..., ge=0, le=1)
    speed_score: float = Field(..., ge=0, le=1)
    cost_score: float = Field(..., ge=0, le=1)
    slippage_score: float = Field(..., ge=0, le=1)


class RouteQuality(BaseModel):
    """Route quality assessment."""
    route_hash: str
    composite_score: float = Field(..., ge=0, le=1)
    breakdown: QualityBreakdown
    sample_size: int
    confidence: float = Field(..., ge=0, le=1)
    scored_at: datetime


# ─── Graph Models ───


class GraphStats(BaseModel):
    """Graph topology statistics."""
    total_nodes: int
    total_edges: int
    total_assets: int
    total_pools: int
    avg_degree: float
    density: float
    connected_components: int
    last_updated_at: datetime


# ─── Liquidity Models ───


class LiquidityProfile(BaseModel):
    """Asset liquidity profile."""
    asset: AssetIdentifier
    total_orderbook_depth: float
    total_pool_reserves: float
    num_trading_pairs: int
    num_pools: int
    avg_spread: float
    volume_24h: float


# ─── Registry Models ───


class RegistryPublishRequest(BaseModel):
    """Request to publish a route to Soroban."""
    route_hash: str
    source_asset: AssetIdentifier
    destination_asset: AssetIdentifier
    quality_score: float = Field(..., ge=0, le=1)


class RegistryEntry(BaseModel):
    """On-chain registry entry."""
    route_hash: str
    contract_id: str
    soroban_tx_hash: str
    quality_score: float
    registered_at: datetime
    last_updated_at: datetime
    is_active: bool


# ─── Health Models ───


class ServiceHealth(BaseModel):
    """Service health response."""
    service: str
    status: str
    version: str = "0.1.0"
    timestamp: datetime
    dependencies: dict[str, str] = Field(default_factory=dict)
