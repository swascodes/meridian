"""Route Scoring Engine for evaluating risk-adjusted route quality."""

from __future__ import annotations

from datetime import datetime, timezone

import networkx as nx

from meridian_shared.models import RouteExplanation


class RouteScoringEngine:
    """Evaluates and scores routes based on risk, liquidity, and slippage."""

    @staticmethod
    def calculate_scores(
        graph: nx.DiGraph,
        path: list[str],
        expected_output: float,
        ideal_output: float,
        explanation: RouteExplanation,
    ) -> tuple[float, float]:
        """Calculate quality score and confidence score.
        
        Args:
            graph: The networkx directed graph.
            path: The node sequence.
            expected_output: Simulated output.
            ideal_output: Theoretical output with 0 slippage and 0 fees.
            explanation: Route details.
            
        Returns:
            Tuple of (quality_score, confidence_score) (both 0.0 to 1.0)
        """
        # --- Quality Score (Route Score) ---
        # 1.0 is a perfect route.
        # Penalized by slippage, fees, and hop count.
        
        # Calculate execution efficiency
        efficiency = expected_output / ideal_output if ideal_output > 0 else 0.0
        efficiency = max(0.0, min(1.0, efficiency))
        
        # Hop penalty (shorter routes are less prone to mid-flight failure)
        hop_count = (len(path) - 1) // 2 if graph.nodes[path[1]].get("node_type") == "pool" else (len(path) - 1)
        hop_penalty = min(0.5, hop_count * 0.05)
        
        # Liquidity bottleneck penalty (risk of front-running or depletion)
        # We normalize the bottleneck relative to a "safe" threshold (e.g. 10,000 base units)
        bottleneck = explanation.bottleneck_liquidity or 0.0
        liquidity_safety = min(1.0, bottleneck / 10000.0)
        liquidity_penalty = (1.0 - liquidity_safety) * 0.2
        
        quality_score = efficiency - hop_penalty - liquidity_penalty
        quality_score = max(0.0, min(1.0, quality_score))
        
        # --- Confidence Score ---
        # 1.0 means we are perfectly confident in the simulation.
        # Penalized by graph staleness.
        
        # Determine average graph node freshness along the path
        now = datetime.now(timezone.utc)
        total_age_seconds = 0.0
        nodes_with_time = 0
        
        for node in path:
            node_data = graph.nodes[node]
            timestamp_str = node_data.get("timestamp")
            if timestamp_str:
                try:
                    ts = datetime.fromisoformat(timestamp_str)
                    age = (now - ts).total_seconds()
                    total_age_seconds += max(0, age)
                    nodes_with_time += 1
                except ValueError:
                    pass
                    
        avg_age_seconds = total_age_seconds / nodes_with_time if nodes_with_time > 0 else 300.0
        
        # If average age is > 5 minutes (300s), confidence drops significantly
        staleness_penalty = min(0.8, avg_age_seconds / 600.0)  # Drops to 0.2 at 10 minutes
        
        confidence_score = 1.0 - staleness_penalty
        
        # Highly illiquid bottlenecks also reduce confidence (high variance in CPMM)
        if bottleneck < 1000.0:
            confidence_score *= 0.8
            
        confidence_score = max(0.0, min(1.0, confidence_score))
        
        return quality_score, confidence_score
