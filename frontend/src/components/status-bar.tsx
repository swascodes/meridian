"use client";

import { useState, useEffect } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ServiceStatus {
  name: string;
  url: string;
  healthy: boolean | null;
}

const SERVICES: Omit<ServiceStatus, "healthy">[] = [
  { name: "API", url: `${API_BASE}/health` },
  { name: "Graph", url: "http://localhost:8001/health" },
  { name: "Optimizer", url: "http://localhost:8002/health" },
  { name: "Oracle", url: "http://localhost:8003/health" },
  { name: "Ingestion", url: "http://localhost:8005/health" },
];

export function StatusBar() {
  const [services, setServices] = useState<ServiceStatus[]>(
    SERVICES.map((s) => ({ ...s, healthy: null }))
  );

  useEffect(() => {
    const check = async () => {
      const results = await Promise.all(
        SERVICES.map(async (s) => {
          try {
            const res = await fetch(s.url, { signal: AbortSignal.timeout(3000) });
            return { ...s, healthy: res.ok };
          } catch {
            return { ...s, healthy: false };
          }
        })
      );
      setServices(results);
    };

    check();
    const interval = setInterval(check, 15000);
    return () => clearInterval(interval);
  }, []);

  const healthyCount = services.filter((s) => s.healthy).length;

  return (
    <div className="max-w-7xl mx-auto px-6 mb-8">
      <div className="flex items-center gap-6 px-4 py-2 rounded-lg bg-[var(--color-bg-secondary)] border border-[var(--color-border)] overflow-x-auto">
        <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] whitespace-nowrap">
          <div
            className={`w-2 h-2 rounded-full ${
              healthyCount === SERVICES.length
                ? "bg-[var(--color-success)]"
                : healthyCount > 0
                ? "bg-[var(--color-warning)]"
                : "bg-[var(--color-error)]"
            } animate-pulse-live`}
          />
          {healthyCount}/{SERVICES.length} services
        </div>
        <div className="h-4 w-px bg-[var(--color-border)]" />
        {services.map((s) => (
          <div key={s.name} className="flex items-center gap-1.5 text-xs whitespace-nowrap">
            <div
              className={`w-1.5 h-1.5 rounded-full ${
                s.healthy === null
                  ? "bg-[var(--color-text-muted)]"
                  : s.healthy
                  ? "bg-[var(--color-success)]"
                  : "bg-[var(--color-error)]"
              }`}
            />
            <span className="text-[var(--color-text-muted)]">{s.name}</span>
          </div>
        ))}
        <div className="ml-auto flex items-center gap-1.5 text-xs text-[var(--color-text-muted)] whitespace-nowrap">
          <span>Stellar Testnet</span>
        </div>
      </div>
    </div>
  );
}
