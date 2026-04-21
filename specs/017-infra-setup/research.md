# Research: Spec 17 — Infrastructure Audit Findings

**Date**: 2026-03-19
**Branch**: `017-infra-setup`
**Method**: Codebase inspection via Serena + direct file reads

---

## Audit Summary

All primary infrastructure files exist. The goal of spec-17 is targeted remediation of specific gaps. No files need to be created from scratch — all work is additive/corrective.

---

## Decision 1: `api_key_encryption_secret` vs `EMBEDINATOR_FERNET_KEY`

**Finding**: `backend/config.py` line 31 defines `api_key_encryption_secret: str = ""` with no `alias`. Pydantic-settings reads this as env var `API_KEY_ENCRYPTION_SECRET`. However, Constitution V specifies: *"The Fernet encryption key MUST come from `EMBEDINATOR_FERNET_KEY` env var."*

**Gap**: Missing `Field(default="", alias="EMBEDINATOR_FERNET_KEY")` — direct Constitution V violation.

**Decision**: Add `alias="EMBEDINATOR_FERNET_KEY"` to the field in `config.py`. Update `.env.example` to use `EMBEDINATOR_FERNET_KEY=` (not `API_KEY_ENCRYPTION_SECRET=`). This is a one-line fix.

**Rationale**: Constitution V is the authoritative source. The alias makes the field read from the correct env var while keeping the Python attribute name descriptive.

**Alternatives considered**: Rename the field to `fernet_key` — rejected; `api_key_encryption_secret` is more descriptive in Python code and is already referenced across the codebase.

---

## Decision 2: `Dockerfile.backend` State

**Finding**: `Dockerfile.backend` is a single-stage build — `FROM python:3.14-slim` only. No Rust compilation stage. No non-root user.

**Gap**: Violates FR-004 (multi-stage Rust+Python) and FR-015 (non-root user).

**Decision**: Rewrite `Dockerfile.backend` as a two-stage build:
- Stage 1: `FROM rust:1.93 AS rust-builder` — compiles `ingestion-worker/`
- Stage 2: `FROM python:3.14-slim` — Python runtime, copies compiled binary, creates non-root user

**Rationale**: FR-003 requires the native binary to be compiled as part of the build. FR-015 (security, confirmed in clarification Q2) requires non-root. These two changes are mandatory.

**Alternatives considered**: Separate `Dockerfile.rust` pre-building the binary — rejected; multi-stage is the idiomatic approach and keeps everything in one file.

---

## Decision 3: Makefile State

**Finding**: Current `Makefile` has 7 targets: `dev`, `test`, `clean`, `docker-up`, `docker-down`, `build`, `lint`. FR-011 requires exactly 14 named targets.

**Missing targets**:
- `setup` — install all dependencies
- `build-rust` — compile ingestion worker
- `dev-infra` — start Qdrant + Ollama only
- `dev-backend` — run backend natively
- `dev-frontend` — run frontend natively
- `up` — full 4-service production mode (currently called `docker-up`)
- `down` — stop all services (currently called `docker-down`)
- `pull-models` — download LLM and embedding models
- `test-cov` — run tests with ≥80% coverage gate (SC-006)
- `test-frontend` — run frontend vitest tests
- `clean-all` — remove all artifacts including volumes

**Decision**: Add all 11 missing targets. Rename existing `docker-up` → `up`, `docker-down` → `down` (or add aliases). Add `##` comments for SC-008 self-documentation. Add `help` target.

**Rationale**: FR-011 is explicit and SC-008 requires self-documentation. The current Makefile is Phase 1 MVP state; spec-17 brings it to production completeness.

---

## Decision 4: `docker-compose.prod.yml` Reconciliation

**Finding**: `docker-compose.prod.yml` contains only 2 services (backend + frontend) as overrides. It appears to be a production-only override file that extends `docker-compose.yml`.

**Decision**: Keep `docker-compose.prod.yml` as an override file for production-specific settings (resource limits, production env vars). Document its purpose clearly in the file header and in `Makefile` comments. The `up` target should use `docker-compose.yml` (full 4-service); the `up-prod` target (optional, not in FR-011) can combine both.

**Rationale**: This pattern (base compose + override) is idiomatic. No consolidation needed. Constitution VII (4 services max) is satisfied — prod compose overrides don't add new services.

---

## Decision 5: GPU Passthrough Verification

**Finding**: `docker-compose.yml` does not contain NVIDIA GPU passthrough config in current grep output. The Ollama service has health check and restart policy, but no `deploy.resources.reservations.devices` block.

**Decision**: A4 must add GPU passthrough block to the Ollama service in `docker-compose.yml`. This is safe — Docker silently ignores the block on CPU-only machines.

**Rationale**: FR-008 explicitly requires GPU passthrough support. SC-003 (single-command production deploy) requires this to work on GPU machines without manual configuration.

---

## Decision 6: `frontend/Dockerfile` — Already Compliant

**Finding**: `frontend/Dockerfile` is already multi-stage (base → deps → builder → runner), includes non-root user (`adduser --system --uid 1001 nextjs; USER nextjs`), and copies from `.next/standalone`.

**Decision**: No changes needed. A3 verifies only.

---

## Decision 7: `docker-compose.yml` — Mostly Compliant

**Finding**: All 4 services present. Health checks present on at least 3 services. Restart policies present. Volumes present. `depends_on` present.

**Decision**: A4 verifies GPU passthrough block is present for Ollama. If missing, adds it. Otherwise no changes needed.

---

## No NEEDS CLARIFICATION Remaining

All questions from the spec clarification session are resolved:
- CI/CD: out of scope ✅
- Non-root containers: FR-015 applies ✅
- Single-node: confirmed ✅
- Secrets via `.env`: confirmed ✅
- Design tradeoffs: in Constraints section ✅
