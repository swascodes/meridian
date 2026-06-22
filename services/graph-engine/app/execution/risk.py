"""Risk Engine — multi-factor risk assessment for routes."""

from __future__ import annotations

from datetime import datetime, timezone

import networkx as nx

from meridian_shared.models import ExecutionRisk, ExecutionSimulation, RiskFactor, RiskLevel


class RiskEngine:
    """Calculates composite risk score from multiple factors."""

    # Factor weights (sum to 1.0)
    WEIGHTS = {
        "liquidity": 0.30,
        "concentration": 0.20,
        "freshness": 0.20,
        "hop": 0.15,
        "volatility": 0.15,
    }

    @classmethod
    def assess_risk(
        cls,
        graph: nx.DiGraph,
        path: list[str],
        simulation: ExecutionSimulation,
    ) -> ExecutionRisk:
        """Assess execution risk for a path."""
        factors: list[RiskFactor] = []

        # 1. Liquidity Risk — bottleneck reserves vs trade size
        liquidity_score = cls._liquidity_risk(graph, path, simulation)
        factors.append(RiskFactor(
            name="liquidity",
            score=liquidity_score,
            weight=cls.WEIGHTS["liquidity"],
            detail="Risk from insufficient depth or reserves along the path",
        ))

        # 2. Concentration Risk — single pool dominance
        concentration_score = cls._concentration_risk(graph, path)
        factors.append(RiskFactor(
            name="concentration",
            score=concentration_score,
            weight=cls.WEIGHTS["concentration"],
            detail="Risk from reliance on a single liquidity source",
        ))

        # 3. Freshness Risk — data age
        freshness_score = cls._freshness_risk(graph, path)
        factors.append(RiskFactor(
            name="freshness",
            score=freshness_score,
            weight=cls.WEIGHTS["freshness"],
            detail="Risk from stale market data",
        ))

        # 4. Hop Risk — path length
        hop_score = cls._hop_risk(path, graph)
        factors.append(RiskFactor(
            name="hop_count",
            score=hop_score,
            weight=cls.WEIGHTS["hop"],
            detail="Risk increases with more hops (execution failure probability)",
        ))

        # 5. Volatility Risk — stub
        factors.append(RiskFactor(
            name="volatility",
            score=0.0,
            weight=cls.WEIGHTS["volatility"],
            detail="Volatility risk (stub — requires historical price data)",
        ))

        # Composite
        composite = sum(f.score * f.weight for f in factors)
        composite = max(0.0, min(1.0, composite))

        if composite < 0.25:
            level = RiskLevel.LOW
        elif composite < 0.50:
            level = RiskLevel.MEDIUM
        elif composite < 0.75:
            level = RiskLevel.HIGH
        else:
            level = RiskLevel.CRITICAL

        return ExecutionRisk(
            risk_score=round(composite, 4),
            risk_level=level,
            factors=factors,
        )

    @classmethod
    def _liquidity_risk(cls, graph: nx.DiGraph, path: list[str], simulation: ExecutionSimulation) -> float:
        """Lower liquidity = higher risk."""
        if not simulation.hop_details:
            return 0.5

        min_ratio = float("inf")
        for hop in simulation.hop_details:
            if hop.input_amount > 0 and hop.output_amount > 0:
                # Ratio of output to input — lower means more slippage
                ratio = hop.output_amount / hop.input_amount if hop.input_amount > 0 else 0
                if ratio < min_ratio:
                    min_ratio = ratio

        if min_ratio == float("inf"):
            return 0.5

        # Risk is inverse of execution quality
        # If ratio is close to spot, risk is low
        # If slippage ate >20%, risk is high
        total_slippage = sum(h.slippage for h in simulation.hop_details)
        return min(1.0, total_slippage * 2.0)

    @classmethod
    def _concentration_risk(cls, graph: nx.DiGraph, path: list[str]) -> float:
        """Single pool dominance risk."""
        pool_count = 0
        i = 0
        while i < len(path) - 1:
            v = path[i + 1]
            if graph.nodes[v].get("node_type") == "pool":
                pool_count += 1
                i += 2
            else:
                i += 1

        if pool_count <= 1:
            return 0.3  # Single pool = moderate risk (no diversification)
        return max(0.0, 0.5 - pool_count * 0.1)

    @classmethod
    def _freshness_risk(cls, graph: nx.DiGraph, path: list[str]) -> float:
        """Risk from stale data."""
        now = datetime.now(timezone.utc)
        ages: list[float] = []

        for node_id in path:
            node = graph.nodes[node_id]
            ts_str = node.get("timestamp")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(str(ts_str))
                    age = (now - ts).total_seconds()
                    ages.append(max(0, age))
                except (ValueError, TypeError):
                    ages.append(600.0)

        if not ages:
            return 0.5

        avg_age = sum(ages) / len(ages)
        # 0s = 0.0 risk, 600s = 1.0 risk
        return min(1.0, avg_age / 600.0)

    @classmethod
    def _hop_risk(cls, path: list[str], graph: nx.DiGraph) -> float:
        """More hops = higher risk of mid-execution failure."""
        # Count logical hops (pool hops count as 1)
        logical_hops = 0
        i = 0
        while i < len(path) - 1:
            v = path[i + 1]
            if graph.nodes[v].get("node_type") == "pool":
                i += 2
            else:
                i += 1
            logical_hops += 1

        # 1 hop = 0.0 risk, 6 hops = 1.0 risk
        return min(1.0, (logical_hops - 1) * 0.2)
