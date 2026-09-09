#!/usr/bin/env bash
# BUG-123 exit-gate probe — docker half. Usage: probe-123-docker.sh <hold-seconds> <timeline-file>
# Kills the backend mid-stream (SIGKILL bypasses `restart: unless-stopped`), holds the outage,
# starts it again, and stamps the moment the container reports healthy.
# The browser half (client watchdog bubble via Playwright MCP) is driven against these stamps.
set -euo pipefail
HOLD="${1:-200}"; OUT="${2:-/dev/stdout}"
ts() { date -u +%Y-%m-%dT%H:%M:%S.%3NZ; }
echo "$(ts) probe_start hold=${HOLD}s" >> "$OUT"
docker kill embedinator-backend >/dev/null
echo "$(ts) backend_killed" >> "$OUT"
sleep "$HOLD"
echo "$(ts) docker_start_issued" >> "$OUT"
docker start embedinator-backend >/dev/null
echo "$(ts) backend_started" >> "$OUT"
while true; do
  s=$(docker inspect --format '{{.State.Health.Status}}' embedinator-backend 2>/dev/null || echo unknown)
  if [ "$s" = "healthy" ]; then echo "$(ts) backend_healthy" >> "$OUT"; break; fi
  sleep 0.5
done
echo "$(ts) probe_docker_half_done" >> "$OUT"
