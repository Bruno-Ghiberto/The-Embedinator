#!/usr/bin/env bash
# run-e2e-live.sh — bring up the live dependencies the real-socket E2E harness needs,
#                   verify them, then hand off to the sanctioned test runner.
#
# WHY THIS EXISTS (spec-31 Phase 0)
#   `tests/e2e/` is not end-to-end. `tests/e2e/test_chat_e2e.py:80` drives the app
#   through `httpx.ASGITransport` — in-process ASGI, no socket, no proxy. Bugs that
#   live in the socket, the proxy, or the process boundary are invisible to it.
#
#   `tests/e2e_real/` fixes that by spawning real processes: its own uvicorn backend,
#   its own fake-Ollama stub, and a real `next dev` server. Those the harness starts
#   itself. What it cannot start for itself is Qdrant, and that is this script's job.
#
# WHAT THIS BRINGS UP, AND WHAT IT DELIBERATELY DOES NOT
#   Starts:      qdrant only.
#   Never starts: the `backend` and `frontend` containers. The harness runs its own
#                 backend and its own Next server, and the containers publish :8000
#                 and :3000. Starting them would either lose the port race or, worse,
#                 win it — and the suite would then be testing a container image built
#                 before the fix commits landed, which is precisely the phantom-
#                 debugging failure `dev-rebuild-backend.sh` was written to end.
#   Never starts: ollama. The harness points OLLAMA_BASE_URL at its own deterministic
#                 stub. A real model server would make the graph non-deterministic.
#
# WHAT THIS SCRIPT WILL NEVER DO
#   No destructive Docker command appears here — no `down -v`, no `volume rm`, no
#   `volume prune`, no `system prune`. Volume destruction is a human-run event by
#   design: the cold-start measurement is an operator gate, and a green suite is
#   never evidence for it. This script only ever starts things.
#
# KNOWN SIDE EFFECT — `next dev` DIRTIES A TRACKED FILE
#   Starting the dev server rewrites `frontend/next-env.d.ts`, switching its routes
#   type import from `./.next/types/routes.d.ts` to `./.next/dev/types/routes.d.ts`.
#   `next build` writes the other variant back, so the two flip the file between them.
#
#   It is a real, reproducible modification to a tracked file, and it matters twice
#   over: a review candidate is frozen by content, so an unrelated byte change
#   invalidates it, and the diff looks like a deliberate edit to anyone reading it.
#
#   After any run that spawned the proxy fixture, check and restore:
#       git status --short frontend/next-env.d.ts
#       git restore frontend/next-env.d.ts
#
#   This script does not restore it automatically. A test runner that quietly edits
#   tracked source is a worse problem than the one it would be solving.
#
# USAGE
#   ./scripts/run-e2e-live.sh                          # preflight, start qdrant, run tests/e2e_real/
#   ./scripts/run-e2e-live.sh -n s31-b0-proxy-green tests/e2e_real/test_proxy_fixture.py
#   ./scripts/run-e2e-live.sh --check-only             # preflight and start qdrant, run nothing
#
#   The handoff is `scripts/run-tests-external.sh`, which launches pytest detached and
#   returns immediately. Poll the status file it prints:
#       cat Docs/Tests/<name>.status   → RUNNING | PASSED | FAILED | ERROR | NO_TESTS
#   Bare `pytest` is denied at the permission layer; do not try to shortcut this.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

readonly QDRANT_CONTAINER="embedinator-qdrant"
readonly QDRANT_HEALTH_TIMEOUT=90
readonly DEFAULT_TARGET="tests/e2e_real/"
readonly DEFAULT_RUN_NAME="s31-b0-e2e-live"

RUN_NAME="$DEFAULT_RUN_NAME"
TEST_TARGET="$DEFAULT_TARGET"
CHECK_ONLY=0

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--name)
      RUN_NAME="$2"; shift 2 ;;
    --check-only)
      CHECK_ONLY=1; shift ;;
    -h|--help)
      # Print the header block verbatim rather than maintaining a second copy of it
      # that drifts out of sync with the real explanation.
      awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "${BASH_SOURCE[0]}"
      exit 0 ;;
    -*)
      echo "Error: unknown option '$1'. Use -h for help." >&2
      exit 1 ;;
    *)
      TEST_TARGET="$1"; shift ;;
  esac
done

# ---------------------------------------------------------------------------
# setting <NAME> <default> — read a setting from the environment, then .env.
#
# docker compose reads .env by itself; this shell does not, so a port overridden
# there would otherwise be invisible and the health probe would poll the wrong port.
# ---------------------------------------------------------------------------
setting() {
  local name="$1" fallback="$2" from_env

  if [[ -n "${!name:-}" ]]; then
    echo "${!name}"
    return
  fi

  if [[ -f "$REPO_ROOT/.env" ]]; then
    from_env="$(grep -E "^[[:space:]]*${name}=" "$REPO_ROOT/.env" | tail -1 | cut -d= -f2- | tr -d '"'\''[:space:]' || true)"
    if [[ -n "$from_env" ]]; then
      echo "$from_env"
      return
    fi
  fi

  echo "$fallback"
}

QDRANT_PORT="$(setting EMBEDINATOR_PORT_QDRANT 6333)"

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
echo "==> Preflight"

if ! command -v docker >/dev/null 2>&1; then
  echo "FATAL: docker not found on PATH." >&2
  exit 1
fi

# The Docker context silently flips to desktop-linux, which is a different daemon:
# containers started under 'default' become invisible and `docker compose ps` returns
# empty. That reads as "nothing is running" and sends you debugging the wrong thing.
DOCKER_CONTEXT="$(docker context show 2>/dev/null || echo unknown)"
if [[ "$DOCKER_CONTEXT" != "default" ]]; then
  echo "FATAL: docker context is '$DOCKER_CONTEXT', expected 'default'." >&2
  echo "       Containers started under another context are invisible to this one." >&2
  echo "       Fix with: docker context use default" >&2
  exit 1
fi
echo "    docker context: $DOCKER_CONTEXT"

if ! command -v node >/dev/null 2>&1; then
  echo "FATAL: node not found on PATH — the next dev proxy fixture cannot start." >&2
  exit 1
fi
echo "    node: $(node --version)"

# The proxy fixture spawns a real `next dev`, which needs a real node_modules in this
# checkout. A symlinked one is not enough: Turbopack rejects a node_modules symlink
# that points outside the project root and the dev server exits 1 on startup.
if [[ ! -d "$REPO_ROOT/frontend/node_modules" ]] || [[ -L "$REPO_ROOT/frontend/node_modules" ]]; then
  echo "FATAL: $REPO_ROOT/frontend/node_modules is missing or is a symlink." >&2
  echo "       Turbopack refuses a symlinked node_modules that points out of the project root." >&2
  echo "       Fix with: (cd frontend && npm ci)" >&2
  exit 1
fi
echo "    frontend/node_modules: present"

if [[ ! -x "$REPO_ROOT/.venv/bin/python" ]]; then
  echo "    NOTE: no .venv yet — run-tests-external.sh will build one and install"
  echo "          requirements on first use. That first run is slow."
fi

# ---------------------------------------------------------------------------
# Start Qdrant
# ---------------------------------------------------------------------------
echo ""
echo "==> Starting Qdrant"

if docker ps --format '{{.Names}}' | grep -qx "$QDRANT_CONTAINER"; then
  echo "    $QDRANT_CONTAINER already running"
elif docker ps -a --format '{{.Names}}' | grep -qx "$QDRANT_CONTAINER"; then
  # Prefer starting the existing container over `compose up`. `docker compose up -d`
  # without the explicit overlay file set silently rewrites service config; starting
  # the container by name touches nothing else in the project.
  echo "    starting existing container $QDRANT_CONTAINER"
  docker start "$QDRANT_CONTAINER" >/dev/null
else
  echo "    no $QDRANT_CONTAINER container yet — creating it via compose"
  docker compose up -d qdrant
fi

echo ""
echo "==> Waiting for Qdrant on :${QDRANT_PORT} (max ${QDRANT_HEALTH_TIMEOUT}s)"

qdrant_ready=0
for i in $(seq 1 "$QDRANT_HEALTH_TIMEOUT"); do
  if curl -fsS --max-time 2 "http://localhost:${QDRANT_PORT}/healthz" >/dev/null 2>&1; then
    echo "    Qdrant healthy after ${i}s"
    qdrant_ready=1
    break
  fi
  sleep 1
done

if [[ "$qdrant_ready" -ne 1 ]]; then
  echo "FATAL: Qdrant did not answer http://localhost:${QDRANT_PORT}/healthz within ${QDRANT_HEALTH_TIMEOUT}s." >&2
  echo "       Check: docker logs $QDRANT_CONTAINER" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Hand off to the sanctioned runner
# ---------------------------------------------------------------------------
if [[ "$CHECK_ONLY" -eq 1 ]]; then
  echo ""
  echo "==> --check-only: dependencies are up, running no tests."
  exit 0
fi

echo ""
echo "==> Handing off to scripts/run-tests-external.sh"
echo "    run name: $RUN_NAME"
echo "    target:   $TEST_TARGET"

# --no-cov is not optional here. pytest.ini sets --cov-fail-under=80, and the harness
# runs the code under test in subprocesses whose coverage this process never collects,
# so a covered run would fail on a number that measures nothing.
exec zsh "$REPO_ROOT/scripts/run-tests-external.sh" -n "$RUN_NAME" --no-cov "$TEST_TARGET"
