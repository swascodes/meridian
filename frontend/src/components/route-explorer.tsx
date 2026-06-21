"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface RouteHop {
  asset: { code: string; issuer: string | null };
  hop_type: string;
}

interface RouteResult {
  route_hash: string;
  source_asset: { code: string; issuer: string | null };
  destination_asset: { code: string; issuer: string | null };
  path: RouteHop[];
  hop_count: number;
  estimated_rate: number;
  estimated_slippage: number;
  total_liquidity: number;
  quality_score: number | null;
}

export function RouteExplorer() {
  const [sourceAsset, setSourceAsset] = useState("native");
  const [destAsset, setDestAsset] = useState("");
  const [amount, setAmount] = useState("100");
  const [routes, setRoutes] = useState<RouteResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const findRoutes = async () => {
    if (!destAsset.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(
        `${API_BASE}/v1/routes/${encodeURIComponent(sourceAsset)}/${encodeURIComponent(destAsset)}?amount=${amount}`
      );
      if (!res.ok) throw new Error(`API returned ${res.status}`);
      const data = await res.json();
      setRoutes(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to fetch routes";
      setError(message);
      setRoutes([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-card p-6">
      <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
        Route Explorer
      </h2>

      {/* Search Form */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div>
          <label className="block text-xs text-[var(--color-text-muted)] mb-1.5">Source Asset</label>
          <input
            type="text"
            value={sourceAsset}
            onChange={(e) => setSourceAsset(e.target.value)}
            placeholder="native or CODE:ISSUER"
            className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--color-border)] text-sm focus:outline-none focus:border-[var(--color-accent)] transition-colors"
          />
        </div>
        <div>
          <label className="block text-xs text-[var(--color-text-muted)] mb-1.5">Destination Asset</label>
          <input
            type="text"
            value={destAsset}
            onChange={(e) => setDestAsset(e.target.value)}
            placeholder="CODE:ISSUER"
            className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--color-border)] text-sm focus:outline-none focus:border-[var(--color-accent)] transition-colors"
          />
        </div>
        <div>
          <label className="block text-xs text-[var(--color-text-muted)] mb-1.5">Amount</label>
          <input
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="100"
            className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--color-border)] text-sm focus:outline-none focus:border-[var(--color-accent)] transition-colors"
          />
        </div>
        <div className="flex items-end">
          <button
            onClick={findRoutes}
            disabled={loading || !destAsset.trim()}
            className="w-full px-4 py-2 rounded-lg bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white text-sm font-medium transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Finding..." : "Find Routes"}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 px-4 py-3 rounded-lg bg-[var(--color-error)]/10 border border-[var(--color-error)]/20 text-[var(--color-error)] text-sm">
          {error}
        </div>
      )}

      {/* Results */}
      {routes.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-[var(--color-text-secondary)]">
            {routes.length} route{routes.length !== 1 ? "s" : ""} found
          </h3>
          {routes.map((route, i) => (
            <div
              key={route.route_hash}
              className="p-4 rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--color-border)] hover:border-[var(--color-border-hover)] transition-colors"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-[var(--color-accent)]/10 text-[var(--color-accent)]">
                    #{i + 1}
                  </span>
                  <span className="text-sm font-mono text-[var(--color-text-muted)]">
                    {route.route_hash.slice(0, 12)}...
                  </span>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-[var(--color-text-muted)]">
                    {route.hop_count} hop{route.hop_count !== 1 ? "s" : ""}
                  </span>
                  {route.quality_score !== null && (
                    <span className={`font-medium ${route.quality_score > 0.8 ? "text-[var(--color-success)]" : route.quality_score > 0.5 ? "text-[var(--color-warning)]" : "text-[var(--color-error)]"}`}>
                      {(route.quality_score * 100).toFixed(1)}% quality
                    </span>
                  )}
                </div>
              </div>

              {/* Path visualization */}
              <div className="flex items-center gap-1 flex-wrap">
                {route.path.map((hop, j) => (
                  <div key={j} className="flex items-center gap-1">
                    <span className="text-sm font-medium px-2 py-1 rounded bg-[var(--color-bg-card)] border border-[var(--color-border)]">
                      {hop.asset.code}
                    </span>
                    {j < route.path.length - 1 && (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-muted)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M5 12h14M12 5l7 7-7 7"/>
                      </svg>
                    )}
                  </div>
                ))}
              </div>

              <div className="mt-3 flex gap-6 text-xs text-[var(--color-text-muted)]">
                <span>Rate: {route.estimated_rate.toFixed(6)}</span>
                <span>Slippage: {(route.estimated_slippage * 100).toFixed(2)}%</span>
                <span>Liquidity: {route.total_liquidity.toLocaleString()}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {routes.length === 0 && !loading && !error && (
        <div className="text-center py-12 text-[var(--color-text-muted)]">
          <svg className="mx-auto mb-3 w-12 h-12 opacity-30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"/>
            <path d="m21 21-4.3-4.3"/>
          </svg>
          <p className="text-sm">Enter a destination asset to discover optimal routes</p>
        </div>
      )}
    </div>
  );
}
