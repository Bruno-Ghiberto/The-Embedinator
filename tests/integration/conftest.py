"""Shared fixtures for integration tests."""

import uuid


def unique_name(prefix: str = "test") -> str:
    """Generate a unique collection name to avoid conflicts across test runs.

    Names are lowercased to satisfy the collection name regex: ^[a-z0-9][a-z0-9_-]*$
    """
    return f"{prefix.lower()}-{uuid.uuid4().hex[:8]}"
