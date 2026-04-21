# ingestion-worker/

High-performance Rust binary for document parsing. Called as a subprocess
by the Python backend during document ingestion.

## What It Does

The ingestion worker reads a file path from its CLI arguments, parses the
document into structured text chunks (preserving headings, code blocks, and
document structure), and writes JSON output to stdout. The Python
`IngestionPipeline` reads this output and continues with embedding and
indexing.

## Supported Formats

| Format   | Parser Module   | Library         |
|----------|-----------------|-----------------|
| PDF      | `pdf.rs`        | pdf-extract 0.8 |
| Markdown | `markdown.rs`   | pulldown-cmark 0.12 |
| Plain text | `text.rs`     | Standard library |

## Source Files

| File                  | Purpose                                    |
|-----------------------|--------------------------------------------|
| `src/main.rs`         | CLI entry point (clap argument parsing)    |
| `src/pdf.rs`          | PDF text extraction                        |
| `src/markdown.rs`     | Markdown parsing with heading tracking     |
| `src/text.rs`         | Plain text processing                      |
| `src/heading_tracker.rs` | Heading hierarchy and breadcrumb generation |
| `src/code.rs`         | Code block detection and handling          |
| `src/types.rs`        | Shared type definitions (Chunk, Metadata)  |

## Building

```bash
# Debug build
cargo build

# Release build (optimized)
cargo build --release

# Binary location
ls target/release/embedinator-worker
```

## Dependencies

From `Cargo.toml`:

| Crate          | Version | Purpose                          |
|----------------|---------|----------------------------------|
| serde          | 1       | JSON serialization               |
| serde_json     | 1       | JSON output formatting           |
| pulldown-cmark | 0.12    | Markdown parsing                 |
| pdf-extract    | 0.8     | PDF text extraction              |
| clap           | 4       | CLI argument parsing             |
| regex          | 1       | Text pattern matching            |

## Integration

The Python backend invokes the worker via `subprocess` in
`backend/ingestion/pipeline.py`. The binary path is configurable:

```
RUST_WORKER_PATH=ingestion-worker/target/release/embedinator-worker
```

In Docker, the binary is compiled in a separate Rust build stage and
copied to `/app/ingestion-worker/target/release/embedinator-worker`.
