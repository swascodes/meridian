use soroban_sdk::{contracttype, BytesN, String};

/// On-chain route configuration stored in the registry.
#[contracttype]
#[derive(Clone, Debug)]
pub struct RouteConfig {
    /// Canonical asset identifier for the source (e.g., "XLM:native" or "USDC:GA5ZS...")
    pub source_asset: String,
    /// Canonical asset identifier for the destination
    pub destination_asset: String,
    /// SHA-256 hash of the full path specification
    pub path_hash: BytesN<32>,
    /// Quality score scaled by 10000 (e.g., 9500 = 0.9500)
    pub quality_score: u32,
    /// Number of intermediate hops
    pub hop_count: u32,
    /// Ledger timestamp when first registered
    pub registered_at: u64,
    /// Ledger timestamp of last update
    pub last_updated_at: u64,
    /// Whether this route is currently active
    pub is_active: bool,
}
