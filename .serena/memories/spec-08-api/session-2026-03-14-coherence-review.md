# Spec 08: API Reference — Coherence Review Session (2026-03-14)

## Goal
Review and fix coherence issues in `Docs/PROMPTS/spec-08-api/08-specify.md` against codebase and blueprints.

## What Was Done
- Full coherence analysis of 08-specify.md against:
  - Actual codebase (schemas.py, config.py, chat.py, sqlite_db.py, API routers)
  - Project Blueprints (api-reference.md, data-model.md, architecture-design.md)
  - Previous spec implementations (02–07)
- Found 22 discrepancies (3 CRITICAL, 8 HIGH, 7 MEDIUM)
- Rewrote 08-specify.md with all fixes applied (255 → 319 lines)

## Key Findings

### Critical Fixes
1. SSE → NDJSON: Architecture-design.md said SSE, but ADR-007 and actual code use NDJSON (`application/x-ndjson`)
2. NDJSON events: Current code has 4 types (chunk, clarification, metadata, error). Blueprint wants 10. Spec now documents both current and target.
3. confidence_score: Blueprint said float 0.0-1.0, but spec-07 implemented int 0-100. Spec corrected to int.

### High Fixes
- llm_model default: llama3.2 → qwen2.5:7b
- Schema naming: Invented names (CollectionSchema) → code convention (*Response/*Request)
- DocumentResponse status values: code had Phase 1 values (uploaded/parsing...), corrected to DB schema (pending/ingesting...)
- Rate limits: config.py has 100/min chat, blueprint says 30/min. Spec uses blueprint target.
- File types: 9 → 12 (added .c, .cpp, .h)

### Key Pattern
Every Pydantic schema now has `# EXISTS/NEW/EXTENSION` annotations with `# NOTE:` comments explaining current-vs-target differences.

## Relevant Files
- Docs/PROMPTS/spec-08-api/08-specify.md — rewritten (319 lines)
