"""Shared test fixtures for The Embedinator backend tests."""

import socket
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import AIMessage

from backend.storage.sqlite_db import SQLiteDB
from backend.agent.schemas import RetrievedChunk


def _is_docker_qdrant_available() -> bool:
    """Check if Qdrant is reachable on localhost:6333 via socket."""
    try:
        with socket.create_connection(("127.0.0.1", 6333), timeout=1):
            return True
    except OSError:
        return False


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "e2e: backend Python E2E tests using in-process ASGI"
    )
    config.addinivalue_line(
        "markers", "require_docker: tests requiring Qdrant on localhost:6333"
    )


def pytest_runtest_setup(item):
    if item.get_closest_marker("require_docker") and not _is_docker_qdrant_available():
        pytest.skip("Qdrant not available on localhost:6333")


@pytest_asyncio.fixture
async def db():
    """Isolated in-memory SQLiteDB. MUST use connect(), not initialize()."""
    instance = SQLiteDB(":memory:")
    await instance.connect()
    yield instance
    await instance.close()


@pytest.fixture
def sample_chunks() -> list[RetrievedChunk]:
    """Pre-built list[RetrievedChunk] with 3 items, scores [0.92, 0.78, 0.65]."""
    return [
        RetrievedChunk(
            chunk_id="chunk-001",
            text="Authentication requires a valid certificate from the WSAA service.",
            source_file="test-document.pdf",
            page=1,
            breadcrumb="Section 1 > Authentication",
            parent_id="parent-001",
            collection="test-collection",
            dense_score=0.92,
            sparse_score=0.75,
            rerank_score=None,
        ),
        RetrievedChunk(
            chunk_id="chunk-002",
            text="Token validation uses SAML 2.0 assertions for authorization.",
            source_file="test-document.pdf",
            page=2,
            breadcrumb="Section 1 > Tokens",
            parent_id="parent-001",
            collection="test-collection",
            dense_score=0.78,
            sparse_score=0.60,
            rerank_score=None,
        ),
        RetrievedChunk(
            chunk_id="chunk-003",
            text="Digital signatures require X.509 certificates for electronic invoicing.",
            source_file="test-document.pdf",
            page=5,
            breadcrumb="Section 2 > Invoicing",
            parent_id="parent-002",
            collection="test-collection",
            dense_score=0.65,
            sparse_score=0.48,
            rerank_score=None,
        ),
    ]


@pytest.fixture
def mock_llm():
    """MagicMock satisfying BaseChatModel interface.

    ainvoke returns AIMessage("This is a test answer.").
    with_structured_output returns self (supports chaining).
    """
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="This is a test answer."))
    llm.with_structured_output = MagicMock(return_value=llm)
    llm.astream = AsyncMock()
    return llm


@pytest.fixture
def mock_qdrant_results() -> list[dict]:
    """Raw Qdrant result dicts matching HybridSearcher payload format.

    Payload keys: text, source_file, page, breadcrumb, parent_id, sparse_score.
    Scores: [0.92, 0.78].
    """
    return [
        {
            "id": "chunk-001",
            "score": 0.92,
            "payload": {
                "text": "Authentication requires a valid certificate from the WSAA service.",
                "source_file": "test-document.pdf",
                "page": 1,
                "breadcrumb": "Section 1 > Authentication",
                "parent_id": "parent-001",
                "sparse_score": 0.75,
            },
        },
        {
            "id": "chunk-002",
            "score": 0.78,
            "payload": {
                "text": "Token validation uses SAML 2.0 assertions for authorization.",
                "source_file": "test-document.pdf",
                "page": 2,
                "breadcrumb": "Section 1 > Tokens",
                "parent_id": "parent-001",
                "sparse_score": 0.60,
            },
        },
    ]
