#!/usr/bin/env bash
# dev-rebuild-backend.sh — rebuild the backend Docker image and restart the service.
#
# Why this exists (spec-28 BUG-014):
#   `Dockerfile.backend` does not bind-mount `backend/`. The Python source lives
#   inside the image. So `docker compose restart backend` does NOT pick up source
#   changes — it just recreates the container from the existing (stale) image.
#   This caused weeks of phantom debugging in spec-28 because live verification
#   was running an image built before the fix commits landed.
#
# Use this script after editing anything under `backend/` to ensure the running
# container actually reflects your source. For frontend hot-reload, see
# `make dev-frontend`. For full native dev with backend hot-reload, see
# `make dev-backend` (uvicorn --reload outside Docker).
#
# Usage:
#   ./scripts/dev-rebuild-backend.sh
#
# Equivalent to:
#   docker compose build backend && docker compose up -d backend
#
# This script is intentionally NOT a Makefile target — the Makefile signature
# is locked at 14 targets per spec-19 SC-010.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Rebuilding backend image..."
docker compose build backend

echo ""
echo "==> Restarting backend container with the new image..."
docker compose up -d backend

echo ""
echo "==> Waiting for backend health (max 60s)..."
for i in $(seq 1 60); do
  if docker compose ps backend --format '{{.Status}}' 2>/dev/null | grep -q healthy; then
    echo "backend healthy after ${i}s"
    exit 0
  fi
  sleep 1
done

echo "WARN: backend did not report healthy within 60s. Check 'docker compose logs backend'." >&2
exit 1
