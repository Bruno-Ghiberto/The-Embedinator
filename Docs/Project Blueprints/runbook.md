# The Embedinator — Operations Runbook

**Version**: 1.0
**Date**: 2026-03-10

---

## Quick Start

```bash
# Clone and start
git clone <repo-url> the-embedinator
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

*This runbook covers The Embedinator's operational procedures. For architecture details, see `claudedocs/architecture-design.md`. For API details, see `claudedocs/api-reference.md`.*
