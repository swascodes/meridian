"""Cursor manager — persistent stream cursor tracking."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from meridian_shared.db import IngestionCursor, get_session

logger = structlog.get_logger()


class CursorManager:
    """Manages persistent cursor positions for resumable streams."""

    def __init__(self, stream_name: str) -> None:
        self.stream_name = stream_name

    async def get_cursor(self) -> str | None:
        """Retrieve the last saved cursor for this stream."""
        async with get_session() as session:
            stmt = select(IngestionCursor).where(IngestionCursor.stream_name == self.stream_name)
            result = await session.execute(stmt)
            cursor = result.scalar_one_or_none()
            return cursor.cursor_value if cursor else None

    async def save_cursor(self, cursor_value: str) -> None:
        """Save or update the cursor position."""
        async with get_session() as session:
            stmt = select(IngestionCursor).where(IngestionCursor.stream_name == self.stream_name)
            result = await session.execute(stmt)
            cursor = result.scalar_one_or_none()

            if cursor:
                cursor.cursor_value = cursor_value
                cursor.updated_at = datetime.now(timezone.utc)
            else:
                session.add(IngestionCursor(
                    stream_name=self.stream_name,
                    cursor_value=cursor_value,
                ))

        logger.debug("cursor_saved", stream=self.stream_name, cursor=cursor_value)
