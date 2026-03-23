"""Unit tests for ChunkSplitter — T026."""

import uuid

import pytest

from backend.ingestion.chunker import (
    EMBEDINATOR_NAMESPACE,
    ChunkSplitter,
    ParentChunkData,
)


@pytest.fixture
def splitter():
    """ChunkSplitter with explicit sizes (avoid settings dependency)."""
    return ChunkSplitter(parent_size=3000, child_size=500)


# --- split_into_parents ---


def test_empty_input_returns_no_parents(splitter):
    """Empty raw_chunks list produces no parents."""
    result = splitter.split_into_parents([], "test.pdf")
    assert result == []


def test_single_short_chunk_produces_one_parent(splitter):
    """A single raw chunk shorter than parent_size creates one parent."""
    raw = [
        {
            "text": "Hello world. " * 50,
            "page": 1,
            "section": "",
            "heading_path": [],
            "doc_type": "prose",
            "chunk_index": 0,
        }
    ]
    parents = splitter.split_into_parents(raw, "test.pdf")
    assert len(parents) == 1
    assert isinstance(parents[0], ParentChunkData)
    assert parents[0].source_file == "test.pdf"
    assert parents[0].page == 1


def test_parent_chunks_respect_size_bounds(splitter):
    """Multiple raw chunks accumulate into parents within size bounds."""
    # Create raw chunks that together exceed parent_size
    raw_chunks = [
        {
            "text": "Sentence one is here. " * 30,  # ~630 chars each
            "page": 1,
            "section": "Intro",
            "heading_path": ["Intro"],
            "doc_type": "prose",
            "chunk_index": i,
        }
        for i in range(10)
    ]
    parents = splitter.split_into_parents(raw_chunks, "doc.pdf")
    assert len(parents) >= 2
    for parent in parents:
        # Parent text should not exceed max_parent (~4000 for default 3000)
        assert len(parent.text) <= 4200  # Allow for join overhead


def test_heading_change_triggers_new_parent(splitter):
    """A change in heading_path forces a new parent chunk."""
    raw_chunks = [
        {
            "text": "Content A. " * 20,
            "page": 1,
            "section": "A",
            "heading_path": ["Chapter 1", "A"],
            "doc_type": "prose",
            "chunk_index": 0,
        },
        {
            "text": "Content B. " * 20,
            "page": 1,
            "section": "B",
            "heading_path": ["Chapter 1", "B"],
            "doc_type": "prose",
            "chunk_index": 1,
        },
    ]
    parents = splitter.split_into_parents(raw_chunks, "doc.pdf")
    assert len(parents) == 2
    assert parents[0].breadcrumb == "Chapter 1 > A"
    assert parents[1].breadcrumb == "Chapter 1 > B"


def test_parent_has_children(splitter):
    """Each parent has child chunks with text, point_id, and chunk_index."""
    raw = [
        {
            "text": "This is a test sentence. " * 80,
            "page": 1,
            "section": "",
            "heading_path": [],
            "doc_type": "prose",
            "chunk_index": 0,
        }
    ]
    parents = splitter.split_into_parents(raw, "test.pdf")
    assert len(parents) == 1
    children = parents[0].children
    assert len(children) >= 1
    for child in children:
        assert "text" in child
        assert "point_id" in child
        assert "chunk_index" in child


def test_whitespace_only_chunks_skipped(splitter):
    """Raw chunks with only whitespace are skipped."""
    raw = [
        {"text": "   ", "page": 1, "section": "", "heading_path": [], "doc_type": "prose", "chunk_index": 0},
        {"text": "\n\n", "page": 1, "section": "", "heading_path": [], "doc_type": "prose", "chunk_index": 1},
    ]
    parents = splitter.split_into_parents(raw, "test.pdf")
    assert parents == []


# --- split_parent_into_children ---


def test_child_chunks_approximately_target_size(splitter):
    """Child chunks are approximately 500 chars each."""
    text = "This is a meaningful sentence. " * 100  # ~3000 chars
    children = splitter.split_parent_into_children(text)
    assert len(children) >= 2
    for child in children:
        # Each child should be roughly around target size (some variance expected)
        assert len(child) <= 600  # Allow reasonable overflow


def test_child_split_preserves_sentence_boundaries(splitter):
    """Children are split on sentence boundaries, not mid-sentence."""
    text = "First sentence here. Second sentence here. Third sentence here. Fourth sentence here."
    children = splitter.split_parent_into_children(text, target_size=50)
    for child in children:
        # Each child should end with a complete sentence (period at end)
        assert (
            child.rstrip().endswith(".")
            or child.rstrip().endswith("!")
            or child.rstrip().endswith("?")
            or len(children) == 1
        )


def test_short_text_returns_single_child(splitter):
    """Text shorter than target_size returns a single child."""
    text = "Short text here."
    children = splitter.split_parent_into_children(text)
    assert len(children) == 1
    assert children[0] == "Short text here."


def test_empty_text_returns_no_children(splitter):
    """Empty or whitespace-only text returns no children."""
    assert splitter.split_parent_into_children("") == []
    assert splitter.split_parent_into_children("   ") == []


def test_very_long_single_sentence(splitter):
    """A single sentence longer than target_size still produces output."""
    text = "A" * 2000  # No sentence boundary
    children = splitter.split_parent_into_children(text)
    assert len(children) == 1
    assert children[0] == text


# --- prepend_breadcrumb ---


def test_breadcrumb_format():
    """Breadcrumb produces '[A > B] text' format."""
    result = ChunkSplitter.prepend_breadcrumb("Hello world", ["Chapter 2", "2.3 Auth"])
    assert result == "[Chapter 2 > 2.3 Auth] Hello world"


def test_breadcrumb_single_heading():
    """Single heading produces '[A] text'."""
    result = ChunkSplitter.prepend_breadcrumb("Content", ["Introduction"])
    assert result == "[Introduction] Content"


def test_breadcrumb_empty_heading_path():
    """Empty heading_path returns text unchanged."""
    result = ChunkSplitter.prepend_breadcrumb("Just text", [])
    assert result == "Just text"


def test_breadcrumb_three_levels():
    """Three-level heading hierarchy."""
    result = ChunkSplitter.prepend_breadcrumb("Details", ["Book", "Chapter 1", "Section 1.1"])
    assert result == "[Book > Chapter 1 > Section 1.1] Details"


# --- compute_point_id ---


def test_uuid5_determinism():
    """Same (source_file, page, chunk_index) always produces the same ID."""
    id1 = ChunkSplitter.compute_point_id("report.pdf", 3, 7)
    id2 = ChunkSplitter.compute_point_id("report.pdf", 3, 7)
    assert id1 == id2
    # Verify it's a valid UUID
    uuid.UUID(id1)


def test_uuid5_uniqueness_different_file():
    """Different source_file produces a different ID."""
    id1 = ChunkSplitter.compute_point_id("report.pdf", 1, 0)
    id2 = ChunkSplitter.compute_point_id("other.pdf", 1, 0)
    assert id1 != id2


def test_uuid5_uniqueness_different_page():
    """Different page produces a different ID."""
    id1 = ChunkSplitter.compute_point_id("report.pdf", 1, 0)
    id2 = ChunkSplitter.compute_point_id("report.pdf", 2, 0)
    assert id1 != id2


def test_uuid5_uniqueness_different_chunk_index():
    """Different chunk_index produces a different ID."""
    id1 = ChunkSplitter.compute_point_id("report.pdf", 1, 0)
    id2 = ChunkSplitter.compute_point_id("report.pdf", 1, 1)
    assert id1 != id2


def test_uuid5_uses_embedinator_namespace():
    """Point ID matches manual UUID5 computation with EMBEDINATOR_NAMESPACE."""
    point_id = ChunkSplitter.compute_point_id("test.pdf", 5, 10)
    expected = str(uuid.uuid5(EMBEDINATOR_NAMESPACE, "global:test.pdf:5:10"))
    assert point_id == expected


def test_uuid5_is_version_5():
    """Generated IDs are UUID version 5."""
    point_id = ChunkSplitter.compute_point_id("doc.pdf", 1, 0)
    parsed = uuid.UUID(point_id)
    assert parsed.version == 5


def test_uuid5_namespace_changes_output():
    """Different id_namespace should produce different deterministic IDs."""
    id1 = ChunkSplitter.compute_point_id("doc.pdf", 1, 0, id_namespace="collection-a")
    id2 = ChunkSplitter.compute_point_id("doc.pdf", 1, 0, id_namespace="collection-b")
    assert id1 != id2
