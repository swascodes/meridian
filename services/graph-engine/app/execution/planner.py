"""Execution Plan Generator — machine-readable execution plans."""

from __future__ import annotations

from datetime import datetime, timezone

import networkx as nx

from meridian_shared.models import ExecutionPlan, ExecutionSimulation, ExecutionStep


class ExecutionPlanner:
    """Generates machine-readable execution plans from paths."""

    @classmethod
    def generate_plan(
        cls,
        graph: nx.DiGraph,
        path: list[str],
        amount: float,
        simulation: ExecutionSimulation,
        route_hash: str,
    ) -> ExecutionPlan:
        """Generate an ordered execution plan."""
        steps: list[ExecutionStep] = []
        step_index = 0
        hop_idx = 0

        i = 0
        while i < len(path) - 1:
            u = path[i]
            v = path[i + 1]
            node_u = graph.nodes[u]
            node_v = graph.nodes[v]

            # Get simulation detail for this hop if available
            hop_detail = simulation.hop_details[hop_idx] if hop_idx < len(simulation.hop_details) else None

            if node_v.get("node_type") == "pool":
                # Pool swap: Asset -> Pool -> Asset
                w = path[i + 2]
                node_w = graph.nodes[w]

                input_asset = f"{node_u.get('code', '?')}:{node_u.get('issuer') or 'native'}"
                output_asset = f"{node_w.get('code', '?')}:{node_w.get('issuer') or 'native'}"

                steps.append(ExecutionStep(
                    step_index=step_index,
                    type="pool_swap",
                    pool_id=node_v.get("pool_id"),
                    input_asset=input_asset,
                    output_asset=output_asset,
                    expected_input=hop_detail.input_amount if hop_detail else amount,
                    expected_output=hop_detail.output_amount if hop_detail else 0.0,
                ))

                i += 2
            else:
                # Orderbook trade
                input_asset = f"{node_u.get('code', '?')}:{node_u.get('issuer') or 'native'}"
                output_asset = f"{node_v.get('code', '?')}:{node_v.get('issuer') or 'native'}"

                steps.append(ExecutionStep(
                    step_index=step_index,
                    type="orderbook_trade",
                    market=f"{node_u.get('code', '?')}/{node_v.get('code', '?')}",
                    input_asset=input_asset,
                    output_asset=output_asset,
                    expected_input=hop_detail.input_amount if hop_detail else amount,
                    expected_output=hop_detail.output_amount if hop_detail else 0.0,
                ))

                i += 1

            step_index += 1
            hop_idx += 1

        return ExecutionPlan(
            route_hash=route_hash,
            steps=steps,
            total_input=amount,
            expected_total_output=simulation.expected_output,
            estimated_duration_ms=len(steps) * 3000,  # ~3s per step
            generated_at=datetime.now(timezone.utc),
        )
