"""Text chunker: parent/child splitting with breadcrumbs and deterministic UUID5 IDs (FR-007, FR-008)."""

import re
import uuid
from dataclasses import dataclass, field

import structlog

from backend.config import settings

logger = structlog.get_logger().bind(component=__name__)

# Deterministic namespace for UUID5 point IDs (FR-008)
EMBEDINATOR_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

# Sentence boundary pattern: split after . ! ? followed by whitespace
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class ParentChunkData:
    """Internal representation of a parent chunk before DB storage."""

    chunk_id: str
    text: str
    source_file: str
    page: int | None
    breadcrumb: str | None
    children: list[dict] = field(default_factory=list)
    # list of {text: str, point_id: str, chunk_index: int}


class ChunkSplitter:
    """Splits raw worker output into parent/child chunks with breadcrumbs and UUID5 IDs."""

    def __init__(self, parent_size: int | None = None, child_size: int | None = None):
        self.parent_size = parent_size or settings.parent_chunk_size
        self.child_size = child_size or settings.child_chunk_size

    def split_into_parents(
        self, raw_chunks: list[dict], source_file: str
    ) -> list[ParentChunkData]:
        """Accumulate raw worker chunks into parent chunks (2000-4000 chars).

        Each raw_chunk has: text, page, section, heading_path, doc_type, chunk_index.
        Start a new parent when adding the next raw chunk would exceed max size (2*parent_size)
        or when there is a heading change.
        """
        if not raw_chunks:
            return []

        max_parent = int(self.parent_size * 4 / 3)  # ~4000 for default 3000
        parents: list[ParentChunkData] = []

        current_text = ""
        current_page: int | None = None
        current_heading_path: list[str] = []
        current_chunk_indices: list[int] = []

        def _flush() -> None:
            nonlocal current_text, current_page, current_heading_path, current_chunk_indices
            if not current_text.strip():
                return

            breadcrumb = " > ".join(current_heading_path) if current_heading_path else None
            chunk_id = self.compute_point_id(
                source_file, current_page or 0, current_chunk_indices[0]
            )

            # Split parent text into children
            child_texts = self.split_parent_into_children(current_text)
            children = []
            for i, child_text in enumerate(child_texts):
                child_idx = current_chunk_indices[0] + i
                point_id = self.compute_point_id(source_file, current_page or 0, child_idx)
                children.append(
                    {"text": child_text, "point_id": point_id, "chunk_index": child_idx}
                )

            parent = ParentChunkData(
                chunk_id=chunk_id,
                text=current_text,
                source_file=source_file,
                page=current_page,
                breadcrumb=breadcrumb,
                children=children,
            )
            parents.append(parent)
            logger.debug(
                "ingestion_parent_chunk_created",
                chunk_id=chunk_id,
                chars=len(current_text),
                children=len(children),
                page=current_page,
            )

            current_text = ""
            current_chunk_indices = []

        for raw in raw_chunks:
            text = raw.get("text", "")
            page = raw.get("page")
            heading_path = raw.get("heading_path", [])
            chunk_index = raw.get("chunk_index", 0)

            if not text.strip():
                continue

            # Start new parent on heading change (section break)
            heading_changed = heading_path != current_heading_path and current_text
            would_exceed = len(current_text) + len(text) > max_parent and current_text

            if heading_changed or would_exceed:
                _flush()

            if not current_text:
                current_page = page
                current_heading_path = heading_path

            if current_text:
                current_text += "\n\n" + text
            else:
                current_text = text

            current_chunk_indices.append(chunk_index)

        # Flush remaining
        _flush()

        logger.info(
            "ingestion_split_into_parents_complete",
            source_file=source_file,
            parent_count=len(parents),
            raw_chunk_count=len(raw_chunks),
        )
        return parents

    def split_parent_into_children(
        self, parent_text: str, target_size: int | None = None
    ) -> list[str]:
        """Split a parent chunk into child chunks (~target_size chars) on sentence boundaries."""
        target = target_size or self.child_size
        if not parent_text.strip():
            return []

        sentences = _SENTENCE_SPLIT_RE.split(parent_text)
        if not sentences:
            return [parent_text]

        children: list[str] = []
        current = ""

        for sentence in sentences:
            if not sentence.strip():
                continue

            if current and len(current) + len(sentence) + 1 > target:
                children.append(current.strip())
                current = sentence
            else:
                current = current + " " + sentence if current else sentence

        if current.strip():
            children.append(current.strip())

        return children

    @staticmethod
    def prepend_breadcrumb(text: str, heading_path: list[str]) -> str:
        """Prepend breadcrumb prefix: '[A > B > C] text'."""
        if not heading_path:
            return text
        prefix = " > ".join(heading_path)
        return f"[{prefix}] {text}"

    @staticmethod
    def compute_point_id(source_file: str, page: int, chunk_index: int) -> str:
        """Deterministic UUID5 for idempotent upserts (FR-008)."""
        key = f"{source_file}:{page}:{chunk_index}"
        return str(uuid.uuid5(EMBEDINATOR_NAMESPACE, key))
