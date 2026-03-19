# A6 — Fixture Files + Coverage Gate (Wave 4)

**Agent type**: `python-expert`
**Model**: `claude-sonnet-4-6`
**Wave**: 4 (sequential — after Wave 3 completes)
**Gate requirement**: `Docs/Tests/spec16-a4.status` = PASSED AND Wave 3 skip checks confirmed. Confirm with orchestrator before starting.

Read `specs/016-testing-strategy/tasks.md` then await orchestrator instructions before proceeding.

---

## Assigned Tasks

| Task | Action |
|------|--------|
| T028 | Create `tests/fixtures/sample.pdf` — valid PDF binary |
| T029 | Create `tests/fixtures/sample.md` — Markdown document |
| T030 | Create `tests/fixtures/sample.txt` — plain UTF-8 text |
| T031 | Verify `pytest.ini` coverage gate; run coverage check |

`tests/fixtures/` directory must be created first:
```bash
mkdir -p tests/fixtures
```

---

## T028 — tests/fixtures/sample.pdf

A real PDF binary — NOT a renamed text file. The ingest API rejects files where `content[:4] != b"%PDF"`.

**Requirements**:
- Magic bytes `%PDF` at byte offset 0.
- Size under 50 KB (SC-008).
- At least 3 pages of readable text.
- Committed as a binary file in git.

**Creation options**:

Option A — Use `fpdf2` (if available in the environment):
```python
from fpdf import FPDF
pdf = FPDF()
for i in range(3):
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, f"Page {i+1}: Sample content for testing chunk extraction and retrieval.")
pdf.output("tests/fixtures/sample.pdf")
```

Option B — Use Python's `struct` to write a minimal valid PDF manually (100-byte skeleton) if `fpdf2` is unavailable.

After creating, verify:
```python
data = open("tests/fixtures/sample.pdf", "rb").read()
assert data[:4] == b"%PDF", "Magic bytes check failed"
assert len(data) < 50 * 1024, "File too large"
```

Then commit:
```bash
git add tests/fixtures/sample.pdf
git commit -m "test: add sample.pdf fixture for ingestion tests"
```

---

## T029 — tests/fixtures/sample.md

Valid Markdown with required structure. Create this file with your text editor or via Python.

**Requirements**:
- At least one `##` heading.
- At least one bulleted list (`- item`).
- At least one fenced code block (```).
- At least 2 prose paragraphs.
- File size 1–5 KB.
- Committed as text.

Example minimum structure:
```markdown
## Overview

This document describes a sample system for testing purposes.

The system processes documents through a pipeline that extracts text, generates embeddings, and stores results in a vector database.

## Features

- Text extraction from PDF and Markdown
- Hybrid dense and sparse vector search
- Cross-encoder reranking

## Code Example

```python
result = searcher.search("query", collection="test")
```

The results are returned in descending relevance order.
```

---

## T030 — tests/fixtures/sample.txt

Plain UTF-8 text with at least 500 words across 3+ paragraphs. No special formatting.

**Requirements**:
- 500+ words (verifiable with `len(open("tests/fixtures/sample.txt").split())`).
- At least 3 distinct paragraphs separated by blank lines.
- File size 2–10 KB.
- Committed as text.

Write 3 paragraphs of technical prose about document processing, search, or retrieval — anything with 500+ words total.

---

## T031 — Coverage Gate Verification

Verify that `pytest.ini` at project root contains `--cov-fail-under=80`:

```bash
grep "cov-fail-under=80" pytest.ini
```

If the line is missing (A1 omitted it), add it to the `addopts` line in `pytest.ini`.

Then run a coverage check:
```bash
zsh scripts/run-tests-external.sh -n spec16-cov tests/unit/
```

Verify:
```bash
cat Docs/Tests/spec16-cov.status
grep "TOTAL" Docs/Tests/spec16-cov.summary   # shows coverage percentage
```

If coverage is below 80%, the status will be FAILED (this is expected behavior — the hard gate is working). Report the actual coverage percentage to the orchestrator regardless of pass/fail.

---

## Post-Task Verification

After T028–T031, confirm fixture files are loadable:
```bash
python -c "
data = open('tests/fixtures/sample.pdf', 'rb').read()
assert data[:4] == b'%PDF', 'PDF magic bytes failed'
assert len(data) < 50 * 1024, 'PDF too large'
print('sample.pdf OK:', len(data), 'bytes')

md = open('tests/fixtures/sample.md').read()
assert '##' in md, 'No heading found'
print('sample.md OK:', len(md), 'chars')

txt = open('tests/fixtures/sample.txt').read()
assert len(txt.split()) >= 500, 'Less than 500 words'
print('sample.txt OK:', len(txt.split()), 'words')
"
```

Confirm all 3 files are tracked by git:
```bash
git ls-files tests/fixtures/
```

Report results to the orchestrator when complete.

---

## Critical Gotchas

- `sample.pdf` MUST be a real PDF binary, not a text file renamed to `.pdf`. Magic byte check: `content[:4] == b"%PDF"`.
- Commit the PDF as binary (`git add` without `--text` flag).
- `pytest.ini` is at project root, not in `src/`.
- NEVER run `pytest` directly. Always use `zsh scripts/run-tests-external.sh`.
