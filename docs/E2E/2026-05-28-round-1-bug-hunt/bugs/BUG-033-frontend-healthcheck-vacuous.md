# BUG-033: Frontend Docker healthcheck is vacuous — wget --spider exits 0 on 404, confirms only TCP port open

- **Severity**: MINOR
- **Layer**: Infrastructure
- **Discovered**: 2026-06-10T21:46:49Z in Phase 1 (P1-S1)
- **Phase scenario**: P1-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Read the frontend service healthcheck in `docker-compose.yml`
2. Observe: `wget --spider http://127.0.0.1:3000/healthz`
3. Verify: run `wget --spider http://127.0.0.1:3000/any-known-404-path` on a live container — exits 0

## Expected
The frontend healthcheck verifies a known-good endpoint (e.g., `/` or a dedicated `/health` route) and fails when the Next.js app is not serving valid content, providing a meaningful "Healthy" signal to Docker Compose.

## Actual
`wget --spider` exits 0 on any HTTP response including 404; the healthcheck confirms only that TCP port 3000 is open, not that the Next.js app is functional; the "Healthy" status shown by `docker compose ps` is therefore unreliable.

## Artifacts
- Screenshot: null
- Log excerpt: logs/P1-S1-startup-warnings.log (gitignored)
- Trace: null

## Root-cause hypothesis
The healthcheck was written to target `/healthz` which does not exist in the Next.js app (confirmed 404 — separate playbook erratum noted by log-analyst); `wget --spider` does not distinguish 2xx from 4xx responses, so the check passes regardless of whether the app is healthy.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Reporter: log-analyst. Suggested fix: replace with `wget -q -O - http://127.0.0.1:3000/ | grep -q '<html'` or `curl --fail -s http://127.0.0.1:3000/ > /dev/null` to assert a real 200 response with content.
