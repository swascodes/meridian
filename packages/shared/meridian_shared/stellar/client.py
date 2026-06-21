"""Stellar SDK client wrapper."""

from __future__ import annotations

from functools import lru_cache

from stellar_sdk import Server
from stellar_sdk.sep.stellar_toml import fetch_stellar_toml

from meridian_shared.config import get_settings


@lru_cache(maxsize=1)
def get_horizon_client() -> Server:
    """Get a cached Horizon server client."""
    settings = get_settings()
    return Server(horizon_url=settings.stellar_horizon_url)


def get_network_passphrase() -> str:
    """Get the network passphrase for transaction signing."""
    return get_settings().stellar_network_passphrase


def parse_asset_identifier(asset_str: str) -> tuple[str, str | None]:
    """Parse 'CODE:ISSUER' or 'native' into (code, issuer|None)."""
    if asset_str.lower() == "native" or asset_str.upper() == "XLM":
        return ("XLM", None)
    parts = asset_str.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid asset identifier: {asset_str}. Expected 'CODE:ISSUER' or 'native'.")
    return (parts[0], parts[1])


def format_asset_identifier(code: str, issuer: str | None) -> str:
    """Format asset into canonical string representation."""
    if issuer is None:
        return "native"
    return f"{code}:{issuer}"


async def resolve_asset_domain(issuer: str) -> str | None:
    """Attempt to resolve the home domain for an asset issuer."""
    try:
        settings = get_settings()
        server = Server(horizon_url=settings.stellar_horizon_url)
        account = server.accounts().account_id(issuer).call()
        home_domain = account.get("home_domain")
        if home_domain:
            return home_domain
    except Exception:
        pass
    return None


async def fetch_asset_toml(domain: str) -> dict | None:
    """Fetch and parse the stellar.toml for a domain."""
    try:
        toml_data = fetch_stellar_toml(domain)
        return dict(toml_data)  # type: ignore[arg-type]
    except Exception:
        return None
