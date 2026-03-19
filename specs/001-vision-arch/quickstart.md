# Quickstart Guide: Vision & System Architecture

**Date**: 2026-03-10 | **Branch**: `001-vision-arch` | **Phase**: 1 (Design)

This guide walks a developer through setting up and running the MVP locally for the first time.

## Prerequisites

- Docker & Docker Compose installed
- Python 3.14.3 or higher (for native development)
- Node.js 20+ (for frontend development)
- Git (to clone the repository)
- ~4GB free disk space (for Ollama models + vector database)

## Quick Setup (5 minutes)

### 1. Clone & Install

```bash
git clone https://github.com/your-org/the-embedinator.git
cd the-embedinator
```

### 2. Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

**Default settings** (suitable for local development):
```
SQLITE_PATH=./data/embedinator.db
QDRANT_HOST=qdrant
QDRANT_PORT=6333
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:7b
API_HOST=0.0.0.0
API_PORT=8000
FRONTEND_PORT=3000
LOG_LEVEL=INFO
```

No changes needed; defaults are local-first.

### 3. Start All Services

```bash
make dev
```

**What happens**:
1. Docker Compose starts 4 services:
   - Qdrant (vector database) on port 6333
   - Ollama (LLM) on port 11434
   - FastAPI backend on port 8000
   - Next.js frontend on port 3000

2. Ollama automatically downloads `qwen2.5:7b` model (~5GB, one-time)

3. Backend and frontend start with hot reload enabled

**Wait for output**:
```
embedinator-backend     | INFO:     Uvicorn running on http://0.0.0.0:8000
embedinator-frontend   | > Ready on http://0.0.0.0:3000
```

### 4. Open Web Interface

Navigate to:
```
http://localhost:3000
```

You should see:
- Collections browser (initially empty)
- "Create Collection" button
- "Upload Document" area

---

## First Test: Upload & Query (5 minutes)

### Step 1: Create a Collection

1. Click **"Create Collection"**
2. Enter name: `Test Collection`
3. Click **"Save"**

You should now see `Test Collection` in the list.

### Step 2: Upload a Test Document

1. Click **"Upload Document"** in the `Test Collection` card
2. Choose a file:
   - Option A: Upload a simple text file with content (e.g., "The capital of France is Paris.")
   - Option B: Download our sample PDF from docs/samples/sample.pdf

3. Click **"Upload"**

Status shows: `uploading` → `parsing` → `indexing` → `indexed` (should complete in 10–30 seconds)

### Step 3: Ask a Question

1. Click the collection name to enter the chat interface
2. In the chat input, type:
   ```
   What is the capital of France?
   ```
3. Click **"Send"** or press Enter

**Expected behavior**:
- Answer appears word-by-word (streaming)
- Confidence score displayed (0–100%)
- Citation below answer: "Source: [filename]"

### Step 4: View Trace

1. Below the answer, click **"View Trace"**
2. See:
   - Full query text
   - Collections searched
   - Passages retrieved (with relevance scores)
   - Confidence breakdown

---

## Command Reference

### Development Commands

```bash
# Start all services with hot reload
make dev

# Stop services
make docker-down

# Build Docker images
make build

# Run tests
make test

# Lint backend + frontend
make lint

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Makefile Targets

See `Makefile` for full list:
```bash
cat Makefile
```

---

## Troubleshooting

### Services Won't Start

**Error: "Address already in use"**

Solution: Stop conflicting containers:
```bash
docker-compose down
# Then retry: make dev
```

**Error: "Cannot connect to Ollama"**

Solution: Wait 30–60 seconds for Ollama to download the model. Check logs:
```bash
docker-compose logs ollama
```

### API Returns 503

**Likely cause**: Qdrant or Ollama not ready

**Check health**:
```bash
curl http://localhost:8000/api/health
```

**Expected response**:
```json
{
  "status": "healthy",
  "services": {
    "sqlite": "ok",
    "qdrant": "ok",
    "ollama": "ok"
  }
}
```

### Upload Fails

**Error: "File format not supported"**

Solution: Ensure file is PDF, Markdown (.md), or plain text (.txt)

**Error: "File too large"**

Solution: Max upload size is 100MB; split large files

### Chat Returns Empty Answer

**Likely causes**:
1. Document not fully indexed yet (check status in collections)
2. Question not answerable from document
3. Confidence too low; system declined to answer

**Debug**: Check trace view for retrieval results

---

## API Testing (curl)

### Create Collection

```bash
curl -X POST http://localhost:8000/api/collections \
  -H "Content-Type: application/json" \
  -d '{"name": "API Test Collection"}'
```

### Upload Document

```bash
curl -X POST http://localhost:8000/api/documents \
  -F "file=@/path/to/document.pdf" \
  -F 'collection_ids=["col-abc123"]'
```

### Submit Query (Streaming)

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the main point?",
    "collection_ids": ["col-abc123"],
    "model_name": "qwen2.5:7b"
  }'
```

Output (NDJSON stream):
```
{"type": "chunk", "text": "The"}
{"type": "chunk", "text": " main"}
...
```

### View Trace

```bash
curl http://localhost:8000/api/traces/trace-abc123
```

---

## File Structure Tour

```
the-embedinator/
├── backend/
│   ├── main.py           # FastAPI app entrypoint
│   ├── config.py         # Settings (env vars)
│   ├── errors.py         # Exception types
│   ├── api/
│   │   ├── collections.py
│   │   ├── documents.py
│   │   ├── chat.py       # Streaming endpoint (main logic)
│   │   ├── traces.py
│   │   └── providers.py
│   ├── storage/
│   │   ├── sqlite_db.py  # Database class
│   │   └── qdrant_client.py
│   └── providers/
│       ├── base.py       # LLMProvider interface
│       └── ollama.py     # Ollama implementation
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── index.tsx         # Collections + upload
│   │   │   ├── chat/[id].tsx     # Chat interface
│   │   │   ├── traces/[id].tsx   # Trace viewer
│   │   │   └── settings.tsx      # Provider config
│   │   └── components/
│   │       ├── ChatBox.tsx       # Streaming display
│   │       └── TraceViewer.tsx
│   └── package.json
├── data/                 # gitignored (runtime data)
│   ├── embedinator.db   # SQLite database
│   ├── uploads/         # User documents
│   └── qdrant_db/       # Vector store
├── docker-compose.yml
├── .env.example
├── Makefile
└── requirements.txt
```

---

## Key Files to Review

| File | Purpose | For learning |
|------|---------|--------------|
| `backend/main.py` | FastAPI app factory + lifespan | Startup/shutdown initialization |
| `backend/api/chat.py` | Streaming endpoint | SSE streaming + async generators |
| `frontend/src/pages/chat/[id].tsx` | Chat UI | Consuming NDJSON streams |
| `backend/storage/sqlite_db.py` | Database wrapper | Async SQLite + WAL mode |
| `docker-compose.yml` | Service orchestration | Multi-service setup |

---

## Next Steps

After verifying the MVP works:

1. **Implement the 27 tasks** from Phase 2 (generated by `/speckit.tasks`)
2. **Add unit tests** for each module (backend/ + frontend/src/)
3. **Run integration tests** across services
4. **Test user workflows** matching 5 user stories + 8 success criteria

---

## Performance Expectations

On recommended hardware (i7-12700K, 64GB RAM, RTX 4070 Ti):

| Metric | Expected | Target (SC) |
|--------|----------|------------|
| First startup (incl. model download) | 2–5 minutes | SC-004 ✓ |
| First words of answer | <1 second | SC-002 ✓ |
| Full answer generation | 3–10 seconds | - |
| Document upload + index (10MB) | 10–30 seconds | - |
| Concurrent queries | 5–10 independent | - |

---

## Documentation

- **Architecture**: See `claudedocs/architecture-design.md` (main reference)
- **Spec**: See `specs/001-vision-arch/spec.md` (requirements)
- **Plan**: See `specs/001-vision-arch/plan.md` (Phase 1 breakdown)
- **Data Model**: See `specs/001-vision-arch/data-model.md` (entities + schemas)
- **API Contracts**: See `specs/001-vision-arch/contracts/api.md` (endpoint specs)

---

## Getting Help

- **Logs**: `docker-compose logs -f [service]`
- **Health check**: `curl http://localhost:8000/api/health`
- **Reset everything**: `docker-compose down -v` (removes data!)
- **GitHub issues**: File a bug with logs attached

---

**You're ready to develop! Next: run `/speckit.tasks` to generate the task list.**
