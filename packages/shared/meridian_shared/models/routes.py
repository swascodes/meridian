"""Execution intelligence models for Phase 4."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskFactor(BaseModel):
    """Individual risk factor."""
    name: str
    score: float = Field(..., ge=0, le=1)
    weight: float = Field(..., ge=0, le=1)
    detail: str = ""


class ExecutionValidation(BaseModel):
    """Result of pre-execution route validation."""
    valid: bool
    reason: str | None = None
    checked_at: datetime
    liquidity_sufficient: bool
    checks: dict[str, bool] = Field(default_factory=dict)


class ExecutionHopDetail(BaseModel):
    """Per-hop simulation detail."""
    hop_index: int
    hop_type: str  # "pool_swap" | "orderbook_trade"
    input_asset: str
    output_asset: str
    input_amount: float
    output_amount: float
    fee_paid: float
    slippage: float
    pool_id: str | None = None


class ExecutionSimulation(BaseModel):
    """Full execution simulation result."""
    expected_output: float
    total_fee: float
    slippage: float
    price_impact: float
    hop_details: list[ExecutionHopDetail] = Field(default_factory=list)
    simulated_at: datetime


class ExecutionRisk(BaseModel):
    """Risk assessment for a route."""
    risk_score: float = Field(..., ge=0, le=1)
    risk_level: RiskLevel
    factors: list[RiskFactor] = Field(default_factory=list)


class ExecutionStep(BaseModel):
    """Single step in an execution plan."""
    step_index: int
    type: str  # "pool_swap" | "orderbook_trade"
    pool_id: str | None = None
    market: str | None = None
    input_asset: str
    output_asset: str
    expected_input: float
    expected_output: float


class ExecutionPlan(BaseModel):
    """Machine-readable execution plan."""
    route_hash: str
    steps: list[ExecutionStep]
    total_input: float
    expected_total_output: float
    estimated_duration_ms: int = 5000
    generated_at: datetime


class RouteValidateRequest(BaseModel):
    """Request to validate a route."""
    source_asset: "AssetIdentifier"  # noqa: F821
    destination_asset: "AssetIdentifier"  # noqa: F821
    amount: float = Field(..., gt=0)
    max_hops: int = Field(default=4, ge=1, le=6)


class RouteExplainResponse(BaseModel):
    """Detailed explanation of a discovered route."""
    route_hash: str
    validation: ExecutionValidation | None = None
    simulation: ExecutionSimulation | None = None
    risk: ExecutionRisk | None = None
    plan: ExecutionPlan | None = None


class CacheStats(BaseModel):
    """Route cache statistics."""
    entries: int
    hit_rate: float
    evictions: int
    ttl_seconds: int
