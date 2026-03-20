# A2 — Frontend Architect: API Routing Fix

## Role & Mission

You are the frontend architect responsible for fixing the critical `NEXT_PUBLIC_API_URL` build-time baking bug by implementing Next.js server-side rewrites, adding a frontend health endpoint, and creating a root route redirect.

## FR Ownership

FR-026, FR-027, FR-028, FR-029, FR-030, FR-031

## Task Ownership

T022 through T026 (Phase 3: Frontend API Routing)

### Tasks

- **T022** [P]: Modify `frontend/next.config.ts`: remove the `env: { NEXT_PUBLIC_API_URL: ... }` block. Add `async rewrites()` returning `[{ source: "/api/:path*", destination: "${process.env.BACKEND_URL || "http://localhost:8000"}/api/:path*" }]` (FR-027)
- **T023** [P]: Modify `frontend/lib/api.ts`: change `API_BASE` from `process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"` to `process.env.NEXT_PUBLIC_API_URL || ""` (empty string for relative paths) (FR-028). Keep the `NEXT_PUBLIC_API_URL` override for advanced deployment scenarios.
- **T024** [P]: Create `frontend/app/healthz/route.ts`: Next.js App Router route handler returning `NextResponse.json({ status: "ok" })` with HTTP 200 (FR-029). Path MUST be `/healthz` (not `/api/health`) to avoid the rewrite rule.
- **T025** [P]: Create `frontend/app/page.tsx`: server component that calls `redirect("/chat")` from `next/navigation` (FR-031). This provides a root route that redirects to the primary chat interface.
- **T026**: Verify frontend builds and all 53 tests pass: `cd frontend && npm run build && npm run test`. Verify rewrites are configured.

## Files to CREATE

| File | Purpose |
|------|---------|
| `frontend/app/healthz/route.ts` | Frontend health endpoint for Docker HEALTHCHECK |
| `frontend/app/page.tsx` | Root route redirect to /chat |

## Files to MODIFY

| File | Changes |
|------|---------|
| `frontend/next.config.ts` | Remove `env` block, add `async rewrites()` proxying `/api/:path*` to `BACKEND_URL` |
| `frontend/lib/api.ts` | Change `API_BASE` to empty string (relative paths). Keep `NEXT_PUBLIC_API_URL` as optional override. |

## Files NEVER to Touch

- `Makefile` — SC-010
- `frontend/package.json` — no new npm packages
- Any `tests/**` files
- Any file owned by A1 or A3 (see 19-implement.md file touch matrix)
- `frontend/app/layout.tsx` — owned by A5 in Wave 2
- `frontend/components/SidebarLayout.tsx` — owned by A5 in Wave 2

## Must-Read Documents (in order)

1. This file (read first)
2. `Docs/DESIGN-019-CROSS-PLATFORM-DX.md` — Section 5 (Frontend API Routing)
3. `specs/019-cross-platform-dx/spec.md` — FR-026 through FR-031
4. `specs/019-cross-platform-dx/tasks.md` — T022 through T026
5. `Docs/PROMPTS/spec-19-cross-platform/19-implement.md` — stale patterns, risk gotchas

## Key Gotchas

1. **NDJSON streaming through rewrites** — Next.js rewrites operate at HTTP level and should NOT buffer. The chat endpoint streams NDJSON. Verify streaming still works after adding rewrites. If streaming breaks, the fallback is keeping `NEXT_PUBLIC_API_URL` as an environment variable that bypasses rewrites for the streaming endpoint.
2. **Frontend test mocks** — After changing `API_BASE` to empty string, existing frontend tests that mock API calls may need their mock URLs updated. You MUST verify all 53 frontend tests pass after the change. Read the existing test file to understand how API calls are mocked before making changes.
3. **No new packages** — The spec explicitly forbids new npm packages. All changes use existing dependencies.
4. **`/healthz` not `/api/health`** — The frontend health endpoint MUST be at `/healthz` to avoid being caught by the `/api/:path*` rewrite rule.
5. **`rewrites()` must be async** — Next.js expects `async rewrites()` in the config.
6. **Keep `NEXT_PUBLIC_API_URL` override** — The empty string default means relative paths. But keep the `process.env.NEXT_PUBLIC_API_URL` check so advanced deployments can still set it.

## Verification Commands

```bash
# Frontend builds
cd frontend && npm run build && echo "PASS: frontend build" || echo "FAIL"

# Frontend tests pass (all 53)
cd frontend && npm run test && echo "PASS: frontend tests" || echo "FAIL"

# Rewrites configured
grep -q 'rewrites' frontend/next.config.ts && echo "PASS: rewrites present" || echo "FAIL"
grep -q 'BACKEND_URL' frontend/next.config.ts && echo "PASS: BACKEND_URL in config" || echo "FAIL"

# API_BASE changed
grep -q '|| ""' frontend/lib/api.ts && echo "PASS: empty API_BASE" || echo "FAIL"

# New files exist
test -f frontend/app/healthz/route.ts && echo "PASS: healthz exists" || echo "FAIL"
test -f frontend/app/page.tsx && echo "PASS: root redirect exists" || echo "FAIL"

# No NEXT_PUBLIC_API_URL baking in next.config.ts
! grep -q 'env:.*NEXT_PUBLIC_API_URL' frontend/next.config.ts && echo "PASS: no env baking" || echo "FAIL"
```

## Task Completion

After completing each task, mark it as `[X]` in `specs/019-cross-platform-dx/tasks.md`.
