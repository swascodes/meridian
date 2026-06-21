"""Route quality scorer — computes composite quality scores."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, func

from meridian_shared.db import Route, RouteExecution, RouteQualityScore, get_session
from meridian_shared.models import QualityBreakdown, RouteQuality
from meridian_shared.redis import RedisKeys, get_redis

logger = structlog.get_logger()


class RouteScorer:
    """Scores routes based on historical execution data."""

    # Score component weights
    WEIGHTS = {
        "liquidity": 0.25,
        "reliability": 0.25,
        "speed": 0.15,
        "cost": 0.20,
        "slippage": 0.15,
    }

    async def score_route(self, route_hash: str) -> RouteQuality | None:
        """Compute quality score for a route."""
        async with get_session() as session:
            # Get route
            stmt = select(Route).where(Route.route_hash == route_hash)
            result = await session.execute(stmt)
            route = result.scalar_one_or_none()

            if not route:
                return None

            # Get recent executions (last 7 days)
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            exec_stmt = (
                select(RouteExecution)
                .where(
                    RouteExecution.route_id == route.id,
                    RouteExecution.executed_at >= cutoff,
                )
                .order_by(RouteExecution.executed_at.desc())
            )
            exec_result = await session.execute(exec_stmt)
            executions = exec_result.scalars().all()

            # Compute scores
            breakdown = self._compute_breakdown(route, executions)
            composite = self._compute_composite(breakdown)
            confidence = self._compute_confidence(len(executions))

            quality = RouteQuality(
                route_hash=route_hash,
                composite_score=composite,
                breakdown=breakdown,
                sample_size=len(executions),
                confidence=confidence,
                scored_at=datetime.now(timezone.utc),
            )

            # Persist score
            score_record = RouteQualityScore(
                route_id=route.id,
                composite_score=composite,
                liquidity_score=breakdown.liquidity_score,
                reliability_score=breakdown.reliability_score,
                speed_score=breakdown.speed_score,
                cost_score=breakdown.cost_score,
                slippage_score=breakdown.slippage_score,
                sample_size=len(executions),
                confidence=confidence,
            )
            session.add(score_record)

            # Cache in Redis
            redis = get_redis()
            cache_key = RedisKeys.route_quality(route_hash)
            await redis.set(cache_key, str(composite), ex=300)

            return quality

    def _compute_breakdown(self, route: Route, executions: list[RouteExecution]) -> QualityBreakdown:
        """Compute individual score components."""
        if not executions:
            # No execution data — score based on route properties
            return QualityBreakdown(
                liquidity_score=min(1.0, (route.total_liquidity or 0) / 100000),
                reliability_score=0.5,
                speed_score=max(0, 1.0 - route.hop_count * 0.15),
                cost_score=max(0, 1.0 - (route.estimated_slippage or 0.05)),
                slippage_score=max(0, 1.0 - (route.estimated_slippage or 0.05) * 10),
            )

        # Reliability: success rate
        success_count = sum(1 for e in executions if e.status == "success")
        reliability = success_count / len(executions)

        # Speed: average execution time (lower is better, normalized to 0-1)
        exec_times = [e.execution_time_ms for e in executions if e.execution_time_ms is not None]
        if exec_times:
            avg_time = sum(exec_times) / len(exec_times)
            speed = max(0, 1.0 - avg_time / 10000)  # 10s = score 0
        else:
            speed = 0.5

        # Slippage: average actual vs expected
        slippages = [e.slippage for e in executions if e.slippage is not None]
        if slippages:
            avg_slippage = sum(slippages) / len(slippages)
            slippage_score = max(0, 1.0 - avg_slippage * 20)  # 5% slippage = score 0
        else:
            slippage_score = 0.5

        # Cost: average deviation from expected output
        cost_scores = []
        for e in executions:
            if e.actual_output and e.expected_output and e.expected_output > 0:
                ratio = float(e.actual_output) / float(e.expected_output)
                cost_scores.append(min(1.0, ratio))
        cost = sum(cost_scores) / len(cost_scores) if cost_scores else 0.5

        # Liquidity
        liquidity = min(1.0, (route.total_liquidity or 0) / 100000)

        return QualityBreakdown(
            liquidity_score=liquidity,
            reliability_score=reliability,
            speed_score=speed,
            cost_score=cost,
            slippage_score=slippage_score,
        )

    def _compute_composite(self, breakdown: QualityBreakdown) -> float:
        """Weighted composite score."""
        return (
            self.WEIGHTS["liquidity"] * breakdown.liquidity_score
            + self.WEIGHTS["reliability"] * breakdown.reliability_score
            + self.WEIGHTS["speed"] * breakdown.speed_score
            + self.WEIGHTS["cost"] * breakdown.cost_score
            + self.WEIGHTS["slippage"] * breakdown.slippage_score
        )

    def _compute_confidence(self, sample_size: int) -> float:
        """Confidence based on sample size. Approaches 1.0 asymptotically."""
        if sample_size == 0:
            return 0.1
        return min(1.0, sample_size / 100)
