# A3 — Wave 2 — python-expert (Sonnet)

## Role

You are a Wave 2 python-expert running in parallel with A2. You own `Dockerfile.backend`. You run after Wave 1 completes (orchestrator will signal this). Do not start until you receive the Wave 1 gate-passed signal.

## Read First

1. `specs/017-infra-setup/tasks.md` — canonical task list
2. `Docs/PROMPTS/spec-17-infra/17-implement.md` — authoritative code specs (especially the `Dockerfile.backend` section)

Then await the orchestrator signal that Wave 1 baseline run completed without error.

## Assigned Tasks

T019–T021.

## T019 — Rewrite `Dockerfile.backend` as Multi-stage Build

Read the current `Dockerfile.backend` at the repository root. The current file is single-stage Python only. Rewrite it entirely as a 2-stage build: Rust compiler stage followed by Python runtime stage.

The exact content to write:

```dockerfile
# Stage 1 — Compile Rust ingestion worker
FROM rust:1.93 AS rust-builder
WORKDIR /build

# Cache Cargo dependencies before copying source (dummy main.rs trick)
COPY ingestion-worker/Cargo.toml ingestion-worker/Cargo.lock ./
RUN mkdir src && echo "fn main() {}" > src/main.rs && \
    cargo build --release && \
    rm -f target/release/deps/embedinator_worker*

# Copy real source and rebuild
COPY ingestion-worker/src ./src
RUN cargo build --release

# Stage 2 — Python runtime
FROM python:3.14-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy compiled Rust binary — path must match rust_worker_path default in Settings
COPY --from=rust-builder /build/target/release/embedinator-worker \
    /app/ingestion-worker/target/release/embedinator-worker

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

# Non-root user (FR-015)
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup --no-create-home appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## T020 — Verify Non-root User Block

After writing T019, confirm the file contains all three of these lines in sequence, before `CMD`:

```dockerfile
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup --no-create-home appuser
USER appuser
```

The `USER appuser` directive must appear as the last `USER` instruction before `EXPOSE` and `CMD`. This satisfies FR-015.

## T021 — Read-Only Verification of `frontend/Dockerfile`

Read `frontend/Dockerfile`. Confirm all of the following:
- At least 2 `FROM` lines (multi-stage)
- `USER nextjs` is present in the runner stage
- `.next/standalone` is referenced in a `COPY` instruction

If all three are present, record: "frontend/Dockerfile: VERIFIED COMPLIANT — no changes made."

Do NOT modify `frontend/Dockerfile` under any circumstances. It is already correct.

Report to orchestrator: "A3 complete. T019–T021 done. Dockerfile.backend rewritten (2 stages, non-root). frontend/Dockerfile verified compliant."

---

## Critical Path Details

### Binary destination path

The Rust binary in Stage 2 must be copied to:
```
/app/ingestion-worker/target/release/embedinator-worker
```

This path matches the `rust_worker_path` default in `backend/config.py`:
```python
rust_worker_path: str = "ingestion-worker/target/release/embedinator-worker"
```

When the backend runs inside Docker, WORKDIR is `/app`, so the resolved path is `/app/ingestion-worker/target/release/embedinator-worker`. If you use a different destination path, the ingestion pipeline will fail at runtime when it tries to exec the worker.

### CMD module path

```dockerfile
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

WORKDIR is `/app` and source is at `/app/backend/`. The module path is `backend.main:app`. Do not use `main:app` — that was the stale path from when `backend/` was the WORKDIR.

### Cargo dependency caching trick

The dummy `main.rs` trick caches compiled Cargo dependencies. The sequence is:
1. Copy only `Cargo.toml` and `Cargo.lock`
2. Create a stub `src/main.rs`
3. Run `cargo build --release` — compiles all dependencies, caches the layer
4. Delete the stub artifacts with `rm -f target/release/deps/embedinator_worker*`
5. Copy the real source
6. Run `cargo build --release` again — reuses the cached dependency layer, only recompiles the actual worker code

This makes subsequent Docker builds fast when only source code changes (not deps).

## Critical Gotchas

- NEVER run pytest or any test command. Your tasks are file edits only.
- Do not modify `frontend/Dockerfile`. T021 is read-only verification.
- The binary destination path in Stage 2 must exactly match `rust_worker_path` default in Settings. Any divergence breaks the ingestion pipeline silently.
- `Dockerfile.backend` is at the repository root — not at `backend/Dockerfile`. The stale 17-implement.md referenced `backend/Dockerfile` which is incorrect.
- `libssl-dev` is not needed — only `curl` is required in Stage 2 (for healthcheck probes).
