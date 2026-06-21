"""Tests for config module."""

import pytest

from meridian_shared.config import Settings, StellarNetwork


def test_default_settings():
    settings = Settings()
    assert settings.stellar_network == StellarNetwork.TESTNET
    assert settings.db_pool_size == 20
    assert settings.log_level == "INFO"


def test_stellar_url_resolution():
    settings = Settings(stellar_network=StellarNetwork.TESTNET)
    assert "testnet" in settings.stellar_horizon_url


def test_mainnet_passphrase():
    settings = Settings(stellar_network=StellarNetwork.MAINNET)
    assert "Public Global" in settings.stellar_network_passphrase
