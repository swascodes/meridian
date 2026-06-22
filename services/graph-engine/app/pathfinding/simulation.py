"""Route Simulation Engine for calculating execution outcomes."""

from __future__ import annotations

import networkx as nx

from meridian_shared.models import RouteExplanation


class RouteSimulationEngine:
    """Simulates physical trade execution across a discovered path."""

    @staticmethod
    def simulate_path(
        graph: nx.DiGraph,
        path: list[str],
        input_amount: float,
    ) -> tuple[float, float, float, RouteExplanation, bool]:
        """Simulate trade execution along a path.
        
        Returns:
            Tuple of (expected_output, estimated_slippage, estimated_fee, explanation, success)
        """
        if not path or len(path) < 2:
            return 0.0, 1.0, 0.0, RouteExplanation(
                base_fee_estimate=0.0,
                liquidity_penalty=1.0,
                hop_penalty=0.0,
                slippage_impact=1.0
            ), False

        current_amount = input_amount
        total_fee_base = 0.0
        
        # Track path execution parameters
        path_expected_rate = 1.0
        
        liquidity_penalties = 0.0
        hop_penalty = (len(path) - 1) * 0.0001
        
        bottleneck_index = None
        bottleneck_liquidity = float('inf')
        
        # Iterate over hops
        i = 0
        while i < len(path) - 1:
            u = path[i]
            v = path[i + 1]
            
            # Check if this is an AMM pool hop (Asset -> Pool -> Asset)
            is_pool_hop = graph.nodes[v].get("node_type") == "pool"
            
            if is_pool_hop:
                # Asset -> Pool edge
                edge_in = graph[u][v]
                pool_node = v
                
                # Pool -> Asset edge
                w = path[i + 2]
                
                reserve_in = edge_in.get("reserve_in", 0.0)
                reserve_out = edge_in.get("reserve_out", 0.0)
                fee_bp = edge_in.get("fee_bp", 30)
                fee_rate = fee_bp / 10000.0
                
                # Check liquidity bottleneck
                if reserve_in < bottleneck_liquidity:
                    bottleneck_liquidity = reserve_in
                    bottleneck_index = i
                
                if current_amount >= reserve_in * 0.99:  # Failsafe if amount exceeds pool capacity
                    return 0.0, 1.0, 0.0, RouteExplanation(
                        base_fee_estimate=total_fee_base,
                        liquidity_penalty=float('inf'),
                        hop_penalty=hop_penalty,
                        slippage_impact=1.0,
                        bottleneck_hop_index=i,
                        bottleneck_liquidity=reserve_in
                    ), False
                
                # CPMM Math
                # dx_net = dx * (1 - f)
                dx_net = current_amount * (1.0 - fee_rate)
                fee_paid = current_amount * fee_rate
                
                # Convert fee paid to base asset equivalent roughly for telemetry
                # Assuming 1:1 if it's the first hop, else approximate
                total_fee_base += fee_paid / (path_expected_rate if path_expected_rate > 0 else 1.0)
                
                # dy = (y * dx_net) / (x + dx_net)
                dy = (reserve_out * dx_net) / (reserve_in + dx_net)
                
                # Update expected rate based on spot price (y/x)
                spot_price = reserve_out / reserve_in if reserve_in > 0 else 0.0
                path_expected_rate *= spot_price
                
                current_amount = dy
                
                # Skip the next node because we processed Asset -> Pool -> Asset
                i += 2
                
            else:
                # Orderbook hop
                edge = graph[u][v]
                
                # Depth available
                bid_depth = edge.get("bid_depth", 0.0)
                ask_depth = edge.get("ask_depth", 0.0)
                mid_price = edge.get("mid_price", 0.0)
                
                # Roughly estimate we consume the depth.
                # If we are selling U for V, we consume V's bids. The capacity is bid_depth.
                capacity = bid_depth
                
                if capacity < bottleneck_liquidity:
                    bottleneck_liquidity = capacity
                    bottleneck_index = i
                
                if current_amount > capacity:
                    return 0.0, 1.0, 0.0, RouteExplanation(
                        base_fee_estimate=total_fee_base,
                        liquidity_penalty=float('inf'),
                        hop_penalty=hop_penalty,
                        slippage_impact=1.0,
                        bottleneck_hop_index=i,
                        bottleneck_liquidity=capacity
                    ), False
                
                # For orderbooks, assume fee is already accounted for in spread or is 0 for native DEX
                # Approximate slippage as linear impact up to capacity
                impact = (current_amount / capacity) * edge.get("spread", 0.001) if capacity > 0 else 0.0
                effective_price = mid_price * (1.0 - impact)
                
                dy = current_amount * effective_price
                
                path_expected_rate *= mid_price
                current_amount = dy
                i += 1
                
        # Final output
        expected_output = current_amount
        ideal_output = input_amount * path_expected_rate
        
        if ideal_output > 0:
            slippage = 1.0 - (expected_output / ideal_output)
        else:
            slippage = 1.0
            
        slippage = max(0.0, min(1.0, slippage))
        
        explanation = RouteExplanation(
            base_fee_estimate=total_fee_base,
            liquidity_penalty=slippage * 2.0,  # Proxy for scoring
            hop_penalty=hop_penalty,
            slippage_impact=slippage,
            bottleneck_hop_index=bottleneck_index,
            bottleneck_liquidity=bottleneck_liquidity
        )
        
        return expected_output, slippage, total_fee_base, explanation, True
