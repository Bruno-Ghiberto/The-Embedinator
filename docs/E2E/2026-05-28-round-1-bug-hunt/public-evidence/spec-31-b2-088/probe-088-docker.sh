#!/usr/bin/env bash
# BUG-088 live probe — docker half. Usage: probe-088-docker.sh <pause-seconds> <timeline-file>
# Pauses the Ollama container (freezes every in-flight LLM socket), holds, unpauses, stamping each step.
# Run it right after a chat turn has been submitted at :3000 (the orchestrator drives the browser half).
set -euo pipefail
HOLD="${1:-150}"; OUT="${2:-/dev/stdout}"
ts() { date -u +%Y-%m-%dT%H:%M:%S.%3NZ; }
echo "$(ts) probe_start hold=${HOLD}s" >> "$OUT"
docker pause embedinator-ollama >/dev/null
echo "$(ts) ollama_paused" >> "$OUT"
sleep "$HOLD"
docker unpause embedinator-ollama >/dev/null
echo "$(ts) ollama_unpaused" >> "$OUT"
echo "$(ts) probe_docker_half_done" >> "$OUT"
