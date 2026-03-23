#!/usr/bin/env python3
"""Idempotent data seeding script for The Embedinator.

Usage:
    python scripts/seed_data.py [--base-url URL] [--timeout SECONDS]

Exit codes:
    0 — Seeding completed successfully (including idempotent re-run)
    1 — Seeding failed (API error, timeout, ingestion failure)
    2 — Cannot connect to backend
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

import httpx

# Resolve the repository root (two levels up from this script)
REPO_ROOT = Path(__file__).parent.parent
FIXTURE_FILE = REPO_ROOT / "tests" / "fixtures" / "sample.md"

COLLECTION_NAME = "sample-knowledge-base"
COLLECTION_DISPLAY = "Sample Knowledge Base"
COLLECTION_DESCRIPTION = "Sample documents for testing and demonstration"
DOCUMENT_FILENAME = "sample.md"


def _header():
    print("Seed Data — The Embedinator")
    print("============================")


def _footer(message: str):
    print("============================")
    print(message)


async def _check_connection(client: httpx.AsyncClient) -> bool:
    """Return True if backend is reachable."""
    try:
        resp = await client.get("/api/health", timeout=5.0)
        return resp.status_code < 500
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


async def _get_existing_collection(client: httpx.AsyncClient) -> dict | None:
    """Return collection dict if 'sample-knowledge-base' already exists, else None."""
    resp = await client.get("/api/collections", timeout=10.0)
    resp.raise_for_status()
    for coll in resp.json().get("collections", []):
        if coll["name"] == COLLECTION_NAME:
            return coll
    return None


async def _create_collection(client: httpx.AsyncClient) -> dict:
    """Create the sample collection. Returns the created collection dict."""
    resp = await client.post(
        "/api/collections",
        json={
            "name": COLLECTION_NAME,
            "description": COLLECTION_DESCRIPTION,
        },
        timeout=10.0,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to create collection: {resp.status_code} {resp.text}"
        )
    return resp.json()


async def _get_existing_document(client: httpx.AsyncClient, collection_id: str) -> dict | None:
    """Return document dict if sample.md is already ingested in the collection, else None."""
    resp = await client.get(
        "/api/documents",
        params={"collection_id": collection_id},
        timeout=10.0,
    )
    resp.raise_for_status()
    for doc in resp.json().get("documents", []):
        if doc.get("filename") == DOCUMENT_FILENAME and doc.get("status") == "completed":
            return doc
    return None


async def _upload_document(client: httpx.AsyncClient, collection_id: str) -> str:
    """Upload sample.md and return the job_id."""
    if not FIXTURE_FILE.exists():
        raise RuntimeError(f"Fixture file not found: {FIXTURE_FILE}")

    file_content = FIXTURE_FILE.read_bytes()
    files = {"file": (DOCUMENT_FILENAME, file_content, "text/markdown")}
    resp = await client.post(
        f"/api/collections/{collection_id}/ingest",
        files=files,
        timeout=30.0,
    )
    if resp.status_code == 409:
        # Duplicate detected by backend
        detail = resp.json().get("detail", {})
        error = detail.get("error", {}) if isinstance(detail, dict) else {}
        if error.get("code") == "DUPLICATE_DOCUMENT":
            return "__duplicate__"
    if resp.status_code not in (200, 202):
        raise RuntimeError(
            f"Failed to upload document: {resp.status_code} {resp.text}"
        )
    return resp.json()["job_id"]


async def _poll_ingestion(
    client: httpx.AsyncClient,
    collection_id: str,
    job_id: str,
    timeout_seconds: int,
) -> dict:
    """Poll job status every 5s until completed/failed or timeout. Returns final job dict."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        resp = await client.get(
            f"/api/collections/{collection_id}/ingest/{job_id}",
            timeout=10.0,
        )
        resp.raise_for_status()
        job = resp.json()
        status = job.get("status", "")
        if status == "completed":
            return job
        if status == "failed":
            raise RuntimeError(
                f"Ingestion failed: {job.get('error_message', 'unknown error')}"
            )
        await asyncio.sleep(5)
    raise RuntimeError(
        f"Ingestion timed out after {timeout_seconds}s (last status: {status})"
    )


async def _get_document_chunk_count(client: httpx.AsyncClient, collection_id: str) -> int:
    """Return chunk_count for the completed sample.md document."""
    resp = await client.get(
        "/api/documents",
        params={"collection_id": collection_id},
        timeout=10.0,
    )
    resp.raise_for_status()
    for doc in resp.json().get("documents", []):
        if doc.get("filename") == DOCUMENT_FILENAME:
            return doc.get("chunk_count") or 0
    return 0


async def seed(base_url: str, timeout: int) -> int:
    """Run the seeding workflow. Returns exit code."""
    _header()

    async with httpx.AsyncClient(base_url=base_url) as client:
        # Check connectivity
        if not await _check_connection(client):
            print(f"ERROR: Cannot connect to backend at {base_url}")
            _footer("Connection failed.")
            return 2

        # ── Collection ────────────────────────────────────────────
        existing_coll = await _get_existing_collection(client)
        if existing_coll:
            collection_id = existing_coll["id"]
            print(f"Collection: {COLLECTION_DISPLAY} (id: {collection_id})")
            print(f"  Status: exists (skipped)")
            coll_created = False
        else:
            try:
                new_coll = await _create_collection(client)
                collection_id = new_coll["id"]
                print(f"Collection: {COLLECTION_DISPLAY} (id: {collection_id})")
                print(f"  Status: created (new)")
                coll_created = True
            except RuntimeError as exc:
                print(f"ERROR creating collection: {exc}")
                _footer("Seeding failed.")
                return 1

        # ── Document ──────────────────────────────────────────────
        existing_doc = await _get_existing_document(client, collection_id)
        if existing_doc:
            chunk_count = existing_doc.get("chunk_count") or 0
            print(f"Document: {DOCUMENT_FILENAME}")
            print(f"  Status: already ingested ({chunk_count} chunks, skipped)")
            _footer("Already seeded. Nothing to do.")
            return 0

        # Upload
        try:
            job_id = await _upload_document(client, collection_id)
        except RuntimeError as exc:
            print(f"ERROR uploading document: {exc}")
            _footer("Seeding failed.")
            return 1

        if job_id == "__duplicate__":
            print(f"Document: {DOCUMENT_FILENAME}")
            print(f"  Status: duplicate detected by backend (skipped)")
            _footer("Already seeded. Nothing to do.")
            return 0

        print(f"Document: {DOCUMENT_FILENAME}")
        print(f"  Uploading... job_id={job_id}")

        # Poll for completion
        try:
            final_job = await _poll_ingestion(client, collection_id, job_id, timeout)
        except RuntimeError as exc:
            print(f"  ERROR: {exc}")
            _footer("Seeding failed.")
            return 1

        chunk_count = await _get_document_chunk_count(client, collection_id)
        chunks_processed = final_job.get("chunks_processed", 0)
        print(f"  Status: ingested ({chunks_processed or chunk_count} chunks)")

        # Validate SC-003: chunk_count > 0
        if chunk_count == 0 and chunks_processed == 0:
            print("  WARNING: chunk_count is 0 — ingestion may have produced no chunks")
            _footer("Seeding completed with warnings.")
            return 1

        _footer("Seeding complete.")
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Idempotent data seeding script for The Embedinator"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Backend API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Ingestion polling timeout in seconds (default: 120)",
    )
    args = parser.parse_args()

    exit_code = asyncio.run(seed(args.base_url, args.timeout))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
