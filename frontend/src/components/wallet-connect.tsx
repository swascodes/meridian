"use client";

import { useState, useCallback } from "react";

interface WalletConnectProps {
  address: string | null;
  onConnect: (address: string | null) => void;
}

export function WalletConnect({ address, onConnect }: WalletConnectProps) {
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const connect = useCallback(async () => {
    setIsConnecting(true);
    setError(null);

    try {
      // Dynamic import to avoid SSR issues
      const freighter = await import("@stellar/freighter-api");

      const { address: addr } = await freighter.requestAccess();
      onConnect(addr);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to connect wallet";
      setError(message);
      console.error("Wallet connection error:", err);
    } finally {
      setIsConnecting(false);
    }
  }, [onConnect]);

  const disconnect = useCallback(() => {
    onConnect(null);
  }, [onConnect]);

  if (address) {
    return (
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--color-bg-card)] border border-[var(--color-border)]">
          <div className="w-2 h-2 rounded-full bg-[var(--color-success)] animate-pulse-live" />
          <span className="text-sm font-mono text-[var(--color-text-secondary)]">
            {address.slice(0, 4)}...{address.slice(-4)}
          </span>
        </div>
        <button
          onClick={disconnect}
          className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-error)] transition-colors"
        >
          Disconnect
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={connect}
        disabled={isConnecting}
        className="px-4 py-2 rounded-lg bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white text-sm font-medium transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed glow-accent"
      >
        {isConnecting ? (
          <span className="flex items-center gap-2">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Connecting...
          </span>
        ) : (
          "Connect Wallet"
        )}
      </button>
      {error && (
        <span className="text-xs text-[var(--color-error)]">{error}</span>
      )}
    </div>
  );
}
