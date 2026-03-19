"""Unit tests for document parser — T031."""

import tempfile
from pathlib import Path

import pytest

from backend.storage.document_parser import parse_document
from backend.errors import IngestionError


def test_parse_txt():
    """Verify plain text parsing."""
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write("Hello, world!")
        f.flush()
        text = parse_document(f.name, ".txt")
    assert text == "Hello, world!"


def test_parse_markdown():
    """Verify Markdown parsing."""
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write("# Title\n\nSome content.")
        f.flush()
        text = parse_document(f.name, ".md")
    assert "Title" in text
    assert "Some content" in text


def test_unsupported_format():
    """Verify unsupported formats raise IngestionError."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        with pytest.raises(IngestionError, match="Unsupported"):
            parse_document(f.name, ".docx")


def test_missing_file():
    """Verify missing file raises IngestionError."""
    with pytest.raises(IngestionError, match="not found"):
        parse_document("/nonexistent/file.txt", ".txt")
