# Subprocess Contract: Rust Ingestion Worker

**Binary**: `embedinator-worker`
**Communication**: stdout (NDJSON) / stderr (diagnostics) / exit code
**Direction**: Python pipeline spawns → Rust worker streams → Python reads

## CLI Interface

```
embedinator-worker --file <path> [--type <pdf|markdown|text|code>]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `--file` | Yes | Absolute path to the input file |
| `--type` | No | Document type hint. Auto-detected from extension if omitted. |

### Type Auto-Detection

| Extension | Detected Type |
|-----------|--------------|
| `.pdf` | `pdf` |
| `.md` | `markdown` |
| `.txt` | `text` |
| `.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.h` | `code` |

## Output: NDJSON to stdout

One JSON object per line. Each line is a complete, self-contained chunk.

### Schema (per line)

```json
{
  "text": "string — extracted text content",
  "page": 3,
  "section": "2.3 Authentication",
  "heading_path": ["Chapter 2: API Reference", "2.3 Authentication"],
  "doc_type": "prose",
  "chunk_profile": "default",
  "chunk_index": 7
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | Yes | Extracted text content for this chunk |
| `page` | integer | Yes | Page number (1-indexed for PDF; section index for MD/text/code) |
| `section` | string | Yes | Current section heading (empty string if none) |
| `heading_path` | string[] | Yes | Full heading hierarchy from document root (empty array if no headings) |
| `doc_type` | string | Yes | `"prose"` for PDF/MD/text, `"code"` for code files |
| `chunk_profile` | string | Yes | `"default"` (reserved for future chunking profiles) |
| `chunk_index` | integer | Yes | Global 0-indexed position of this chunk within the document |

### DocType Values

| Value | Used For | Chunking Strategy |
|-------|----------|-------------------|
| `prose` | PDF, Markdown, plain text | Paragraph/sentence boundary splitting |
| `code` | Code files (.py, .js, etc.) | Paragraph-boundary splitting with code-aware handling |

## Diagnostics: stderr

Human-readable error and warning messages. Not parsed by the Python pipeline — logged verbatim.

```
[WARN] Page 45: no extractable text (image-only page)
[ERROR] Failed to parse page 102: invalid PDF object
```

## Exit Codes

| Code | Meaning | Pipeline Behavior |
|------|---------|-------------------|
| 0 | Success — all pages/sections parsed | Process all chunks, mark job `completed` |
| 1 | File error (not found, permission denied, unsupported) | Process any streamed chunks, mark job `failed` |
| 2 | Parse error (corrupt file, partial failure) | Process successfully streamed chunks, mark job `failed` |

### Partial Output Guarantee

If the worker exits with code 1 or 2, any chunks already written to stdout are valid and should be processed by the pipeline. The worker writes complete JSON lines atomically — a line either appears in full or not at all.

## Spawn Pattern (Python)

```python
import subprocess

proc = subprocess.Popen(
    [settings.rust_worker_path, "--file", file_path],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

for line in proc.stdout:
    chunk = json.loads(line.strip())
    # process chunk...

proc.wait()
stderr_output = proc.stderr.read()

if proc.returncode != 0:
    logger.error("worker_failed", exit_code=proc.returncode, stderr=stderr_output)
```

## Expected Output Volume

| Input | Approximate Output |
|-------|-------------------|
| 200-page PDF | ~600 chunks |
| 10-page Markdown | ~30 chunks |
| 500-line code file | ~10 chunks |
| 1-page text file | ~2-3 chunks |

## Invariants

1. Every output line is valid JSON (parseable by `json.loads`)
2. `chunk_index` is monotonically increasing within a single run (0, 1, 2, ...)
3. `page` is monotonically non-decreasing (pages are processed in order)
4. `heading_path` is consistent — if `heading_path` is `["A", "B"]`, then a chunk in section B always includes `["A", "B"]`, not just `["B"]`
5. Empty text chunks (e.g., image-only PDF pages) are NOT emitted — the worker skips them and logs a warning to stderr
6. The worker produces no side effects beyond stdout/stderr output — it does not modify the input file or any other files
