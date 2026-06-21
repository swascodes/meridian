"""Route execution simulator."""

from __future__ import annotations

import structlog
import orjson

from meridian_shared.redis import RedisKeys, get_redis

logger = structlog.get_logger()


class RouteSimulator:
    """Simulates route execution against current orderbook/pool state."""

    async def simulate(self, path_nodes: list[dict], amount: float) -> dict:
        """Simulate executing a trade along the given path.

        Returns estimated slippage, output amount, and execution metrics.
        """
        current_amount = amount
        total_slippage = 0.0
        total_liquidity = 0.0
        total_spread = 0.0
        hop_count = 0

        for i in range(len(path_nodes) - 1):
            source = path_nodes[i]
            dest = path_nodes[i + 1]

            hop_result = await self._simulate_hop(source, dest, current_amount)
            current_amount = hop_result["output_amount"]
            total_slippage += hop_result["slippage"]
            total_liquidity += hop_result["liquidity"]
            total_spread += hop_result["spread"]
            hop_count += 1

        # Overall metrics
        effective_rate = current_amount / amount if amount > 0 else 0
        return {
            "output_amount": current_amount,
            "effective_rate": effective_rate,
            "slippage": total_slippage / max(hop_count, 1),
            "total_liquidity": total_liquidity,
            "avg_spread": total_spread / max(hop_count, 1),
            "total_weight": total_slippage + total_spread,
            "hop_count": hop_count,
        }

    async def _simulate_hop(self, source: dict, dest: dict, amount: float) -> dict:
        """Simulate a single hop execution."""
        redis = get_redis()

        source_code = source.get("code", "XLM")
        dest_code = dest.get("code", "XLM")

        # Try to get cached orderbook
        cache_key = RedisKeys.orderbook(source_code, dest_code)
        cached = await redis.get(cache_key)

        if cached:
            try:
                orderbook = orjson.loads(cached) if isinstance(cached, (bytes, str)) else eval(cached)  # noqa: S307
                return self._execute_against_orderbook(orderbook, amount)
            except Exception:
                pass

        # Fallback: estimate from edge data
        edge_type = dest.get("edge_type", "orderbook")
        if edge_type == "amm":
            return self._estimate_amm_execution(source, dest, amount)

        return self._estimate_default(amount)

    def _execute_against_orderbook(self, orderbook: dict, amount: float) -> dict:
        """Execute order against cached orderbook state."""
        asks = orderbook.get("asks", [])
        remaining = amount
        total_cost = 0.0
        total_filled = 0.0

        for level in asks:
            price = float(level.get("price", 0))
            available = float(level.get("amount", 0))

            if remaining <= 0:
                break

            fill = min(remaining, available)
            total_cost += fill * price
            total_filled += fill
            remaining -= fill

        if total_filled == 0:
            return {"output_amount": 0, "slippage": 1.0, "liquidity": 0, "spread": 1.0}

        avg_price = total_cost / total_filled
        best_price = float(asks[0]["price"]) if asks else avg_price
        slippage = (avg_price - best_price) / best_price if best_price > 0 else 0

        return {
            "output_amount": total_cost,
            "slippage": max(0, slippage),
            "liquidity": sum(float(a.get("amount", 0)) for a in asks),
            "spread": float(orderbook.get("spread", 0)),
        }

    def _estimate_amm_execution(self, source: dict, dest: dict, amount: float) -> dict:
        """Estimate AMM execution using constant product formula."""
        reserve_in = float(dest.get("reserve_a", 10000))
        reserve_out = float(dest.get("reserve_b", 10000))
        fee_bp = int(dest.get("fee_bp", 30))

        # x * y = k formula
        amount_with_fee = amount * (10000 - fee_bp) / 10000
        output = (reserve_out * amount_with_fee) / (reserve_in + amount_with_fee)

        # Price impact
        ideal_output = amount * (reserve_out / reserve_in)
        slippage = (ideal_output - output) / ideal_output if ideal_output > 0 else 0

        return {
            "output_amount": output,
            "slippage": max(0, slippage),
            "liquidity": reserve_in + reserve_out,
            "spread": fee_bp / 10000,
        }

    def _estimate_default(self, amount: float) -> dict:
        """Default estimation when no market data available."""
        return {
            "output_amount": amount * 0.995,  # Assume 0.5% cost
            "slippage": 0.005,
            "liquidity": 0,
            "spread": 0.005,
        }
