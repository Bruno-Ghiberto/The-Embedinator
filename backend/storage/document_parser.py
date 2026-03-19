"""Document parsing: PDF, Markdown, and plain text → raw text extraction."""

from pathlib import Path

from backend.errors import IngestionError


def parse_document(file_path: str, suffix: str) -> str:
    """Parse a document file and return extracted text content."""
    path = Path(file_path)
    if not path.exists():
        raise IngestionError(f"File not found: {file_path}")

    if suffix in (".txt", ".md"):
        return _parse_text(path)
    elif suffix == ".pdf":
        return _parse_pdf(path)
    else:
        raise IngestionError(f"Unsupported file format: {suffix}")


def _parse_text(path: Path) -> str:
    """Read plain text or Markdown files."""
    return path.read_text(encoding="utf-8")


def _parse_pdf(path: Path) -> str:
    """Extract text from PDF using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise IngestionError("pypdf is required for PDF parsing. Install with: pip install pypdf")

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)

    if not pages:
        raise IngestionError(f"No text extracted from PDF: {path.name}")

    return "\n\n".join(pages)
