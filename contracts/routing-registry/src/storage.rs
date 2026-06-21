use soroban_sdk::{contracttype, Address, BytesN, Env};

use crate::types::RouteConfig;

#[contracttype]
pub enum DataKey {
    Admin,
    Route(BytesN<32>),
    RouteKeys,
}

/// Check if an admin has been set.
pub fn has_admin(env: &Env) -> bool {
    env.storage().instance().has(&DataKey::Admin)
}

/// Set the admin address.
pub fn set_admin(env: &Env, admin: &Address) {
    env.storage().instance().set(&DataKey::Admin, admin);
}

/// Get the admin address.
pub fn get_admin(env: &Env) -> Option<Address> {
    env.storage().instance().get(&DataKey::Admin)
}

/// Save a route configuration.
pub fn save_route(env: &Env, route_key: &BytesN<32>, config: &RouteConfig) {
    env.storage()
        .persistent()
        .set(&DataKey::Route(route_key.clone()), config);

    // Extend TTL to ~30 days (assuming 5-second ledger close)
    env.storage().persistent().extend_ttl(
        &DataKey::Route(route_key.clone()),
        518400,  // 30 days in ledgers
        518400,
    );
}

/// Get a route configuration.
pub fn get_route(env: &Env, route_key: &BytesN<32>) -> Option<RouteConfig> {
    env.storage()
        .persistent()
        .get(&DataKey::Route(route_key.clone()))
}

/// Check if a route exists.
pub fn has_route(env: &Env, route_key: &BytesN<32>) -> bool {
    env.storage()
        .persistent()
        .has(&DataKey::Route(route_key.clone()))
}

/// Remove a route from storage.
pub fn remove_route(env: &Env, route_key: &BytesN<32>) {
    env.storage()
        .persistent()
        .remove(&DataKey::Route(route_key.clone()));
}

/// Get all stored route keys (for enumeration).
pub fn get_all_route_keys(env: &Env) -> Option<soroban_sdk::Vec<BytesN<32>>> {
    env.storage().instance().get(&DataKey::RouteKeys)
}
