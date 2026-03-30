# Quickstart: Chat & Agentic RAG Pipeline Fix

**Feature**: 024-chat-fix | **Date**: 2026-03-27

## Prerequisites

- Docker Compose running: `docker compose ps` shows 4 healthy services
- At least one collection with ingested documents (e.g., `arca-backend-test`)
- Browser open to `http://localhost:3000`

## Verification Commands

### Backend Health
```bash
curl -s http://localhost:8000/api/health | python3 -m json.tool
# Expected: {"status": "healthy", "services": [...all "ok"...]}
```

### Chat API (Direct)
```bash
curl -s -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello", "collection_ids": ["07d3308c-5bb9-49a8-bcf7-5edafbcb8dca"], "llm_model": "qwen2.5:7b"}' \
  | head -10
# Expected: NDJSON lines starting with {"type": "session", ...}
```

### Chat API (Through Proxy)
```bash
curl -s -N -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello", "collection_ids": ["07d3308c-5bb9-49a8-bcf7-5edafbcb8dca"], "llm_model": "qwen2.5:7b"}' \
  | head -10
# Expected: Same NDJSON lines as direct
```

### Check Call Limit Warnings
```bash
docker compose logs backend --tail=50 2>&1 | rg "call_limit"
# Expected after fix: No output (no warnings)
```

### Check Makefile Unchanged
```bash
git diff Makefile
# Expected: No output (no changes)
```

## Docker Rebuild Commands

### Frontend only
```bash
docker compose build frontend && docker compose up -d frontend
```

### Backend only
```bash
docker compose build backend && docker compose up -d backend
```

### Both
```bash
docker compose build backend frontend && docker compose up -d
```

## Browser Verification Checklist

1. Open `http://localhost:3000/chat`
2. Select a collection (click card or use config panel)
3. Type a question and press Send
4. **Verify**: Response text appears (not skeleton bars)
5. **Verify**: Confidence meter appears after response completes
6. Click sidebar "New Chat"
7. **Verify**: Chat panel clears to empty state
8. Send another message
9. **Verify**: Conversation appears in sidebar with correct title and count
10. Click the sidebar conversation entry
11. **Verify**: Messages load into chat panel

## Available Collections

| ID | Name |
|----|------|
| `07d3308c-5bb9-49a8-bcf7-5edafbcb8dca` | arca-backend-test |
| `cb24fd8a-c964-466e-8a90-b0d17eda9103` | test- |
