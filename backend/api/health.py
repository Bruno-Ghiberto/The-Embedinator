"""System health check endpoint with per-service latency measurements.

FR-037: All health probes in this module use direct httpx.AsyncClient calls.
They intentionally bypass the HybridSearcher circuit breaker so that health
checks always reflect actual service availability rather than circuit state.
"""

import time

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.agent.schemas import HealthResponse, HealthServiceStatus
from backend.config import settings

router = APIRouter()

# Module-level flag: True until the first readiness probe completes (FR-035).
# Callers see "starting" on the very first /api/health call so orchestrators
# (e.g. docker-compose depends_on) know the backend is still initialising.
_first_probe = True


@router.get("/api/health/live")
async def health_live():
    """Liveness probe — returns alive unconditionally, no dependency checks (FR-032)."""
    return {"status": "alive"}


@router.get("/api/health")
async def health(request: Request):
    """Readiness probe: probe SQLite, Qdrant, and Ollama with latency measurements."""
    global _first_probe

    # FR-035: On the very first call return "starting" without probing dependencies.
    if _first_probe:
        _first_probe = False
        response = HealthResponse(status="starting", services=[])
        return JSONResponse(content=response.model_dump(), status_code=200)

    services = []
    all_ok = True

    # 1. SQLite probe
    sqlite_status = await _probe_sqlite(request)
    services.append(sqlite_status)
    if sqlite_status.status == "error":
        all_ok = False

    # 2. Qdrant probe
    qdrant_status = await _probe_qdrant(request)
    services.append(qdrant_status)
    if qdrant_status.status == "error":
        all_ok = False

    # 3. Ollama probe
    # NOTE FR-037: Uses direct httpx call — intentionally bypasses HybridSearcher
    # circuit breaker so this probe always reflects true Ollama availability.
    ollama_status = await _probe_ollama()
    services.append(ollama_status)
    if ollama_status.status == "error":
        all_ok = False

    status = "healthy" if all_ok else "degraded"
    status_code = 200 if all_ok else 503

    response = HealthResponse(
        status=status,
        services=services,
    )

    return JSONResponse(
        content=response.model_dump(),
        status_code=status_code,
    )


async def _probe_sqlite(request: Request) -> HealthServiceStatus:
    """Probe SQLite with SELECT 1."""
    start = time.monotonic()
    try:
        db = request.app.state.db
        await db.db.execute("SELECT 1")
        latency = round((time.monotonic() - start) * 1000, 1)
        return HealthServiceStatus(name="sqlite", status="ok", latency_ms=latency)
    except Exception as e:
        return HealthServiceStatus(name="sqlite", status="error", error_message=str(e))


async def _probe_qdrant(request: Request) -> HealthServiceStatus:
    """Probe Qdrant health check."""
    start = time.monotonic()
    try:
        qdrant = request.app.state.qdrant
        is_healthy = await qdrant.health_check()
        latency = round((time.monotonic() - start) * 1000, 1)
        if is_healthy:
            return HealthServiceStatus(name="qdrant", status="ok", latency_ms=latency)
        else:
            return HealthServiceStatus(name="qdrant", status="error", error_message="Unreachable")
    except Exception as e:
        return HealthServiceStatus(name="qdrant", status="error", error_message=str(e))


async def _probe_ollama() -> HealthServiceStatus:
    """Probe Ollama via /api/tags and check model availability (FR-034).

    NOTE FR-037: Uses direct httpx call — intentionally bypasses HybridSearcher
    circuit breaker so this probe always reflects true Ollama availability.
    """
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            latency = round((time.monotonic() - start) * 1000, 1)
            if resp.status_code == 200:
                data = resp.json()
                available_names = {m["name"] for m in data.get("models", [])}
                models = {
                    settings.default_llm_model: settings.default_llm_model in available_names,
                    settings.default_embed_model: settings.default_embed_model in available_names,
                }
                return HealthServiceStatus(
                    name="ollama", status="ok", latency_ms=latency, models=models
                )
            else:
                return HealthServiceStatus(
                    name="ollama", status="error",
                    error_message=f"HTTP {resp.status_code}",
                )
    except Exception as e:
        return HealthServiceStatus(name="ollama", status="error", error_message=str(e))
