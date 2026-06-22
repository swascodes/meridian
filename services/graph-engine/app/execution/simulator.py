"""Execution Simulator — detailed per-hop simulation with CPMM and orderbook depth."""

from __future__ import annotations

from datetime import datetime, timezone

import networkx as nx

from meridian_shared.models import ExecutionHopDetail, ExecutionSimulation


class ExecutionSimulator:
    """Simulates execution across a path with per-hop detail."""

    @classmethod
    def simulate_execution(
        cls,
        graph: nx.DiGraph,
        path: list[str],
        amount: float,
    ) -> ExecutionSimulation:
        """Run full execution simulation returning per-hop breakdown."""
        if not path or len(path) < 2:
            return ExecutionSimulation(
                expected_output=0.0,
                total_fee=0.0,
                slippage=1.0,
                price_impact=1.0,
                hop_details=[],
                simulated_at=datetime.now(timezone.utc),
            )

        current_amount = amount
        total_fee = 0.0
        hop_details: list[ExecutionHopDetail] = []
        hop_index = 0

        i = 0
        while i < len(path) - 1:
            u = path[i]
            v = path[i + 1]
            node_v = graph.nodes[v]

            if node_v.get("node_type") == "pool":
                # AMM pool swap: Asset -> Pool -> Asset
                edge = graph[u][v]
                w = path[i + 2]
                node_u = graph.nodes[u]
                node_w = graph.nodes[w]

                reserve_in = float(edge.get("reserve_in", 0))
                reserve_out = float(edge.get("reserve_out", 0))
                fee_bp = int(edge.get("fee_bp", 30))
                fee_rate = fee_bp / 10000.0

                input_asset = f"{node_u.get('code', '?')}:{node_u.get('issuer') or 'native'}"
                output_asset = f"{node_w.get('code', '?')}:{node_w.get('issuer') or 'native'}"

                if reserve_in <= 0 or reserve_out <= 0:
                    # Dead pool
                    hop_details.append(ExecutionHopDetail(
                        hop_index=hop_index,
                        hop_type="pool_swap",
                        input_asset=input_asset,
                        output_asset=output_asset,
                        input_amount=current_amount,
                        output_amount=0.0,
                        fee_paid=0.0,
                        slippage=1.0,
                        pool_id=node_v.get("pool_id"),
                    ))
                    current_amount = 0.0
                    break

                # CPMM: dy = (y * dx_net) / (x + dx_net)
                dx_net = current_amount * (1.0 - fee_rate)
                fee_paid = current_amount * fee_rate
                dy = (reserve_out * dx_net) / (reserve_in + dx_net)

                # Spot rate without fee
                spot_rate = reserve_out / reserve_in
                ideal_output = current_amount * spot_rate
                hop_slippage = 1.0 - (dy / ideal_output) if ideal_output > 0 else 0.0
                hop_slippage = max(0.0, hop_slippage)

                total_fee += fee_paid

                hop_details.append(ExecutionHopDetail(
                    hop_index=hop_index,
                    hop_type="pool_swap",
                    input_asset=input_asset,
                    output_asset=output_asset,
                    input_amount=current_amount,
                    output_amount=dy,
                    fee_paid=fee_paid,
                    slippage=hop_slippage,
                    pool_id=node_v.get("pool_id"),
                ))

                current_amount = dy
                i += 2
            else:
                # Orderbook trade
                edge = graph[u][v]
                node_u = graph.nodes[u]

                input_asset = f"{node_u.get('code', '?')}:{node_u.get('issuer') or 'native'}"
                output_asset = f"{node_v.get('code', '?')}:{node_v.get('issuer') or 'native'}"

                bid_depth = float(edge.get("bid_depth", 0))
                mid_price = float(edge.get("mid_price", 0))
                spread = float(edge.get("spread", 0))

                if mid_price <= 0:
                    hop_details.append(ExecutionHopDetail(
                        hop_index=hop_index,
                        hop_type="orderbook_trade",
                        input_asset=input_asset,
                        output_asset=output_asset,
                        input_amount=current_amount,
                        output_amount=0.0,
                        fee_paid=0.0,
                        slippage=1.0,
                    ))
                    current_amount = 0.0
                    break

                # Linear depth consumption model
                capacity = bid_depth if bid_depth > 0 else current_amount * 10
                fill_ratio = min(1.0, current_amount / capacity) if capacity > 0 else 0.0
                impact = fill_ratio * spread
                effective_price = mid_price * (1.0 - impact)
                dy = current_amount * effective_price

                hop_slippage = impact
                fee_paid_ob = 0.0  # DEX has no explicit fee, cost is in spread

                hop_details.append(ExecutionHopDetail(
                    hop_index=hop_index,
                    hop_type="orderbook_trade",
                    input_asset=input_asset,
                    output_asset=output_asset,
                    input_amount=current_amount,
                    output_amount=dy,
                    fee_paid=fee_paid_ob,
                    slippage=hop_slippage,
                ))

                current_amount = dy
                i += 1

            hop_index += 1

        # Overall metrics
        expected_output = current_amount
        overall_slippage = 1.0 - (expected_output / (amount * 1.0)) if amount > 0 and expected_output > 0 else 0.0
        overall_slippage = max(0.0, min(1.0, overall_slippage))
        price_impact = sum(h.slippage for h in hop_details) / len(hop_details) if hop_details else 0.0

        return ExecutionSimulation(
            expected_output=expected_output,
            total_fee=total_fee,
            slippage=overall_slippage,
            price_impact=price_impact,
            hop_details=hop_details,
            simulated_at=datetime.now(timezone.utc),
        )
