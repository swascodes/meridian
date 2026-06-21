"""Pluggable pathfinding strategies."""

from __future__ import annotations

import abc

import networkx as nx


class PathfindingStrategy(abc.ABC):
    """Abstract base class for pathfinding strategies."""

    @abc.abstractmethod
    def find_paths(
        self,
        graph: nx.DiGraph,
        source: str,
        dest: str,
        weight_func: callable,
        max_hops: int,
        max_paths: int,
    ) -> list[list[str]]:
        """Find paths between source and destination nodes."""
        pass


class DijkstraStrategy(PathfindingStrategy):
    """Finds the single absolute shortest path using Dijkstra's algorithm."""

    def find_paths(
        self,
        graph: nx.DiGraph,
        source: str,
        dest: str,
        weight_func: callable,
        max_hops: int,
        max_paths: int,
    ) -> list[list[str]]:
        try:
            path = nx.dijkstra_path(graph, source, dest, weight=weight_func)
            if len(path) - 1 <= max_hops:
                return [path]
            return []
        except nx.NetworkXNoPath:
            return []


class YensStrategy(PathfindingStrategy):
    """Finds the K-shortest loopless paths using Yen's algorithm."""

    def find_paths(
        self,
        graph: nx.DiGraph,
        source: str,
        dest: str,
        weight_func: callable,
        max_hops: int,
        max_paths: int,
    ) -> list[list[str]]:
        paths = []
        try:
            # shortest_simple_paths implements Yen's algorithm in NetworkX
            path_generator = nx.shortest_simple_paths(graph, source, dest, weight=weight_func)
            for path in path_generator:
                if len(path) - 1 <= max_hops:
                    paths.append(path)
                if len(paths) >= max_paths:
                    break
            return paths
        except nx.NetworkXNoPath:
            return []
