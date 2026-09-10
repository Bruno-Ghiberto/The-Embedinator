# BUG-054: ~30s proxy idle timeout silently cuts large uploads and cold-start chats

> **FIXED 2026-08-31** by spec-31 Batch 2, tasks 2.1 + 2.2 (unit 1) — commit `8b7d640`. The filed
> root-cause hypothesis **held in part**: the upload half was refuted (uploads were cut by a size
> cap, BUG-040's mechanism, not by a timer), the cold-chat half held and named the timer correctly.
> See [Resolution](#resolution) below.

- **Severity**: CRITICAL
- **Layer**: Infrastructure
- **Discovered**: 2026-06-11T16:22:00Z in Phase 2 (P2-S6)
- **Fixed**: 2026-08-31 (spec-31 tasks 2.1 + 2.2, commit `8b7d640`)
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
- Public evidence: public-evidence/BUG-054-proxy-timeout.txt (tracked)

## Root-cause hypothesis

**⚠ PARTIALLY REFUTED 2026-08-04 — the upload half of this paragraph is wrong.** Uploads were not
cut by a timer; they were truncated by the proxy's 10 MiB `proxyClientMaxBodySize` default, and a
39-second proxied upload completed successfully. The chat half — a real ~30 s socket-inactivity
timer on the proxied request — is correct and is what the 2026-07-03 and 2026-07-28 updates below
established. The text is retained verbatim because it was the filed reasoning; see
[Resolution](#resolution) for the measurement that separates the two halves.

The Next.js API proxy (or its default 30-second `bodyParser` / response-limit timeout) kills large multipart uploads before the FastAPI handler completes reading the body. FastAPI sees an abrupt connection close, emits a bare `http_request status=400`, but structlog never records an `error` event because the handler never entered structured error handling. The proxy synthesises or propagates the 400 upstream; the UI's throwApiError then further degrades the message (BUG-050).

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/137
- **Rationale**: A ~30s idle proxy timeout breaks both documented core flows — large uploads die as a 400 masquerading behind "Internal Server Error" with an infinitely looping retry, and the same layer silently cancels slow chat queries, initiating the BUG-073/074 hang chain.

## Notes
Affects files requiring > 30 s to upload through the proxy; threshold is connection-speed-dependent and will be lower on slow links. Cross-evidence: BUG-050 (throwApiError envelope mismatch) causes the UI to render "Internal Server Error" instead of the real 400 + trace_id, compounding the user-visible damage. BUG-040 (UI cap 50 MB vs backend 100 MB) would hide this for most users via client-side rejection before the request is sent, but direct API calls bypass both gates. Discovery trace_id: a9128936-9f4b-4571-9cd6-752b91c28661.

**UPDATE 2026-07-03** (Q-014 exit-checklist incident, no severity change): the same ~30s idle/inactivity timeout also cancels slow CHAT queries, not just uploads. Q-014's first run = 50.2s total with a 34.79s SILENT gap → cancelled at ~30s of inactivity. It is an IDLE timeout, not a total-duration timeout: the retest ran 44.8s total and COMPLETED, because no single silent gap in that run crossed 30s. Source location: NOT configured in `next.config.ts` or `docker-compose.yml` (log-analyst + frontend-inspector both confirmed via grep — see logs/P3-Q014-timeout-source.log) → best-evidence conclusion is a Next.js standalone-server / Node http / undici BUILT-IN default inside the `rewrites()`-based proxy path (exact constant unconfirmed; grep frontend source for the literal `30000`/`30_000` for precision later). This is the SAME underlying layer as the original 30028ms upload-path measurement. Cross-ref BUG-073/074/075 (the chat-path hang chain this idle timeout triggers).

**UPDATE 2026-07-03 (P4-S4 repro)**: the same ~30s idle timeout cut short the BUG-082 unbounded ambiguous-intent loop (24 consecutive `agent_intent_classified` "ambiguous" cycles, trace `56c94450`, `21:36:34`→`21:37:04`) — confirming this idle-timeout layer also silently terminates a backend-side infinite-loop condition, not just slow-but-progressing queries. Cross-ref BUG-082.

**UPDATE 2026-07-28 (P7-S1 — the timeout is NOT cold-start-scoped; scope materially broadened)**: an initial cold-start-scoped hypothesis was CORRECTED by log-analyst with better evidence. Controlled A/B on the chat path — COLD run (thread `d4303789`, trace `33a1816c`): Ollama cold load 31.88s, intent POST total 33.257s, first silent gap **33.341s**, exceeding the ~30s idle timeout → wedged; 0 further log lines, 0 Ollama calls, 0 new checkpoints, 0 `query_traces` rows, never reached `rewrite_query` or the research loop. WARM run (thread `54606bb9`, trace `1eafcf5d`): first silent gap **2.376s**, intent POST 2.298s → completed normally, 20 checkpoints, `query_traces` 1008→1009. The ONLY difference between wedged and completed was the length of the first silent gap: 33.34s vs 2.38s, straddling the timeout.

**BROADENING — any slow first node triggers this, not just a cold model load**: a later turn wedged at 14:21:42 on a WARM model, first silent gap **49.3s**, cause `agent_classify_intent_failed error=OutputParserException` (see BUG-069), then nothing — no `rewrite_query`, no research, no checkpoint, no trace row. So the trigger is "first node slower than ~30s", of which cold-model load is only one instance.

**PROXY LAYER ISOLATED (team-lead, independent confirmation)**: an identical query issued DIRECT to `:8000`, bypassing the Next.js proxy, completed in 13s — same backend, same corpus. That places the cut at the proxy layer, not in the backend.

**User-facing consequence**: with Ollama `keep_alive` observed at ~5 minutes ("UNTIL 4 minutes from now"), a user's FIRST chat after startup — or any chat after ~5 minutes idle — is silently cut. On a demo or first-run path that is close to the modal case.

**Registrar recommendation on title and severity — Lead decision required.** The registered title ("Large UI uploads fail at 30-second proxy timeout") now understates the finding badly: this is no longer an upload defect. Proposed title (72 chars, within the 80-char schema limit): `~30s proxy idle timeout silently cuts large uploads and cold-start chats`. Layer should remain `Infrastructure` — the defect is genuinely at the proxy layer, now isolated by the direct-to-8000 control. Severity is currently MAJOR; the registrar does not self-adjudicate severity, but records that the first-chat-after-startup path being silently cut is a strong CRITICAL case. Neither title nor severity changed on disk pending the Lead's ruling.

**SEVERITY ESCALATED MAJOR -> CRITICAL AND TITLE REPLACED, 2026-07-28 (team-lead ruling, apply-7).** Title was "Large UI uploads fail at 30-second proxy timeout", which understated a defect that is no longer about uploads; it now reads `~30s proxy idle timeout silently cuts large uploads and cold-start chats` (72 chars, within the 80-char schema limit). Layer stays `Infrastructure` — the direct-to-`:8000` control isolates the cut to the proxy layer. The public issue label requires the corresponding MAJOR -> CRITICAL edit.

**FURTHER BROADENING (frontend-inspector, 2026-07-28)**: the wedge reproduced on a WARM model at turn 4, running **383s with no timeout firing at any layer**. Combined with the earlier warm 49.3s `OutputParserException` gap (BUG-069), this establishes the trigger is not cold-start-specific at all: ANY slow first node trips it, and at least two independent causes are now evidenced — cold model load, and accumulated-history classifier degradation. Escalation basis: the first chat after startup, or after ~5 minutes idle (Ollama `keep_alive` ~5min), is silently cut with no error — close to the modal first-run path on a demo.

## Resolution

**FIXED** — spec-31 Batch 2, tasks 2.1 and 2.2 (unit 1). Commit `8b7d640`, 9 files, +529/−29,
shared with BUG-040 and BUG-074's Branch T.

**The filed hypothesis held in part, and the record's two halves turned out to have two different
mechanisms.**

*The upload half was refuted* on 2026-08-04, before this fix, by a three-arm measurement on the
live Docker stack: 12.6 MB through the proxy failed at 63.5 s; the same file direct to `:8000`
returned 202 at 41.0 s; **8.0 MB through the proxy returned 202 at 39.0 s**. A 39-second proxied
request completing is incompatible with a ~30 s cut on the upload path. Uploads were being
truncated by Next's `proxyClientMaxBodySize` 10 MiB default — BUG-040's mechanism, a size cap, not
a timer. The original `30028 ms` was how long a 26.1 MB transfer ran before reaching that cap.

*The cold-chat half held*, and the 2026-07-28 broadening ("any first node slower than ~30 s trips
it") was the accurate reading. `experimental.proxyTimeout` is real: a socket-**inactivity** timer
on the proxied request, default 30 000 ms. It only accepts a finite number — `0` falls back to
30000 and `null` is stripped by the config merge — so it can be raised but not disabled. An upload
keeps bytes flowing and can never go idle; a chat waiting for a cold model's first frame sends
nothing on the wire and does. That is why the same layer cut one and not the other.

**What changed.** `frontend/next.config.ts` now sets `experimental.proxyTimeout: 600_000` and
`experimental.proxyClientMaxBodySize: 104_857_600`. Both keys were required — one per half of this
record. No mechanism was added: these are two configuration values on a proxy that already
existed, and the only new mechanism in the same commit is BUG-074's client watchdog, justified in
that record.

**Evidence.**

- Static regression, `frontend/tests/unit/next-config.test.ts`: imports `next.config.ts` (never
  regexes it) and asserts `proxyClientMaxBodySize === 104_857_600` exactly, `proxyTimeout` finite
  and ≥ 300 000 ms, and `STREAM_IDLE_TIMEOUT_MS` strictly inside the proxy window. Necessary, not
  sufficient — it pins the values, it cannot demonstrate the timer.
- Frontend suite after unit 1: **96 passed** (74 before).
- Live stack, GC-2 proxy half — a chat through `:3000` with a forced **51.110 s** silent gap
  (`docker pause embedinator-backend` mid-turn) reached `done` at **55.778 s** on the new
  configuration; the 30 s default provably cut this:
  [`../public-evidence/spec-31-b2-gc2/pause-gap.log`](../public-evidence/spec-31-b2-gc2/pause-gap.log)
  and `pause-gap.ndjson`.
- Live stack, cold retest on the same configuration — model unloaded, first chat at `:3000`, max
  gap 6.833 s, `done` at 11.999 s, and the baked config verified inside the image
  (`"proxyTimeout":600000`, `"proxyClientMaxBodySize":104857600`):
  [`../public-evidence/spec-31-b2-gc2/cold-retest.txt`](../public-evidence/spec-31-b2-gc2/cold-retest.txt).

**Still open / follow-ups.**

- The three caps agree only by literal duplication (`frontend/lib/types.ts`,
  `frontend/next.config.ts`, `backend/config.py`); raising one alone reopens BUG-040.
- `proxyClientMaxBodySize` counts the raw multipart envelope while the UI and the backend count the
  file, so a file within a few hundred bytes of 100 MiB passes the client guard and is truncated by
  the proxy.
- `proxyTimeout` is inactivity-based, so an upload that stalls upstream now waits up to 600 s for
  the proxy's 500 instead of 30 s. Chat is bounded by the 120 s client watchdog (BUG-074) and, from
  unit 4, by the backend's 90 s in-flight LLM deadline (BUG-088).
- Only the standalone/Docker path exhibits this timer — `next dev` applies no idle cut — so a green
  `tests/e2e_real` run is not evidence for this record; the live stack is.
