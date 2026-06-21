use soroban_sdk::{Address, Env};

use crate::errors::RegistryError;
use crate::storage::get_admin;

/// Verify that the caller is the contract admin.
pub fn require_admin(env: &Env, caller: &Address) -> Result<(), RegistryError> {
    let admin = get_admin(env).ok_or(RegistryError::NotInitialized)?;
    if *caller != admin {
        return Err(RegistryError::Unauthorized);
    }
    Ok(())
}
