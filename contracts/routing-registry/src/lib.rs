#![no_std]

mod admin;
mod errors;
mod storage;
mod types;

use soroban_sdk::{contract, contractimpl, Address, BytesN, Env, String, Vec};

use crate::admin::require_admin;
use crate::errors::RegistryError;
use crate::storage::{
    get_route, has_route, remove_route, save_route, set_admin, get_all_route_keys,
};
use crate::types::RouteConfig;

#[contract]
pub struct RoutingRegistry;

#[contractimpl]
impl RoutingRegistry {
    /// Initialize the contract with an admin address.
    pub fn initialize(env: Env, admin: Address) {
        if storage::has_admin(&env) {
            panic!("already initialized");
        }
        set_admin(&env, &admin);
    }

    /// Register a new optimal route on-chain.
    ///
    /// Only callable by the admin.
    /// The route_key is a hash identifying the source->destination asset pair.
    pub fn register_route(
        env: Env,
        caller: Address,
        route_key: BytesN<32>,
        source_asset: String,
        destination_asset: String,
        path_hash: BytesN<32>,
        quality_score: u32,      // Score * 10000 (e.g., 9500 = 0.95)
        hop_count: u32,
    ) -> Result<(), RegistryError> {
        require_admin(&env, &caller)?;
        caller.require_auth();

        if quality_score > 10000 {
            return Err(RegistryError::InvalidScore);
        }
        if hop_count == 0 || hop_count > 6 {
            return Err(RegistryError::InvalidHopCount);
        }

        let config = RouteConfig {
            source_asset,
            destination_asset,
            path_hash,
            quality_score,
            hop_count,
            registered_at: env.ledger().timestamp(),
            last_updated_at: env.ledger().timestamp(),
            is_active: true,
        };

        save_route(&env, &route_key, &config);

        Ok(())
    }

    /// Get the registered route configuration for a given route key.
    pub fn get_route(env: Env, route_key: BytesN<32>) -> Result<RouteConfig, RegistryError> {
        get_route(&env, &route_key).ok_or(RegistryError::RouteNotFound)
    }

    /// Update an existing route's quality score and path.
    ///
    /// Only callable by the admin.
    pub fn update_route(
        env: Env,
        caller: Address,
        route_key: BytesN<32>,
        new_path_hash: BytesN<32>,
        new_quality_score: u32,
    ) -> Result<(), RegistryError> {
        require_admin(&env, &caller)?;
        caller.require_auth();

        let mut config = get_route(&env, &route_key).ok_or(RegistryError::RouteNotFound)?;

        if new_quality_score > 10000 {
            return Err(RegistryError::InvalidScore);
        }

        config.path_hash = new_path_hash;
        config.quality_score = new_quality_score;
        config.last_updated_at = env.ledger().timestamp();

        save_route(&env, &route_key, &config);

        Ok(())
    }

    /// Deactivate a registered route.
    ///
    /// Only callable by the admin.
    pub fn deactivate_route(
        env: Env,
        caller: Address,
        route_key: BytesN<32>,
    ) -> Result<(), RegistryError> {
        require_admin(&env, &caller)?;
        caller.require_auth();

        let mut config = get_route(&env, &route_key).ok_or(RegistryError::RouteNotFound)?;
        config.is_active = false;
        config.last_updated_at = env.ledger().timestamp();

        save_route(&env, &route_key, &config);

        Ok(())
    }

    /// Check if a route exists and is active.
    pub fn is_route_active(env: Env, route_key: BytesN<32>) -> bool {
        match get_route(&env, &route_key) {
            Some(config) => config.is_active,
            None => false,
        }
    }

    /// Remove a route entirely from storage.
    ///
    /// Only callable by the admin.
    pub fn remove_route(
        env: Env,
        caller: Address,
        route_key: BytesN<32>,
    ) -> Result<(), RegistryError> {
        require_admin(&env, &caller)?;
        caller.require_auth();

        if !has_route(&env, &route_key) {
            return Err(RegistryError::RouteNotFound);
        }

        remove_route(&env, &route_key);
        Ok(())
    }
}

#[cfg(test)]
mod test;
