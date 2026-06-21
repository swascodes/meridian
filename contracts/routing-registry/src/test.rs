#![cfg(test)]

use soroban_sdk::{testutils::Address as _, Address, BytesN, Env, String};

use crate::{RoutingRegistry, RoutingRegistryClient};

fn setup_test() -> (Env, RoutingRegistryClient<'static>, Address) {
    let env = Env::default();
    env.mock_all_auths();

    let contract_id = env.register(RoutingRegistry, ());
    let client = RoutingRegistryClient::new(&env, &contract_id);

    let admin = Address::generate(&env);
    client.initialize(&admin);

    (env, client, admin)
}

#[test]
fn test_register_and_get_route() {
    let (env, client, admin) = setup_test();

    let route_key = BytesN::from_array(&env, &[1u8; 32]);
    let path_hash = BytesN::from_array(&env, &[2u8; 32]);
    let source = String::from_str(&env, "XLM:native");
    let dest = String::from_str(&env, "USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN");

    client.register_route(
        &admin,
        &route_key,
        &source,
        &dest,
        &path_hash,
        &9500,
        &2,
    );

    let config = client.get_route(&route_key);
    assert_eq!(config.quality_score, 9500);
    assert_eq!(config.hop_count, 2);
    assert!(config.is_active);
}

#[test]
fn test_update_route() {
    let (env, client, admin) = setup_test();

    let route_key = BytesN::from_array(&env, &[1u8; 32]);
    let path_hash = BytesN::from_array(&env, &[2u8; 32]);
    let source = String::from_str(&env, "XLM:native");
    let dest = String::from_str(&env, "USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN");

    client.register_route(&admin, &route_key, &source, &dest, &path_hash, &8000, &3);

    let new_path_hash = BytesN::from_array(&env, &[3u8; 32]);
    client.update_route(&admin, &route_key, &new_path_hash, &9200);

    let config = client.get_route(&route_key);
    assert_eq!(config.quality_score, 9200);
    assert_eq!(config.path_hash, new_path_hash);
}

#[test]
fn test_deactivate_route() {
    let (env, client, admin) = setup_test();

    let route_key = BytesN::from_array(&env, &[1u8; 32]);
    let path_hash = BytesN::from_array(&env, &[2u8; 32]);
    let source = String::from_str(&env, "XLM:native");
    let dest = String::from_str(&env, "USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN");

    client.register_route(&admin, &route_key, &source, &dest, &path_hash, &9000, &2);

    assert!(client.is_route_active(&route_key));

    client.deactivate_route(&admin, &route_key);

    assert!(!client.is_route_active(&route_key));
}

#[test]
fn test_remove_route() {
    let (env, client, admin) = setup_test();

    let route_key = BytesN::from_array(&env, &[1u8; 32]);
    let path_hash = BytesN::from_array(&env, &[2u8; 32]);
    let source = String::from_str(&env, "XLM:native");
    let dest = String::from_str(&env, "USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN");

    client.register_route(&admin, &route_key, &source, &dest, &path_hash, &9000, &2);
    client.remove_route(&admin, &route_key);

    // Should fail to get removed route
    assert!(!client.is_route_active(&route_key));
}

#[test]
#[should_panic(expected = "Error(Contract, #3)")]
fn test_invalid_score() {
    let (env, client, admin) = setup_test();

    let route_key = BytesN::from_array(&env, &[1u8; 32]);
    let path_hash = BytesN::from_array(&env, &[2u8; 32]);
    let source = String::from_str(&env, "XLM:native");
    let dest = String::from_str(&env, "USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN");

    client.register_route(&admin, &route_key, &source, &dest, &path_hash, &15000, &2);
}

#[test]
#[should_panic(expected = "Error(Contract, #4)")]
fn test_invalid_hop_count() {
    let (env, client, admin) = setup_test();

    let route_key = BytesN::from_array(&env, &[1u8; 32]);
    let path_hash = BytesN::from_array(&env, &[2u8; 32]);
    let source = String::from_str(&env, "XLM:native");
    let dest = String::from_str(&env, "USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN");

    client.register_route(&admin, &route_key, &source, &dest, &path_hash, &9000, &7);
}
