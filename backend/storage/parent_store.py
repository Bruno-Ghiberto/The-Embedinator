"""Parent chunk reads from SQLite.

Follows existing SQLiteDB patterns from backend/storage/sqlite_db.py.
Uses aiosqlite async connection from the shared DB instance.
"""

from __future__ import annotations

import structlog

from backend.agent.schemas import ParentChunk
from backend.errors import SQLiteError

logger = structlog.get_logger().bind(component=__name__)


class ParentStore:
    """Read parent chunks from SQLite parent_chunks table."""

    def __init__(self, db):
        """Initialize with the shared SQLiteDB instance.

        Args:
            db: An SQLiteDB instance (backend/storage/sqlite_db.py).
        """
        self.db = db

    async def get_by_ids(self, parent_ids: list[str]) -> list[ParentChunk]:
        """Fetch parent chunks by ID list.

        Args:
            parent_ids: List of parent chunk UUIDs.

        Returns:
            List of ParentChunk objects. Missing IDs are silently skipped.

        Raises:
            SQLiteError: If database read fails.
        """
        if not parent_ids:
            return []

        try:
            placeholders = ",".join("?" for _ in parent_ids)
            cursor = await self.db.db.execute(
                f"SELECT id AS parent_id, text, source_file, page, breadcrumb, collection_id AS collection "
                f"FROM parent_chunks WHERE id IN ({placeholders})",
                parent_ids,
            )
            rows = await cursor.fetchall()

            results = [
                ParentChunk(
                    parent_id=row["parent_id"],
                    text=row["text"],
                    source_file=row["source_file"],
                    page=row["page"],
                    breadcrumb=row["breadcrumb"],
                    collection=row["collection"],
                )
                for row in rows
            ]

            logger.info("storage_parent_chunks_fetched", requested=len(parent_ids), found=len(results))
            return results

        except Exception as exc:
            logger.warning("storage_parent_store_read_failed", error=str(exc))
            raise SQLiteError(f"Failed to fetch parent chunks: {exc}") from exc

    async def get_all_by_collection(self, collection_id: str) -> list[ParentChunk]:
        """Retrieve all parent chunks for a collection.

        Args:
            collection_id: The collection UUID to filter by.

        Returns:
            List of ParentChunk objects for that collection.

        Raises:
            SQLiteError: If database read fails.
        """
        try:
            cursor = await self.db.db.execute(
                "SELECT id AS parent_id, text, source_file, page, breadcrumb, collection_id AS collection "
                "FROM parent_chunks WHERE collection_id = ?",
                (collection_id,),
            )
            rows = await cursor.fetchall()

            results = [
                ParentChunk(
                    parent_id=row["parent_id"],
                    text=row["text"],
                    source_file=row["source_file"],
                    page=row["page"],
                    breadcrumb=row["breadcrumb"],
                    collection=row["collection"],
                )
                for row in rows
            ]

            logger.info(
                "parent_chunks_by_collection_fetched",
                collection_id=collection_id,
                found=len(results),
            )
            return results

        except Exception as exc:
            logger.warning("storage_parent_store_collection_read_failed", error=str(exc))
            raise SQLiteError(f"Failed to fetch parent chunks by collection: {exc}") from exc
