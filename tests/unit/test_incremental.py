"""Unit tests for IncrementalChecker — spec-06 ingestion pipeline."""

import hashlib
from unittest.mock import AsyncMock

import pytest

from backend.ingestion.incremental import IncrementalChecker


class TestComputeFileHash:
    """Tests for SHA256 hash computation."""

    def test_known_input_produces_known_hash(self, tmp_path):
        """SHA256 of known content matches expected hex digest."""
        test_file = tmp_path / "test.txt"
        content = b"hello world"
        test_file.write_bytes(content)

        result = IncrementalChecker.compute_file_hash(str(test_file))
        expected = hashlib.sha256(content).hexdigest()
        assert result == expected

    def test_empty_file_hash(self, tmp_path):
        """Empty file produces the SHA256 of empty bytes."""
        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")

        result = IncrementalChecker.compute_file_hash(str(test_file))
        expected = hashlib.sha256(b"").hexdigest()
        assert result == expected

    def test_large_file_hash_consistency(self, tmp_path):
        """File larger than 8KB block size still hashes correctly."""
        test_file = tmp_path / "large.bin"
        content = b"x" * 32768  # 32KB = 4 blocks of 8KB
        test_file.write_bytes(content)

        result = IncrementalChecker.compute_file_hash(str(test_file))
        expected = hashlib.sha256(content).hexdigest()
        assert result == expected

    def test_different_content_different_hash(self, tmp_path):
        """Different file contents produce different hashes."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_bytes(b"content A")
        file_b.write_bytes(b"content B")

        hash_a = IncrementalChecker.compute_file_hash(str(file_a))
        hash_b = IncrementalChecker.compute_file_hash(str(file_b))
        assert hash_a != hash_b

    def test_same_content_same_hash(self, tmp_path):
        """Identical content in different files produces identical hash."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_bytes(b"identical content")
        file_b.write_bytes(b"identical content")

        hash_a = IncrementalChecker.compute_file_hash(str(file_a))
        hash_b = IncrementalChecker.compute_file_hash(str(file_b))
        assert hash_a == hash_b


class TestCheckDuplicate:
    """Tests for duplicate detection."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_duplicate_completed_returns_true(self, mock_db):
        """Same hash + completed status -> (True, existing_doc_id)."""
        mock_db.find_document_by_hash.return_value = {
            "id": "doc-abc123",
            "status": "completed",
        }
        checker = IncrementalChecker(mock_db)

        is_dup, doc_id = await checker.check_duplicate("col-1", "hashABC")

        assert is_dup is True
        assert doc_id == "doc-abc123"
        mock_db.find_document_by_hash.assert_awaited_once_with("col-1", "hashABC")

    @pytest.mark.asyncio
    async def test_no_match_returns_false(self, mock_db):
        """No document with this hash -> (False, None)."""
        mock_db.find_document_by_hash.return_value = None
        checker = IncrementalChecker(mock_db)

        is_dup, doc_id = await checker.check_duplicate("col-1", "hashXYZ")

        assert is_dup is False
        assert doc_id is None

    @pytest.mark.asyncio
    async def test_failed_status_not_duplicate(self, mock_db):
        """Same hash + failed status -> (False, None) — allows re-ingestion (FR-004)."""
        mock_db.find_document_by_hash.return_value = {
            "id": "doc-failed123",
            "status": "failed",
        }
        checker = IncrementalChecker(mock_db)

        is_dup, doc_id = await checker.check_duplicate("col-1", "hashABC")

        assert is_dup is False
        assert doc_id is None

    @pytest.mark.asyncio
    async def test_pending_status_not_duplicate(self, mock_db):
        """Same hash + pending status -> (False, None)."""
        mock_db.find_document_by_hash.return_value = {
            "id": "doc-pending",
            "status": "pending",
        }
        checker = IncrementalChecker(mock_db)

        is_dup, doc_id = await checker.check_duplicate("col-1", "hashABC")

        assert is_dup is False
        assert doc_id is None

    @pytest.mark.asyncio
    async def test_per_collection_scoping(self, mock_db):
        """Same hash in different collections -> not duplicate."""
        # First call: collection A has it
        mock_db.find_document_by_hash.side_effect = [
            {"id": "doc-inA", "status": "completed"},
            None,  # Second call: collection B doesn't
        ]
        checker = IncrementalChecker(mock_db)

        is_dup_a, _ = await checker.check_duplicate("col-A", "hashABC")
        is_dup_b, _ = await checker.check_duplicate("col-B", "hashABC")

        assert is_dup_a is True
        assert is_dup_b is False


class TestCheckChange:
    """Tests for change detection."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        # Mock the nested db.db.execute pattern for direct SQL queries
        mock_cursor = AsyncMock()
        db.db = AsyncMock()
        db.db.execute = AsyncMock(return_value=mock_cursor)
        return db, mock_cursor

    @pytest.mark.asyncio
    async def test_changed_file_returns_old_doc_id(self, mock_db):
        """Same filename, different hash -> (True, old_doc_id)."""
        db, mock_cursor = mock_db
        mock_row = {"id": "doc-old123", "file_hash": "oldHash"}
        mock_cursor.fetchone = AsyncMock(return_value=mock_row)

        checker = IncrementalChecker(db)
        is_changed, old_id = await checker.check_change("col-1", "report.pdf", "newHash")

        assert is_changed is True
        assert old_id == "doc-old123"

    @pytest.mark.asyncio
    async def test_no_existing_file_returns_false(self, mock_db):
        """No document with this filename -> (False, None)."""
        db, mock_cursor = mock_db
        mock_cursor.fetchone = AsyncMock(return_value=None)

        checker = IncrementalChecker(db)
        is_changed, old_id = await checker.check_change("col-1", "new-file.pdf", "someHash")

        assert is_changed is False
        assert old_id is None

    @pytest.mark.asyncio
    async def test_same_hash_same_filename_returns_false(self, mock_db):
        """Same filename + same hash -> query returns no rows (WHERE hash != ?)."""
        db, mock_cursor = mock_db
        mock_cursor.fetchone = AsyncMock(return_value=None)

        checker = IncrementalChecker(db)
        is_changed, old_id = await checker.check_change("col-1", "report.pdf", "sameHash")

        assert is_changed is False
        assert old_id is None
        # Verify the SQL query includes the hash != condition
        call_args = db.db.execute.call_args
        sql = call_args[0][0]
        assert "file_hash != ?" in sql
