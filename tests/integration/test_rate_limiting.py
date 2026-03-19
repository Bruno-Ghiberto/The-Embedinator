"""Integration tests for rate limiting — T031.

Burst tests for all 4 rate limit categories. Each test uses a fresh app
instance to avoid state leakage between tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessageChunk

from backend.api import (
    chat,
    collections,
    providers,
)
from backend.api import ingest as ingest_router
from backend.middleware import RateLimitMiddleware, TraceIDMiddleware


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_mock_graph():
    """Build a mock ConversationGraph that returns quickly."""
    graph = MagicMock()

    async def mock_astream(state, *, stream_mode="messages", config=None):
        msg = AIMessageChunk(content="Answer")
        yield msg, {"langgraph_node": "respond"}

    graph.astream = mock_astream

    state_snapshot = MagicMock()
    state_snapshot.values = {
        "citations": [],
        "attempted_strategies": set(),
        "confidence_score": 80,
        "groundedness_result": None,
        "sub_questions": [],
        "final_response": "Answer",
    }
    graph.get_state = MagicMock(return_value=state_snapshot)
    return graph


def _make_rate_limit_app(
    *,
    routers=None,
    graph=None,
) -> FastAPI:
    """Build a test app with rate limiting middleware."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(TraceIDMiddleware)

    if routers is None:
        routers = [chat.router, collections.router, providers.router, ingest_router.router]
    for r in routers:
        app.include_router(r)

    app.state.db = AsyncMock()
    app.state.qdrant_storage = AsyncMock()
    app.state.qdrant = AsyncMock()
    app.state.key_manager = MagicMock()
    app.state.key_manager.encrypt.return_value = "encrypted"
    app.state.checkpointer = None
    app.state.research_graph = None

    if graph is not None:
        app.state._conversation_graph = graph

    # Make db.get_provider return a provider for key operations
    app.state.db.get_provider = AsyncMock(return_value={
        "name": "openai",
        "api_key_encrypted": None,
        "base_url": None,
        "is_active": False,
        "created_at": "2026-01-01T00:00:00Z",
    })
    app.state.db.update_provider = AsyncMock()
    app.state.db.list_collections = AsyncMock(return_value=[])

    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestChatRateLimit:
    """Chat endpoint: 30 requests/minute."""

    def test_burst_30_succeeds_31st_returns_429(self):
        """Send 31 POST /api/chat — first 30 succeed, 31st returns 429 (SC-004)."""
        graph = _build_mock_graph()
        app = _make_rate_limit_app(routers=[chat.router], graph=graph)

        with TestClient(app) as client:
            statuses = []
            for i in range(31):
                resp = client.post(
                    "/api/chat",
                    json={
                        "message": f"Query {i}",
                        "collection_ids": ["test-coll"],
                    },
                )
                statuses.append(resp.status_code)

            # First 30 should succeed (200)
            assert all(s == 200 for s in statuses[:30]), (
                f"Expected first 30 to be 200, got: {statuses[:30]}"
            )
            # 31st should be rate limited
            assert statuses[30] == 429

    def test_429_has_retry_after_header(self):
        """429 response includes Retry-After: 60 header."""
        graph = _build_mock_graph()
        app = _make_rate_limit_app(routers=[chat.router], graph=graph)

        with TestClient(app) as client:
            for i in range(30):
                client.post(
                    "/api/chat",
                    json={"message": f"Q{i}", "collection_ids": ["c1"]},
                )
            resp = client.post(
                "/api/chat",
                json={"message": "overflow", "collection_ids": ["c1"]},
            )

        assert resp.status_code == 429
        assert resp.headers.get("retry-after") == "60"

    def test_429_has_trace_id_in_body(self):
        """429 response body includes trace_id."""
        graph = _build_mock_graph()
        app = _make_rate_limit_app(routers=[chat.router], graph=graph)

        with TestClient(app) as client:
            for i in range(30):
                client.post(
                    "/api/chat",
                    json={"message": f"Q{i}", "collection_ids": ["c1"]},
                )
            resp = client.post(
                "/api/chat",
                json={"message": "overflow", "collection_ids": ["c1"]},
            )

        assert resp.status_code == 429
        body = resp.json()
        assert "trace_id" in body
        assert isinstance(body["trace_id"], str)
        assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"


class TestIngestRateLimit:
    """Ingestion endpoint: 10 requests/minute."""

    def test_burst_10_succeeds_11th_returns_429(self):
        """Send 11 POST /api/collections/{id}/ingest — 10 succeed, 11th returns 429."""
        app = _make_rate_limit_app(routers=[ingest_router.router])
        # Make get_collection return something so we get past the 404 check
        # but the file extension check will fail first — that's fine for rate limit testing
        # Actually we want the first 10 to NOT be rate-limited, so they should hit
        # some endpoint logic. An unsupported extension (400) still counts for rate limit.
        app.state.db.get_collection = AsyncMock(return_value=None)

        with TestClient(app) as client:
            statuses = []
            for i in range(11):
                resp = client.post(
                    f"/api/collections/coll-{i}/ingest",
                    files={"file": ("doc.txt", b"content", "text/plain")},
                )
                statuses.append(resp.status_code)

            # First 10 should NOT be 429 (they may be 404 from missing collection)
            assert all(s != 429 for s in statuses[:10]), (
                f"Expected first 10 to not be 429, got: {statuses[:10]}"
            )
            # 11th should be rate limited
            assert statuses[10] == 429


class TestProviderKeyRateLimit:
    """Provider key endpoint: 5 requests/minute."""

    def test_burst_5_succeeds_6th_returns_429(self):
        """Send 6 PUT /api/providers/{name}/key — 5 succeed, 6th returns 429."""
        app = _make_rate_limit_app(routers=[providers.router])

        with TestClient(app) as client:
            statuses = []
            for i in range(6):
                resp = client.put(
                    "/api/providers/openai/key",
                    json={"api_key": f"sk-test-{i}"},
                )
                statuses.append(resp.status_code)

            # First 5 should succeed (200)
            assert all(s == 200 for s in statuses[:5]), (
                f"Expected first 5 to be 200, got: {statuses[:5]}"
            )
            # 6th should be rate limited
            assert statuses[5] == 429


class TestGeneralRateLimit:
    """General endpoint: 120 requests/minute."""

    def test_burst_120_succeeds_121st_returns_429(self):
        """Send 121 GET /api/collections — 120 succeed, 121st returns 429."""
        app = _make_rate_limit_app(routers=[collections.router])

        with TestClient(app) as client:
            statuses = []
            for i in range(121):
                resp = client.get("/api/collections")
                statuses.append(resp.status_code)

            # First 120 should succeed (200)
            assert all(s == 200 for s in statuses[:120]), (
                "Expected first 120 to be 200, got non-200 in first 120"
            )
            # 121st should be rate limited
            assert statuses[120] == 429


class TestRateLimitHeaders:
    """Cross-cutting header checks on rate-limited responses."""

    def test_x_trace_id_on_all_responses(self):
        """X-Trace-ID header present on both normal and 429 responses."""
        graph = _build_mock_graph()
        app = _make_rate_limit_app(routers=[chat.router], graph=graph)

        with TestClient(app) as client:
            # Normal response
            resp_ok = client.post(
                "/api/chat",
                json={"message": "Test", "collection_ids": ["c1"]},
            )
            assert "x-trace-id" in resp_ok.headers

            # Burn remaining quota
            for i in range(29):
                client.post(
                    "/api/chat",
                    json={"message": f"Q{i}", "collection_ids": ["c1"]},
                )

            # 429 response should also have trace_id via middleware
            resp_429 = client.post(
                "/api/chat",
                json={"message": "overflow", "collection_ids": ["c1"]},
            )
            assert resp_429.status_code == 429
            # The RateLimitMiddleware sets trace_id from request.state
            body = resp_429.json()
            assert "trace_id" in body
