"""Unit tests for citation building."""

from backend.agent.citations import build_citations, format_passages_for_prompt


def _make_passage(doc_id="doc1", doc_name="test.pdf", text="Some text", score=0.9, chunk=0):
    return {
        "id": f"p-{doc_id}-{chunk}",
        "document_id": doc_id,
        "document_name": doc_name,
        "text": text,
        "relevance_score": score,
        "chunk_index": chunk,
    }


def test_build_citations_basic():
    passages = [_make_passage()]
    citations = build_citations(passages)
    assert len(citations) == 1
    assert citations[0]["document_name"] == "test.pdf"


def test_build_citations_deduplicates_documents():
    passages = [
        _make_passage(doc_id="doc1", chunk=0),
        _make_passage(doc_id="doc1", chunk=1),
        _make_passage(doc_id="doc2", chunk=0),
    ]
    citations = build_citations(passages, max_citations=5)
    assert len(citations) == 2


def test_build_citations_max_limit():
    passages = [_make_passage(doc_id=f"doc{i}") for i in range(10)]
    citations = build_citations(passages, max_citations=3)
    assert len(citations) == 3


def test_build_citations_truncates_text():
    long_text = "x" * 500
    passages = [_make_passage(text=long_text)]
    citations = build_citations(passages)
    assert len(citations[0]["passage_text"]) == 200


def test_format_passages_for_prompt():
    passages = [
        _make_passage(doc_name="a.pdf", text="First passage"),
        _make_passage(doc_name="b.pdf", text="Second passage"),
    ]
    result = format_passages_for_prompt(passages)
    assert "[1] (Source: a.pdf) First passage" in result
    assert "[2] (Source: b.pdf) Second passage" in result


def test_format_passages_respects_max():
    passages = [_make_passage(doc_id=f"doc{i}", text=f"text{i}") for i in range(10)]
    result = format_passages_for_prompt(passages, max_passages=2)
    assert "[1]" in result
    assert "[2]" in result
    assert "[3]" not in result
