"use client";

import { useState, useEffect } from "react";
import { WalletConnect } from "@/components/wallet-connect";
import { RouteExplorer } from "@/components/route-explorer";
import { NetworkStats } from "@/components/network-stats";
import { StatusBar } from "@/components/status-bar";

export default function Home() {
  const [walletAddress, setWalletAddress] = useState<string | null>(null);

  return (
    <div className="min-h-screen gradient-mesh">
      {/* Header */}
      <header className="border-b border-[var(--color-border)] bg-[var(--color-bg-primary)]/80 backdrop-blur-lg sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--color-accent)] to-[var(--color-success)] flex items-center justify-center">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/>
                <path d="M2 12h20"/>
              </svg>
            </div>
            <span className="text-lg font-semibold tracking-tight">Meridian</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--color-accent)]/10 text-[var(--color-accent)] font-medium">
              Phase 1
            </span>
          </div>

          <nav className="hidden md:flex items-center gap-8">
            <a href="#routes" className="text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors">
              Route Explorer
            </a>
            <a href="#network" className="text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors">
              Network
            </a>
            <a href="http://localhost:8000/docs" target="_blank" className="text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors">
              API Docs
            </a>
          </nav>

          <WalletConnect
            address={walletAddress}
            onConnect={setWalletAddress}
          />
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-6 pt-20 pb-16">
        <div className="max-w-2xl">
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight leading-tight">
            Route Intelligence
            <br />
            <span className="bg-gradient-to-r from-[var(--color-accent)] to-[var(--color-success)] bg-clip-text text-transparent">
              for Stellar
            </span>
          </h1>
          <p className="mt-4 text-lg text-[var(--color-text-secondary)] leading-relaxed max-w-lg">
            Find the highest-quality paths for value transfer. Powered by real-time
            liquidity analysis, historical execution data, and predictive routing.
          </p>
        </div>
      </section>

      {/* Status Bar */}
      <StatusBar />

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 pb-20 space-y-8">
        <section id="routes">
          <RouteExplorer />
        </section>

        <section id="network">
          <NetworkStats />
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-[var(--color-border)] py-8">
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between text-sm text-[var(--color-text-muted)]">
          <span>© 2026 Meridian. Built on Stellar.</span>
          <div className="flex gap-6">
            <a href="http://localhost:8000/docs" target="_blank" className="hover:text-[var(--color-text-secondary)] transition-colors">
              API
            </a>
            <a href="https://github.com" target="_blank" className="hover:text-[var(--color-text-secondary)] transition-colors">
              GitHub
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
