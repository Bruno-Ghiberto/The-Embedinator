# Agent: A5-rust-worker

**subagent_type**: system-architect | **Model**: Sonnet 4.6 | **Wave**: 2

## Mission

Implement the Rust ingestion worker binary (`embedinator-worker`) that parses documents (PDF, Markdown, plain text, code) and streams structured text chunks as NDJSON to stdout. This binary is spawned as a subprocess by the Python pipeline. Implement all parser modules, the heading hierarchy tracker, the NDJSON output serialization, the CLI interface, and comprehensive inline Rust tests.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-06-ingestion/06-implement.md` -- full code specifications (the authoritative reference)
2. `specs/006-ingestion-pipeline/contracts/worker-ndjson.md` -- THE DEFINITIVE CONTRACT: CLI interface, NDJSON schema, exit codes, invariants, expected output volumes
3. `specs/006-ingestion-pipeline/spec.md` -- FR-006 (native binary worker, NDJSON streaming), US4 acceptance scenarios
4. `specs/006-ingestion-pipeline/research.md` -- R1: pdf-extract crate selection
5. `specs/006-ingestion-pipeline/tasks.md` -- T012-T020
6. `ingestion-worker/Cargo.toml` -- dependencies (created by A1 as stub)

## Assigned Tasks

- T012: [P] [US4] Implement `types.rs`: `Chunk` struct with 7 fields (text, page, section, heading_path, doc_type, chunk_profile, chunk_index). `DocType` enum with exactly 2 variants: `Prose` and `Code`. Serde derives with `#[serde(rename_all = "lowercase")]` on DocType.
- T013: [P] [US4] Implement `heading_tracker.rs`: `HeadingTracker` struct with `push(level, text)` and `path() -> Vec<String>`. Push removes same-or-deeper level entries before inserting. Path returns current heading hierarchy.
- T014: [US4] Implement `text.rs`: plain text chunking. Split on double newlines (paragraph boundaries). Sentence boundary fallback within long paragraphs. Emit `Chunk` with `doc_type: Prose`.
- T015: [P] [US4] Implement `code.rs`: code file handling for 9 extensions (.py, .js, .ts, .rs, .go, .java, .c, .cpp, .h). Paragraph-boundary chunking similar to text.rs. Emit with `doc_type: Code`.
- T016: [US4] Implement `markdown.rs`: parse with pulldown-cmark. Split at H1/H2/H3 heading boundaries. Use HeadingTracker to maintain heading hierarchy. Emit chunks with correct `heading_path`.
- T017: [US4] Implement `pdf.rs`: PDF text extraction using `pdf-extract` crate (R1). Page-by-page iteration. Emit one or more chunks per page. Skip image-only pages (warn to stderr).
- T018: [US4] Implement `main.rs`: clap CLI (`--file <path>`, `--type <pdf|markdown|text|code>`). Auto-detect type from extension per worker-ndjson.md contract. Dispatch to parser module. Serialize each Chunk as NDJSON line to stdout. Write errors to stderr. Exit codes 0/1/2.
- T019: [US4] Write Rust tests in inline `#[cfg(test)]` modules: test NDJSON output schema, test heading_tracker hierarchy, test type auto-detection, test partial output on parse error.
- T020: [US4] Build release binary and smoke test: `cargo build --release`. Verify NDJSON output for a plain text file.

## Files to Create/Modify

### Create (replace A1 stubs with full implementations)
- `ingestion-worker/src/types.rs`
- `ingestion-worker/src/heading_tracker.rs`
- `ingestion-worker/src/text.rs`
- `ingestion-worker/src/code.rs`
- `ingestion-worker/src/markdown.rs`
- `ingestion-worker/src/pdf.rs`
- `ingestion-worker/src/main.rs`

### Modify
- `ingestion-worker/Cargo.toml` (adjust if A1 stub needs corrections)

## Key Patterns

- **DocType enum**: EXACTLY 2 variants: `Prose` and `Code`. NO `Table` or `Mixed`. Use `#[serde(rename_all = "lowercase")]` so JSON output is `"prose"` and `"code"`.
- **NDJSON output**: One complete JSON object per line to stdout. Use `serde_json::to_string(&chunk)` + `println!`. Each line must be a valid JSON object parseable by `json.loads` in Python.
- **HeadingTracker**: Maintains a `Vec<(usize, String)>` of (level, text) pairs. `push(level, text)` removes all entries where level >= the new level, then appends. `path()` returns the text values in order.
- **Type auto-detection**: Match file extension in main.rs: `.pdf` -> pdf, `.md` -> markdown, `.txt` -> text, `.py`/`.js`/`.ts`/`.rs`/`.go`/`.java`/`.c`/`.cpp`/`.h` -> code.
- **Exit codes**: 0=success (all pages parsed), 1=file error (not found, permission denied), 2=parse error (corrupt file, partial output). Use `std::process::exit()`.
- **Partial output (R4)**: If a parse error occurs mid-document, all chunks already written to stdout are valid. The Python pipeline reads them before checking the exit code.
- **stderr diagnostics**: Use `eprintln!` for warnings and errors. Format: `[WARN] Page 45: no extractable text` or `[ERROR] Failed to parse page 102`.
- **chunk_index**: Global 0-indexed counter across the entire document. Monotonically increasing.
- **chunk_profile**: Always `"default"` for Phase 2.
- **pdf-extract**: Use `pdf_extract::extract_text_from_mem` for in-memory extraction, or read file then extract page-by-page. Handle the case where a page has no extractable text (skip, warn to stderr).
- **pulldown-cmark**: Use `pulldown_cmark::Parser` with `Options::ENABLE_TABLES | Options::ENABLE_HEADING_ATTRIBUTES`. Iterate events, split on `Event::Start(Tag::Heading(..))`.

## Constraints

- Rust tests run via `cargo test` (NOT pytest, NOT the external test runner)
- NEVER modify Python files -- you only work in `ingestion-worker/`
- The binary name must be `embedinator-worker` (set in Cargo.toml `[[bin]]` or `[package]` name)
- All output goes to stdout (NDJSON) or stderr (diagnostics). No file creation.
- The worker must handle files up to 100MB without running out of memory
- `heading_path` must be consistent: same heading hierarchy for all chunks in a section
- Empty text chunks (e.g., image-only PDF pages) are NOT emitted -- skip and warn to stderr

## Checkpoint

Binary builds, tests pass, smoke test produces valid NDJSON:

```bash
cargo build --release --manifest-path ingestion-worker/Cargo.toml
cd ingestion-worker && cargo test && cd ..
cd ingestion-worker && cargo clippy -- -D warnings && cd ..

# Smoke test with plain text:
echo "Hello world.\n\nThis is paragraph two.\n\nAnd paragraph three." > /tmp/_embedinator_smoke.txt
./ingestion-worker/target/release/embedinator-worker --file /tmp/_embedinator_smoke.txt --type text
# Expected: NDJSON lines with doc_type "prose"

# Smoke test with auto-detection:
echo "def hello(): pass" > /tmp/_embedinator_smoke.py
./ingestion-worker/target/release/embedinator-worker --file /tmp/_embedinator_smoke.py
# Expected: NDJSON with doc_type "code"

rm -f /tmp/_embedinator_smoke.txt /tmp/_embedinator_smoke.py
```
