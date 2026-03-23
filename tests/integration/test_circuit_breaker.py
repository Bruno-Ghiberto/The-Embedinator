"""Integration tests for circuit breaker behavior on QdrantStorage.

All tests require a live Qdrant environment (marked require_docker) but
deliberately test with a bad port (6334) to force connection failures and
verify the circuit breaker state machine.

They are auto-skipped when Qdrant is unreachable on localhost:6333 via the
pytest_runtest_setup hook in tests/conftest.py.

CRITICAL: Always check `if instance is None` BEFORE `getattr(instance,
'_circuit_open', False)` to avoid getattr(None, ...) returning False and
masking a missing instance.
"""

import asyncio
import time

import pytest

from backend.errors import CircuitOpenError
from backend.storage.qdrant_client import QdrantStorage


def _bad_port_storage() -> QdrantStorage:
    """Return a QdrantStorage pointing to a port where nothing is listening."""
    storage = QdrantStorage(host="localhost", port=6334)
    # Lower the threshold so tests don't need many failure iterations.
    storage._max_failures = 3
    return storage


@pytest.mark.require_docker
async def test_circuit_opens_after_repeated_failures():
    """After _max_failures consecutive failures, _circuit_open becomes True."""
    storage = _bad_port_storage()
    assert storage._circuit_open is False

    # health_check() does not call _check_circuit() — it just tries and records.
    # Call it _max_failures times to exhaust the threshold.
    for _ in range(storage._max_failures):
        result = await storage.health_check()
        assert result is False  # Every attempt should fail

    assert storage._circuit_open is True, (
        f"Expected _circuit_open=True after {storage._max_failures} failures, "
        f"got _failure_count={storage._failure_count}"
    )


@pytest.mark.require_docker
async def test_circuit_open_raises_circuit_open_error_without_network_call():
    """When the circuit is open, CircuitOpenError is raised before any network call.

    The None-instance guard (recommended pattern):
        if instance is None:
            raise CircuitOpenError("No storage instance")
        if getattr(instance, '_circuit_open', False):
            raise CircuitOpenError("Circuit is open")

    Here we verify the same behaviour via _check_circuit() on a live instance.
    """
    storage = _bad_port_storage()

    # Manually open the circuit — avoids waiting for real network failures.
    storage._circuit_open = True
    storage._failure_count = storage._max_failures
    storage._last_failure_time = time.monotonic()

    # _check_circuit() must raise CircuitOpenError without attempting to connect.
    with pytest.raises(CircuitOpenError):
        storage._check_circuit()

    # create_collection() must also raise (it calls _check_circuit() first).
    with pytest.raises(CircuitOpenError):
        await storage.create_collection("should-not-reach-qdrant", vector_size=384)


@pytest.mark.require_docker
async def test_circuit_resets_after_cooldown_expires():
    """After the cooldown period elapses, the circuit transitions to closed."""
    storage = _bad_port_storage()

    # Open the circuit with a very short cooldown.
    storage._circuit_open = True
    storage._failure_count = storage._max_failures
    storage._cooldown_secs = 1
    storage._last_failure_time = time.monotonic()

    # Circuit is still open — _check_circuit() should raise.
    with pytest.raises(CircuitOpenError):
        storage._check_circuit()

    # Wait past the cooldown window.
    await asyncio.sleep(1.1)

    # _check_circuit() should now reset the circuit (half-open probe).
    storage._check_circuit()  # Must NOT raise

    assert storage._circuit_open is False, (
        "Circuit should have reset to closed after cooldown elapsed"
    )
