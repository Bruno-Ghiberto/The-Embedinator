"""Ingestion pipeline: orchestrates parse -> chunk -> embed -> store flow."""

import asyncio
import json
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import structlog

from backend.config import settings
from backend.errors import CircuitOpenError
from backend.ingestion.chunker import ChunkSplitter
from backend.ingestion.embedder import BatchEmbedder
from backend.ingestion.incremental import IncrementalChecker
from backend.storage.qdrant_client import QdrantClientWrapper
from backend.storage.sqlite_db import SQLiteDB

logger = structlog.get_logger().bind(component=__name__)


class UpsertBuffer:
    """Buffer for Qdrant points when upsert fails due to outages (FR-012).

    Holds up to MAX_CAPACITY points. When full, signals the caller to pause.
    """

    MAX_CAPACITY = 1000

    def __init__(self) -> None:
        self._buffer: list[dict] = []

    def add(self, points: list[dict]) -> bool:
        """Add points to buffer. Returns False if buffer is at capacity."""
        self._buffer.extend(points)
        if len(self._buffer) >= self.MAX_CAPACITY:
            return False
        return True

    async def flush(
        self, qdrant: QdrantClientWrapper, collection_id: str
    ) -> int:
        """Batch upsert all buffered points and clear buffer.

        Returns count of points flushed.
        """
        if not self._buffer:
            return 0
        batch_size = settings.qdrant_upsert_batch_size
        flushed = 0
        for i in range(0, len(self._buffer), batch_size):
            batch = self._buffer[i : i + batch_size]
            await qdrant.upsert(collection_id, batch)
            flushed += len(batch)
        self._buffer.clear()
        return flushed

    @property
    def pending_count(self) -> int:
        """Return current buffer size."""
        return len(self._buffer)


@dataclass
class IngestionResult:
    """Result of a completed ingestion job."""

    document_id: str
    job_id: str
    status: str
    chunks_processed: int = 0
    chunks_skipped: int = 0
    error: str | None = None


class IngestionPipeline:
    """Orchestrates the full ingestion flow: parse -> chunk -> embed -> store.

    Accepts db and qdrant via constructor DI.
    """

    def __init__(self, db: SQLiteDB, qdrant: QdrantClientWrapper, embedding_provider=None):
        self.db = db
        self.qdrant = qdrant
        self.chunker = ChunkSplitter()
        self.embedder = BatchEmbedder(embedding_provider=embedding_provider)

    async def ingest_file(
        self,
        file_path: str,
        filename: str,
        collection_id: str,
        document_id: str,
        job_id: str,
        file_hash: str | None = None,
    ) -> IngestionResult:
        """Full ingestion pipeline for a single document.

        Steps:
        1. Update job status -> started
        2. Spawn Rust worker subprocess
        3. Read NDJSON stdout line-by-line, update status -> streaming
        4. Pass raw chunks to ChunkSplitter (parent/child + breadcrumbs + UUID5)
        5. Embed children via BatchEmbedder, update status -> embedding
        6. Batch upsert to Qdrant (settings.qdrant_upsert_batch_size per call)
        7. Store parents in SQLite parent_chunks table
        8. Update document chunk_count and status -> completed
        9. Update job status -> completed with chunks_processed count
        """
        ingestion_trace_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(trace_id=ingestion_trace_id)
        chunks_processed = 0
        chunks_skipped = 0
        worker_failed = False
        worker_error = None

        try:
            # Compute file hash at pipeline entry if not provided
            if file_hash is None:
                file_hash = IncrementalChecker.compute_file_hash(file_path)

            # Step 1: Update job status -> started
            await self.db.update_ingestion_job(job_id, status="started")
            await self.db.update_document_status(document_id, "ingesting")

            # Step 2: Spawn Rust worker subprocess
            proc = await self._spawn_worker(file_path)

            # Step 3: Read NDJSON stdout line-by-line
            await self.db.update_ingestion_job(job_id, status="streaming")
            raw_chunks = await self._read_worker_output(proc)

            # Check worker exit status
            proc.wait()
            if proc.returncode != 0:
                stderr_output = proc.stderr.read() if proc.stderr else ""
                worker_failed = True
                worker_error = f"Worker exited with code {proc.returncode}: {stderr_output}"
                logger.error(
                    "ingestion_worker_failed",
                    exit_code=proc.returncode,
                    stderr=stderr_output,
                    document_id=document_id,
                    error="WorkerError",
                )

            if not raw_chunks:
                # No chunks produced — still complete if worker succeeded
                if worker_failed:
                    await self.db.update_ingestion_job(
                        job_id,
                        status="failed",
                        error_msg=worker_error,
                        chunks_processed=0,
                    )
                    await self.db.update_document_status(document_id, "failed")
                    return IngestionResult(
                        document_id=document_id,
                        job_id=job_id,
                        status="failed",
                        error=worker_error,
                    )
                # Worker succeeded but produced no chunks
                now = datetime.now(timezone.utc).isoformat()
                await self.db.update_document_status(
                    document_id, "completed", chunk_count=0, ingested_at=now
                )
                await self.db.update_ingestion_job(
                    job_id, status="completed", chunks_processed=0
                )
                return IngestionResult(
                    document_id=document_id,
                    job_id=job_id,
                    status="completed",
                    chunks_processed=0,
                )

            # Step 4: Pass raw chunks to ChunkSplitter
            parent_chunks = self.chunker.split_into_parents(raw_chunks, filename)

            # Step 5: Embed children via BatchEmbedder
            await self.db.update_ingestion_job(job_id, status="embedding")

            # Collect all child texts for embedding
            all_children = []
            for parent in parent_chunks:
                for child in parent.children:
                    breadcrumb_text = self.chunker.prepend_breadcrumb(
                        child["text"],
                        parent.breadcrumb.split(" > ") if parent.breadcrumb else [],
                    )
                    all_children.append(
                        {
                            "text": breadcrumb_text,
                            "raw_text": child["text"],
                            "point_id": child["point_id"],
                            "chunk_index": child["chunk_index"],
                            "parent": parent,
                        }
                    )

            if all_children:
                texts_to_embed = [c["text"] for c in all_children]
                embeddings, embed_skipped = await self._embed_with_retry(
                    texts_to_embed, job_id
                )
                chunks_skipped += embed_skipped

                # Build Qdrant points (skip None entries from validation)
                points = []
                for child_info, embedding in zip(all_children, embeddings):
                    if embedding is None:
                        continue

                    parent = child_info["parent"]
                    points.append(
                        {
                            "id": child_info["point_id"],
                            "vector": embedding,
                            "payload": {
                                "parent_id": parent.chunk_id,
                                "source_file": parent.source_file,
                                "page": parent.page,
                                "chunk_index": child_info["chunk_index"],
                                "breadcrumb": parent.breadcrumb,
                                "text": child_info["raw_text"],
                                "collection_id": collection_id,
                                "document_id": document_id,
                            },
                        }
                    )

                # Step 6: Batch upsert to Qdrant
                if points:
                    chunks_processed = await self._batch_upsert(
                        collection_id, points, job_id=job_id
                    )

            # Step 7: Store parents in SQLite parent_chunks table
            for parent in parent_chunks:
                await self.db.insert_parent_chunk(
                    chunk_id=parent.chunk_id,
                    collection_id=collection_id,
                    document_id=document_id,
                    text=parent.text,
                    source_file=parent.source_file,
                    page=parent.page,
                    breadcrumb=parent.breadcrumb,
                )

            # If worker failed, process chunks but mark as failed (R4: partial output)
            if worker_failed:
                await self.db.update_ingestion_job(
                    job_id,
                    status="failed",
                    error_msg=worker_error,
                    chunks_processed=chunks_processed,
                    chunks_skipped=chunks_skipped,
                )
                await self.db.update_document_status(
                    document_id, "failed", chunk_count=chunks_processed
                )
                return IngestionResult(
                    document_id=document_id,
                    job_id=job_id,
                    status="failed",
                    chunks_processed=chunks_processed,
                    chunks_skipped=chunks_skipped,
                    error=worker_error,
                )

            # Step 8: Update document chunk_count and status -> completed
            now = datetime.now(timezone.utc).isoformat()
            await self.db.update_document_status(
                document_id, "completed", chunk_count=chunks_processed, ingested_at=now
            )

            # Step 9: Update job status -> completed
            await self.db.update_ingestion_job(
                job_id,
                status="completed",
                chunks_processed=chunks_processed,
                chunks_skipped=chunks_skipped,
            )

            logger.info(
                "ingestion_job_completed",
                document_id=document_id,
                job_id=job_id,
                chunks_processed=chunks_processed,
                chunks_skipped=chunks_skipped,
            )

            return IngestionResult(
                document_id=document_id,
                job_id=job_id,
                status="completed",
                chunks_processed=chunks_processed,
                chunks_skipped=chunks_skipped,
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(
                "ingestion_job_failed",
                document_id=document_id,
                job_id=job_id,
                error=type(e).__name__,
                detail=error_msg,
            )
            await self.db.update_ingestion_job(
                job_id,
                status="failed",
                error_msg=error_msg,
                chunks_processed=chunks_processed,
                chunks_skipped=chunks_skipped,
            )
            await self.db.update_document_status(document_id, "failed")
            return IngestionResult(
                document_id=document_id,
                job_id=job_id,
                status="failed",
                chunks_processed=chunks_processed,
                chunks_skipped=chunks_skipped,
                error=error_msg,
            )
        finally:
            structlog.contextvars.clear_contextvars()

    async def _spawn_worker(self, file_path: str) -> subprocess.Popen:
        """Spawn Rust worker subprocess per worker-ndjson.md contract."""
        proc = subprocess.Popen(
            [settings.rust_worker_path, "--file", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return proc

    async def _read_worker_output(self, proc: subprocess.Popen) -> list[dict]:
        """Read NDJSON lines from worker stdout. Handles partial output (R4)."""
        raw_chunks = []
        for line in proc.stdout:
            line = line.strip()
            if line:
                try:
                    chunk = json.loads(line)
                    raw_chunks.append(chunk)
                except json.JSONDecodeError:
                    logger.warning("ingestion_worker_invalid_json_line", line=line[:100], error="JSONDecodeError")
        return raw_chunks

    async def delete_old_document_data(
        self,
        collection_name: str,
        source_file: str,
        old_document_id: str,
    ) -> None:
        """Delete old Qdrant points and parent chunks for a re-ingested document.

        Called when change detection finds the same filename with a different hash (FR-005).
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        # Delete Qdrant points by source_file payload filter
        try:
            await self.qdrant.client.delete(
                collection_name=collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="source_file",
                            match=MatchValue(value=source_file),
                        )
                    ]
                ),
            )
            logger.info(
                "ingestion_old_qdrant_points_deleted",
                collection_name=collection_name,
                source_file=source_file,
            )
        except Exception as e:
            logger.error(
                "ingestion_old_qdrant_points_delete_failed",
                collection_name=collection_name,
                source_file=source_file,
                error=type(e).__name__,
            )
            raise

        # Delete old parent chunks from SQLite
        deleted_count = await self.db.delete_parent_chunks_by_document(old_document_id)
        logger.info(
            "ingestion_old_parent_chunks_deleted",
            document_id=old_document_id,
            count=deleted_count,
        )

    async def _embed_with_retry(
        self, texts: list[str], job_id: str
    ) -> tuple[list[list[float] | None], int]:
        """Embed texts with Ollama outage handling (FR-013).

        On CircuitOpenError or httpx connection errors: pause job, retry with
        exponential backoff, resume on success.
        """
        backoff = 5.0
        max_backoff = 60.0
        while True:
            try:
                return await self.embedder.embed_chunks(texts)
            except (CircuitOpenError, httpx.ConnectError, httpx.ConnectTimeout):
                await self.db.update_ingestion_job(job_id, status="paused")
                logger.warning(
                    "ingestion_ollama_outage_paused",
                    job_id=job_id,
                    next_retry_secs=backoff,
                    error="CircuitOpenError",
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

    async def _batch_upsert(
        self,
        collection_id: str,
        points: list[dict],
        job_id: str | None = None,
    ) -> int:
        """Upsert points in batches with fault-tolerant buffering (FR-012).

        On Qdrant failure: buffer points in UpsertBuffer. If buffer is full,
        pause job and poll for recovery. On recovery, flush buffer and resume.
        """
        buffer = UpsertBuffer()
        batch_size = settings.qdrant_upsert_batch_size
        upserted = 0

        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            try:
                await self.qdrant.upsert(collection_id, batch)
                upserted += len(batch)
            except Exception:
                logger.warning(
                    "ingestion_qdrant_upsert_failed_buffering",
                    batch_size=len(batch),
                    buffer_pending=buffer.pending_count,
                    error="Exception",
                )
                has_capacity = buffer.add(batch)
                if not has_capacity:
                    # Buffer full — pause and wait for recovery
                    upserted += await self._wait_and_flush(
                        buffer, collection_id, job_id
                    )

        # Flush any remaining buffered points
        if buffer.pending_count > 0:
            upserted += await self._wait_and_flush(
                buffer, collection_id, job_id
            )

        return upserted

    async def _wait_and_flush(
        self,
        buffer: "UpsertBuffer",
        collection_id: str,
        job_id: str | None,
    ) -> int:
        """Pause job, poll for Qdrant recovery, flush buffer, resume."""
        if job_id:
            await self.db.update_ingestion_job(job_id, status="paused")
        logger.info("ingestion_job_paused_qdrant_outage", pending=buffer.pending_count)

        # Retry loop with exponential backoff
        backoff = 5.0
        max_backoff = 60.0
        while True:
            await asyncio.sleep(backoff)
            try:
                flushed = await buffer.flush(self.qdrant, collection_id)
                if job_id:
                    await self.db.update_ingestion_job(job_id, status="embedding")
                logger.info("ingestion_job_resumed_qdrant_recovered", flushed=flushed)
                return flushed
            except Exception:
                logger.warning(
                    "ingestion_qdrant_still_unavailable",
                    next_retry_secs=backoff,
                    error="Exception",
                )
                backoff = min(backoff * 2, max_backoff)
