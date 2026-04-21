"""Unit tests for backend.storage.chunker.chunk_text (T014).

chunk_text is a MODULE-LEVEL FUNCTION — do NOT instantiate any class.
Returns list[dict] with keys: text, chunk_index, start_offset, end_offset.
"""

from __future__ import annotations

import pytest

from backend.storage.chunker import chunk_text


# ---------------------------------------------------------------------------
# T014.1 — Empty input
# ---------------------------------------------------------------------------


class TestChunkTextEmpty:
    def test_empty_string_returns_empty_list(self):
        """chunk_text('') must return []."""
        result = chunk_text("")
        assert result == []

    def test_whitespace_only_returns_empty_list(self):
        """chunk_text with only spaces/newlines must return []."""
        result = chunk_text("   \n\t  \n  ")
        assert result == []

    def test_empty_returns_list_type(self):
        """Return value must be a list."""
        result = chunk_text("")
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# T014.2 — Short text → single chunk
# ---------------------------------------------------------------------------


class TestChunkTextShortText:
    def test_short_text_returns_single_chunk(self):
        """Text shorter than chunk_size must produce exactly one chunk."""
        short_text = "This is a short text."
        result = chunk_text(short_text, chunk_size=500)
        assert len(result) == 1

    def test_single_chunk_contains_text(self):
        """The single chunk's 'text' field must contain the input text (stripped)."""
        short_text = "Hello world."
        result = chunk_text(short_text, chunk_size=500)
        assert result[0]["text"] == short_text.strip()

    def test_single_chunk_index_is_zero(self):
        """First chunk must have chunk_index=0."""
        result = chunk_text("A short text.", chunk_size=500)
        assert result[0]["chunk_index"] == 0

    def test_single_chunk_offsets_present(self):
        """Single chunk must have start_offset and end_offset keys."""
        result = chunk_text("Some text.", chunk_size=500)
        assert "start_offset" in result[0]
        assert "end_offset" in result[0]

    def test_single_chunk_start_offset_is_zero(self):
        """First chunk always starts at offset 0."""
        result = chunk_text("Some text.", chunk_size=500)
        assert result[0]["start_offset"] == 0


# ---------------------------------------------------------------------------
# T014.3 — Long text → multiple chunks
# ---------------------------------------------------------------------------


class TestChunkTextLongText:
    def test_long_text_produces_multiple_chunks(self):
        """Text longer than chunk_size must produce more than one chunk."""
        # Generate text clearly longer than 500 chars
        long_text = "Word " * 200  # ~1000 chars
        result = chunk_text(long_text, chunk_size=200)
        assert len(result) > 1

    def test_chunk_indices_are_sequential(self):
        """chunk_index values must start at 0 and increment by 1."""
        long_text = "Sentence number N. " * 50
        result = chunk_text(long_text, chunk_size=100, chunk_overlap=10)
        indices = [c["chunk_index"] for c in result]
        assert indices == list(range(len(result)))

    def test_all_chunks_have_required_keys(self):
        """Every chunk dict must have text, chunk_index, start_offset, end_offset."""
        long_text = "The quick brown fox jumped. " * 30
        result = chunk_text(long_text, chunk_size=100, chunk_overlap=10)
        for chunk in result:
            assert "text" in chunk
            assert "chunk_index" in chunk
            assert "start_offset" in chunk
            assert "end_offset" in chunk

    def test_chunks_cover_most_of_text(self):
        """All chunks combined should cover most of the original text content."""
        long_text = "Alpha beta gamma delta epsilon. " * 20
        result = chunk_text(long_text, chunk_size=100, chunk_overlap=10)
        # Combined text should contain substantial portion of original
        combined = " ".join(c["text"] for c in result)
        assert len(combined) >= len(long_text) * 0.5


# ---------------------------------------------------------------------------
# T014.4 — No chunk exceeds max_size
# ---------------------------------------------------------------------------


class TestChunkTextMaxSize:
    def test_no_chunk_exceeds_chunk_size_by_more_than_boundary_slack(self):
        """Each chunk's text length must not exceed chunk_size by a large margin.

        The implementation may extend slightly past chunk_size to find a
        sentence/paragraph boundary, but should not exceed 2x chunk_size.
        """
        chunk_size = 150
        long_text = (
            "This is a longer sentence that continues. " * 20 + "Another paragraph starts here and continues on. " * 10
        )
        result = chunk_text(long_text, chunk_size=chunk_size, chunk_overlap=20)
        for chunk in result:
            # Allow 2x slack for boundary-seeking, but not unbounded growth
            assert len(chunk["text"]) <= chunk_size * 2, (
                f"Chunk {chunk['chunk_index']} text length {len(chunk['text'])} exceeds 2×chunk_size={2 * chunk_size}"
            )

    def test_chunk_size_controls_granularity(self):
        """Smaller chunk_size must produce more chunks than larger chunk_size."""
        long_text = "The quick brown fox. " * 40
        result_small = chunk_text(long_text, chunk_size=50, chunk_overlap=5)
        result_large = chunk_text(long_text, chunk_size=200, chunk_overlap=20)
        assert len(result_small) > len(result_large)


# ---------------------------------------------------------------------------
# T014.5 — Overlap parameter
# ---------------------------------------------------------------------------


class TestChunkTextOverlap:
    def test_overlap_zero_no_repeated_content(self):
        """With chunk_overlap=0, there should be minimal/no repeated content."""
        text = "AAA " * 10 + "BBB " * 10 + "CCC " * 10
        result = chunk_text(text, chunk_size=40, chunk_overlap=0)
        # With zero overlap, each chunk should start after the previous ends
        for i in range(1, len(result)):
            prev_end = result[i - 1]["end_offset"]
            curr_start = result[i]["start_offset"]
            # With overlap=0, current start == previous end (or very close)
            assert curr_start >= prev_end or curr_start == 0

    def test_overlap_creates_content_shared_between_consecutive_chunks(self):
        """With positive overlap, consecutive chunks should share some content."""
        # Use simple text with no boundary detection (no punctuation) to
        # ensure predictable overlap behavior
        text = "x" * 300
        result = chunk_text(text, chunk_size=100, chunk_overlap=30)
        if len(result) >= 2:
            # With overlap=30, chunk 1 should start before chunk 0 ends
            chunk0_end = result[0]["end_offset"]
            chunk1_start = result[1]["start_offset"]
            assert chunk1_start < chunk0_end

    def test_overlap_does_not_cause_infinite_loop(self):
        """Large overlap relative to chunk_size must not hang."""
        text = "Word " * 100
        # overlap < chunk_size required for progress — test 49/50 ratio
        result = chunk_text(text, chunk_size=50, chunk_overlap=49)
        # Should complete and produce at least one chunk
        assert len(result) >= 1

    def test_chunk_index_increments_with_overlap(self):
        """chunk_index must increment sequentially even with overlap."""
        text = "The fox jumps over the lazy dog. " * 20
        result = chunk_text(text, chunk_size=100, chunk_overlap=20)
        if len(result) > 1:
            indices = [c["chunk_index"] for c in result]
            assert indices == list(range(len(result)))
