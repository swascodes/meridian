"""Route Validator — pre-execution validation of discovered routes."""

from __future__ import annotations

from datetime import datetime, timezone

import networkx as nx

from meridian_shared.models import ExecutionValidation


class RouteValidator:
    """Validates whether a route can realistically execute."""

    # Configurable thresholds
    MIN_RESERVE_RATIO = 0.05   # Trade must be < 5% of pool reserves
    MAX_SPREAD = 0.50          # 50% max spread
    MAX_STALENESS_S = 2592000  # 30 days (relaxed for local testing)

    @classmethod
    def validate_route(
        cls,
        graph: nx.DiGraph,
        path: list[str],
        amount: float,
    ) -> ExecutionValidation:
        """Validate a path for execution readiness."""
        now = datetime.now(timezone.utc)
        checks: dict[str, bool] = {}
        reasons: list[str] = []
        liquidity_sufficient = True
        
        if not path or len(path) < 2:
            return ExecutionValidation(
                valid=False,
                reason="Invalid path length (< 2 nodes)",
                checked_at=now,
                liquidity_sufficient=False,
                checks={"path_length_valid": False},
            )

        i = 0
        while i < len(path) - 1:
            u = path[i]
            v = path[i + 1]

            if v not in graph or u not in graph:
                checks[f"hop_{i}_nodes_exist"] = False
                reasons.append(f"Hop {i}: node missing from graph")
                i += 1
                continue

            node_v = graph.nodes[v]

            if node_v.get("node_type") == "pool":
                # Pool hop: Asset -> Pool -> Asset
                edge = graph[u][v]
                pool_id = node_v.get("pool_id", "unknown")

                # Pool exists
                checks[f"pool_{pool_id}_exists"] = True

                # Pool active (reserves > 0)
                reserve_in = float(edge.get("reserve_in", 0))
                reserve_out = float(edge.get("reserve_out", 0))
                pool_active = reserve_in > 0 and reserve_out > 0
                checks[f"pool_{pool_id}_active"] = pool_active
                if not pool_active:
                    reasons.append(f"Pool {pool_id}: zero reserves")

                # Reserves sufficient
                if amount > reserve_in * (1.0 / cls.MIN_RESERVE_RATIO):
                    checks[f"pool_{pool_id}_reserves_sufficient"] = False
                    reasons.append(f"Pool {pool_id}: trade too large for reserves ({amount} vs {reserve_in})")
                    liquidity_sufficient = False
                else:
                    checks[f"pool_{pool_id}_reserves_sufficient"] = True

                # Staleness
                ts_str = edge.get("timestamp") or node_v.get("timestamp")
                stale = cls._check_staleness(ts_str, now)
                checks[f"pool_{pool_id}_fresh"] = not stale
                if stale:
                    reasons.append(f"Pool {pool_id}: data stale (>{cls.MAX_STALENESS_S}s)")

                # Skip pool -> asset edge
                i += 2
            else:
                # Orderbook hop
                edge = graph[u][v]

                # Market exists
                checks[f"hop_{i}_market_exists"] = True

                # Depth sufficient
                bid_depth = float(edge.get("bid_depth", 0))
                ask_depth = float(edge.get("ask_depth", 0))
                depth_ok = bid_depth > 0 or ask_depth > 0
                checks[f"hop_{i}_depth_sufficient"] = depth_ok
                if not depth_ok:
                    reasons.append(f"Hop {i}: zero orderbook depth")
                    liquidity_sufficient = False

                if bid_depth > 0 and amount > bid_depth:
                    liquidity_sufficient = False
                    checks[f"hop_{i}_capacity_sufficient"] = False
                    reasons.append(f"Hop {i}: trade exceeds bid depth ({amount} vs {bid_depth})")
                else:
                    checks[f"hop_{i}_capacity_sufficient"] = True

                # Spread tolerance
                spread = float(edge.get("spread", 0))
                spread_ok = spread <= cls.MAX_SPREAD
                checks[f"hop_{i}_spread_ok"] = spread_ok
                if not spread_ok:
                    reasons.append(f"Hop {i}: spread {spread:.2%} exceeds {cls.MAX_SPREAD:.0%}")

                # Staleness
                ts_str = edge.get("timestamp")
                stale = cls._check_staleness(ts_str, now)
                checks[f"hop_{i}_fresh"] = not stale
                if stale:
                    reasons.append(f"Hop {i}: data stale")

                i += 1

        valid = len(reasons) == 0
        return ExecutionValidation(
            valid=valid,
            reason="; ".join(reasons) if reasons else None,
            checked_at=now,
            liquidity_sufficient=liquidity_sufficient,
            checks=checks,
        )

    @classmethod
    def _check_staleness(cls, ts_str: str | None, now: datetime) -> bool:
        if not ts_str:
            return True  # No timestamp = stale
        try:
            ts = datetime.fromisoformat(str(ts_str))
            age = (now - ts).total_seconds()
            return age > cls.MAX_STALENESS_S
        except (ValueError, TypeError):
            return True
