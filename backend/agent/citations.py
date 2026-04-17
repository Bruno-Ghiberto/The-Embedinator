"""Citation construction from retrieved passages — T036.

Maps passages to source documents and builds citation objects.
"""


def build_citations(passages: list[dict], max_citations: int = 3) -> list[dict]:
    """Build citation list from top passages.

    Each citation includes document name and a text excerpt (max 200 chars).
    """
    citations = []
    seen_docs = set()

    for p in passages[:max_citations]:
        doc_key = p["document_id"]
        if doc_key in seen_docs:
            continue
        seen_docs.add(doc_key)
        citations.append(
            {
                "document_name": p["document_name"],
                "document_id": p["document_id"],
                "passage_text": p["text"][:200],
                "chunk_index": p["chunk_index"],
                "relevance_score": p["relevance_score"],
            }
        )

    return citations


def format_passages_for_prompt(passages: list[dict], max_passages: int = 5) -> str:
    """Format passages into a numbered text block for LLM prompt injection."""
    return "\n\n".join(
        f"[{i + 1}] (Source: {p['document_name']}) {p['text']}" for i, p in enumerate(passages[:max_passages])
    )
