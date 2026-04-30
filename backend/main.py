"""FastAPI application factory with lifespan management."""

import logging
import logging as stdlib_logging
import os
import sys
import tempfile
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path

import aiosqlite

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.providers.base import ProviderRateLimitError
from backend.errors import EmbeddinatorError, QdrantConnectionError, OllamaConnectionError, UnsupportedModelError
from backend.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    TraceIDMiddleware,
)
from backend.storage.sqlite_db import SQLiteDB
from backend.storage.qdrant_client import QdrantClientWrapper
from backend.providers.registry import ProviderRegistry
from backend.api import collections, documents, chat, traces, providers, health
from backend.api import ingest as ingest_router
from backend.api import models as models_router
from backend.api import settings as api_settings


_SENSITIVE_KEYS = {"api_key", "password", "secret", "token", "authorization"}


def _strip_sensitive_fields(logger, method, event_dict: dict) -> dict:
    """Redact sensitive field values in log records (FR-006)."""
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict


def _configure_logging(log_level: str = "INFO", log_level_overrides: str = ""):
    """Configure structured JSON logging with structlog.

    Builds a per-component level filter from LOG_LEVEL_OVERRIDES and inserts it
    between merge_contextvars and add_log_level so that method_name is still
    the raw log-method string (T038–T039, US3, FR-004).
    """
    # --- Parse per-component override string (T038) ---
    override_map: dict[str, int] = {}
    _startup_warnings: list[tuple[str, dict]] = []

    for pair in log_level_overrides.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            _startup_warnings.append(("http_log_override_invalid_format", {"pair": pair}))
            continue
        module, level_str = pair.split("=", 1)
        level_int = stdlib_logging.getLevelName(level_str.strip().upper())
        if not isinstance(level_int, int):
            _startup_warnings.append(
                (
                    "http_log_override_invalid_level",
                    {"module": module.strip(), "level": level_str.strip()},
                )
            )
            continue
        override_map[module.strip()] = level_int

    # --- Per-component filter processor (T039) ---
    def _filter_by_component(logger, method_name: str, event_dict: dict) -> dict:
        """Drop events that fall below the per-component override level.

        Uses ``event_dict.get("component", "")`` because loggers are bound with
        ``.bind(component=__name__)`` (A1 migration). Reads ``method_name``
        directly instead of ``event_dict.get("level")`` because add_log_level
        has not run yet at this processor position.
        """
        component = event_dict.get("component", "")
        if not component:
            return event_dict  # no component key → pass through
        component_override = override_map.get(component)
        if component_override is None:
            return event_dict  # no override for this component → pass through
        event_level = stdlib_logging.getLevelName(method_name.upper())
        if isinstance(event_level, int) and event_level < component_override:
            raise structlog.DropEvent()
        return event_dict

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _filter_by_component,  # inserted between merge_contextvars and add_log_level
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _strip_sensitive_fields,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level.upper(), logging.INFO)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Emit any deferred startup warnings AFTER structlog is configured (SC-007)
    if _startup_warnings:
        _warn_logger = structlog.get_logger(__name__)
        for event_name, kwargs in _startup_warnings:
            _warn_logger.warning(event_name, **kwargs)


async def _prune_old_checkpoint_threads(checkpointer, max_threads: int, logger) -> int:
    # spec-26 DISK-001: keep most-recent max_threads threads, delete the rest.
    # checkpoint_id is UUIDv6 — lex-sort = time-sort. 0 disables.
    if max_threads <= 0:
        return 0
    async with checkpointer.conn.execute(
        "SELECT thread_id, MAX(checkpoint_id) AS latest FROM checkpoints GROUP BY thread_id ORDER BY latest DESC"
    ) as cursor:
        rows = await cursor.fetchall()
    if len(rows) <= max_threads:
        return 0
    pruned = 0
    for tid, _latest in rows[max_threads:]:
        try:
            await checkpointer.adelete_thread(tid)
            pruned += 1
        except Exception as e:
            logger.warning("storage_checkpoint_prune_failed", thread_id=tid, error=str(e))

    # spec-28 BUG-014 layer 1 + spec-029 R1: reclaim freelist pages after pruning.
    # With auto_vacuum=INCREMENTAL (set by _migrate_checkpoint_auto_vacuum at startup),
    # each PRAGMA incremental_vacuum call reclaims one page from the freelist.
    # In WAL journal mode (used by AsyncSqliteSaver) a single call only reclaims one
    # page, so we loop until freelist_count == 0 — same end-state as the old VACUUM.
    if pruned > 0:
        try:
            await checkpointer.conn.commit()
            # Best-effort: capture freelist count before reclaim for the log.
            try:
                async with checkpointer.conn.execute("PRAGMA freelist_count") as _cur:
                    (_freelist_before,) = await _cur.fetchone()
                freelist_pages_reclaimed: int | None = _freelist_before
            except Exception:
                freelist_pages_reclaimed = None
            # Loop until all freelist pages are reclaimed (WAL mode: one page per call).
            for _ in range(freelist_pages_reclaimed or 0):
                await checkpointer.conn.execute("PRAGMA incremental_vacuum")
                async with checkpointer.conn.execute("PRAGMA freelist_count") as _cur:
                    (_remaining,) = await _cur.fetchone()
                if _remaining == 0:
                    break
            logger.info(
                "storage_checkpoint_incremental_vacuumed",
                pruned_threads=pruned,
                freelist_pages_reclaimed=freelist_pages_reclaimed,
            )
        except Exception as e:
            logger.warning(
                "storage_checkpoint_incremental_vacuum_failed",
                pruned_threads=pruned,
                error=type(e).__name__,
                detail=str(e)[:200],
            )
    return pruned


async def _check_checkpoint_integrity(checkpointer, logger) -> bool:
    # spec-28 BUG-014 layer 2: surface checkpoints.db corruption at startup,
    # before the first /api/chat request hits a corrupt page write and the
    # exception escapes into a SERVICE_UNAVAILABLE response (BUG-013).
    # Warn-only; recovery procedure is documented in
    # docs/E2E/2026-04-24-bug-hunt/bugs-raw/BUG-013-chat-service-unavailable.md
    try:
        async with checkpointer.conn.execute("PRAGMA integrity_check") as cursor:
            rows = await cursor.fetchall()
    except Exception as e:
        logger.warning(
            "storage_checkpoint_integrity_check_failed",
            error=type(e).__name__,
            detail=str(e)[:200],
        )
        return False

    if not rows:
        logger.warning("storage_checkpoint_integrity_no_result")
        return False

    if rows[0][0] == "ok" and len(rows) == 1:
        logger.info("storage_checkpoint_integrity_ok")
        return True

    issues = [r[0] for r in rows]
    logger.warning(
        "storage_checkpoint_integrity_failed",
        first_issue=issues[0],
        total_issues=len(issues),
        recovery_runbook="docs/E2E/2026-04-24-bug-hunt/bugs-raw/BUG-013-chat-service-unavailable.md#resolution",
    )
    return False


async def _migrate_checkpoint_auto_vacuum(path: str, logger) -> bool:
    """Idempotent: ensure auto_vacuum=INCREMENTAL on the SQLite DB at path.

    Behaviour matrix (PRAGMA auto_vacuum × PRAGMA page_count):

      auto_vacuum  page_count   action                               return
      ───────────  ──────────   ─────────────────────────────────    ──────
      2 (INCR)     any          no-op; log DEBUG                     False
      0 (NONE)     0            PRAGMA auto_vacuum=2 only            True
      0 (NONE)     >0           PRAGMA auto_vacuum=2; VACUUM         True
      1 (FULL)     any          no-op; log WARNING                   False

    For a non-existent path: aiosqlite creates the file, sets auto_vacuum=2,
    returns True. The caller's subsequent AsyncSqliteSaver.setup() then creates
    the schema on a DB that will auto-track freelist pages.

    Side effects: opens raw aiosqlite connection, runs PRAGMAs, closes.
    No exceptions are caught — caller must handle.

    Logs (structured):
      INFO  storage_checkpoint_auto_vacuum_already_set     when no-op (mode=2)
      INFO  storage_checkpoint_auto_vacuum_migrating       before VACUUM (mode=0, page_count>0)
      INFO  storage_checkpoint_auto_vacuum_migrated        after VACUUM, with elapsed_ms (int)
      WARN  storage_checkpoint_auto_vacuum_unexpected_mode if mode=FULL (informational)
    """
    async with aiosqlite.connect(path) as conn:
        async with conn.execute("PRAGMA auto_vacuum") as cur:
            (mode,) = await cur.fetchone()
        async with conn.execute("PRAGMA page_count") as cur:
            (page_count,) = await cur.fetchone()

        if mode == 2:
            # Already INCREMENTAL — idempotent no-op.
            logger.info("storage_checkpoint_auto_vacuum_already_set", path=path, current_mode=mode)
            return False

        if mode == 1:
            # FULL mode — out of scope to migrate; log warning and bail.
            logger.warning("storage_checkpoint_auto_vacuum_unexpected_mode", path=path, mode=mode)
            return False

        # mode == 0 (NONE): migrate to INCREMENTAL.
        await conn.execute("PRAGMA auto_vacuum = 2")

        if page_count > 0:
            # Existing DB — must VACUUM to physically rewrite with the new mode.
            logger.info(
                "storage_checkpoint_auto_vacuum_migrating",
                path=path,
                prior_mode=mode,
                page_count=page_count,
            )
            t0 = time.perf_counter()
            await conn.execute("VACUUM")
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            logger.info(
                "storage_checkpoint_auto_vacuum_migrated",
                path=path,
                prior_mode=mode,
                elapsed_ms=elapsed_ms,
            )
        # For page_count==0 (fresh/empty file), PRAGMA auto_vacuum=2 is sufficient.
        # VACUUM on an empty file is a no-op and adds latency for no gain.
        await conn.commit()

    return True


class RecoveryResult(StrEnum):
    """Result of ``_recover_checkpoint_db``.

    StrEnum (Python 3.11+) so values serialise cleanly in structlog event dicts
    and compare equal to plain strings in tests — ``assert result == "recovered"``
    works without ``.value`` boilerplate.
    """

    SKIPPED = "skipped"  # path missing OR DB passes integrity_check
    RECOVERED = "recovered"  # salvage succeeded; file swapped
    FRESH_FALLBACK = "fresh_fallback"  # salvage failed; original archived; path absent
    REFUSED_WAL = "refused_wal"  # -wal sibling present; refused to act


async def _recover_checkpoint_db(path: str, logger) -> RecoveryResult:
    """Pre-connection integrity check + opt-in auto-recovery.

    PRECONDITION: caller has already verified ``settings.checkpoint_auto_recover``
    is True before invoking this function.  This helper does NOT read settings;
    it is testable in isolation.  The lifespan gates the call.

    Behaviour:
      1. If path does not exist → log INFO, return SKIPPED.
      2. If ``<path>-wal`` exists → log ERROR, return REFUSED_WAL, leave all files untouched.
         (WAL check is BEFORE open to avoid SQLite modifying/consuming the WAL
         during connection open/close — an open() call on a WAL-mode DB with a
         live WAL file can destroy the evidence before we can refuse.)
      3. Open raw aiosqlite, run ``PRAGMA integrity_check``, close connection.
         If result == [('ok',)] → log INFO, return SKIPPED.
      4. Otherwise run salvage sequence:
         a. salvage_path = path + ".salvage"; unlink if exists (defensive).
         b. Open raw aiosqlite on ``path``, execute ``VACUUM INTO '<salvage_path>'``, close.
         c. Open raw aiosqlite on ``salvage_path``, execute REINDEX then
            ``PRAGMA integrity_check``, close.
         d. If salvage integrity == [('ok',)]:
              - archive original: ``os.replace(path, archive_path)`` (archive-first, NFR-002)
              - cleanup -shm/-wal siblings (best-effort)
              - ``os.replace(salvage_path, path)``
              - log INFO, return RECOVERED
            Else (salvage also corrupt, or VACUUM INTO raised):
              - archive original (best-effort)
              - delete salvage (best-effort)
              - cleanup siblings
              - leave ``path`` absent
              - log ERROR, return FRESH_FALLBACK

    Edge cases handled per design §8:
    - Salvage path collision: unconditional unlink before use.
    - Archive path collision: microsecond-precision timestamp; collision loop up to 100 iterations.
    - -shm/-wal cleanup after any file swap (best-effort, wrapped in try/except FileNotFoundError).
    - All aiosqlite connections use ``async with`` — no connection leaks on exception.
    - OSError/PermissionError during file ops → escalate to FRESH_FALLBACK with clear log.
    """
    import sqlite3 as _sqlite3

    # ------------------------------------------------------------------
    # Step 1: fresh install — nothing to check.
    # ------------------------------------------------------------------
    if not os.path.exists(path):
        logger.info("storage_checkpoint_recovery_skipped_path_missing", path=path)
        return RecoveryResult.SKIPPED

    # ------------------------------------------------------------------
    # Step 2: refuse to act if a -wal sibling exists BEFORE opening the DB.
    # Must check WAL before any aiosqlite.connect() call — opening a WAL-mode
    # DB with a live WAL file causes SQLite to modify/consume the WAL during
    # connection open/close, destroying the evidence. The REFUSED_WAL contract
    # is: "leave all files untouched; let the operator resolve manually."
    # ------------------------------------------------------------------
    wal_path = path + "-wal"
    if os.path.exists(wal_path):
        logger.error(
            "storage_checkpoint_recovery_refused_wal_present",
            path=path,
            wal_path=wal_path,
            runbook="docs/E2E/2026-04-24-bug-hunt/bugs-raw/BUG-013-chat-service-unavailable.md#resolution",
        )
        return RecoveryResult.REFUSED_WAL

    # ------------------------------------------------------------------
    # Step 3: integrity check (no WAL sibling → safe to open).
    # ------------------------------------------------------------------
    try:
        async with aiosqlite.connect(path) as conn:
            async with conn.execute("PRAGMA integrity_check") as cur:
                rows = await cur.fetchall()
    except Exception:
        rows = []  # treat unreadable DB as corrupt — fall through to recovery

    if rows and rows[0][0] == "ok" and len(rows) == 1:
        logger.info("storage_checkpoint_recovery_skipped_integrity_ok", path=path)
        return RecoveryResult.SKIPPED

    # ------------------------------------------------------------------
    # Step 4: salvage sequence.
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    salvage_path = path + ".salvage"

    # Defensive: remove stale salvage from a prior failed attempt.
    try:
        os.unlink(salvage_path)
    except FileNotFoundError:
        pass

    salvage_ok = False
    vacuum_into_failed = False
    vacuum_into_exc_name: str = ""

    try:
        # 4a (continued): VACUUM INTO to produce a cleaned copy.
        async with aiosqlite.connect(path) as conn:
            await conn.execute(f"VACUUM INTO '{salvage_path}'")

        # 4b (continued): verify salvage integrity.
        async with aiosqlite.connect(salvage_path) as conn:
            await conn.execute("REINDEX")
            async with conn.execute("PRAGMA integrity_check") as cur:
                salvage_rows = await cur.fetchall()

        salvage_ok = bool(salvage_rows) and salvage_rows[0][0] == "ok" and len(salvage_rows) == 1

    except Exception as exc:
        vacuum_into_failed = True
        vacuum_into_exc_name = type(exc).__name__

    # ------------------------------------------------------------------
    # Build archive path (microsecond-precision timestamp, collision-safe).
    # ------------------------------------------------------------------
    def _make_archive_path() -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        candidate = f"{path}.corrupt-{ts}"
        if not os.path.exists(candidate):
            return candidate
        for i in range(1, 101):
            alt = f"{candidate}_{i}"
            if not os.path.exists(alt):
                return alt
        raise RuntimeError(f"Could not find a unique archive path after 100 attempts: {candidate}")

    def _cleanup_siblings(base: str) -> None:
        """Best-effort removal of -shm and -wal siblings."""
        for suffix in ("-shm", "-wal"):
            try:
                os.unlink(base + suffix)
            except FileNotFoundError:
                pass

    if salvage_ok:
        # ------------------------------------------------------------------
        # RECOVERED path.
        # ------------------------------------------------------------------
        archive_path = _make_archive_path()
        salvage_size = os.path.getsize(salvage_path)
        # Archive-first (NFR-002): original is safe before any swap.
        os.replace(path, archive_path)
        _cleanup_siblings(path)
        os.replace(salvage_path, path)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(
            "storage_checkpoint_auto_recovered",
            path=path,
            archive_path=archive_path,
            salvage_size_bytes=salvage_size,
            elapsed_ms=elapsed_ms,
        )
        return RecoveryResult.RECOVERED
    else:
        # ------------------------------------------------------------------
        # FRESH_FALLBACK path — salvage failed or VACUUM INTO raised.
        # ------------------------------------------------------------------
        reason = f"vacuum_into_failed:{vacuum_into_exc_name}" if vacuum_into_failed else "salvage_corrupt"

        # Archive original (best-effort — on read-only FS this may fail).
        try:
            archive_path = _make_archive_path()
            os.replace(path, archive_path)
        except (OSError, PermissionError) as exc:
            archive_path = f"<archive failed: {type(exc).__name__}>"

        # Clean up the failed salvage (best-effort).
        try:
            os.unlink(salvage_path)
        except FileNotFoundError:
            pass

        _cleanup_siblings(path)

        logger.error(
            "storage_checkpoint_fresh_db_fallback",
            path=path,
            archive_path=archive_path,
            reason=reason,
        )
        return RecoveryResult.FRESH_FALLBACK


def _validate_model_support(model: str, supported: list[str]) -> None:
    """Fail fast if the configured LLM is not in the supported list.

    spec-26: FR-004 Path B — raises UnsupportedModelError on unsupported/thinking models.
    Called from lifespan before any graph compilation so the container never starts silently broken.
    """
    if model not in supported:
        raise UnsupportedModelError(model=model, supported=supported)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, Qdrant, providers, checkpointer. Shutdown: close connections."""
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    _configure_logging(settings.log_level, settings.log_level_overrides)
    logger = structlog.get_logger().bind(component=__name__)

    # spec-26: FR-004 Path B — fail fast before any graph or provider initialization
    _validate_model_support(settings.default_llm_model, settings.supported_llm_models)
    logger.info("startup_model_validated", model=settings.default_llm_model)

    # FR-044: Ensure upload directory exists before any I/O
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    logger.info("startup_upload_dir_ensured", path=settings.upload_dir)

    # FR-045: Verify data directory is writable; abort with clear error if not
    data_dir = Path(settings.upload_dir).parent
    try:
        _tmp = tempfile.NamedTemporaryFile(dir=data_dir, prefix=".writetest_", delete=False)
        _tmp.close()
        Path(_tmp.name).unlink()
    except PermissionError:
        logger.error("startup_data_dir_not_writable", path=str(data_dir))
        raise SystemExit(1)

    # Startup
    db = SQLiteDB(settings.sqlite_path)
    await db.connect()
    app.state.db = db
    logger.info("storage_sqlite_initialized", path=settings.sqlite_path)

    qdrant = QdrantClientWrapper(settings.qdrant_host, settings.qdrant_port)
    await qdrant.connect()
    app.state.qdrant = qdrant
    logger.info("storage_qdrant_initialized", host=settings.qdrant_host)

    # Spec 07: QdrantStorage (full-featured, coexists with QdrantClientWrapper)
    from backend.storage.qdrant_client import QdrantStorage

    qdrant_storage = QdrantStorage(settings.qdrant_host, settings.qdrant_port)
    app.state.qdrant_storage = qdrant_storage
    logger.info("storage_qdrant_storage_initialized")

    # Spec 07: KeyManager (optional -- graceful degradation if env var missing)
    from backend.providers.key_manager import KeyManager

    try:
        key_manager = KeyManager()
        app.state.key_manager = key_manager
        logger.info("storage_key_manager_initialized")
    except ValueError as e:
        logger.warning("storage_key_manager_skipped", reason=str(e))
        app.state.key_manager = None

    registry = ProviderRegistry(settings)
    await registry.initialize(db)
    app.state.registry = registry
    logger.info("provider_providers_initialized")

    # LangGraph checkpointer — separate DB for checkpoint state
    checkpoint_path = settings.sqlite_path.replace("embedinator.db", "checkpoints.db")

    # spec-029 R2 (gated): opt-in auto-recovery BEFORE opening connection.
    # Must run BEFORE R1 so that FRESH_FALLBACK (path absent) flows into R1's
    # auto_vacuum setup on the new empty file.
    if settings.checkpoint_auto_recover:
        _recovery_result = await _recover_checkpoint_db(checkpoint_path, logger)
        logger.info("storage_checkpoint_recovery_result", result=_recovery_result)

    # spec-029 R1 (unconditional): ensure auto_vacuum=INCREMENTAL before connection.
    # R1 MUST run after R2 — FRESH_FALLBACK leaves path missing; R1 creates the
    # file with auto_vacuum=INCREMENTAL so AsyncSqliteSaver.setup() builds the
    # schema on a DB that will never accumulate unbounded freelist pages.
    await _migrate_checkpoint_auto_vacuum(checkpoint_path, logger)

    checkpointer_cm = AsyncSqliteSaver.from_conn_string(checkpoint_path)
    checkpointer = await checkpointer_cm.__aenter__()
    await checkpointer.setup()
    await _check_checkpoint_integrity(checkpointer, logger)
    pruned = await _prune_old_checkpoint_threads(checkpointer, settings.checkpoint_max_threads, logger)
    if pruned > 0:
        logger.info(
            "storage_checkpoint_pruned",
            pruned_threads=pruned,
            max_threads=settings.checkpoint_max_threads,
        )
    app.state.checkpointer = checkpointer
    app.state._checkpointer_cm = checkpointer_cm
    logger.info("storage_checkpointer_initialized", path=checkpoint_path)

    # ENH-001: Cross-session store for user preferences and query patterns
    from langgraph.store.memory import InMemoryStore

    store = InMemoryStore()
    app.state.store = store
    logger.info("agent_cross_session_store_initialized")

    # --- Spec 03: ResearchGraph infrastructure ---
    from backend.retrieval.searcher import HybridSearcher
    from backend.retrieval.reranker import Reranker
    from backend.storage.parent_store import ParentStore
    from backend.agent.tools import create_research_tools
    from backend.agent.research_graph import build_research_graph
    from backend.agent.conversation_graph import build_conversation_graph

    hybrid_searcher = HybridSearcher(qdrant.client, settings)
    app.state.hybrid_searcher = hybrid_searcher
    logger.info("retrieval_hybrid_searcher_initialized")

    reranker_instance = Reranker(settings)
    app.state.reranker = reranker_instance
    logger.info("retrieval_reranker_initialized", model=settings.reranker_model)

    parent_store = ParentStore(db)
    app.state.parent_store = parent_store
    logger.info("storage_parent_store_initialized")

    # Build tool list via closure-based factory (R6)
    embed_provider = registry._ollama_embed
    research_tools = create_research_tools(
        hybrid_searcher, reranker_instance, parent_store, embed_provider=embed_provider
    )
    app.state.research_tools = research_tools
    logger.info("agent_research_tools_created", count=len(research_tools))

    # --- Spec 04: MetaReasoningGraph (Layer 3) ---
    from backend.agent.meta_reasoning_graph import build_meta_reasoning_graph

    # FR-011: skip meta-reasoning if max_attempts=0
    meta_reasoning_graph = None
    if settings.meta_reasoning_max_attempts > 0:
        meta_reasoning_graph = build_meta_reasoning_graph()
        logger.info("agent_meta_reasoning_graph_compiled")

    # Build graph chain inside-out: MetaReasoning -> Research -> Conversation
    research_graph = build_research_graph(
        tools=research_tools,
        meta_reasoning_graph=meta_reasoning_graph,
    )
    conversation_graph = build_conversation_graph(
        research_graph=research_graph,
        checkpointer=checkpointer,
        store=store,
    )
    app.state.conversation_graph = conversation_graph
    logger.info("agent_graphs_compiled", meta_reasoning_enabled=meta_reasoning_graph is not None)

    # FR-003: Observable startup warning — estimated in-process model memory (no psutil)
    # Approximate sizes for loaded sentence-transformer models.
    # LLM inference engine (Ollama/external) excluded — runs in a separate process.
    logger.warning(
        "agent_estimated_model_memory_footprint",
        reranker_model=settings.reranker_model,
        reranker_model_size_mb=400,
        embed_model=settings.default_embed_model,
        embed_model_size_mb=300,
        estimated_total_model_mb=700,
        budget_target_mb=600,
        note="SC-005: backend idle memory target <600 MB excluding inference engine",
    )

    # FR-050: Initialize shutdown flag — False during normal operation
    app.state.shutting_down = False

    yield

    # FR-050: Signal all in-flight requests to reject new work
    app.state.shutting_down = True

    # FR-051: WAL checkpoint for main database before closing
    await db.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    await db.close()

    # FR-051: WAL checkpoint for checkpoints database
    async with aiosqlite.connect(checkpoint_path) as ckpt_conn:
        await ckpt_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    # FR-052: Explicitly close the LangGraph checkpointer connection
    await app.state._checkpointer_cm.__aexit__(None, None, None)

    await qdrant.close()
    logger.info("storage_shutdown_complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="The Embedinator",
        description="Self-hosted agentic RAG system for private document intelligence",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware (order matters — outermost first)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(TraceIDMiddleware)

    # CORS middleware — allow local network access (no auth, FR-012)
    origins = [o.strip() for o in settings.cors_origins.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handler: rate limit errors from cloud providers → HTTP 429
    @app.exception_handler(ProviderRateLimitError)
    async def rate_limit_handler(request: Request, exc: ProviderRateLimitError):
        trace_id = getattr(request.state, "trace_id", "")
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "PROVIDER_RATE_LIMIT",
                    "message": f"Rate limit exceeded for provider: {exc.provider}",
                    "details": {"provider": exc.provider},
                },
                "trace_id": trace_id,
            },
        )

    # Exception handler: Qdrant connection errors → HTTP 503
    @app.exception_handler(QdrantConnectionError)
    async def qdrant_connection_error_handler(request: Request, exc: QdrantConnectionError):
        trace_id = getattr(request.state, "trace_id", "")
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "QDRANT_UNAVAILABLE",
                    "message": "Vector database is temporarily unavailable",
                    "details": {},
                },
                "trace_id": trace_id,
            },
        )

    # Exception handler: Ollama connection errors → HTTP 503
    @app.exception_handler(OllamaConnectionError)
    async def ollama_connection_error_handler(request: Request, exc: OllamaConnectionError):
        trace_id = getattr(request.state, "trace_id", "")
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "OLLAMA_UNAVAILABLE",
                    "message": "Inference service is temporarily unavailable",
                    "details": {},
                },
                "trace_id": trace_id,
            },
        )

    # Exception handler: global catch-all for any EmbeddinatorError → HTTP 500
    @app.exception_handler(EmbeddinatorError)
    async def embedinator_error_handler(request: Request, exc: EmbeddinatorError):
        trace_id = getattr(request.state, "trace_id", "")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An internal error occurred",
                    "details": {},
                },
                "trace_id": trace_id,
            },
        )

    # Register routers
    app.include_router(collections.router, tags=["collections"])
    app.include_router(documents.router, tags=["documents"])
    app.include_router(chat.router, tags=["chat"])
    app.include_router(traces.router, tags=["traces"])
    app.include_router(providers.router, tags=["providers"])
    app.include_router(health.router, tags=["health"])
    app.include_router(ingest_router.router, tags=["ingest"])
    app.include_router(models_router.router, tags=["models"])
    app.include_router(api_settings.router, tags=["settings"])

    return app


app = create_app()
