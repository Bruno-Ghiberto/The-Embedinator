"""Text chunking with parent/child strategy for RAG retrieval."""


def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[dict]:
    """Split text into overlapping chunks.

    Returns a list of chunk dicts with:
        - text: chunk content
        - chunk_index: position in document
        - start_offset: character offset in original text
        - end_offset: character offset in original text
    """
    if not text.strip():
        return []

    chunks = []
    start = 0
    index = 0

    while start < len(text):
        end = start + chunk_size

        # Try to break at a sentence or paragraph boundary
        if end < len(text):
            # Look for paragraph break
            para_break = text.rfind("\n\n", start, end)
            if para_break > start + chunk_size // 2:
                end = para_break + 2
            else:
                # Look for sentence break
                for sep in (". ", ".\n", "! ", "? "):
                    sent_break = text.rfind(sep, start, end)
                    if sent_break > start + chunk_size // 2:
                        end = sent_break + len(sep)
                        break

        chunk_text_content = text[start:end].strip()
        if chunk_text_content:
            chunks.append({
                "text": chunk_text_content,
                "chunk_index": index,
                "start_offset": start,
                "end_offset": min(end, len(text)),
            })
            index += 1

        start = end - chunk_overlap
        if start >= len(text):
            break

    return chunks
