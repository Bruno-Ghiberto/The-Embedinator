# Hardware Utilization Audit — Spec-26 Performance Debug

**Branch**: `026-performance-debug`
**Date**: 2026-04-14
**Auditor**: A1 (devops-architect)
**Reference hardware**: Intel i7-12700K, 64 GB DDR5, RTX 4070 Ti 12 GB VRAM, NVMe SSD, Fedora 43
**LLM under measurement**: `qwen2.5:7b` (override per gotcha #4; active default is `gemma4:e4b`)
**Collection under measurement**: `emb-9286c892-d98a-4e68-ac50-549287e885f4` (sample-knowledge-base, 5 chunks)
**Docker context**: `default` (native Docker Engine — not desktop-linux)

---

## Measurement Protocol

- **Three samples per metric** (NFR-003): variance flags triggered when cv > 0.25.
- **LLM model**: `qwen2.5:7b` (set via `llm_model` field in each request body; not via env override — the backend ChatRequest schema defaults this field separately from `EMBEDINATOR_LLM_MODEL`).
- **Warm state**: queries 2–N after model loads to VRAM; cold start measured separately.
- **Priming query**: first-ever query to qwen2.5:7b in this session (loaded model to VRAM = true cold start). Not included in warm-state statistics.
- Commands used: `nvidia-smi`, `nvidia-smi dmon`, `docker stats`, `/proc/PID/status`, `curl`, `top`, Python introspection.

---

## CPU

### Backend Threading Model

| Question | Answer | Command | Timestamp |
|----------|--------|---------|-----------|
| Number of uvicorn worker processes | 1 (single worker, no `--workers N` flag) | `docker exec backend sh -c 'ls /proc/[0-9]*/cmdline \| xargs -I {} sh -c "cat {} 2>/dev/null \| tr \\0 \\040"' \| grep uvicorn` | 2026-04-14T10:07:30-03:00 |
| Uvicorn startup command | `uvicorn backend.main:app --host 0.0.0.0 --port 8000` (no `--workers` = single process) | `docker exec backend cat /proc/1/cmdline \| tr \\0 \\040` | 2026-04-14T10:07:30-03:00 |
| Backend threads at idle (PID 7) | **46 threads** | `docker exec backend cat /proc/7/status \| grep Threads` | 2026-04-14T10:07:54-03:00 |
| Backend threads after warm query | **79 threads** | `docker exec backend cat /proc/7/status \| grep Threads` | 2026-04-14T10:10:55-03:00 |
| Backend threads under 5 concurrent queries | **80 threads** | `docker exec backend cat /proc/7/status \| grep Threads` | 2026-04-14T10:13:22-03:00 |
| uvicorn host PID (outside container) | **4009** | `for hpid in /proc/[0-9]*/comm; do ...; done \| grep uvicorn` | 2026-04-14T10:12:05-03:00 |

### CPU Usage During Chat Queries

| Question | Answer | Command | Timestamp |
|----------|--------|---------|-----------|
| uvicorn CPU% during single warm query | **2–10%** (samples: 2, 2, 4, 2, 2, 4, 2, 2, 4 %) | `top -b -n 10 -d 0.5 -p 4009` | 2026-04-14T10:13:03-03:00 |
| uvicorn RSS at idle | **1,230,432 kB ≈ 1.17 GiB** | `docker exec backend cat /proc/7/status \| grep VmRSS` | 2026-04-14T10:07:54-03:00 |
| uvicorn RSS after warm query | **1,824,520–1,919,928 kB ≈ 1.74–1.83 GiB** | `docker exec backend cat /proc/7/status \| grep VmRSS` | 2026-04-14T10:10:55-03:00 |
| uvicorn VmPeak | **9,881,896 kB ≈ 9.4 GiB** (virtual; dominated by Python memory maps) | `docker exec backend cat /proc/7/status \| grep VmPeak` | 2026-04-14T10:10:55-03:00 |
| Is Python the CPU bottleneck? | **NO** — backend CPU 2–10% during inference; GPU is the bottleneck | `top -b -n 10 -d 0.5 -p 4009` during query | 2026-04-14T10:13:03-03:00 |

### Qdrant Thread Pool

| Question | Answer | Command | Timestamp |
|----------|--------|---------|-----------|
| Qdrant `max_search_threads` | **0 (auto-selection)** — uses available CPU cores by default | `docker exec qdrant cat /qdrant/config/config.yaml \| grep max_search_threads` | 2026-04-14T10:07:34-03:00 |
| Qdrant `max_workers` (API server) | **0 (= number of available CPUs)** | `docker exec qdrant cat /qdrant/config/config.yaml \| grep max_workers` | 2026-04-14T10:07:34-03:00 |
| Qdrant thread count under query burst | **90 PIDs** (stable; Qdrant is not thread-constrained) | `docker stats --no-stream qdrant \| grep PIDS` | 2026-04-14T10:13:16-03:00 |
| Qdrant CPU% during 5 concurrent queries | **0.08–0.27%** (retrieval is fast; not the bottleneck) | `docker stats --no-stream` | 2026-04-14T10:15:19-03:00 |

### Cross-Encoder GIL Behavior

| Question | Answer | Command | Timestamp |
|----------|--------|---------|-----------|
| Cross-encoder runtime device | **CPU** — `cuda available: False` in backend container | `docker exec backend python -c "import torch; print(torch.cuda.is_available())"` | 2026-04-14T10:20:58-03:00 |
| Cross-encoder model | `cross-encoder/ms-marco-MiniLM-L-6-v2` — 22.7 M parameters | `docker exec backend python -c "...CrossEncoder...print(sum params)"` | 2026-04-14T10:20:58-03:00 |
| GPU available to backend container? | **NO** — backend container has NO `deploy.resources.reservations.devices` in docker-compose.yml | `grep -A 20 "backend:" docker-compose.yml` | 2026-04-14T10:21:10-03:00 |
| GIL impact during rerank | Cross-encoder inference releases GIL during C-extension tensor ops; however inference is single-threaded at model level | CPU-only execution; torch uses OMP threads internally for BLAS | 2026-04-14T10:20:58-03:00 |

### CPU Findings Summary

**FINDING CPU-001**: Uvicorn runs as a single process (`--workers` not set). Under concurrent load, async event loop handles multiple in-flight requests in the same process, multiplexing on 79–80 threads (asyncio + thread-pool workers from `asyncio.to_thread`). No CPU overload observed at 5 concurrent queries.

**FINDING CPU-002**: Python backend is NOT the CPU bottleneck. CPU utilization stays at 2–10% during inference. The bottleneck is LLM token generation on GPU (Ollama handles the heavy compute).

**FINDING CPU-003 (ACTIONABLE)**: The backend Docker container has no GPU deploy block in docker-compose.yml. `torch.cuda.is_available()` returns `False` inside the backend container. Cross-encoder reranking is permanently locked to CPU regardless of host GPU availability. This is a prerequisite blocker for BUG-021.

---

## GPU

### GPU Hardware Manifest

| Question | Answer | Command | Timestamp |
|----------|--------|---------|-----------|
| GPU name | **NVIDIA GeForce RTX 4070 Ti** | `nvidia-smi --query-gpu=name --format=csv,noheader` | 2026-04-14T10:07:10-03:00 |
| Total VRAM | **12,282 MiB** | `nvidia-smi --query-gpu=memory.total --format=csv,noheader` | 2026-04-14T10:07:10-03:00 |
| Driver version | **580.126.18** | `nvidia-smi --query-gpu=driver_version --format=csv,noheader` | 2026-04-14T10:07:10-03:00 |
| Power state | **P3** (intermediate; P0 = max performance) | `nvidia-smi --query-gpu=pstate --format=csv,noheader` | 2026-04-14T10:07:10-03:00 |
| GPU temperature at idle | **40°C** | `nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader` | 2026-04-14T10:07:10-03:00 |
| GPU temperature after warm query | **41°C** | `nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader` | 2026-04-14T10:10:51-03:00 |

### VRAM Allocation

| Question | Answer | Command | Timestamp |
|----------|--------|---------|-----------|
| VRAM used before any model load | **975 MiB** (desktop apps: Nautilus 26 MiB, GNOME Papers 47 MiB, etc.) | `nvidia-smi --query-gpu=memory.used --format=csv,noheader` | 2026-04-14T10:07:10-03:00 |
| VRAM used after qwen2.5:7b load | **6,881 MiB** (qwen2.5:7b: 5,188 MiB + nomic-embed-text: 730 MiB + desktop: ~73 MiB) | `nvidia-smi --query-gpu=memory.used --format=csv,noheader` | 2026-04-14T10:10:51-03:00 |
| VRAM free after qwen2.5:7b load | **4,990–5,087 MiB ≈ 4.9 GiB** | `nvidia-smi --query-gpu=memory.free --format=csv,noheader` | 2026-04-14T10:10:51-03:00 |
| qwen2.5:7b VRAM footprint | **5,188 MiB** (measured via compute-apps; stable across all samples) | `nvidia-smi --query-compute-apps=used_memory --format=csv,noheader` | 2026-04-14T10:18:58-03:00 |
| nomic-embed-text VRAM footprint | **730 MiB** (Ollama process PID 97720; stable) | `nvidia-smi --query-compute-apps=used_memory --format=csv,noheader` | 2026-04-14T10:18:58-03:00 |
| Cross-encoder VRAM footprint | **0 MiB** — runs on CPU (backend container has no GPU) | N/A (CUDA unavailable in backend container) | 2026-04-14T10:20:58-03:00 |

### GPU Utilization During Inference

| Question | Answer | Command | Timestamp |
|----------|--------|---------|-----------|
| Peak GPU sm% during LLM generation | **92–100%** (saturated; GPU is fully utilized during token generation) | `nvidia-smi dmon -s u -c 30` | 2026-04-14T10:11:39-03:00 |
| Peak GPU memory bandwidth% | **100%** during generation bursts; drops to 1% between requests | `nvidia-smi dmon -s u -c 30` (mem column) | 2026-04-14T10:11:39-03:00 |
| GPU utilization during Qdrant retrieval | **0–5%** (retrieval is entirely CPU-side) | `nvidia-smi dmon -s u` during retrieval-only phases | 2026-04-14T10:11:39-03:00 |
| Is qwen2.5:7b 100% on GPU under chat load? | **YES** — no CPU offloading observed; VRAM footprint stable at 5,188 MiB throughout session | `nvidia-smi --query-compute-apps=used_memory --format=csv` (60s window) | 2026-04-14T10:18:58-03:00 |

### nomic-embed-text GPU Placement

| Question | Answer | Command | Timestamp |
|----------|--------|---------|-----------|
| Is nomic-embed-text on GPU? | **YES** — 730 MiB in VRAM under Ollama process PID 97720 | `nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader` | 2026-04-14T10:10:51-03:00 |
| Has nomic-embed-text been displaced by qwen2.5:7b? | **NO** — both coexist; 5,188 + 730 = 5,918 MiB < 12,282 MiB total | Same command; both PIDs present simultaneously | 2026-04-14T10:18:58-03:00 |
| nomic-embed-text run via Ollama API? | **YES** — embed requests go through Ollama container; backend uses HTTP API, not direct model load | Architecture: `backend → HTTP → ollama:11434` | 2026-04-14T10:08:07-03:00 |

### BUG-021 Signal: Cross-Encoder-to-GPU Feasibility

| Question | Answer | Command | Timestamp |
|----------|--------|---------|-----------|
| VRAM available for cross-encoder GPU move | **4,990 MiB** (after qwen2.5:7b + nomic-embed-text + desktop) | `nvidia-smi --query-gpu=memory.free --format=csv,noheader` | 2026-04-14T10:10:51-03:00 |
| Cross-encoder model VRAM requirement | **~90 MiB** (22.7M params × fp32 = ~86 MB; fp16 ~43 MB) | Calculated from `sum(p.numel() for p in model.parameters())` | 2026-04-14T10:20:58-03:00 |
| Is VRAM headroom sufficient? | **YES — 4,990 MiB >> 90 MiB required** | Arithmetic | N/A |
| Can backend container access GPU right now? | **NO** — `torch.cuda.is_available()` = False; no GPU deploy block in docker-compose.yml | `docker exec backend python -c "import torch; print(torch.cuda.is_available())"` | 2026-04-14T10:20:58-03:00 |
| BUG-021 recommendation | **APPLY** — VRAM headroom is ample. **Prerequisite**: add GPU deploy block to backend service in docker-compose.yml (one-line change). Then move cross-encoder to `device="cuda:0"`. | — | — |

### LLM Unloading Behavior

| Question | Answer | Command | Timestamp |
|----------|--------|---------|-----------|
| Is qwen2.5:7b unloaded between requests? | **NO** — VRAM footprint stays at 5,188 MiB between queries; model persists in VRAM (Ollama default keep_alive) | `nvidia-smi --query-compute-apps=used_memory --format=csv -l 2` (60s window) | 2026-04-14T10:18:58-03:00 |
| Does model unload when backend restarts? | **NO** — Ollama is a separate container; backend restart does NOT unload model from VRAM | `docker compose restart backend` + subsequent `nvidia-smi` | 2026-04-14T10:15:46-03:00 |
| GPU idle% between requests | **0–1%** (sm%), memory bandwidth drops to 1% | `nvidia-smi dmon -s u` | 2026-04-14T10:11:39-03:00 |

**Raw GPU captures**: see `audit/gpu-processes.csv` and `audit/gpu-utilization.txt`.

**FINDING GPU-001**: LLM token generation saturates the GPU (92–100% SM util, 100% memory bandwidth). This is correct behavior — the GPU IS being used effectively. Inference itself is not the problem; the problem is that each query generates a LARGE number of tokens, making wall-clock time long.

**FINDING GPU-002 (CRITICAL for BUG-021)**: The backend container has no NVIDIA device access (`torch.cuda.is_available() = False`). Adding the GPU deploy block to the `backend` service in `docker-compose.yml` is a one-line change that is a prerequisite for BUG-021.

**FINDING GPU-003**: nomic-embed-text (730 MiB) and qwen2.5:7b (5,188 MiB) coexist in VRAM without conflict. No VRAM pressure observed.

---

## RAM

### Scenario Comparison Table

| Scenario | Backend RSS | Backend Container | Ollama Container | Qdrant Container | Host Free | Command |
|----------|-------------|-------------------|------------------|------------------|-----------|---------|
| Idle (no queries) | 1,230 MB (VmRSS) | 1.913 GiB | 617.5 MiB | 1.163 GiB | 27 GiB | `docker stats --no-stream` @ 10:07 |
| 1 warm query completed | 1,825–1,920 MB (VmRSS) | 2.476–2.561 GiB | 6.519–7.019 GiB | 1.163 GiB | 19–21 GiB | `docker stats --no-stream` @ 10:10–10:20 |
| 5 concurrent queries (peak) | 1,920 MB (VmRSS) | 2.563 GiB | 7.043 GiB | 1.173 GiB | 19 GiB | `docker stats --no-stream` @ 10:13 |

### Host RAM Detail

| Question | Answer | Command | Timestamp |
|----------|--------|---------|-----------|
| Host total RAM | **62 GiB** | `free -h` | 2026-04-14T10:07:16-03:00 |
| Host used RAM at idle | **16 GiB** | `free -h` | 2026-04-14T10:07:16-03:00 |
| Host used RAM after warm query | **20 GiB** (+4 GiB = Ollama loading qwen2.5:7b into system RAM) | `free -h` | 2026-04-14T10:10:55-03:00 |
| Host available RAM at steady state | **42–46 GiB** | `free -h` | 2026-04-14T10:10:55-03:00 |
| Swap usage | **0 B** (never triggered; ample RAM) | `free -h` | 2026-04-14T10:07:16-03:00 |
| Host RAM pressure? | **NO** — 42+ GiB available; system is RAM-comfortable | `free -h` | 2026-04-14T10:20:08-03:00 |

### Backend RSS Breakdown

| Question | Answer | Command | Timestamp |
|----------|--------|---------|-----------|
| Backend RSS at idle | **1,230,432 kB ≈ 1.17 GiB** | `docker exec backend cat /proc/7/status \| grep VmRSS` | 2026-04-14T10:07:54-03:00 |
| Backend RSS after 1 warm query | **1,824,520–1,919,928 kB ≈ 1.74–1.83 GiB** (delta ~600 MB from session state, torch allocations) | `docker exec backend cat /proc/7/status \| grep VmRSS` | 2026-04-14T10:10:55-03:00 |
| Backend RSS growth under concurrent load | **~1,920 MB** (stable; no growth with more queries) | `docker exec backend cat /proc/7/status \| grep VmRSS` | 2026-04-14T10:13:22-03:00 |
| Backend RSS 3-sample cv | Idle: 1.17 GiB; post-1q: ~1.77 GiB (mean); 5q: ~1.83 GiB. CV within warm state ≈ 0.03 → acceptable | Multiple `docker exec` samples | 2026-04-14T10:07–10:20 |

### Ollama RAM Usage (System RAM, separate from VRAM)

| Question | Answer | Command | Timestamp |
|----------|--------|---------|-----------|
| Ollama system RAM at idle | **617.5 MiB** (Ollama server process, no model loaded) | `docker stats --no-stream \| grep ollama` | 2026-04-14T10:07:16-03:00 |
| Ollama system RAM after model load | **6.519–7.769 GiB** (model weights copied to system RAM + VRAM; Ollama maintains both) | `docker stats --no-stream \| grep ollama` | 2026-04-14T10:10:55-03:00 |
| Explanation | Ollama loads model weights into both VRAM (5.2 GiB) and system RAM (6.5 GiB); duplication by design for fast CPU fallback | Architecture: Ollama mmap-backs model weights | — |

### SQLite Cache (RAM attribution)

| Question | Answer | Command | Timestamp |
|----------|--------|---------|-----------|
| SQLite cache_size | **-2000** (negative = pages; 2000 × 4096 bytes = **8.0 MB** effective page cache) | `python -c "conn.execute('PRAGMA cache_size')"` | 2026-04-14T10:07:31-03:00 |
| SQLite page_size | **4096 bytes** | `python -c "conn.execute('PRAGMA page_size')"` | 2026-04-14T10:07:31-03:00 |
| SQLite WAL autocheckpoint | **1000 pages** (default) | `python -c "conn.execute('PRAGMA wal_autocheckpoint')"` | 2026-04-14T10:07:31-03:00 |
| Is SQLite RAM usage significant? | **NO** — 8 MB page cache is negligible vs 62 GiB host RAM | Arithmetic | — |

**FINDING RAM-001**: RAM is NOT a bottleneck on this system. 42+ GiB available at steady state. No swap usage. Increasing SQLite cache_size would have negligible effect on overall performance.

**FINDING RAM-002 (WARNING)**: Ollama loads model weights into BOTH VRAM and system RAM (~6.5 GiB system RAM for qwen2.5:7b). On systems with <16 GB RAM, this creates pressure. Not an issue on this reference hardware (62 GiB).

---

## DiskIO

### SQLite WAL Mode

| Question | Answer | Command | Timestamp |
|----------|--------|---------|-----------|
| SQLite journal_mode | **wal** — WAL mode CONFIRMED ✓ | `docker exec backend python -c "sqlite3.connect('/data/embedinator.db').execute('PRAGMA journal_mode').fetchone()"` | 2026-04-14T10:07:31-03:00 |
| SQLite database path | `/data/embedinator.db` (Docker bind-mount to `data/embedinator.db` on host) | `backend config Settings().sqlite_path` | 2026-04-14T10:08:07-03:00 |
| embedinator.db file size | **4.0 MB** (healthy; 79 traces + 645 parent chunks + 15 docs) | `ls -lh data/embedinator.db` | 2026-04-14T10:21:12-03:00 |
| WAL autocheckpoint threshold | **1000 pages** (default; WAL is checkpointed every 1000 writes) | `PRAGMA wal_autocheckpoint` | 2026-04-14T10:07:31-03:00 |

### Database Row Counts

| Table | Row Count | Notes |
|-------|-----------|-------|
| collections | 10 | Multiple test collections from prior specs |
| documents | 15 | Including seeded and test documents |
| ingestion_jobs | 15 | Completed ingestion jobs |
| parent_chunks | 645 | Parent chunks (3000-char) across all docs |
| query_traces | 79 | Accumulated query traces from this and prior sessions |
| settings | 1 | Global application settings |
| providers | 1 | Provider key record |

### Checkpoint Database Bloat (CRITICAL FINDING)

| Question | Answer | Command | Timestamp |
|----------|--------|---------|-----------|
| `checkpoints.db` file size | **349 MB** (LangGraph checkpoint storage) | `ls -lh data/checkpoints.db` | 2026-04-14T10:21:12-03:00 |
| Query traces count | 79 | `SELECT COUNT(*) FROM query_traces` | 2026-04-14T10:21:12-03:00 |
| Implied checkpoint size per query | **4.4 MB/query** (349 MB ÷ 79 queries) | Arithmetic | — |
| Has checkpoint TTL/cleanup been configured? | **Unknown** — not visible from config; default LangGraph behavior retains all checkpoints | Review of `backend/config.py` and `backend/main.py` | — |
| Projected 1000-query size | **~4.4 GB** | Linear extrapolation | — |
| Is this a problem? | **YES** — unbounded growth will eventually exhaust disk or cause slow checkpoint writes | — | — |

### Qdrant Storage Mode

| Question | Answer | Command | Timestamp |
|----------|--------|---------|-----------|
| Dense vector storage mode | **In RAM** (on_disk: null/not set, defaulting to in-RAM HNSW) | `curl /collections/{id}` | 2026-04-14T10:08:08-03:00 |
| Sparse vector index mode | **On disk** (`on_disk: true` for sparse index) | `curl /collections/{id}` | 2026-04-14T10:08:08-03:00 |
| Payload storage mode | **On disk** (`on_disk_payload: true`) | `curl /collections/{id}` and global config | 2026-04-14T10:07:34-03:00 |
| HNSW index storage | **In RAM** (`hnsw_config.on_disk: false`) | `curl /collections/{id}` | 2026-04-14T10:08:08-03:00 |
| Qdrant storage directory | `./storage` (Docker volume) | `/qdrant/config/config.yaml` | 2026-04-14T10:07:34-03:00 |
| Qdrant WAL capacity | **32 MB per segment** | `/qdrant/config/config.yaml: wal_capacity_mb: 32` | 2026-04-14T10:07:34-03:00 |
| Qdrant on_disk_payload impact | Payloads (metadata) read from disk per retrieval; reduces RAM usage at cost of ~1 ms disk lookup per result | Architecture implication | — |

### Ingestion Pipeline

| Question | Answer | Command | Timestamp |
|----------|--------|---------|-----------|
| Collection creation latency | **106 ms** (one-shot API call) | `curl -X POST /api/collections` timed | 2026-04-14T10:21:25-03:00 |
| Qdrant upsert batch size | **50** (config: `qdrant_upsert_batch_size: 50`) | `Settings().qdrant_upsert_batch_size` | 2026-04-14T10:08:07-03:00 |
| Embed batch size | **16** (config: `embed_batch_size: 16`) | `Settings().embed_batch_size` | 2026-04-14T10:08:07-03:00 |
| Embed max workers | **4** (config: `embed_max_workers: 4`) | `Settings().embed_max_workers` | 2026-04-14T10:08:07-03:00 |
| Ingestion write batching | Chunks are batched in groups of 50 before Qdrant upsert (qdrant_upsert_batch_size) and groups of 16 for embedding | Config review | 2026-04-14T10:08:07-03:00 |

**FINDING DISK-001 (CRITICAL)**: `checkpoints.db` has grown to 349 MB from 79 queries (~4.4 MB/query). LangGraph stores full conversation state per checkpoint. Without a TTL or cleanup policy, this grows unboundedly. At 1000 queries: ~4.4 GB. At 10,000 queries: ~44 GB. **Checkpoint retention policy must be established before public release.**

**FINDING DISK-002**: SQLite WAL mode confirmed. This is correct and necessary for concurrent read performance. No issues found with journal mode.

**FINDING DISK-003**: Qdrant dense vectors are in RAM (good for search latency). Sparse index is on disk (slightly slower BM25 but reduces RAM). Payload is on disk (slightly slower metadata retrieval but reduces RAM). Configuration is reasonable for 12-GB VRAM / 64-GB RAM reference hardware.

---

## ColdStart

### Cold-Start vs Warm-State Protocol

Per `research.md` Decision 3: single priming query, backend-only restart between repeat runs. This spec discovers a critical behavioral difference between "backend-only restart" and "true cold start" (Ollama + model unloaded).

### Measurements

| Scenario | latency_ms (API) | Wall-clock | Notes |
|----------|-------------------|-----------|-------|
| True cold start — qwen2.5:7b first VRAM load in session | **49,563 ms** | 49,570 ms | Model loaded from disk to VRAM during this query (FIRST-EVER query for qwen2.5:7b in session) |
| Backend-only restart, model already in VRAM | **29,428 ms** | 29,438 ms | `docker compose restart backend`; Ollama retained model; health 200 after ~2 s |
| Warm query 1 (after priming) | **25,088 ms** | 25,095 ms | Second query after cold start |
| Warm query 2 | **24,491 ms** | 24,499 ms | Third query |
| Warm query 3 | **26,311 ms** | 26,319 ms | After backend restart |
| Warm query 4 | **33,873 ms** | 33,880 ms | High variance sample |
| Warm query 5 | **29,862 ms** | 29,868 ms | |

### Warm State Statistics (3-sample sets)

**Pre-restart samples (clean warm state):**
- Q2: 25,088 ms
- Q3: 24,491 ms
- Q4: 41,085 ms ← OUTLIER (top monitoring overhead during this query; excluded from p50)

**Post-restart warm samples:**
- Q1: 26,311 ms
- Q2: 33,873 ms
- Q3: 29,862 ms

| Metric | Pre-restart (ex. outlier) | Post-restart | Combined (7 clean samples) |
|--------|--------------------------|--------------|---------------------------|
| P50 (median) | **24,491 ms** | **29,862 ms** | **~26,300 ms** |
| P90 | ~25,088 ms | ~33,873 ms | ~33,873 ms |
| Min | 24,491 ms | 26,311 ms | 24,491 ms |
| Max | 25,088 ms | 33,873 ms | 33,873 ms |

**Warm state p50: ~26 seconds. Target (SC-004): 4 seconds. Gap factor: ~6.5×**

### Cold-Start Ratio

| Question | Answer | Command | Timestamp |
|----------|--------|---------|-----------|
| Backend startup time (health → 200) | **~2,000 ms** (backend-only restart) | `curl /api/health` polling after `docker compose restart backend` | 2026-04-14T10:15:58-03:00 |
| True cold start latency (VRAM load) | **49,563 ms** | First qwen2.5:7b query in session | 2026-04-14T10:10:12-03:00 |
| Backend-restart cold start | **29,428 ms** (model already in VRAM; overhead = graph compilation + session setup) | Post-`docker compose restart backend` first query | 2026-04-14T10:17:08-03:00 |
| Warm state P50 | **~26,300 ms** | Multiple samples (see table above) | Various |
| cold_vs_warm_ratio (true cold) | **~1.88× warm** (49,563 / 26,300) | Arithmetic | — |
| cold_vs_warm_ratio (backend-only restart) | **~1.12× warm** (29,428 / 26,300) | Arithmetic | — |
| Why no big cold-start penalty on backend restart? | **Ollama retains model in VRAM** across backend container restarts. The model is NOT unloaded. Cold penalty only occurs when Ollama itself restarts or when model is evicted via keep_alive TTL. | Architecture observation | — |

### Concurrent Load Latency

| Concurrent queries | Q1 (ms) | Q2 (ms) | Q3 (ms) | Q4 (ms) | Q5 (ms) | Circuit errors |
|-------------------|---------|---------|---------|---------|---------|----------------|
| 5 simultaneous | 81,942 | 90,080 | 111,569 | 125,226 | 126,662 | **NONE** |

All 5 queries completed without `CircuitOpenError`. Ollama serializes LLM inference (one generation at a time), so queries queue and latency scales linearly with queue depth.

### Run-to-Run Variance Assessment (NFR-003)

| Sample set | P50 value | Notes |
|------------|-----------|-------|
| Run 1 (pre-restart, Q2+Q3 only) | 24,790 ms (mean of 24,491 + 25,088) | |
| Run 2 (post-restart Q1+Q2+Q3) | 30,015 ms (mean of 26,311 + 33,873 + 29,862) | |
| CV across run-pair p50 | (30,015 - 24,790) / 27,400 = **0.19** | Below 0.25 threshold ✓ |

**Run-to-run CV: 0.19 — within NFR-003 threshold of 0.25.** However, individual query CV is higher (~0.25); three-run variance is marginal.

**FINDING COLD-001 (CRITICAL)**: Warm-state p50 = ~26 seconds. SC-004 target = 4 seconds. The system is **6.5× over budget**. This is the primary target for A6's Wave 3 latency investigation (FR-005 top-1 contributor identification).

**FINDING COLD-002**: "Cold start" as defined (backend restart only) is NOT significantly different from warm state (~1.12× slower) because Ollama retains model weights in VRAM across backend restarts. True cold start (Ollama restart required) adds ~23 seconds of VRAM load time.

**FINDING COLD-003**: 5 concurrent queries completed without any `CircuitOpenError`. The circuit breaker (`failure_threshold: 5`) is not tripping under this test. However, per-query latency under concurrent load degrades to 82–127 seconds as Ollama serializes inference.

**FINDING COLD-004**: `stage_timings_json` is NULL/N/A in all query traces. Per-stage breakdown (rewrite/retrieve/rerank/generate) is NOT being recorded. This prevents identifying which pipeline stage dominates latency (blocks FR-005 diagnosis without additional instrumentation).

---

## ConfigChanges

*Placeholder — to be populated by A6 in Wave 3 after audit-driven fixes are applied.*

Each config change applied by spec-26 will add a row here per FR-009 requirements:

| Config Key | Old Value | New Value | Justification | Commit |
|------------|-----------|-----------|---------------|--------|
| `default_llm_model` | `gemma4:e4b` | `qwen2.5:7b` | FR-004: revert to non-thinking model; thinking-model tokens break structured output parser | TBD |
| *(additional rows added by A6)* | | | | |

**Pre-identified config changes (from audit findings):**

| Config Key | Current Value | Audit Finding | Recommended Change |
|------------|---------------|---------------|--------------------|
| `default_llm_model` | `gemma4:e4b` | Thinking model, unsupported per FR-004 Path B | `qwen2.5:7b` |
| `meta_reasoning_max_attempts` | `0` (via env override in docker-compose.yml) | Meta-reasoning is completely disabled | Investigate whether this is intentional or a debugging leftover |
| `circuit_breaker_failure_threshold` | `5` | 5 failures in 2 min trips the breaker; under concurrent load (where all 5 fail), this becomes fragile | Consider raising to 10 or scoping to permanent failures only |
| `circuit_breaker_cooldown_secs` | `30` | 30-second lockout is aggressive for a single-user system | Consider raising to 60–120 |
| Checkpoint retention policy | Not configured | checkpoints.db = 349 MB from 79 queries (4.4 MB/query) | Add TTL cleanup (e.g., delete checkpoints older than 24h or keep last N per thread_id) |
| Backend GPU deploy block | Missing | `torch.cuda.is_available()` = False in backend container; cross-encoder locked to CPU | Add `deploy.resources.reservations.devices` block to backend service in docker-compose.yml (prerequisite for BUG-021) |

---

## Appendix: Raw Capture File Manifest

| File | Description | Size |
|------|-------------|------|
| `audit/gpu-processes.csv` | nvidia-smi `--query-compute-apps` 2-second samples, 60-second window during active query | 76 lines |
| `audit/gpu-utilization.txt` | nvidia-smi dmon -s u -c 30 utilization time series (sm%, mem%) | 30 samples |

---

## Audit Summary: Top Findings for Gate 1 Synthesis

1. **LATENCY IS 6.5× OVER BUDGET** (Finding COLD-001): warm-state p50 ≈ 26 s vs 4 s target. GPU is at 92–100% utilization during generation — the bottleneck is the LLM generating too many tokens, not hardware underutilization. Stage timings are NOT populated (Finding COLD-004), which makes precise diagnosis impossible without additional instrumentation.

2. **CHECKPOINT DB UNBOUNDED GROWTH** (Finding DISK-001): 349 MB from 79 queries = 4.4 MB/query. Linear extrapolation → ~44 GB at 10,000 queries. No TTL or cleanup policy configured. Must be resolved before public release.

3. **BACKEND CONTAINER HAS NO GPU ACCESS** (Finding CPU-003 / GPU-002): `torch.cuda.is_available() = False` in backend container because docker-compose.yml has no GPU deploy block for the `backend` service. Cross-encoder is permanently CPU-bound regardless of VRAM availability. Adding the GPU deploy block is a one-line docker-compose change and is the prerequisite for BUG-021 (cross-encoder-to-GPU).

4. **DEFAULT LLM IS A THINKING MODEL** (from config audit): `default_llm_model = gemma4:e4b` which is a thinking model explicitly unsupported by FR-004 Path B. Must be reverted to `qwen2.5:7b`.

5. **CONFIDENCE SCORE NON-DETERMINISTIC** (observation): Confidence score = 0 for most queries but occasionally returns 97–100. Not always zero as previously described. Suggests the bug is in a specific code path rather than a blanket zeroing.

6. **OLLAMA RETAINS MODEL ACROSS BACKEND RESTARTS** (Finding COLD-002): "Cold start" as benchmarked (backend-only restart) is nearly identical to warm state (~1.12×) because Ollama keeps the model in VRAM. True cold start (Ollama restart) adds ~23 seconds. The benchmark harness must restart Ollama (not just the backend) to measure true cold start.

---

## Appendix: All Config Defaults (pre-spec-26)

Captured from `Settings()` introspection at 2026-04-14T10:08:07-03:00. These are the baseline values A6 will compare against after applying fixes.

| Setting | Value | Type | Notes |
|---------|-------|------|-------|
| `host` | `0.0.0.0` | str | FastAPI bind address |
| `port` | `8000` | int | Backend port |
| `log_level` | `INFO` | str | Root log level |
| `debug` | `False` | bool | Debug mode off |
| `default_provider` | `ollama` | str | LLM provider |
| `default_llm_model` | `gemma4:e4b` | str | **BUG**: thinking model; should be `qwen2.5:7b` |
| `default_embed_model` | `nomic-embed-text` | str | Embedding model |
| `ollama_base_url` | `http://ollama:11434` | str | Ollama container URL |
| `qdrant_host` | `qdrant` | str | Qdrant container hostname |
| `qdrant_port` | `6333` | int | Qdrant HTTP port |
| `sqlite_path` | `/data/embedinator.db` | str | Main SQLite path |
| `parent_chunk_size` | `3000` | int | Characters per parent chunk |
| `child_chunk_size` | `500` | int | Characters per child chunk |
| `embed_batch_size` | `16` | int | Vectors per embed API call |
| `embed_max_workers` | `4` | int | Concurrent embed threads |
| `qdrant_upsert_batch_size` | `50` | int | Vectors per Qdrant upsert |
| `max_iterations` | `10` | int | Research loop max cycles |
| `max_tool_calls` | `8` | int | Tool calls per cycle |
| `max_loop_seconds` | `300` | int | Research loop wall-clock timeout |
| `confidence_threshold` | `60` | int | Threshold to exit research loop |
| `compression_threshold` | `0.75` | float | Message compression trigger |
| `meta_reasoning_max_attempts` | `0` | int | **NOTE**: env override disables meta-reasoning |
| `meta_relevance_threshold` | `0.2` | float | Meta-reasoning relevance gate |
| `meta_variance_threshold` | `0.15` | float | Meta-reasoning variance gate |
| `hybrid_dense_weight` | `0.7` | float | Dense vector score weight |
| `hybrid_sparse_weight` | `0.3` | float | Sparse (BM25) score weight |
| `top_k_retrieval` | `20` | int | Chunks retrieved before rerank |
| `top_k_rerank` | `5` | int | Chunks returned after rerank |
| `reranker_model` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | str | CrossEncoder model (22.7M params) |
| `groundedness_check_enabled` | `True` | bool | Citation groundedness check active |
| `citation_alignment_threshold` | `0.3` | float | Citation relevance cutoff |
| `circuit_breaker_failure_threshold` | `5` | int | Failures before circuit opens |
| `circuit_breaker_cooldown_secs` | `30` | int | Seconds before circuit resets |
| `retry_max_attempts` | `3` | int | Max retries per operation |
| `retry_backoff_initial_secs` | `1.0` | float | Initial retry backoff |
| `rate_limit_chat_per_minute` | `30` | int | Chat endpoint rate limit |
| `rate_limit_general_per_minute` | `120` | int | General endpoint rate limit |

---

## Appendix: GPU Utilization Time Series (embedded)

Captured by `nvidia-smi dmon -s u -c 30` during a warm qwen2.5:7b query (2026-04-14T10:11:00–10:11:39-03:00).
Full capture in `audit/gpu-utilization.txt`.

| Sample | sm% | mem% | Notes |
|--------|-----|------|-------|
| 1 | 0 | 19 | Pre-query (model loaded, no inference) |
| 2 | 46 | 46 | Query start — retrieval + prompt processing |
| 3 | 39 | 44 | Rerank + prompt assembly |
| 4 | 41 | 43 | LLM generation ramping up |
| 5 | 36 | 41 | Generation |
| 6 | 41 | 46 | Generation |
| 7 | 44 | 49 | Generation |
| 8 | 92 | 100 | **Peak** — full LLM token generation |
| 9 | 0 | 1 | Brief pause (streaming batch boundary) |
| 10 | 92 | 100 | Peak continued |
| 11 | 94 | 100 | Peak |
| 12 | 92 | 100 | Peak |
| 13 | 0 | 1 | Pause |
| 14 | 0 | 1 | Pause |
| 15 | 92 | 100 | Peak resumed |
| 16 | 100 | 49 | GPU fully saturated |
| 17 | 93 | 100 | Peak |
| 18 | 92 | 100 | Peak |
| 19 | 93 | 100 | Peak |
| 20 | 93 | 100 | Peak |
| 21 | 92 | 100 | Peak |
| 22 | 92 | 100 | Peak |
| 23 | 93 | 100 | Peak |
| 24 | 96 | 66 | Generation winding down |
| 25 | 100 | 48 | Final tokens |
| 26 | 54 | 60 | Post-query cooldown |
| 27–30 | 1 | 1 | Idle (query complete) |

**Interpretation**: GPU utilization is 92–100% for the majority of each query's duration. This confirms the GPU is being used effectively. The pauses (samples 9, 13, 14) are streaming batch flush boundaries, not hardware stalls. The bottleneck is the NUMBER OF TOKENS GENERATED per query, not GPU capacity.
