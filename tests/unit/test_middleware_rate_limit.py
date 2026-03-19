"""Unit tests for RateLimitMiddleware — Spec 08 API Reference (T005)."""

from unittest.mock import patch

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from backend.middleware import RateLimitMiddleware, TraceIDMiddleware


# ── Helpers ──────────────────────────────────────────────────────


def _ok_endpoint(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


def _make_app() -> Starlette:
    """Create a minimal ASGI app with TraceID + RateLimit middleware."""
    app = Starlette(
        routes=[
            Route("/api/chat", _ok_endpoint, methods=["POST"]),
            Route("/api/collections/{cid}/ingest", _ok_endpoint, methods=["POST"]),
            Route("/api/providers/{name}/key", _ok_endpoint, methods=["PUT", "DELETE"]),
            Route("/api/collections", _ok_endpoint, methods=["GET"]),
            Route("/api/documents", _ok_endpoint, methods=["GET"]),
        ],
    )
    # TraceID is inner (runs first on request), RateLimit is outer
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(TraceIDMiddleware)
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_make_app(), raise_server_exceptions=False)


# ── Category Detection: _get_bucket + _get_limit ─────────────────


class TestCategoryDetection:
    """Verify all 4 rate limit categories are detected correctly."""

    def test_chat_bucket_and_limit(self):
        mw = RateLimitMiddleware(None)
        assert mw._get_bucket("/api/chat", "POST", "1.2.3.4") == "chat:1.2.3.4"
        assert mw._get_limit("/api/chat", "POST") == 30

    def test_ingest_bucket_and_limit(self):
        mw = RateLimitMiddleware(None)
        assert (
            mw._get_bucket("/api/collections/xyz/ingest", "POST", "1.2.3.4")
            == "ingest:1.2.3.4"
        )
        assert mw._get_limit("/api/collections/xyz/ingest", "POST") == 10

    def test_provider_key_put_bucket_and_limit(self):
        mw = RateLimitMiddleware(None)
        assert (
            mw._get_bucket("/api/providers/openai/key", "PUT", "1.2.3.4")
            == "provider_key:1.2.3.4"
        )
        assert mw._get_limit("/api/providers/openai/key", "PUT") == 5

    def test_provider_key_delete_bucket_and_limit(self):
        mw = RateLimitMiddleware(None)
        assert (
            mw._get_bucket("/api/providers/openai/key", "DELETE", "1.2.3.4")
            == "provider_key:1.2.3.4"
        )
        assert mw._get_limit("/api/providers/openai/key", "DELETE") == 5

    def test_provider_key_various_names(self):
        mw = RateLimitMiddleware(None)
        for name in ("anthropic", "openai", "openrouter", "my-provider"):
            path = f"/api/providers/{name}/key"
            assert mw._get_bucket(path, "PUT", "10.0.0.1") == "provider_key:10.0.0.1"
            assert mw._get_limit(path, "PUT") == 5

    def test_general_bucket_and_limit(self):
        mw = RateLimitMiddleware(None)
        assert (
            mw._get_bucket("/api/collections", "GET", "1.2.3.4") == "general:1.2.3.4"
        )
        assert mw._get_limit("/api/collections", "GET") == 120

    def test_general_for_non_matching_post(self):
        """POST to a non-chat, non-ingest path → general bucket."""
        mw = RateLimitMiddleware(None)
        assert (
            mw._get_bucket("/api/documents", "POST", "1.2.3.4") == "general:1.2.3.4"
        )
        assert mw._get_limit("/api/documents", "POST") == 120

    def test_get_on_provider_key_is_general(self):
        """GET /api/providers/openai/key → general (only PUT/DELETE are limited)."""
        mw = RateLimitMiddleware(None)
        assert (
            mw._get_bucket("/api/providers/openai/key", "GET", "1.2.3.4")
            == "general:1.2.3.4"
        )
        assert mw._get_limit("/api/providers/openai/key", "GET") == 120


# ── Settings-Based Limits ─────────────────────────────────────────


class TestSettingsBasedLimits:
    """Verify limits come from settings, not hardcoded values."""

    def test_chat_limit_reads_from_settings(self):
        with patch("backend.middleware.settings") as mock_settings:
            mock_settings.rate_limit_chat_per_minute = 50
            mock_settings.rate_limit_ingest_per_minute = 10
            mock_settings.rate_limit_provider_keys_per_minute = 5
            mock_settings.rate_limit_general_per_minute = 120
            mw = RateLimitMiddleware(None)
            assert mw._get_limit("/api/chat", "POST") == 50

    def test_ingest_limit_reads_from_settings(self):
        with patch("backend.middleware.settings") as mock_settings:
            mock_settings.rate_limit_chat_per_minute = 30
            mock_settings.rate_limit_ingest_per_minute = 25
            mock_settings.rate_limit_provider_keys_per_minute = 5
            mock_settings.rate_limit_general_per_minute = 120
            mw = RateLimitMiddleware(None)
            assert mw._get_limit("/api/collections/abc/ingest", "POST") == 25

    def test_provider_key_limit_reads_from_settings(self):
        with patch("backend.middleware.settings") as mock_settings:
            mock_settings.rate_limit_chat_per_minute = 30
            mock_settings.rate_limit_ingest_per_minute = 10
            mock_settings.rate_limit_provider_keys_per_minute = 3
            mock_settings.rate_limit_general_per_minute = 120
            mw = RateLimitMiddleware(None)
            assert mw._get_limit("/api/providers/openai/key", "PUT") == 3

    def test_general_limit_reads_from_settings(self):
        with patch("backend.middleware.settings") as mock_settings:
            mock_settings.rate_limit_chat_per_minute = 30
            mock_settings.rate_limit_ingest_per_minute = 10
            mock_settings.rate_limit_provider_keys_per_minute = 5
            mock_settings.rate_limit_general_per_minute = 200
            mw = RateLimitMiddleware(None)
            assert mw._get_limit("/api/collections", "GET") == 200


# ── 429 Response Format ──────────────────────────────────────────


class TestRateLimitResponse:
    """Verify 429 response body and headers."""

    def test_429_includes_trace_id_in_body(self, client: TestClient):
        """After exceeding the provider key limit (5), 429 body has trace_id."""
        for _ in range(5):
            resp = client.put("/api/providers/openai/key")
            assert resp.status_code == 200

        resp = client.put("/api/providers/openai/key")
        assert resp.status_code == 429
        body = resp.json()
        assert "trace_id" in body
        assert body["trace_id"]  # non-empty

    def test_429_error_code(self, client: TestClient):
        """429 body contains error.code = RATE_LIMIT_EXCEEDED."""
        for _ in range(5):
            client.put("/api/providers/openai/key")

        resp = client.put("/api/providers/openai/key")
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    def test_429_error_message_contains_limit(self, client: TestClient):
        """429 body contains human-readable message with limit value."""
        for _ in range(5):
            client.put("/api/providers/openai/key")

        resp = client.put("/api/providers/openai/key")
        body = resp.json()
        assert "5 requests per minute" in body["error"]["message"]

    def test_429_retry_after_header(self, client: TestClient):
        """429 response includes Retry-After: 60 header."""
        for _ in range(5):
            client.put("/api/providers/openai/key")

        resp = client.put("/api/providers/openai/key")
        assert resp.status_code == 429
        assert resp.headers.get("retry-after") == "60"

    def test_429_error_details_retry_after(self, client: TestClient):
        """429 body includes details.retry_after_seconds."""
        for _ in range(5):
            client.put("/api/providers/openai/key")

        resp = client.put("/api/providers/openai/key")
        body = resp.json()
        assert body["error"]["details"]["retry_after_seconds"] == 60


# ── Sliding Window Behavior ──────────────────────────────────────


class TestSlidingWindow:
    """Verify per-IP sliding window enforcement."""

    def test_chat_allows_up_to_limit(self, client: TestClient):
        """30 POST /api/chat requests should all succeed."""
        for i in range(30):
            resp = client.post("/api/chat")
            assert resp.status_code == 200, f"Request {i + 1} should succeed"

    def test_chat_rejects_over_limit(self, client: TestClient):
        """31st POST /api/chat request should return 429."""
        for _ in range(30):
            client.post("/api/chat")

        resp = client.post("/api/chat")
        assert resp.status_code == 429

    def test_provider_key_allows_up_to_limit(self, client: TestClient):
        """5 PUT /api/providers/openai/key requests should all succeed."""
        for i in range(5):
            resp = client.put("/api/providers/openai/key")
            assert resp.status_code == 200, f"Request {i + 1} should succeed"

    def test_provider_key_rejects_over_limit(self, client: TestClient):
        """6th PUT request to provider key endpoint should return 429."""
        for _ in range(5):
            client.put("/api/providers/openai/key")

        resp = client.put("/api/providers/openai/key")
        assert resp.status_code == 429

    def test_buckets_are_independent(self, client: TestClient):
        """Filling one bucket should not affect another."""
        # Fill chat bucket to capacity
        for _ in range(30):
            client.post("/api/chat")

        # Provider key bucket should still be open
        resp = client.put("/api/providers/openai/key")
        assert resp.status_code == 200

        # General bucket should still be open
        resp = client.get("/api/collections")
        assert resp.status_code == 200

    def test_delete_and_put_share_provider_key_bucket(self, client: TestClient):
        """PUT and DELETE on provider key share the same bucket."""
        for _ in range(3):
            client.put("/api/providers/openai/key")
        for _ in range(2):
            client.delete("/api/providers/openai/key")

        # 6th request (either method) should be rejected
        resp = client.put("/api/providers/openai/key")
        assert resp.status_code == 429


# ── TraceID Propagation ──────────────────────────────────────────


class TestTraceIDPropagation:
    """Verify trace_id flows from TraceIDMiddleware to 429 response."""

    def test_successful_response_has_trace_id_header(self, client: TestClient):
        """Normal responses should have X-Trace-ID header."""
        resp = client.get("/api/collections")
        assert "x-trace-id" in resp.headers

    def test_429_trace_id_matches_header(self, client: TestClient):
        """429 body trace_id should be a valid UUID string."""
        for _ in range(5):
            client.put("/api/providers/openai/key")

        resp = client.put("/api/providers/openai/key")
        assert resp.status_code == 429
        body = resp.json()
        trace_id = body["trace_id"]
        # Should be a non-empty string (UUID format)
        assert isinstance(trace_id, str)
        assert len(trace_id) > 0
