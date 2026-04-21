# Research: Security Hardening

**Branch**: `013-security-hardening` | **Date**: 2026-03-17

## Status: No Unknowns

All implementation decisions were resolved in `13-specify.md` (the authoritative context prompt). This document records the rationale for those decisions.

---

## R1 — Chat Message Truncation Limit

**Decision**: 10,000 characters (hardcoded; not configurable in this spec).

**Rationale**: Matches the security blueprint. A 10k-char limit fits comfortably within all supported LLM context windows while preventing context abuse. Silent truncation (no error, no log) avoids user-visible failures for edge-case inputs.

**Alternatives Considered**:
- Configurable via Settings: rejected — YAGNI; single-user system; adds complexity without benefit.
- Error instead of truncation: rejected — would break user experience on long pastes; truncation is safer default.

---

## R2 — Qdrant Filter Key Whitelist Strategy

**Decision**: Module-level `ALLOWED_FILTER_KEYS = {"doc_type", "source_file", "page", "chunk_index"}` constant in `searcher.py`. Unknown keys silently skipped via `continue` in `_build_filter()`.

**Rationale**: The allowed set matches the actual payload fields used in Qdrant point storage. Silent ignore (not error) prevents breaking existing clients that might pass additional metadata. Future extensions require an explicit spec amendment.

**Alternatives Considered**:
- Class attribute on `HybridSearcher`: rejected — module-level constant matches the code sample in spec and is equally accessible.
- Raise 400 on unknown key: rejected — spec explicitly says "silently ignored"; raising would be a breaking change for any client.

---

## R3 — Filename Sanitization Strategy

**Decision**: Inline function `_sanitize_filename(raw: str) -> str` in `ingest.py`. Takes basename, removes `..`, replaces `[^a-zA-Z0-9._-]` with `_`, returns `"upload"` if empty.

**Rationale**: No import beyond stdlib `re`. The module-private naming (`_sanitize_filename`) follows existing patterns in `ingest.py`. Fallback to `"upload"` prevents empty-string downstream failures (e.g., on a filename of `"../../"`).

**Alternatives Considered**:
- `pathlib.Path(filename).name`: rejected as sole defense — `Path("../../etc/passwd").name` returns `"passwd"`, which is correct, but the `.replace("..", "")` step is still needed for edge cases like filenames that ARE just `".."`.
- `FileValidator` class: explicitly out of scope — spec-13 does not create new modules.

---

## R4 — PDF Magic Byte Check Scope

**Decision**: PDF-only. Check `content[:4] == b"%PDF"`. No checks for `.md`, `.txt`, `.py`, `.js`, etc.

**Rationale**: Plain-text formats have no reliable single-magic-byte signature. PDF is the only binary format in the extension allowlist with a well-defined 4-byte magic number. Adding magic checks for text formats would produce false positives (e.g., a Python file that happens to start with `%PDF`).

**Alternatives Considered**:
- `python-magic` / `libmagic` for comprehensive MIME verification: explicitly out of scope per spec (would add system dependency).
- Check all binary formats: no other binary format in the allowlist (pdf, md, txt, py, js, ts, rs, go, java, c, cpp, h).

---

## R5 — Log Redaction Scope

**Decision**: Top-level log record keys only, case-insensitive match against `{"api_key", "password", "secret", "token", "authorization"}`. Replace value with `"[REDACTED]"` — do not delete the key. No deep/nested scanning.

**Rationale**: Consistent with spec §IV observability: knowing a field was present (key visible) is more useful for debugging than having it silently absent. Nested scanning adds O(n) recursion overhead per log event — out of scope per spec.

**Implementation**: Inserted as a structlog processor at position 6 (immediately before `JSONRenderer`). Processor signature: `_strip_sensitive_fields(logger, method, event_dict: dict) -> dict`.

---

## R6 — No New Dependencies Constraint

**Decision**: All spec-13 changes use Python stdlib only. `re` is the only new import (added to `ingest.py` as `import re as _re`).

**Rationale**: SC-007 explicitly forbids new external dependencies. `re`, `os`, and all other needed constructs are either stdlib or already imported in the target files.
