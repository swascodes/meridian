"""Tests for Stellar client utilities."""

import pytest

from meridian_shared.stellar.client import (
    format_asset_identifier,
    parse_asset_identifier,
)


def test_parse_native():
    code, issuer = parse_asset_identifier("native")
    assert code == "XLM"
    assert issuer is None


def test_parse_xlm():
    code, issuer = parse_asset_identifier("XLM")
    assert code == "XLM"
    assert issuer is None


def test_parse_credit():
    code, issuer = parse_asset_identifier("USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN")
    assert code == "USDC"
    assert issuer == "GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN"


def test_parse_invalid():
    with pytest.raises(ValueError):
        parse_asset_identifier("INVALID_FORMAT_NO_COLON")


def test_format_native():
    assert format_asset_identifier("XLM", None) == "native"


def test_format_credit():
    result = format_asset_identifier("USDC", "GA5Z")
    assert result == "USDC:GA5Z"
