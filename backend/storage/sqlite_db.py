"""Async SQLite database with WAL mode and FK enforcement.

Spec-07 Storage Architecture: 7 tables with full CRUD operations.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite
import structlog

from backend.errors import SQLiteError

logger = structlog.get_logger().bind(component=__name__)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS collections (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    embedding_model     TEXT NOT NULL DEFAULT 'nomic-embed-text',
    chunk_profile       TEXT NOT NULL DEFAULT 'default',
    qdrant_collection_name  TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id              TEXT PRIMARY KEY,
    collection_id   TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    file_path       TEXT,
    file_hash       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    chunk_count     INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    ingested_at     TEXT,
    UNIQUE(collection_id, file_hash)
);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id              TEXT PRIMARY KEY,
    document_id     TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'started',
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    error_msg       TEXT,
    chunks_processed INTEGER DEFAULT 0,
    chunks_skipped  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS parent_chunks (
    id              TEXT PRIMARY KEY,
    collection_id   TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    document_id     TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    text            TEXT NOT NULL,
    metadata_json   TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_parent_chunks_collection ON parent_chunks(collection_id);
CREATE INDEX IF NOT EXISTS idx_parent_chunks_document ON parent_chunks(document_id);

CREATE TABLE IF NOT EXISTS query_traces (
    id                          TEXT PRIMARY KEY,
    session_id                  TEXT NOT NULL,
    query                       TEXT NOT NULL,
    sub_questions_json          TEXT,
    collections_searched        TEXT,
    chunks_retrieved_json       TEXT,
    reasoning_steps_json        TEXT,
    strategy_switches_json      TEXT,
    meta_reasoning_triggered    INTEGER DEFAULT 0,
    latency_ms                  INTEGER,
    llm_model                   TEXT,
    embed_model                 TEXT,
    confidence_score            INTEGER,
    created_at                  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_traces_session ON query_traces(session_id);
CREATE INDEX IF NOT EXISTS idx_traces_created ON query_traces(created_at);

CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS providers (
    name       TEXT PRIMARY KEY,
    api_key_encrypted TEXT,
    base_url   TEXT,
    is_active  INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


class SQLiteDB:
    """Async SQLite storage with WAL mode and FK enforcement."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open connection, enable WAL + FKs, init schema."""
        try:
            if self.db_path != ":memory:":
                Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self.db = await aiosqlite.connect(self.db_path)
            self.db.row_factory = aiosqlite.Row
            await self.db.execute("PRAGMA journal_mode=WAL")
            await self.db.execute("PRAGMA foreign_keys=ON")
            await self.db.execute("PRAGMA synchronous=NORMAL")
            await self._init_schema()
            logger.info("storage_sqlite_connected", db_path=self.db_path)
        except aiosqlite.Error as e:
            raise SQLiteError(f"Failed to initialize SQLite: {e}") from e

    async def close(self) -> None:
        """Close database connection."""
        if self.db:
            await self.db.close()
            self.db = None

    async def __aenter__(self) -> "SQLiteDB":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def _init_schema(self) -> None:
        """Create all 7 tables (idempotent). Uses IF NOT EXISTS."""
        await self.db.executescript(_SCHEMA_SQL)
        await self.db.commit()
        await self._migrate_providers_columns()
        await self._migrate_query_traces_columns()

    async def _migrate_providers_columns(self) -> None:
        """Add provider_type and config_json columns if not present."""
        cursor = await self.db.execute("PRAGMA table_info(providers)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "provider_type" not in columns:
            await self.db.execute(
                "ALTER TABLE providers ADD COLUMN provider_type TEXT"
            )
        if "config_json" not in columns:
            await self.db.execute(
                "ALTER TABLE providers ADD COLUMN config_json TEXT"
            )
        await self.db.commit()

    async def _migrate_query_traces_columns(self) -> None:
        """Add provider_name and stage_timings_json columns to query_traces if not present (idempotent)."""
        cursor = await self.db.execute("PRAGMA table_info(query_traces)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "provider_name" not in columns:
            await self.db.execute(
                "ALTER TABLE query_traces ADD COLUMN provider_name TEXT"
            )
        if "stage_timings_json" not in columns:
            await self.db.execute(
                "ALTER TABLE query_traces ADD COLUMN stage_timings_json TEXT"
            )
        await self.db.commit()

    # ── Collections ───────────────────────────────────────────────

    async def create_collection(
        self,
        id: str,
        name: str,
        embedding_model: str,
        chunk_profile: str,
        qdrant_collection_name: str,
        description: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            """INSERT INTO collections
               (id, name, description, embedding_model, chunk_profile, qdrant_collection_name, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (id, name, description, embedding_model, chunk_profile, qdrant_collection_name, now),
        )
        await self.db.commit()

    async def get_collection(self, collection_id: str) -> dict | None:
        cursor = await self.db.execute(
            """SELECT id, name, description, embedding_model, chunk_profile,
                      qdrant_collection_name, created_at
               FROM collections WHERE id = ?""",
            (collection_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_collection_by_name(self, name: str) -> dict | None:
        cursor = await self.db.execute(
            """SELECT id, name, description, embedding_model, chunk_profile,
                      qdrant_collection_name, created_at
               FROM collections WHERE name = ?""",
            (name,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_collections(self) -> list[dict]:
        cursor = await self.db.execute(
            """SELECT id, name, description, embedding_model, chunk_profile,
                      qdrant_collection_name, created_at
               FROM collections ORDER BY created_at DESC"""
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def update_collection(self, collection_id: str, **kwargs: Any) -> None:
        if not kwargs:
            return
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [collection_id]
        await self.db.execute(
            f"UPDATE collections SET {sets} WHERE id = ?",  # noqa: S608
            vals,
        )
        await self.db.commit()

    async def delete_collection(self, collection_id: str) -> None:
        await self.db.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
        await self.db.commit()

    # ── Documents ─────────────────────────────────────────────────

    async def create_document(
        self,
        id: str,
        collection_id: str,
        filename: str,
        file_hash: str,
        file_path: str | None = None,
        status: str = "pending",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            """INSERT INTO documents
               (id, collection_id, filename, file_path, file_hash, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (id, collection_id, filename, file_path, file_hash, status, now),
        )
        await self.db.commit()

    async def get_document(self, doc_id: str) -> dict | None:
        cursor = await self.db.execute(
            """SELECT id, collection_id, filename, file_path, file_hash,
                      status, chunk_count, created_at, ingested_at
               FROM documents WHERE id = ?""",
            (doc_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_document_by_hash(self, collection_id: str, file_hash: str) -> dict | None:
        cursor = await self.db.execute(
            """SELECT id, collection_id, filename, file_path, file_hash,
                      status, chunk_count, created_at, ingested_at
               FROM documents WHERE collection_id = ? AND file_hash = ?""",
            (collection_id, file_hash),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_documents(self, collection_id: str) -> list[dict]:
        cursor = await self.db.execute(
            """SELECT id, collection_id, filename, file_path, file_hash,
                      status, chunk_count, created_at, ingested_at
               FROM documents WHERE collection_id = ? ORDER BY created_at""",
            (collection_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def update_document(self, doc_id: str, **kwargs: Any) -> None:
        if not kwargs:
            return
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [doc_id]
        await self.db.execute(
            f"UPDATE documents SET {sets} WHERE id = ?",  # noqa: S608
            vals,
        )
        await self.db.commit()

    async def delete_document(self, doc_id: str) -> None:
        await self.db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        await self.db.commit()

    # ── Ingestion Jobs ────────────────────────────────────────────

    async def create_ingestion_job(
        self,
        id: str,
        document_id: str,
        status: str = "started",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            """INSERT INTO ingestion_jobs (id, document_id, status, started_at)
               VALUES (?, ?, ?, ?)""",
            (id, document_id, status, now),
        )
        await self.db.commit()

    async def get_ingestion_job(self, job_id: str) -> dict | None:
        cursor = await self.db.execute(
            """SELECT id, document_id, status, started_at, finished_at,
                      error_msg, chunks_processed, chunks_skipped
               FROM ingestion_jobs WHERE id = ?""",
            (job_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_ingestion_jobs(self, document_id: str) -> list[dict]:
        cursor = await self.db.execute(
            """SELECT id, document_id, status, started_at, finished_at,
                      error_msg, chunks_processed, chunks_skipped
               FROM ingestion_jobs WHERE document_id = ? ORDER BY started_at""",
            (document_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def update_ingestion_job(
        self,
        job_id: str,
        status: str | None = None,
        chunks_processed: int | None = None,
        chunks_skipped: int | None = None,
        finished_at: str | None = None,
        error_msg: str | None = None,
    ) -> None:
        updates: list[str] = []
        params: list[Any] = []
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if chunks_processed is not None:
            updates.append("chunks_processed = ?")
            params.append(chunks_processed)
        if chunks_skipped is not None:
            updates.append("chunks_skipped = ?")
            params.append(chunks_skipped)
        if finished_at is not None:
            updates.append("finished_at = ?")
            params.append(finished_at)
        if error_msg is not None:
            updates.append("error_msg = ?")
            params.append(error_msg)
        if not updates:
            return
        params.append(job_id)
        await self.db.execute(
            f"UPDATE ingestion_jobs SET {', '.join(updates)} WHERE id = ?",  # noqa: S608
            params,
        )
        await self.db.commit()

    # ── Parent Chunks ─────────────────────────────────────────────

    async def create_parent_chunk(
        self,
        id: str,
        collection_id: str,
        document_id: str,
        text: str,
        metadata_json: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            """INSERT INTO parent_chunks (id, collection_id, document_id, text, metadata_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (id, collection_id, document_id, text, metadata_json, now),
        )
        await self.db.commit()

    async def get_parent_chunk(self, parent_id: str) -> dict | None:
        cursor = await self.db.execute(
            """SELECT id, collection_id, document_id, text, metadata_json, created_at
               FROM parent_chunks WHERE id = ?""",
            (parent_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_parent_chunks_batch(self, parent_ids: list[str]) -> list[dict]:
        if not parent_ids:
            return []
        placeholders = ",".join("?" for _ in parent_ids)
        cursor = await self.db.execute(
            f"SELECT id, collection_id, document_id, text, metadata_json, created_at "  # noqa: S608
            f"FROM parent_chunks WHERE id IN ({placeholders})",
            parent_ids,
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def list_parent_chunks(
        self,
        collection_id: str,
        document_id: str | None = None,
    ) -> list[dict]:
        if document_id:
            cursor = await self.db.execute(
                """SELECT id, collection_id, document_id, text, metadata_json, created_at
                   FROM parent_chunks WHERE collection_id = ? AND document_id = ?""",
                (collection_id, document_id),
            )
        else:
            cursor = await self.db.execute(
                """SELECT id, collection_id, document_id, text, metadata_json, created_at
                   FROM parent_chunks WHERE collection_id = ?""",
                (collection_id,),
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def delete_parent_chunks(self, document_id: str) -> None:
        await self.db.execute(
            "DELETE FROM parent_chunks WHERE document_id = ?", (document_id,)
        )
        await self.db.commit()

    # ── Query Traces ──────────────────────────────────────────────

    async def create_query_trace(
        self,
        id: str,
        session_id: str,
        query: str,
        collections_searched: str,
        chunks_retrieved_json: str,
        latency_ms: int,
        llm_model: str | None = None,
        embed_model: str | None = None,
        confidence_score: int | None = None,
        sub_questions_json: str | None = None,
        reasoning_steps_json: str | None = None,
        strategy_switches_json: str | None = None,
        meta_reasoning_triggered: bool = False,
        provider_name: str | None = None,
        stage_timings_json: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            """INSERT INTO query_traces
               (id, session_id, query, sub_questions_json, collections_searched,
                chunks_retrieved_json, reasoning_steps_json, strategy_switches_json,
                meta_reasoning_triggered, latency_ms, llm_model, embed_model,
                confidence_score, provider_name, stage_timings_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                id, session_id, query, sub_questions_json, collections_searched,
                chunks_retrieved_json, reasoning_steps_json, strategy_switches_json,
                int(meta_reasoning_triggered), latency_ms, llm_model, embed_model,
                confidence_score, provider_name, stage_timings_json, now,
            ),
        )
        await self.db.commit()

    async def list_query_traces(self, session_id: str, limit: int = 100) -> list[dict]:
        cursor = await self.db.execute(
            """SELECT id, session_id, query, sub_questions_json, collections_searched,
                      chunks_retrieved_json, reasoning_steps_json, strategy_switches_json,
                      meta_reasoning_triggered, latency_ms, llm_model, embed_model,
                      confidence_score, created_at
               FROM query_traces WHERE session_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (session_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def list_traces(
        self,
        session_id: str | None = None,
        collection_id: str | None = None,
        min_confidence: int | None = None,
        max_confidence: int | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        """List query traces with optional filters and pagination."""
        conditions: list[str] = []
        params: list[Any] = []
        if session_id is not None:
            conditions.append("session_id = ?")
            params.append(session_id)
        if collection_id is not None:
            conditions.append("collections_searched LIKE ?")
            params.append(f"%{collection_id}%")
        if min_confidence is not None:
            conditions.append("confidence_score >= ?")
            params.append(min_confidence)
        if max_confidence is not None:
            conditions.append("confidence_score <= ?")
            params.append(max_confidence)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        params.extend([limit, offset])
        cursor = await self.db.execute(
            f"SELECT id, session_id, query, sub_questions_json, collections_searched,"  # noqa: S608
            f" chunks_retrieved_json, reasoning_steps_json, strategy_switches_json,"
            f" meta_reasoning_triggered, latency_ms, llm_model, embed_model,"
            f" confidence_score, created_at"
            f" FROM query_traces{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_trace(self, trace_id: str) -> dict | None:
        """Get a single query trace by ID."""
        cursor = await self.db.execute(
            """SELECT id, session_id, query, sub_questions_json, collections_searched,
                      chunks_retrieved_json, reasoning_steps_json, strategy_switches_json,
                      meta_reasoning_triggered, latency_ms, llm_model, embed_model,
                      confidence_score, created_at, stage_timings_json
               FROM query_traces WHERE id = ?""",
            (trace_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        d = dict(row)
        # Parse stage_timings_json into stage_timings dict (R-004: default {})
        raw = d.pop("stage_timings_json", None)
        if raw:
            try:
                import json as _json
                d["stage_timings"] = _json.loads(raw)
            except (ValueError, TypeError):
                d["stage_timings"] = {}
        else:
            d["stage_timings"] = {}
        return d

    async def get_query_traces_by_timerange(
        self,
        start_ts: str,
        end_ts: str,
        limit: int = 1000,
    ) -> list[dict]:
        cursor = await self.db.execute(
            """SELECT id, session_id, query, sub_questions_json, collections_searched,
                      chunks_retrieved_json, reasoning_steps_json, strategy_switches_json,
                      meta_reasoning_triggered, latency_ms, llm_model, embed_model,
                      confidence_score, created_at
               FROM query_traces WHERE created_at >= ? AND created_at <= ?
               ORDER BY created_at DESC LIMIT ?""",
            (start_ts, end_ts, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ── Settings ──────────────────────────────────────────────────

    async def get_setting(self, key: str) -> str | None:
        cursor = await self.db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else None

    async def set_setting(self, key: str, value: str) -> None:
        await self.db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        await self.db.commit()

    async def list_settings(self) -> dict[str, str]:
        cursor = await self.db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        return {r["key"]: r["value"] for r in rows}

    async def delete_setting(self, key: str) -> None:
        await self.db.execute("DELETE FROM settings WHERE key = ?", (key,))
        await self.db.commit()

    # ── Providers ─────────────────────────────────────────────────

    async def create_provider(
        self,
        name: str,
        api_key_encrypted: str | None = None,
        base_url: str | None = None,
        is_active: bool = True,
    ) -> None:
        await self.db.execute(
            """INSERT INTO providers (name, api_key_encrypted, base_url, is_active)
               VALUES (?, ?, ?, ?)""",
            (name, api_key_encrypted, base_url, int(is_active)),
        )
        await self.db.commit()

    async def get_provider(self, name: str) -> dict | None:
        cursor = await self.db.execute(
            """SELECT name, api_key_encrypted, base_url, is_active, created_at
               FROM providers WHERE name = ?""",
            (name,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        result = dict(row)
        result["is_active"] = bool(result["is_active"])
        return result

    async def list_providers(self) -> list[dict]:
        cursor = await self.db.execute(
            "SELECT name, api_key_encrypted, base_url, is_active, created_at FROM providers"
        )
        rows = await cursor.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["is_active"] = bool(d["is_active"])
            results.append(d)
        return results

    async def update_provider(
        self,
        name: str,
        is_active: bool | None = None,
        api_key_encrypted: str | None = None,
        base_url: str | None = None,
    ) -> None:
        updates: list[str] = []
        params: list[Any] = []
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(int(is_active))
        if api_key_encrypted is not None:
            updates.append("api_key_encrypted = ?")
            params.append(api_key_encrypted)
        if base_url is not None:
            updates.append("base_url = ?")
            params.append(base_url)
        if not updates:
            return
        params.append(name)
        await self.db.execute(
            f"UPDATE providers SET {', '.join(updates)} WHERE name = ?",  # noqa: S608
            params,
        )
        await self.db.commit()

    async def delete_provider(self, name: str) -> None:
        await self.db.execute("DELETE FROM providers WHERE name = ?", (name,))
        await self.db.commit()

    async def get_active_provider(self) -> dict | None:
        """Return the first active provider, or None."""
        cursor = await self.db.execute(
            """SELECT name, api_key_encrypted, base_url, is_active,
                      provider_type, config_json, created_at
               FROM providers WHERE is_active = 1 LIMIT 1"""
        )
        row = await cursor.fetchone()
        if not row:
            return None
        result = dict(row)
        result["is_active"] = bool(result["is_active"])
        return result

    async def upsert_provider(
        self,
        name: str,
        provider_type: str | None = None,
        config_json: str | None = None,
        is_active: bool = True,
    ) -> None:
        """Insert or replace a provider record."""
        if is_active:
            await self.db.execute(
                "UPDATE providers SET is_active = 0 WHERE name != ?", (name,)
            )
        await self.db.execute(
            """INSERT OR REPLACE INTO providers
               (name, provider_type, config_json, is_active)
               VALUES (?, ?, ?, ?)""",
            (name, provider_type, config_json, int(is_active)),
        )
        await self.db.commit()
