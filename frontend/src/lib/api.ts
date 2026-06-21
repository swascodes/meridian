const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ApiError {
  detail: string;
  status: number;
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const error: ApiError = {
      detail: await res.text(),
      status: res.status,
    };
    throw error;
  }

  return res.json();
}

// ─── Routes ───

export interface AssetIdentifier {
  code: string;
  issuer: string | null;
}

export interface RouteHop {
  asset: AssetIdentifier;
  pool_id?: string;
  hop_type: string;
}

export interface RouteResult {
  route_hash: string;
  source_asset: AssetIdentifier;
  destination_asset: AssetIdentifier;
  path: RouteHop[];
  hop_count: number;
  estimated_rate: number;
  estimated_slippage: number;
  total_liquidity: number;
  quality_score: number | null;
  discovered_at: string;
}

export interface RouteSimulationResult {
  route: RouteResult;
  input_amount: number;
  expected_output: number;
  estimated_slippage: number;
  price_impact: number;
  execution_probability: number;
  warnings: string[];
}

export interface GraphStats {
  total_nodes: number;
  total_edges: number;
  total_assets: number;
  total_pools: number;
  avg_degree: number;
  density: number;
  connected_components: number;
  last_updated_at: string;
}

export interface ServiceHealth {
  service: string;
  status: string;
  version: string;
  timestamp: string;
}

// ─── API Functions ───

export const api = {
  routes: {
    find: (source: string, dest: string, amount = 100) =>
      apiFetch<RouteResult[]>(
        `/v1/routes/${encodeURIComponent(source)}/${encodeURIComponent(dest)}?amount=${amount}`
      ),

    alternatives: (source: string, dest: string, amount = 100) =>
      apiFetch<RouteResult[]>(
        `/v1/routes/${encodeURIComponent(source)}/${encodeURIComponent(dest)}/alternatives?amount=${amount}`
      ),

    simulate: (body: {
      source_asset: AssetIdentifier;
      destination_asset: AssetIdentifier;
      amount: number;
      max_hops?: number;
      slippage_tolerance?: number;
    }) =>
      apiFetch<RouteSimulationResult>("/v1/routes/simulate", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },

  graph: {
    stats: () => apiFetch<GraphStats>("/v1/graph/stats"),
  },

  health: {
    check: () => apiFetch<ServiceHealth>("/health"),
  },
};
