"use client";

import React, { useState, useEffect, useRef } from "react";

interface Asset {
  node_id: string;
  code: string;
  issuer: string | null;
  domain: string | null;
  trustlines: number;
  degree: number;
}

interface AssetSelectorProps {
  label: string;
  value: { code: string; issuer: string | null } | null;
  onChange: (asset: { code: string; issuer: string | null }) => void;
  placeholder?: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function AssetSelector({ label, value, onChange, placeholder = "Search asset..." }: AssetSelectorProps) {
  const [query, setQuery] = useState("");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Click outside to close
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (!isOpen) return;

    let isCancelled = false;
    let timeoutId: ReturnType<typeof setTimeout>;

    const fetchAssets = async (retryCount = 0) => {
      if (!isCancelled) setLoading(true);
      if (retryCount > 0 && !isCancelled) setRetrying(true);

      try {
        const res = await fetch(`${API_BASE}/v1/graph/assets?limit=50${query ? `&q=${encodeURIComponent(query)}` : ""}`);
        if (isCancelled) return;

        if (res.ok) {
          const data = await res.json();
          setAssets(data.assets || []);
          setRetrying(false);
          setLoading(false);
        } else if (res.status === 502 || res.status === 503) {
          // Graph initializing, retry with exponential backoff
          const delay = Math.min(1000 * Math.pow(1.5, retryCount), 10000);
          timeoutId = setTimeout(() => fetchAssets(retryCount + 1), delay);
        } else {
          setAssets([]);
          setRetrying(false);
          setLoading(false);
        }
      } catch (err) {
        if (isCancelled) return;
        console.error("Failed to fetch assets", err);
        // Retry on network errors
        const delay = Math.min(1000 * Math.pow(1.5, retryCount), 10000);
        timeoutId = setTimeout(() => fetchAssets(retryCount + 1), delay);
      }
    };

    timeoutId = setTimeout(() => fetchAssets(0), 300);

    return () => {
      isCancelled = true;
      clearTimeout(timeoutId);
    };
  }, [query, isOpen]);

  const displayValue = value ? `${value.code}${value.issuer ? ` (${value.issuer.slice(0,4)}...${value.issuer.slice(-4)})` : ""}` : "";

  return (
    <div className="relative" ref={wrapperRef}>
      <label className="block text-xs text-[var(--color-text-muted)] mb-1.5">{label}</label>
      <div 
        onClick={() => setIsOpen(true)}
        className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--color-border)] text-sm focus-within:border-[var(--color-accent)] transition-colors cursor-text flex items-center justify-between"
      >
        {isOpen ? (
          <input
            autoFocus
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={placeholder}
            className="w-full bg-transparent focus:outline-none text-sm"
          />
        ) : (
          <span className={value ? "" : "text-[var(--color-text-muted)]"}>
            {value ? displayValue : placeholder}
          </span>
        )}
        <svg className="w-4 h-4 text-[var(--color-text-muted)] ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
        </svg>
      </div>

      {isOpen && (
        <div className="absolute z-50 w-full mt-1 bg-[var(--color-bg-elevated)] border border-[var(--color-border)] rounded-lg shadow-xl max-h-60 overflow-y-auto">
          {retrying && assets.length === 0 ? (
            <div className="p-3 text-xs text-center text-[var(--color-warning)] animate-pulse">Graph initializing... (Retrying)</div>
          ) : loading && assets.length === 0 ? (
            <div className="p-3 text-xs text-center text-[var(--color-text-muted)]">Loading assets...</div>
          ) : assets.length === 0 ? (
            <div className="p-3 text-xs text-center text-[var(--color-text-muted)]">No active assets found</div>
          ) : (
            <ul className="py-1">
              {assets.map((asset) => (
                <li 
                  key={asset.node_id}
                  onClick={() => {
                    onChange({ code: asset.code, issuer: asset.issuer });
                    setIsOpen(false);
                    setQuery("");
                  }}
                  className="px-3 py-2 hover:bg-[var(--color-bg-card)] cursor-pointer flex items-center justify-between group"
                >
                  <div className="flex flex-col">
                    <span className="text-sm font-medium">{asset.code}</span>
                    {asset.issuer ? (
                      <span className="text-[10px] text-[var(--color-text-muted)] font-mono">
                        {asset.issuer.slice(0,8)}...{asset.issuer.slice(-8)}
                      </span>
                    ) : (
                      <span className="text-[10px] text-[var(--color-success)] font-mono">Native</span>
                    )}
                  </div>
                  <div className="flex flex-col items-end">
                    <span className="text-[10px] text-[var(--color-text-muted)] group-hover:text-[var(--color-accent)] transition-colors">
                      Degree: {asset.degree}
                    </span>
                    {asset.domain && (
                      <span className="text-[10px] text-[var(--color-text-muted)]">{asset.domain}</span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
