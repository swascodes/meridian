import pytest
import networkx as nx
from app.pathfinding.simulation import RouteSimulationEngine
from app.execution.simulator import ExecutionSimulator
from app.execution.validator import RouteValidator

def test_simulation_empty_path():
    graph = nx.DiGraph()
    # Should not crash, should return success=False and slippage=1.0
    out, slip, fee, exp, success = RouteSimulationEngine.simulate_path(graph, [], 100.0)
    assert not success
    assert slip == 1.0

def test_simulation_short_path():
    graph = nx.DiGraph()
    graph.add_node("A", node_type="asset")
    out, slip, fee, exp, success = RouteSimulationEngine.simulate_path(graph, ["A"], 100.0)
    assert not success
    assert slip == 1.0

def test_simulator_empty_path():
    graph = nx.DiGraph()
    sim = ExecutionSimulator.simulate_execution(graph, [], 100.0)
    assert sim.expected_output == 0.0
    assert sim.slippage == 1.0

def test_validator_empty_path():
    graph = nx.DiGraph()
    val = RouteValidator.validate_route(graph, [], 100.0)
    assert not val.valid
    assert val.reason == "Invalid path length (< 2 nodes)"
