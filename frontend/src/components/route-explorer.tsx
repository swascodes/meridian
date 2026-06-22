"use client";

import React, { useState, useEffect } from "react";
import { Horizon } from "@stellar/stellar-sdk";
import { AssetSelector } from "./asset-selector";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const HORIZON_URLS: Record<string, string> = {
  live: "https://horizon.stellar.org",
  simulation: "https://horizon.stellar.org",
  testnet: "https://horizon-testnet.stellar.org",
};

type Mode = "live" | "simulation" | "testnet";

const MODE_META: Record<Mode, { label: string; badge: string; badgeColor: string; icon: string }> = {
  live: {
    label: "Live Trading",
    badge: "Mainnet — Real Execution",
    badgeColor: "bg-[var(--color-success)]/15 text-[var(--color-success)] border-[var(--color-success)]/30",
    icon: "⚡",
  },
  simulation: {
    label: "Mainnet Simulation",
    badge: "Simulation Only — No Funds Required",
    badgeColor: "bg-[var(--color-accent)]/15 text-[var(--color-accent)] border-[var(--color-accent)]/30",
    icon: "🔬",
  },
  testnet: {
    label: "Testnet Simulation",
    badge: "Testnet Environment",
    badgeColor: "bg-[var(--color-warning)]/15 text-[var(--color-warning)] border-[var(--color-warning)]/30",
    icon: "🧪",
  },
};

interface RouteHop {
  asset: { code: string; issuer: string | null };
  hop_type: string;
}

interface ExecutionSimulation {
  expected_output: number;
  total_fee: number;
  slippage: number;
  price_impact: number;
  hop_details: any[];
}

interface ExecutionRisk {
  risk_score: number;
  risk_level: string;
  factors: any[];
}

interface ExecutionValidation {
  valid: boolean;
  reason: string | null;
  liquidity_sufficient: boolean;
}

interface ExecutionPlan {
  route_hash: string;
  steps: any[];
  total_input: number;
  expected_total_output: number;
  estimated_duration_ms: number;
}

interface RouteExplanation {
  base_fee_estimate: number;
  liquidity_penalty: number;
  hop_penalty: number;
  slippage_impact: number;
}

interface RouteResult {
  route_hash: string;
  source_asset: { code: string; issuer: string | null };
  destination_asset: { code: string; issuer: string | null };
  path: RouteHop[];
  hop_count: number;
  expected_output: number;
  estimated_rate: number;
  estimated_slippage: number;
  estimated_fee: number;
  total_liquidity: number;
  quality_score: number | null;
  confidence_score: number | null;
  execution_score: number | null;
  risk: ExecutionRisk | null;
  validation: ExecutionValidation | null;
  simulation: ExecutionSimulation | null;
  plan: ExecutionPlan | null;
  explanation: RouteExplanation | null;
}

interface Diagnostics {
  source_exists: boolean;
  destination_exists: boolean;
  source_degree: number;
  destination_degree: number;
  same_component: boolean;
  path_exists: boolean;
  component_size: number;
  candidate_paths_found: number;
  failure_reason: string | null;
}

interface RouteExplorerProps {
  walletAddress?: string | null;
}

export function RouteExplorer({ walletAddress }: RouteExplorerProps) {
  const [mode, setMode] = useState<Mode>("simulation");
  const [sourceAsset, setSourceAsset] = useState<{code: string, issuer: string | null}>({ code: "XLM", issuer: null });
  const [destAsset, setDestAsset] = useState<{code: string, issuer: string | null} | null>(null);
  const [amount, setAmount] = useState("100");

  const [routes, setRoutes] = useState<RouteResult[]>([]);
  const [diagnostics, setDiagnostics] = useState<Diagnostics | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedRoute, setExpandedRoute] = useState<string | null>(null);

  // Debug state
  const [debugPayload, setDebugPayload] = useState<any>(null);
  const [debugResponse, setDebugResponse] = useState<any>(null);

  // Wallet balances state
  const [balances, setBalances] = useState<Record<string, number>>({});
  const [trustlines, setTrustlines] = useState<Set<string>>(new Set());
  const [fetchingBalances, setFetchingBalances] = useState(false);

  // Fetch balances when wallet connects or mode changes
  useEffect(() => {
    if (!walletAddress) {
      setBalances({});
      setTrustlines(new Set());
      return;
    }

    // Only fetch balances in modes that use a wallet
    if (mode === "simulation") return;

    const horizonUrl = HORIZON_URLS[mode];
    const horizonServer = new Horizon.Server(horizonUrl);

    const fetchAccount = async () => {
      setFetchingBalances(true);
      try {
        const account = await horizonServer.loadAccount(walletAddress);
        const newBalances: Record<string, number> = {};
        const newTrustlines = new Set<string>();

        account.balances.forEach((b: any) => {
          if (b.asset_type === "native") {
            newBalances["XLM:native"] = parseFloat(b.balance);
            newTrustlines.add("XLM:native");
          } else {
            const key = `${b.asset_code}:${b.asset_issuer}`;
            newBalances[key] = parseFloat(b.balance);
            newTrustlines.add(key);
          }
        });

        setBalances(newBalances);
        setTrustlines(newTrustlines);
      } catch (err: any) {
        if (err?.response?.status === 404 || err?.message?.includes("Not Found")) {
          // Unfunded account — perfectly valid state, just 0 balances
          setBalances({});
          setTrustlines(new Set());
        } else {
          console.error("Failed to fetch wallet balances", err);
        }
      } finally {
        setFetchingBalances(false);
      }
    };

    fetchAccount();
  }, [walletAddress, mode]);

  const getAssetKey = (asset: {code: string, issuer: string | null} | null) => {
    if (!asset) return "";
    return asset.issuer ? `${asset.code}:${asset.issuer}` : "XLM:native";
  };

  const sourceKey = getAssetKey(sourceAsset);
  const destKey = getAssetKey(destAsset);

  const sourceBalance = balances[sourceKey] || 0;
  const hasDestTrustline = destKey === "XLM:native" || trustlines.has(destKey);
  const isBalanceInsufficient = parseFloat(amount || "0") > sourceBalance;

  // --- Mode-specific validation ---
  // Route discovery is NEVER blocked by balance.
  // Balance/trustline only affects execution readiness in live mode.
  let btnDisabled = false;
  let validationMessage = "";
  let executionBlocked = false;
  let executionBlockReason = "";

  if (!destAsset) {
    btnDisabled = true;
    validationMessage = "Select a destination asset.";
  } else if (!amount || parseFloat(amount) <= 0) {
    btnDisabled = true;
    validationMessage = "Enter a valid amount.";
  }

  if (mode === "live") {
    if (!walletAddress) {
      btnDisabled = true;
      validationMessage = "Connect wallet for live trading.";
    } else {
      // Balance and trustline warnings — do NOT block discovery
      if (isBalanceInsufficient) {
        executionBlocked = true;
        executionBlockReason = "Insufficient balance for execution.";
      }
      if (!hasDestTrustline && destAsset) {
        executionBlocked = true;
        executionBlockReason = executionBlockReason
          ? executionBlockReason + " Missing destination trustline."
          : "Missing destination trustline.";
      }
    }
  }

  if (mode === "testnet" && !walletAddress) {
    // Testnet requires a wallet too, but doesn't block discovery
    // Just warn, still allow route search
    validationMessage = "Connect a testnet wallet for balance info.";
  }

  const findRoutes = async () => {
    if (!destAsset || !sourceAsset) return;

    setLoading(true);
    setError(null);
    setExpandedRoute(null);
    setDiagnostics(null);
    setDebugResponse(null);

    const payload = {
      source_asset: sourceAsset,
      destination_asset: destAsset,
      amount: parseFloat(amount),
      simulate: true,
      risk_analysis: true,
      validate_execution: true,
      mode,
    };

    setDebugPayload(payload);

    try {
      const res = await fetch(`${API_BASE}/v1/routes/discover`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      
      console.log(`[API] fetch status: ${res.status} ${res.statusText}`);
      
      if (!res.ok) {
        const text = await res.text();
        console.error(`[API] Error response:`, text);
        setDebugResponse(text);
        throw new Error(`API returned ${res.status}: ${text}`);
      }
      const data = await res.json();
      
      console.log(`[API] Raw response:`, data);
      setDebugResponse(data);

      const foundRoutes = data.routes || [];
      console.log(`[API] Routes length:`, foundRoutes.length);
      
      if (data.failure_reason) {
        setError(data.failure_reason);
      } else if (foundRoutes.length === 0) {
        setError("No routes found for the requested criteria.");
      }
      
      setRoutes(foundRoutes);

      // Fetch diagnostics if failure reason exists
      if (data.failure_reason) {
        const diagRes = await fetch(`${API_BASE}/v1/routes/debug?source_code=${sourceAsset.code}${sourceAsset.issuer ? `&source_issuer=${sourceAsset.issuer}` : ''}&dest_code=${destAsset.code}${destAsset.issuer ? `&dest_issuer=${destAsset.issuer}` : ''}`);
        if (diagRes.ok) {
          const diagData = await diagRes.json();
          setDiagnostics(diagData);
        }
      }

    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to fetch routes";
      console.error("[API] Fetch caught error:", err);
      setError(message);
      setRoutes([]);
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = (hash: string) => {
    setExpandedRoute(expandedRoute === hash ? null : hash);
  };

  const getRiskColor = (level?: string) => {
    switch (level) {
      case "LOW": return "text-[var(--color-success)]";
      case "MEDIUM": return "text-[var(--color-warning)]";
      case "HIGH":
      case "CRITICAL": return "text-[var(--color-error)]";
      default: return "text-[var(--color-text-muted)]";
    }
  };

  const meta = MODE_META[mode];

  return (
    <div className="glass-card p-6">
      <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
        Smart Order Router
      </h2>

      {/* Mode Selector */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        {(Object.keys(MODE_META) as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => { setMode(m); setRoutes([]); setDiagnostics(null); setError(null); }}
            className={`
              px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 border
              ${mode === m
                ? "bg-[var(--color-accent)] text-white border-[var(--color-accent)] shadow-lg shadow-[var(--color-accent)]/20"
                : "bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] border-[var(--color-border)] hover:border-[var(--color-accent)]/50 hover:text-[var(--color-text-primary)]"
              }
            `}
          >
            <span className="mr-1.5">{MODE_META[m].icon}</span>
            {MODE_META[m].label}
          </button>
        ))}
      </div>

      {/* Mode Badge */}
      <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border mb-5 ${meta.badgeColor}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
        {meta.badge}
      </div>

      {/* Search Form */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-2">
        <div className="md:col-span-1">
          <AssetSelector
            label="Source Asset"
            value={sourceAsset}
            onChange={setSourceAsset}
          />
          {(mode === "live" || mode === "testnet") && walletAddress && sourceAsset && (
            <div className="text-[10px] text-[var(--color-text-muted)] mt-1 ml-1">
              Balance: {fetchingBalances ? "..." : sourceBalance.toLocaleString()}
            </div>
          )}
        </div>

        <div className="md:col-span-1">
          <AssetSelector
            label="Destination Asset"
            value={destAsset}
            onChange={setDestAsset}
          />
          {mode === "live" && walletAddress && destAsset && (
            <div className="text-[10px] text-[var(--color-text-muted)] mt-1 ml-1">
              Trustline: {hasDestTrustline ? <span className="text-[var(--color-success)]">Active</span> : <span className="text-[var(--color-error)]">Missing</span>}
            </div>
          )}
        </div>

        <div className="md:col-span-1">
          <label className="block text-xs text-[var(--color-text-muted)] mb-1.5">Amount</label>
          <input
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="100"
            className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--color-border)] text-sm focus:outline-none focus:border-[var(--color-accent)] transition-colors"
          />
        </div>
        <div className="md:col-span-1 flex items-end">
          <button
            onClick={findRoutes}
            disabled={loading || btnDisabled}
            className="w-full px-4 py-2 rounded-lg bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white text-sm font-medium transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed h-[38px] flex items-center justify-center"
          >
            {loading ? "Discovering..." : "Find Best Route"}
          </button>
        </div>
      </div>

      {/* Validation and Error Banners */}
      {validationMessage && (
        <div className="p-3 mb-4 rounded border border-[var(--color-warning)] bg-[var(--color-warning)] bg-opacity-10 text-[var(--color-warning)] text-sm">
          {validationMessage}
        </div>
      )}
      {error && (
        <div className="mb-4">
          <div className="p-3 rounded border border-[var(--color-error)] bg-[var(--color-error)] bg-opacity-10 text-[var(--color-error)] text-sm font-medium">
            Backend Failure: {error}
          </div>
          {diagnostics && (
            <div className="mt-2 p-3 bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg text-xs font-mono overflow-x-auto">
              <div className="text-[var(--color-text-muted)] mb-2 uppercase tracking-wider font-sans text-[10px]">Diagnostics Report</div>
              <pre className="text-[var(--color-text)]">
                {JSON.stringify(diagnostics, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Execution Warning (does NOT block discovery) */}
      {mode === "live" && executionBlocked && routes.length > 0 && (
        <div className="mb-4 px-4 py-2.5 rounded-lg bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/20 text-[var(--color-warning)] text-xs flex items-center gap-2">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          {executionBlockReason}
        </div>
      )}

      {/* Results */}
      {routes.length > 0 && (
        <div className="space-y-3 mt-4">
          <h3 className="text-sm font-medium text-[var(--color-text-secondary)] mb-4">
            {routes.length} execution plan{routes.length !== 1 ? "s" : ""} generated
          </h3>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                <tr>
                  <th className="pb-3 px-2 font-medium">Rank</th>
                  <th className="pb-3 px-2 font-medium">Path</th>
                  <th className="pb-3 px-2 font-medium">Expected Output</th>
                  <th className="pb-3 px-2 font-medium">Slippage</th>
                  <th className="pb-3 px-2 font-medium">Fees</th>
                  <th className="pb-3 px-2 font-medium">Risk</th>
                  <th className="pb-3 px-2 font-medium">Exec Score</th>
                  <th className="pb-3 px-2 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]/50">
                {routes.map((route, i) => (
                  <React.Fragment key={route.route_hash}>
                    <tr className="hover:bg-[var(--color-bg-elevated)]/50 transition-colors group cursor-pointer" onClick={() => toggleExpand(route.route_hash)}>
                      <td className="py-3 px-2">
                        <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-[var(--color-accent)]/10 text-[var(--color-accent)] text-xs font-semibold">
                          {i + 1}
                        </span>
                      </td>
                      <td className="py-3 px-2">
                        <div className="flex items-center gap-1 flex-wrap">
                          {route?.path?.map((hop, j) => (
                            <div key={j} className="flex items-center gap-1">
                              <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${hop?.hop_type === "amm" ? "bg-[var(--color-success)]/10 text-[var(--color-success)]" : "bg-[var(--color-bg-card)] border border-[var(--color-border)]"}`}>
                                {hop?.asset?.code}
                              </span>
                              {j < (route?.path?.length || 0) - 1 && (
                                <span className="text-[var(--color-text-muted)] text-xs">→</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </td>
                      <td className="py-3 px-2 font-medium">
                        {(route?.expected_output || 0).toLocaleString(undefined, { maximumFractionDigits: 4 })}
                      </td>
                      <td className="py-3 px-2 text-[var(--color-text-secondary)]">
                        {((route?.estimated_slippage || 0) * 100).toFixed(2)}%
                      </td>
                      <td className="py-3 px-2 text-[var(--color-text-secondary)]">
                        {(route?.estimated_fee || 0).toFixed(4)}
                      </td>
                      <td className="py-3 px-2">
                        <div className="flex flex-col">
                          <span className={`text-xs font-semibold ${getRiskColor(route?.risk?.risk_level)}`}>
                            {route?.risk?.risk_level || "UNKNOWN"}
                          </span>
                          <span className="text-[10px] text-[var(--color-text-muted)]">
                            Score: {(route?.risk?.risk_score ?? 0).toFixed(2)}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-2">
                        <span className="text-sm font-semibold text-[var(--color-accent)]">
                          {((route?.execution_score ?? 0) * 100).toFixed(1)}
                        </span>
                      </td>
                      <td className="py-3 px-2 text-right">
                        <svg
                          className={`w-4 h-4 text-[var(--color-text-muted)] transform transition-transform ${expandedRoute === route.route_hash ? "rotate-180" : ""}`}
                          fill="none" stroke="currentColor" viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                        </svg>
                      </td>
                    </tr>

                    {/* Expanded Details */}
                    {expandedRoute === route.route_hash && (
                      <tr className="bg-[var(--color-bg-elevated)]/30">
                        <td colSpan={8} className="p-4 border-b border-[var(--color-border)]">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

                            {/* Validation & Simulation */}
                            <div className="space-y-4">
                              <div>
                                <h4 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider mb-2">Validation</h4>
                                <div className="p-3 rounded bg-[var(--color-bg-card)] border border-[var(--color-border)]">
                                  <div className="flex items-center gap-2 mb-2">
                                    <div className={`w-2 h-2 rounded-full ${route?.validation?.valid ? 'bg-[var(--color-success)]' : 'bg-[var(--color-error)]'}`}></div>
                                    <span className="text-sm font-medium">{route?.validation?.valid ? "Execution Ready" : "Validation Failed"}</span>
                                  </div>
                                  {!route?.validation?.valid && (
                                    <p className="text-xs text-[var(--color-error)]">{route?.validation?.reason}</p>
                                  )}
                                  <div className="mt-2 text-xs text-[var(--color-text-muted)]">
                                    Liquidity Sufficient: {route?.validation?.liquidity_sufficient ? "Yes" : "No"}
                                  </div>
                                </div>
                              </div>

                              <div>
                                <h4 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider mb-2">Simulation Impact</h4>
                                <div className="p-3 rounded bg-[var(--color-bg-card)] border border-[var(--color-border)] text-xs space-y-1">
                                  <div className="flex justify-between">
                                    <span className="text-[var(--color-text-muted)]">Price Impact</span>
                                    <span>{((route?.simulation?.price_impact ?? 0) * 100).toFixed(2)}%</span>
                                  </div>
                                  <div className="flex justify-between">
                                    <span className="text-[var(--color-text-muted)]">Bottleneck Liquidity</span>
                                    <span>{(route?.total_liquidity || 0).toLocaleString()}</span>
                                  </div>
                                  <div className="flex justify-between">
                                    <span className="text-[var(--color-text-muted)]">Confidence</span>
                                    <span>{((route?.confidence_score ?? 0) * 100).toFixed(1)}%</span>
                                  </div>
                                </div>
                              </div>
                            </div>

                            {/* Execution Plan */}
                            <div>
                              <h4 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider mb-2">Execution Plan</h4>
                              <div className="space-y-2">
                                {route?.plan?.steps?.map((step: any, idx: number) => (
                                  <div key={idx} className="p-3 rounded bg-[var(--color-bg-card)] border border-[var(--color-border)]">
                                    <div className="flex items-center justify-between mb-2">
                                      <span className="text-xs font-medium px-2 py-0.5 rounded bg-[var(--color-bg-elevated)]">
                                        Step {(step?.step_index || 0) + 1}
                                      </span>
                                      <span className="text-[10px] uppercase text-[var(--color-text-muted)] tracking-wider">
                                        {step?.type?.replace('_', ' ')}
                                      </span>
                                    </div>

                                    <div className="flex items-center justify-between text-sm">
                                      <div className="flex flex-col">
                                        <span className="font-medium text-[var(--color-error)]">-{(step?.expected_input || 0).toFixed(4)}</span>
                                        <span className="text-xs text-[var(--color-text-muted)]">{step?.input_asset?.split(':')[0]}</span>
                                      </div>

                                      <svg className="w-4 h-4 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
                                      </svg>

                                      <div className="flex flex-col items-end">
                                        <span className="font-medium text-[var(--color-success)]">+{(step?.expected_output || 0).toFixed(4)}</span>
                                        <span className="text-xs text-[var(--color-text-muted)]">{step?.output_asset?.split(':')[0]}</span>
                                      </div>
                                    </div>

                                    {step?.pool_id && (
                                      <div className="mt-2 text-[10px] text-[var(--color-text-muted)] text-right font-mono">
                                        Pool: {step.pool_id.slice(0, 8)}...{step.pool_id.slice(-8)}
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>

                              {/* Execute Route — Live only */}
                              {mode === "live" && (
                                <div className="mt-4">
                                  <button
                                    disabled={executionBlocked || !route?.validation?.valid}
                                    className="w-full px-4 py-2.5 rounded-lg bg-[var(--color-success)] hover:bg-[var(--color-success)]/80 text-white text-sm font-semibold transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                                  >
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                                    Execute Route
                                  </button>
                                  {executionBlocked && (
                                    <p className="text-[10px] text-[var(--color-warning)] mt-1 text-center">{executionBlockReason}</p>
                                  )}
                                </div>
                              )}

                              {/* Simulation badge for non-live modes */}
                              {mode !== "live" && (
                                <div className="mt-4 text-center">
                                  <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[10px] font-medium border ${meta.badgeColor}`}>
                                    {meta.icon} {mode === "simulation" ? "Simulation — No execution" : "Testnet — No execution"}
                                  </span>
                                </div>
                              )}
                            </div>

                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty state */}
      {routes.length === 0 && !loading && !error && !diagnostics && (
        <div className="text-center py-12 text-[var(--color-text-muted)]">
          <svg className="mx-auto mb-3 w-12 h-12 opacity-30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"/>
            <path d="m21 21-4.3-4.3"/>
          </svg>
          <p className="text-sm">
            {mode === "simulation"
              ? "Select assets and amount to simulate route execution"
              : mode === "testnet"
                ? "Connect testnet wallet, then select assets to simulate"
                : "Connect wallet and select assets to discover executable routes"
            }
          </p>
        </div>
      )}

      {/* Debug Panel */}
      <div className="mt-8 border border-[var(--color-border)] rounded-lg p-4 bg-[var(--color-bg-elevated)]/30">
        <h3 className="text-sm font-bold text-[var(--color-text-secondary)] mb-3 uppercase tracking-wider">Debug Info</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-[var(--color-text-muted)] mb-1">Request Payload</div>
            <pre className="text-[10px] p-2 bg-[var(--color-bg-card)] rounded overflow-x-auto border border-[var(--color-border)] text-[var(--color-text-secondary)] max-h-48">
              {debugPayload ? JSON.stringify(debugPayload, null, 2) : "No request yet"}
            </pre>
          </div>
          <div>
            <div className="text-xs text-[var(--color-text-muted)] mb-1">Raw API Response</div>
            <pre className="text-[10px] p-2 bg-[var(--color-bg-card)] rounded overflow-x-auto border border-[var(--color-border)] text-[var(--color-text-secondary)] max-h-48">
              {debugResponse ? JSON.stringify(debugResponse, null, 2) : "No response yet"}
            </pre>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-4 text-xs">
          <div className="px-3 py-1.5 rounded bg-[var(--color-bg-card)] border border-[var(--color-border)]">
            <span className="text-[var(--color-text-muted)] mr-2">Routes Rendered:</span>
            <span className="font-mono font-medium">{routes.length}</span>
          </div>
          {error && (
            <div className="px-3 py-1.5 rounded bg-[var(--color-error)]/10 border border-[var(--color-error)]/30 text-[var(--color-error)]">
              <span className="opacity-70 mr-2">Fetch Error:</span>
              <span className="font-mono font-medium">{error}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
