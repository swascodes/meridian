use soroban_sdk::contracterror;

#[contracterror]
#[derive(Copy, Clone, Debug, Eq, PartialEq, PartialOrd, Ord)]
#[repr(u32)]
pub enum RegistryError {
    /// Caller is not the contract admin
    Unauthorized = 1,
    /// Route not found in registry
    RouteNotFound = 2,
    /// Quality score must be 0-10000
    InvalidScore = 3,
    /// Hop count must be 1-6
    InvalidHopCount = 4,
    /// Route already exists (use update instead)
    RouteAlreadyExists = 5,
    /// Contract not initialized
    NotInitialized = 6,
}
