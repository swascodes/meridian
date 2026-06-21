"use client";

import { useState, useEffect } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Stats {
  total_nodes: number;
  total_edges: number;
  total_assets: number;
  total_pools: number;
  avg_degree: number;
  density: number;
  connected_components: number;
}

export function NetworkStats() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch(`${API_BASE}/v1/graph/stats`);
        if (res.ok) {
          setStats(await res.json());
        }
      } catch {
        // API may not be running yet
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, []);

  const statCards = stats
    ? [
        { label: "Assets", value: stats.total_assets.toLocaleString(), icon: "◆" },
        { label: "Edges", value: stats.total_edges.toLocaleString(), icon: "⟷" },
        { label: "Pools", value: stats.total_pools.toLocaleString(), icon: "◎" },
        { label: "Components", value: stats.connected_components.toLocaleString(), icon: "⬡" },
        { label: "Avg Degree", value: stats.avg_degree.toFixed(2), icon: "⊛" },
        { label: "Density", value: (stats.density * 100).toFixed(3) + "%", icon: "▣" },
      ]
    : Array.from({ length: 6 }, (_, i) => ({ label: "—", value: "—", icon: "·" }));

  return (
    <div className="glass-card p-6">
      <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 20V10"/>
          <path d="M18 20V4"/>
          <path d="M6 20v-4"/>
        </svg>
        Network Graph
      </h2>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {statCards.map((stat, i) => (
          <div
            key={i}
            className={`p-4 rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--color-border)] ${loading ? "animate-pulse" : ""}`}
          >
            <div className="text-lg mb-1">{stat.icon}</div>
            <div className="text-2xl font-bold tracking-tight">{stat.value}</div>
            <div className="text-xs text-[var(--color-text-muted)] mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      {!loading && !stats && (
        <div className="mt-4 text-center text-sm text-[var(--color-text-muted)]">
          Graph engine not connected. Start services with{" "}
          <code className="px-1.5 py-0.5 rounded bg-[var(--color-bg-elevated)] text-[var(--color-accent)]">
            make dev
          </code>
        </div>
      )}
    </div>
  );
}
