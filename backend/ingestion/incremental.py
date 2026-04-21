"""SHA256-based duplicate detection and change detection for re-ingestion."""

import hashlib

import structlog

from backend.storage.sqlite_db import SQLiteDB

logger = structlog.get_logger().bind(component=__name__)


class IncrementalChecker:
    """SHA256-based duplicate detection and change detection for re-ingestion."""

    def __init__(self, db: SQLiteDB):
        self.db = db

    @staticmethod
    def compute_file_hash(file_path: str) -> str:
        """Compute SHA256 hex digest of file content, reading in 8KB blocks."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                sha256.update(block)
        return sha256.hexdigest()

    async def check_duplicate(self, collection_id: str, file_hash: str) -> tuple[bool, str | None]:
        """Check if a document with this hash already exists (completed) in the collection.

        Returns (is_duplicate, existing_document_id).
        A document with status 'failed' is NOT a duplicate (allows re-ingestion per FR-004).
        """
        result = await self.db.get_document_by_hash(collection_id, file_hash)
        if result is None:
            return (False, None)

        if result["status"] == "completed":
            logger.info(
                "ingestion_duplicate_detected",
                collection_id=collection_id,
                existing_doc_id=result["id"],
            )
            return (True, result["id"])

        # Failed or other non-completed status: not a duplicate
        return (False, None)

    async def check_change(self, collection_id: str, filename: str, new_hash: str) -> tuple[bool, str | None]:
        """Check if a document with the same filename but different hash exists.

        Returns (is_changed, old_document_id).
        If changed, the caller should delete old vectors and re-ingest (FR-005).
        """
        cursor = await self.db.db.execute(
            "SELECT id, file_hash FROM documents WHERE collection_id = ? AND filename = ? AND file_hash != ? AND status = 'completed'",
            (collection_id, filename, new_hash),
        )
        row = await cursor.fetchone()
        if row is None:
            return (False, None)

        logger.info(
            "ingestion_change_detected",
            collection_id=collection_id,
            filename=filename,
            old_doc_id=row["id"],
        )
        return (True, row["id"])
