# The Embedinator — Operations Runbook

**Version**: 1.0
**Date**: 2026-03-10

---

## Quick Start

```bash
# Clone and start
git clone https://github.com/Bruno-Ghiberto/The-Embedinator.git the-embedinator
cd the-embedinator
cp .env.example .env
docker compose up --build -d

# Wait for Ollama model download (first run only, ~5 min)
docker logs embedinator-ollama -f

# Verify all services are healthy
docker ps
curl http://localhost:8000/api/health
```

---

## E2E Verification

Use this section to verify the full application stack works end-to-end after a fresh start. Follow the steps in order — each step depends on the previous one succeeding.

### 1. Starting the Application

```bash
# Option A — Branded launcher (macOS/Linux)
./embedinator.sh

# Option B — Docker Compose directly
cp .env.example .env          # First run only
docker compose up --build -d

# GPU overlays (optional, first run only)
COMPOSE_PROFILES=nvidia docker compose up -d   # NVIDIA GPU
COMPOSE_PROFILES=amd docker compose up --build -d   # AMD GPU
```

Wait for the Ollama model to download on first run (~5 minutes for `qwen2.5:7b`):

```bash
docker logs embedinator-ollama -f
# Look for: "model 'qwen2.5:7b' loaded" or similar completion message
```

---

### 2. Verifying Services Are Healthy

All four services must be `healthy` before proceeding. Check with:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

Expected output (all services `healthy`):

```
NAMES                    STATUS
embedinator-qdrant       Up X minutes (healthy)
embedinator-ollama       Up X minutes (healthy)
embedinator-backend      Up X minutes (healthy)
embedinator-frontend     Up X minutes (healthy)
```

Verify each service's health endpoint individually:

```bash
# Qdrant — vector database
curl -s http://localhost:6333/healthz
# Expected: {"title":"qdrant - version v1.x.x","status":"ok"}

# Ollama — language model server
curl -s http://localhost:11434/api/tags | python3 -m json.tool
# Expected: JSON with "models" array (empty is fine before seeding)

# Backend — FastAPI application
curl -s http://localhost:8000/api/health | python3 -m json.tool
# Expected: {"status":"ok","version":"...","checks":{...}}

# Frontend — Next.js application
curl -o /dev/null -s -w "%{http_code}\n" http://localhost:3000
# Expected: 307 (redirect to /chat) or 200
```

---

### 3. Seeding Test Data

The seed script creates a "Sample Knowledge Base" collection and ingests `tests/fixtures/sample.md`. It is idempotent — safe to run multiple times.

```bash
python scripts/seed_data.py

# With custom backend URL (e.g. non-default port):
python scripts/seed_data.py --base-url http://localhost:8000

# With longer timeout for slow hardware:
python scripts/seed_data.py --timeout 300
```

Expected output (first run):

```
Seed Data — The Embedinator
============================
Collection: Sample Knowledge Base (id: <uuid>)
  Status: created (new)
Document: sample.md
  Uploading... job_id=<uuid>
  Status: ingested (N chunks)
============================
Seeding complete.
```

**Exit codes**: `0` = success, `1` = seeding failed, `2` = cannot reach backend.

If seeding fails, check backend logs:

```bash
docker compose logs embedinator-backend --tail=50
```

---

### 4. Running the Smoke Test

The smoke test (`scripts/smoke_test.py`) performs 13 end-to-end checks covering health endpoints, API endpoints, collection creation, document upload, ingestion polling, chat streaming, citation verification, and cleanup.

```bash
# Basic run (uses localhost:8000)
python scripts/smoke_test.py

# With custom URL
python scripts/smoke_test.py --base-url http://localhost:8000
```

Expected output (all passing):

```
[PASS] Backend health          0.12s
[PASS] Qdrant health           0.05s
[PASS] Ollama health           0.08s
[PASS] Frontend health         0.10s
[PASS] Collections list        0.15s
...
Results: 13/13 passed
```

**Exit codes**: `0` = all checks passed, `1` = one or more checks failed.

> **Note**: If `scripts/smoke_test.py` does not yet exist, use the manual chat verification below as an alternative.

---

### 5. Manual Chat Verification (Alternative to Smoke Test)

If the smoke test is unavailable or you need to debug a specific step, verify chat manually:

```bash
# 1. Get the collection ID from the seeded data
COLLECTION_ID=$(curl -s http://localhost:8000/api/collections \
  | python3 -c "import sys,json; cs=json.load(sys.stdin)['collections']; print(next(c['id'] for c in cs if c['name']=='sample-knowledge-base'), end='')")
echo "Collection ID: $COLLECTION_ID"

# 2. Send a chat request (streaming NDJSON)
curl -s -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"What is this document about?\",\"collection_id\":\"$COLLECTION_ID\",\"session_id\":\"test-session-1\"}"

# Expected: Multiple NDJSON lines, last line contains citations
```

A healthy response streams multiple JSON lines. The final `metadata` line should include a `citations` array with at least one entry referencing `sample.md`.

---

### 6. Reading Docker Logs

Use these commands to diagnose failures at any layer:

```bash
# Follow all services in real time
docker compose logs -f

# Follow a specific service
docker compose logs -f embedinator-backend
docker compose logs -f embedinator-frontend
docker compose logs -f embedinator-ollama
docker compose logs -f embedinator-qdrant

# Last N lines (useful for startup errors)
docker compose logs --tail=100 embedinator-backend

# Since a specific time
docker compose logs --since="2026-03-20T10:00:00" embedinator-backend
```

Backend logs use structured JSON format (structlog). To pretty-print them:

```bash
docker compose logs embedinator-backend | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        obj = json.loads(line.strip())
        print(obj.get('timestamp',''), obj.get('level',''), obj.get('event',''))
    except json.JSONDecodeError:
        print(line, end='')
"
```

---

### 7. Common Failure Modes

| Symptom | Likely Cause | Fix |
|---|---|---|
| Container exits immediately (code 1) | Missing `.env` file | `cp .env.example .env` |
| Backend `unhealthy` after 60s | Qdrant or Ollama not ready yet | Wait; check `docker compose logs embedinator-backend` |
| Frontend `unhealthy` | IPv6 resolution (Alpine) | Fixed in spec-21; rebuild with `docker compose build frontend` |
| Ollama `unhealthy` for >10 min | Model still downloading | Wait; watch with `docker logs embedinator-ollama -f` |
| Ingestion stuck at "pending" | Ollama overloaded or OOM | Check `docker stats`; reduce concurrency |
| Chat returns empty citations | Wrong collection ID | Verify `collection_id` matches a collection with ingested docs |
| Chat returns 500 | Backend graph init failure | Check `docker compose logs embedinator-backend --tail=50` for stack trace |
| Port conflict on 8000/3000/6333 | Another service using the port | Change via `EMBEDINATOR_PORT_BACKEND` / `EMBEDINATOR_PORT_FRONTEND` in `.env` |
| `seed_data.py` exits with code 2 | Backend not reachable | Ensure backend is healthy first (`curl http://localhost:8000/api/health`) |

---

### 8. Debugging Checklist

If the application is not working, follow these steps in order before filing a bug report:

**App won't start at all:**
- [ ] `docker ps -a` — are any containers in `Exit` state?
- [ ] `docker compose logs embedinator-backend --tail=100` — look for Python tracebacks
- [ ] Is `.env` present? (`ls -la .env`) — copy from `.env.example` if missing
- [ ] Is Docker running and has sufficient memory? (`docker info | grep Memory`)
- [ ] Are required ports free? (`ss -tlnp | grep -E '8000|3000|6333|11434'`)

**Services start but healthchecks fail:**
- [ ] `docker compose logs embedinator-ollama --tail=20` — is model download still in progress?
- [ ] `curl -v http://127.0.0.1:6333/healthz` — is Qdrant responding?
- [ ] `curl -v http://127.0.0.1:8000/api/health` — is backend responding?
- [ ] `docker stats --no-stream` — is any container at memory limit?

**Ingestion fails:**
- [ ] `curl http://localhost:8000/api/collections/<id>/ingest/<job_id>` — check job status and `error_message`
- [ ] `docker compose logs embedinator-backend --tail=50` — look for ingestion pipeline errors
- [ ] Is the file a text-based PDF/Markdown/text? Image-based PDFs are not supported.
- [ ] Is the file under the upload size limit? (default 100 MB)

**Chat doesn't return answers:**
- [ ] Is there a collection with completed documents? (`curl http://localhost:8000/api/collections`)
- [ ] Is `collection_id` correct in the request body?
- [ ] Did seeding succeed? (`python scripts/seed_data.py` — should exit 0)
- [ ] `docker compose logs embedinator-backend --tail=50` — look for retrieval or LLM errors
- [ ] Is Ollama healthy and the model loaded? (`curl http://localhost:11434/api/tags`)

---

## Service Overview

| Service | Container | Port | Health Check |
|---|---|---|---|
| Qdrant | `embedinator-qdrant` | 6333 (HTTP), 6334 (gRPC) | `GET /healthz` |
| Ollama | `embedinator-ollama` | 11434 | `GET /api/tags` |
| Backend (FastAPI) | `embedinator-backend` | 8000 | `GET /api/health` |
| Frontend (Next.js) | `embedinator-frontend` | 3000 | HTTP 200 on `/` |

---

## Common Operations

### Starting / Stopping

```bash
# Start all services
docker compose up -d

# Stop all services (preserves data)
docker compose down

# Stop and remove volumes (DESTROYS DATA)
docker compose down -v

# Restart a single service
docker compose restart backend
```

### Viewing Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f ollama

# Last 100 lines
docker compose logs --tail=100 backend
```

### Checking Health

```bash
# All-in-one health check
curl -s http://localhost:8000/api/health | python3 -m json.tool

# Individual service checks
curl -s http://localhost:6333/healthz           # Qdrant
curl -s http://localhost:11434/api/tags          # Ollama
curl -s http://localhost:8000/api/health         # Backend
curl -s http://localhost:3000                    # Frontend
```

---

## Backup & Restore

### SQLite Database

```bash
# Backup (while system is running — WAL mode supports this)
cp data/embedinator.db data/embedinator.db.bak

# Restore
docker compose down
cp data/embedinator.db.bak data/embedinator.db
docker compose up -d
```

### Qdrant Data

```bash
# Backup Qdrant storage
docker compose down
tar -czf qdrant-backup.tar.gz data/qdrant_db/

# Restore
tar -xzf qdrant-backup.tar.gz
docker compose up -d
```

### Full System Backup

```bash
docker compose down
tar -czf embedinator-backup-$(date +%Y%m%d).tar.gz \
  data/embedinator.db \
  data/qdrant_db/ \
  .env
```

### Full System Restore

```bash
docker compose down
tar -xzf embedinator-backup-YYYYMMDD.tar.gz
docker compose up -d
```

---

## Encryption Key Management

### Setting the Fernet Key

```bash
# Generate a secure key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Add to .env
echo "EMBEDINATOR_FERNET_KEY=<generated-key>" >> .env
```

**Important**: If you change the Fernet key after storing API keys, the stored keys become unrecoverable. You'll need to re-enter all provider API keys.

### Rotating the Fernet Key

Not supported in MVP. To rotate:
1. Note which providers have API keys configured
2. Change `EMBEDINATOR_FERNET_KEY` in `.env`
3. Restart backend: `docker compose restart backend`
4. Re-enter all provider API keys via the Settings UI

---

## Troubleshooting

### Ollama Shows "Unhealthy"

**Symptoms**: `docker ps` shows Ollama as unhealthy; backend can't generate embeddings.

**Diagnosis**:
```bash
docker logs embedinator-ollama --tail=50
curl http://localhost:11434/api/tags
```

**Common causes**:
1. **Model still downloading**: First run pulls `qwen2.5:7b` (~5 GB). Wait for completion.
2. **Insufficient RAM**: 7B model needs ~8 GB. Check with `docker stats`.
3. **GPU driver issues**: Ollama falls back to CPU if GPU unavailable — check `docker logs`.

**Fix**:
```bash
# If model download was interrupted
docker compose restart ollama
docker logs embedinator-ollama -f  # Watch for completion
```

### Qdrant Shows "Unhealthy"

**Symptoms**: Health check fails; vector searches return errors.

**Diagnosis**:
```bash
docker logs embedinator-qdrant --tail=50
curl http://localhost:6333/healthz
```

**Common causes**:
1. **Port conflict**: Another service using 6333. Check `ss -tlnp | grep 6333`.
2. **Corrupted storage**: Rare. Restore from backup or delete `data/qdrant_db/` and re-ingest.
3. **OOM killed**: Check `dmesg | grep -i oom`. Increase Docker memory limit.

### Backend Won't Start

**Diagnosis**:
```bash
docker logs embedinator-backend --tail=100
```

**Common causes**:
1. **Missing `.env` file**: Copy from example: `cp .env.example .env`
2. **Qdrant/Ollama not ready**: Backend depends on both — check their health first
3. **Port 8000 in use**: Change port in `docker-compose.yml` or stop conflicting service
4. **Python dependency issue**: Rebuild: `docker compose build backend`

### Rate Limiting Errors (429)

**Symptoms**: API returns `429 Too Many Requests`.

**Fix**: Wait for the rate limit window to expire (1 minute). If limits are too restrictive, adjust in `.env`:
```bash
RATE_LIMIT_CHAT_PER_MINUTE=60
RATE_LIMIT_INGEST_PER_MINUTE=20
RATE_LIMIT_DEFAULT_PER_MINUTE=240
```

### Ingestion Stuck / Failed

**Diagnosis**:
```bash
# Check job status
curl http://localhost:8000/api/collections/<id>/ingest/<job_id>
```

**Common causes**:
1. **Ollama overloaded**: Embedding takes time. Check Ollama logs.
2. **File too large**: Default limit is 100 MB. Check `MAX_UPLOAD_SIZE_MB`.
3. **Unsupported PDF**: Scanned/image PDFs are not supported. Only text-based PDFs work.

### Frontend Not Loading

**Diagnosis**:
```bash
docker logs embedinator-frontend --tail=50
curl http://localhost:3000
```

**Common causes**:
1. **Backend not ready**: Frontend depends on backend. Check backend health first.
2. **Port 3000 in use**: Change in `docker-compose.yml`.
3. **Build failure**: Rebuild: `docker compose build frontend`

---

## Performance Monitoring

### Query Latency

```bash
# Check recent query latencies via API
curl -s "http://localhost:8000/api/stats" | python3 -m json.tool

# Detailed traces
curl -s "http://localhost:8000/api/traces?limit=10" | python3 -m json.tool
```

### Resource Usage

```bash
# Docker container resource usage
docker stats --no-stream

# Specific service memory
docker stats embedinator-backend --no-stream
```

### Database Size

```bash
ls -lh data/embedinator.db
du -sh data/qdrant_db/
```

---

## Production Deployment Notes

### Recommended Changes for Production

1. **TLS**: Add a reverse proxy (Caddy recommended for auto-TLS)
2. **Fernet key**: Set a strong `EMBEDINATOR_FERNET_KEY` in `.env`
3. **Debug mode**: Set `DEBUG=false` and `LOG_LEVEL=WARNING`
4. **CORS**: Set `CORS_ORIGINS` to your actual domain
5. **Port exposure**: Do NOT expose 6333 or 11434 publicly
6. **Workers**: Use `docker-compose.prod.yml` which runs uvicorn with 4 workers

```bash
# Production start
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Monitoring

- Health endpoint: `GET /api/health` — poll every 30s
- Stats endpoint: `GET /api/stats` — daily review
- Observability page: `http://localhost:3000/observability` — query performance review
- Docker logs: Forward to your log aggregation system if available

---

*This runbook covers The Embedinator's operational procedures. For architecture details, see `docs/architecture-design.md`. For API details, see `docs/api-reference.md`.*
