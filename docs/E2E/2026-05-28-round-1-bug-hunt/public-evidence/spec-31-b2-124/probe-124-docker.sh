#!/usr/bin/env bash
# BUG-124 live probe — docker half. Usage: probe-124-docker.sh <outage-seconds> <timeline-file>
# Stops the backend, holds the outage, starts it, and stamps the moment the container is healthy.
# The browser half (banner text via Playwright MCP) is driven by the orchestrator against the stamps.
set -euo pipefail
OUTAGE="${1:-190}"; OUT="${2:-/dev/stdout}"
ts() { date -u +%Y-%m-%dT%H:%M:%S.%3NZ; }
echo "$(ts) probe_start outage=${OUTAGE}s" >> "$OUT"
docker stop embedinator-backend >/dev/null
echo "$(ts) backend_stopped" >> "$OUT"
sleep "$OUTAGE"
echo "$(ts) docker_start_issued" >> "$OUT"
docker start embedinator-backend >/dev/null
while true; do
  s=$(docker inspect --format '{{.State.Health.Status}}' embedinator-backend 2>/dev/null || echo unknown)
  if [ "$s" = "healthy" ]; then echo "$(ts) backend_healthy" >> "$OUT"; break; fi
  sleep 0.5
done
echo "$(ts) probe_docker_half_done" >> "$OUT"
