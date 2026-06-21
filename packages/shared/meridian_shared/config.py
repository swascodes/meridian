"""Centralized configuration via pydantic-settings."""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class StellarNetwork(str, Enum):
    MAINNET = "mainnet"
    TESTNET = "testnet"
    FUTURENET = "futurenet"
    STANDALONE = "standalone"


_HORIZON_URLS: dict[StellarNetwork, str] = {
    StellarNetwork.MAINNET: "https://horizon.stellar.org",
    StellarNetwork.TESTNET: "https://horizon-testnet.stellar.org",
    StellarNetwork.FUTURENET: "https://horizon-futurenet.stellar.org",
    StellarNetwork.STANDALONE: "http://localhost:8000",
}

_SOROBAN_URLS: dict[StellarNetwork, str] = {
    StellarNetwork.MAINNET: "https://soroban-rpc.mainnet.stellar.gateway.fm",
    StellarNetwork.TESTNET: "https://soroban-testnet.stellar.org",
    StellarNetwork.FUTURENET: "https://rpc-futurenet.stellar.org",
    StellarNetwork.STANDALONE: "http://localhost:8000/soroban/rpc",
}

_NETWORK_PASSPHRASES: dict[StellarNetwork, str] = {
    StellarNetwork.MAINNET: "Public Global Stellar Network ; September 2015",
    StellarNetwork.TESTNET: "Test SDF Network ; September 2015",
    StellarNetwork.FUTURENET: "Test SDF Future Network ; October 2022",
    StellarNetwork.STANDALONE: "Standalone Network ; February 2017",
}


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Database ───
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://meridian:meridian_dev_password@postgres:5432/meridian"
    )
    db_pool_size: int = Field(default=20)
    db_max_overflow: int = Field(default=10)
    db_pool_timeout: int = Field(default=30)
    db_echo: bool = Field(default=False)

    # ─── Redis ───
    redis_url: RedisDsn = Field(default="redis://redis:6379/0")
    redis_max_connections: int = Field(default=50)

    # ─── Stellar ───
    stellar_network: StellarNetwork = Field(default=StellarNetwork.TESTNET)
    stellar_horizon_url: str = Field(default="")
    stellar_soroban_rpc_url: str = Field(default="")
    stellar_network_passphrase: str = Field(default="")

    # ─── Service URLs ───
    graph_engine_url: str = Field(default="http://graph-engine:8001")
    route_optimizer_url: str = Field(default="http://route-optimizer:8002")
    quality_oracle_url: str = Field(default="http://quality-oracle:8003")
    predictive_engine_url: str = Field(default="http://predictive-engine:8004")
    ingestion_url: str = Field(default="http://ingestion:8005")

    # ─── Auth ───
    jwt_secret: str = Field(default="change-this-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiration_minutes: int = Field(default=60)
    api_key_header: str = Field(default="X-Meridian-API-Key")

    # ─── Logging ───
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")

    # ─── Ingestion ───
    ingestion_orderbook_poll_interval: int = Field(default=30)
    ingestion_pool_sync_interval: int = Field(default=60)
    ingestion_asset_discovery_interval: int = Field(default=300)
    ingestion_max_orderbook_depth: int = Field(default=50)

    def model_post_init(self, __context: object) -> None:
        """Resolve Stellar URLs from network if not explicitly set."""
        if not self.stellar_horizon_url:
            self.stellar_horizon_url = _HORIZON_URLS[self.stellar_network]
        if not self.stellar_soroban_rpc_url:
            self.stellar_soroban_rpc_url = _SOROBAN_URLS[self.stellar_network]
        if not self.stellar_network_passphrase:
            self.stellar_network_passphrase = _NETWORK_PASSPHRASES[self.stellar_network]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
