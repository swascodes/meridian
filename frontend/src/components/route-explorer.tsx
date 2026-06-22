"use client";

import React, { useState, useEffect } from "react";
import { Horizon } from "@stellar/stellar-sdk";
import { AssetSelector } from "./asset-selector";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const server = new Horizon.Server("https://horizon.stellar.org");

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
  const [sourceAsset, setSourceAsset] = useState<{code: string, issuer: string | null}>({ code: "XLM", issuer: null });
  const [destAsset, setDestAsset] = useState<{code: string, issuer: string | null} | null>(null);
  const [amount, setAmount] = useState("100");
  
  const [routes, setRoutes] = useState<RouteResult[]>([]);
  const [diagnostics, setDiagnostics] = useState<Diagnostics | null>(null);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedRoute, setExpandedRoute] = useState<string | null>(null);

  // Wallet balances state
  const [balances, setBalances] = useState<Record<string, number>>({});
  const [trustlines, setTrustlines] = useState<Set<string>>(new Set());
  const [fetchingBalances, setFetchingBalances] = useState(false);

  useEffect(() => {
    if (!walletAddress) {
      setBalances({});
      setTrustlines(new Set());
      return;
    }

    const fetchAccount = async () => {
      setFetchingBalances(true);
      try {
        const account = await server.loadAccount(walletAddress);
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
      } catch (err) {
        console.error("Failed to fetch wallet balances", err);
      } finally {
        setFetchingBalances(false);
      }
    };

    fetchAccount();
  }, [walletAddress]);

  const getAssetKey = (asset: {code: string, issuer: string | null} | null) => {
    if (!asset) return "";
    return asset.issuer ? `${asset.code}:${asset.issuer}` : "XLM:native";
  };

  const sourceKey = getAssetKey(sourceAsset);
  const destKey = getAssetKey(destAsset);
  
  const sourceBalance = balances[sourceKey] || 0;
  const hasDestTrustline = destKey === "XLM:native" || trustlines.has(destKey);
  const isBalanceInsufficient = parseFloat(amount || "0") > sourceBalance;

  const findRoutes = async () => {
    if (!destAsset || !sourceAsset) return;

    setLoading(true);
    setError(null);
    setExpandedRoute(null);
    setDiagnostics(null);

    const payload = {
      source_asset: sourceAsset,
      destination_asset: destAsset,
      amount: parseFloat(amount),
      simulate: true,
      risk_analysis: true,
      validate_execution: true,
    };

    try {
      const res = await fetch(`${API_BASE}/v1/routes/discover`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`API returned ${res.status}: ${text}`);
      }
      const data = await res.json();
      
      const foundRoutes = data.routes || [];
      setRoutes(foundRoutes);

      if (foundRoutes.length === 0) {
        // Trigger investigation
        const diagRes = await fetch(`${API_BASE}/v1/routes/investigate?source_code=${sourceAsset.code}${sourceAsset.issuer ? `&source_issuer=${sourceAsset.issuer}` : ''}&dest_code=${destAsset.code}${destAsset.issuer ? `&dest_issuer=${destAsset.issuer}` : ''}`);
        if (diagRes.ok) {
          const diagData = await diagRes.json();
          setDiagnostics(diagData);
        }
      }

    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to fetch routes";
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

  // Validation state logic
  let btnDisabled = true;
  let validationMessage = "";

  if (!walletAddress) {
    validationMessage = "Connect wallet to discover executable routes.";
  } else if (!destAsset) {
    validationMessage = "Select a destination asset.";
  } else if (!amount || parseFloat(amount) <= 0) {
    validationMessage = "Enter a valid amount.";
  } else if (isBalanceInsufficient) {
    validationMessage = "Insufficient source balance.";
  } else if (!hasDestTrustline) {
    validationMessage = "Missing destination trustline.";
  } else {
    btnDisabled = false;
  }

  return (
    <div className="glass-card p-6">
      <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
        Smart Order Router
      </h2>

      {/* Search Form */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-2">
        <div className="md:col-span-1">
          <AssetSelector 
            label="Source Asset" 
            value={sourceAsset} 
            onChange={setSourceAsset} 
          />
          {walletAddress && sourceAsset && (
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
          {walletAddress && destAsset && (
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

      {/* Validation Warning */}
      {validationMessage && (
        <div className={`mb-6 text-xs px-2 ${btnDisabled && walletAddress ? 'text-[var(--color-warning)]' : 'text-[var(--color-text-muted)]'}`}>
          {validationMessage}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mb-4 px-4 py-3 rounded-lg bg-[var(--color-error)]/10 border border-[var(--color-error)]/20 text-[var(--color-error)] text-sm">
          {error}
        </div>
      )}

      {/* Diagnostics Panel */}
      {diagnostics && routes.length === 0 && !loading && (
        <div className="mt-6 border border-[var(--color-error)]/30 bg-[var(--color-error)]/5 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-[var(--color-error)] mb-3 flex items-center gap-2">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            Route Discovery Failed
          </h3>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4 font-medium uppercase tracking-wider">
            Reason: <span className="text-[var(--color-text-primary)]">{diagnostics.failure_reason}</span>
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            <div className="p-2 rounded bg-[var(--color-bg-elevated)]">
              <div className="text-[var(--color-text-muted)] mb-1">Source Degree</div>
              <div className="font-mono">{diagnostics.source_degree}</div>
            </div>
            <div className="p-2 rounded bg-[var(--color-bg-elevated)]">
              <div className="text-[var(--color-text-muted)] mb-1">Dest Degree</div>
              <div className="font-mono">{diagnostics.destination_degree}</div>
            </div>
            <div className="p-2 rounded bg-[var(--color-bg-elevated)]">
              <div className="text-[var(--color-text-muted)] mb-1">Component Match</div>
              <div className="font-mono">{diagnostics.same_component ? "Yes" : "No"}</div>
            </div>
            <div className="p-2 rounded bg-[var(--color-bg-elevated)]">
              <div className="text-[var(--color-text-muted)] mb-1">Paths Evaluated</div>
              <div className="font-mono">{diagnostics.candidate_paths_found}</div>
            </div>
          </div>
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
                          {route.path.map((hop, j) => (
                            <div key={j} className="flex items-center gap-1">
                              <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${hop.hop_type === "amm" ? "bg-[var(--color-success)]/10 text-[var(--color-success)]" : "bg-[var(--color-bg-card)] border border-[var(--color-border)]"}`}>
                                {hop.asset.code}
                              </span>
                              {j < route.path.length - 1 && (
                                <span className="text-[var(--color-text-muted)] text-xs">→</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </td>
                      <td className="py-3 px-2 font-medium">
                        {route.expected_output.toLocaleString(undefined, { maximumFractionDigits: 4 })}
                      </td>
                      <td className="py-3 px-2 text-[var(--color-text-secondary)]">
                        {(route.estimated_slippage * 100).toFixed(2)}%
                      </td>
                      <td className="py-3 px-2 text-[var(--color-text-secondary)]">
                        {route.estimated_fee.toFixed(4)}
                      </td>
                      <td className="py-3 px-2">
                        <div className="flex flex-col">
                          <span className={`text-xs font-semibold ${getRiskColor(route.risk?.risk_level)}`}>
                            {route.risk?.risk_level || "UNKNOWN"}
                          </span>
                          <span className="text-[10px] text-[var(--color-text-muted)]">
                            Score: {(route.risk?.risk_score ?? 0).toFixed(2)}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-2">
                        <span className="text-sm font-semibold text-[var(--color-accent)]">
                          {((route.execution_score ?? 0) * 100).toFixed(1)}
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
                            
                            {/* Validation & Explanation */}
                            <div className="space-y-4">
                              <div>
                                <h4 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider mb-2">Validation</h4>
                                <div className="p-3 rounded bg-[var(--color-bg-card)] border border-[var(--color-border)]">
                                  <div className="flex items-center gap-2 mb-2">
                                    <div className={`w-2 h-2 rounded-full ${route.validation?.valid ? 'bg-[var(--color-success)]' : 'bg-[var(--color-error)]'}`}></div>
                                    <span className="text-sm font-medium">{route.validation?.valid ? "Execution Ready" : "Validation Failed"}</span>
                                  </div>
                                  {!route.validation?.valid && (
                                    <p className="text-xs text-[var(--color-error)]">{route.validation?.reason}</p>
                                  )}
                                  <div className="mt-2 text-xs text-[var(--color-text-muted)]">
                                    Liquidity Sufficient: {route.validation?.liquidity_sufficient ? "Yes" : "No"}
                                  </div>
                                </div>
                              </div>
                              
                              <div>
                                <h4 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider mb-2">Simulation Impact</h4>
                                <div className="p-3 rounded bg-[var(--color-bg-card)] border border-[var(--color-border)] text-xs space-y-1">
                                  <div className="flex justify-between">
                                    <span className="text-[var(--color-text-muted)]">Price Impact</span>
                                    <span>{(route.simulation?.price_impact ?? 0 * 100).toFixed(2)}%</span>
                                  </div>
                                  <div className="flex justify-between">
                                    <span className="text-[var(--color-text-muted)]">Bottleneck Liquidity</span>
                                    <span>{route.total_liquidity.toLocaleString()}</span>
                                  </div>
                                  <div className="flex justify-between">
                                    <span className="text-[var(--color-text-muted)]">Confidence</span>
                                    <span>{((route.confidence_score ?? 0) * 100).toFixed(1)}%</span>
                                  </div>
                                </div>
                              </div>
                            </div>
                            
                            {/* Execution Plan */}
                            <div>
                              <h4 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider mb-2">Execution Plan</h4>
                              <div className="space-y-2">
                                {route.plan?.steps.map((step, idx) => (
                                  <div key={idx} className="p-3 rounded bg-[var(--color-bg-card)] border border-[var(--color-border)]">
                                    <div className="flex items-center justify-between mb-2">
                                      <span className="text-xs font-medium px-2 py-0.5 rounded bg-[var(--color-bg-elevated)]">
                                        Step {step.step_index + 1}
                                      </span>
                                      <span className="text-[10px] uppercase text-[var(--color-text-muted)] tracking-wider">
                                        {step.type.replace('_', ' ')}
                                      </span>
                                    </div>
                                    
                                    <div className="flex items-center justify-between text-sm">
                                      <div className="flex flex-col">
                                        <span className="font-medium text-[var(--color-error)]">-{step.expected_input.toFixed(4)}</span>
                                        <span className="text-xs text-[var(--color-text-muted)]">{step.input_asset.split(':')[0]}</span>
                                      </div>
                                      
                                      <svg className="w-4 h-4 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
                                      </svg>
                                      
                                      <div className="flex flex-col items-end">
                                        <span className="font-medium text-[var(--color-success)]">+{step.expected_output.toFixed(4)}</span>
                                        <span className="text-xs text-[var(--color-text-muted)]">{step.output_asset.split(':')[0]}</span>
                                      </div>
                                    </div>
                                    
                                    {step.pool_id && (
                                      <div className="mt-2 text-[10px] text-[var(--color-text-muted)] text-right font-mono">
                                        Pool: {step.pool_id.slice(0, 8)}...{step.pool_id.slice(-8)}
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
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
          <p className="text-sm">Configure assets and amount to generate execution plans</p>
        </div>
      )}
    </div>
  );
}
