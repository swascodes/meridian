"""Asset models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class AssetType(str, Enum):
    NATIVE = "native"
    CREDIT_ALPHANUM4 = "credit_alphanum4"
    CREDIT_ALPHANUM12 = "credit_alphanum12"


class AssetIdentifier(BaseModel):
    """Lightweight asset reference."""
    code: str = Field(..., max_length=12)
    issuer: str | None = Field(None, max_length=56)

    @property
    def canonical(self) -> str:
        return f"{self.code}:{self.issuer}" if self.issuer else "native"


class AssetDetail(AssetIdentifier):
    """Full asset information."""
    id: UUID
    asset_type: AssetType
    domain: str | None = None
    is_verified: bool = False
    total_trustlines: int = 0
    total_volume_24h: float = 0.0
    first_seen_at: datetime
    last_seen_at: datetime
