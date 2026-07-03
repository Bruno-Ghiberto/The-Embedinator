# BUG-054: Large UI uploads fail at 30-second proxy timeout

- **Severity**: MAJOR
- **Layer**: Infrastructure
- **Discovered**: 2026-06-11T16:22:00Z in Phase 2 (P2-S6)
- **Phase scenario**: P2-S6
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Upload a file > ~10 MB via the UI to any collection.
2. Watch the upload progress; after exactly 30 seconds the upload widget reports an error.
3. Backend log shows a single `http_request` event with `status=400 duration_ms=30028` — no structlog error event, no document or job row created.

## Expected
Large uploads complete successfully; if a size limit is exceeded the error is surfaced cleanly with the correct HTTP status and message, not a proxy timeout masquerading as a 400.

## Actual
The Next.js dev server (or proxy layer in front of FastAPI) enforces a ~30-second request timeout. For large files (observed at 26.1 MB plain text in P2-S6), the upstream ingest handler takes > 30 s to receive and begin processing the multipart body, causing the proxy to abort the connection and return a 400 after exactly 30028 ms. Zero structlog error events are emitted; no document or job row is created; the upload directory (`/data/uploads/f0539bbf.../`) contains only a prior probe file (s6-probe.txt, clean). The UI renders "Internal Server Error" (BUG-050 envelope mismatch masks the real 400 + trace_id) with a retry button that loops indefinitely.

## Artifacts
- Screenshot: screenshots/BUG-054-retry-500.png (gitignored)
- Log excerpt: logs/BUG-054-proxy-timeout.txt (gitignored)
- Trace: null

## Root-cause hypothesis
The Next.js API proxy (or its default 30-second `bodyParser` / response-limit timeout) kills large multipart uploads before the FastAPI handler completes reading the body. FastAPI sees an abrupt connection close, emits a bare `http_request status=400`, but structlog never records an `error` event because the handler never entered structured error handling. The proxy synthesises or propagates the 400 upstream; the UI's throwApiError then further degrades the message (BUG-050).

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Affects files requiring > 30 s to upload through the proxy; threshold is connection-speed-dependent and will be lower on slow links. Cross-evidence: BUG-050 (throwApiError envelope mismatch) causes the UI to render "Internal Server Error" instead of the real 400 + trace_id, compounding the user-visible damage. BUG-040 (UI cap 50 MB vs backend 100 MB) would hide this for most users via client-side rejection before the request is sent, but direct API calls bypass both gates. Discovery trace_id: a9128936-9f4b-4571-9cd6-752b91c28661.

**UPDATE 2026-07-03** (Q-014 exit-checklist incident, no severity change): the same ~30s idle/inactivity timeout also cancels slow CHAT queries, not just uploads. Q-014's first run = 50.2s total with a 34.79s SILENT gap → cancelled at ~30s of inactivity. It is an IDLE timeout, not a total-duration timeout: the retest ran 44.8s total and COMPLETED, because no single silent gap in that run crossed 30s. Source location: NOT configured in `next.config.ts` or `docker-compose.yml` (log-analyst + frontend-inspector both confirmed via grep — see logs/P3-Q014-timeout-source.log) → best-evidence conclusion is a Next.js standalone-server / Node http / undici BUILT-IN default inside the `rewrites()`-based proxy path (exact constant unconfirmed; grep frontend source for the literal `30000`/`30_000` for precision later). This is the SAME underlying layer as the original 30028ms upload-path measurement. Cross-ref BUG-073/074/075 (the chat-path hang chain this idle timeout triggers).
