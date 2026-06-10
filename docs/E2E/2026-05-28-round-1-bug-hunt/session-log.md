# Session Log — Spec-30 Round 1 Bug Hunt

**Session opened**: 2026-06-02T00:00:00Z
**Pilot**: Bruno Ghiberto
**Branch**: 030-e2e-test-v3
**develop HEAD at session start**: 3d8d5ff5465aade8aae92b81cfb1ff604ed31d5e
**spec/plan/playbook SHAs**: 09f5e403a9c352bda4d5ffb42ea8040b930d12b5
**Next free BUG ID**: BUG-024

---

[2026-06-02 00:00:00] Orchestrator | phase-transition | Phase 0 opened
[2026-06-02 00:00:01] Orchestrator | phase-transition | Phase 0 closed — session directory scaffolded, next-bug-id.txt=BUG-024, status: phase-0-complete

<!-- Placeholder rows for phases 1–8 — filled in by sdd-apply-1 through sdd-apply-8 -->

[2026-06-10T17:46:50-03:00] Orchestrator | phase-transition | Phase 1 (Cold Start) opened
[2026-06-10T18:41:36-03:00] Pilot | observation | P1.S1 — stack brought down and up (DEVIATION: `docker compose down` run WITHOUT `-v`; playbook specifies `down -v` — volumes preserved, warm-volume cold start). All 4 services healthy: qdrant 10.4s, ollama 15.9s, backend 26.4s, frontend 26.6s (started→healthy per docker ps); total ~27s, within 30s/service and 90s/total budget. Relayed by Lead from raw terminal output.
[2026-06-10T18:43:55-03:00] FrontendInspector | finding | P1.S1/S2 capture complete — LCP 248ms (PASS, budget 2000ms); 4 candidate findings pending correlation: (A) React hydration error #418 on every cold load [MAJOR-suggested]; (B) /api/health reports nomic-embed-text=false yet overall status "healthy" + UI shows only "Backend connected" — silent health-lie [CRITICAL-suggested]; (C) no per-service health badges exist, P1-S3 as written untestable [MAJOR-suggested]; (D) favicon.ico 404 [COSMETIC-suggested]; plus a11y form-field-without-id [MINOR-suggested]. Screenshot: screenshots/P1-S2-dashboard-first-paint.png. Registration deferred until log-analyst correlation returns.
[2026-06-10T18:46:49-03:00] LogAnalyst | finding | P1.S1 startup sweep — ERROR=0, 5 warning signals; nomic-embed-text IS installed (ollama /api/tags: nomic-embed-text:latest 261MB) → /api/health false flag is a tag-suffix string-match bug, refutes CRITICAL premise of inspector finding B; SC-005 idle memory 610.8MiB>600MB budget; 6 LangGraph RunnableConfig UserWarnings; HF Hub unauth warning; 22 stale qdrant collections from preserved volumes (WAL replay clean, expected — Phase 2 entry context). ERRATUM (log-only, no bug file): playbook P1-S2 says `curl localhost:8000/healthz` but real endpoint is /api/health (/healthz is 404) — playbook doc error, not a runtime defect. Log excerpt: logs/P1-S1-startup-warnings.log.
[2026-06-10T18:47:30-03:00] BugRegistrar | discovery | Phase 1 registration complete — BUG-024 (MAJOR/Frontend), BUG-025 (MINOR/Backend), BUG-026 (MAJOR/Backend), BUG-027 (MAJOR/Frontend), BUG-028 (COSMETIC/Frontend), BUG-029 (MINOR/Frontend), BUG-030 (MINOR/Backend), BUG-031 (MINOR/Backend), BUG-032 (COSMETIC/Backend), BUG-033 (MINOR/Infrastructure); 10 bugs registered; next-bug-id.txt=BUG-034
[2026-06-10T19:07:53-03:00] Pilot | observation | P1.S3 starting — pausing qdrant
[2026-06-10T19:10:48-03:00] Pilot | observation | P1.S3 — yellow banner "Vector database is starting up." appeared on dashboard during qdrant pause (screenshot taken 19:09:58). UI reacts to qdrant unavailability, but message wording is misleading: qdrant is paused/unreachable, not starting up. Collection list still rendered (cached). Model selector shows qwen2.5:7b.
[2026-06-10T19:11:36-03:00] FrontendInspector | finding | P1.S3 timeline captured at 3s resolution — qdrant pause produced 19 consecutive /api/health 503s (reqid 166-184). Three candidate findings pending log-analyst correlation: (E) silent health-lie window — banner showed "Backend connected" for ~6-9s while /api/health returned 503/degraded/qdrant-Unreachable [CRITICAL-suggested, playbook P1-S3 discovery criterion met]; (F) degradation message says "Vector database is starting up." while actual backend state is "Qdrant circuit breaker is open" — false reassurance [MAJOR-suggested]; (G) banner CSS identical for healthy and degraded states — no color/icon/visual differentiation, text-only signal [MAJOR-suggested]. Recovery clean: health 200 at ~18s post-unpause, banner recovered within one ~3s polling cycle, no stuck state.
[2026-06-10T19:12:14-03:00] Pilot | observation | P1.S3 — completed; qdrant unpaused, stack back up (recovery confirmed clean by inspector: health 200 + banner restored within one polling cycle). Relayed by Lead.
[2026-06-10T19:13:34-03:00] LogAnalyst | finding | P1.S3 backend correlation — pause ~22:08:43Z; health endpoint HUNG ~18s (no per-probe sub-timeout, curl 4s timeouts at 22:08:47/22:08:56); CB tripped 22:08:58 (circuit_qdrant_opened failure_count=5); fast 503 "degraded"+"circuit breaker is open" 22:09:01→22:10:01; half-open 22:10:03 on-demand; recovery ≤5s post-unpause. CB open total 65s vs 30s Constitution cooldown (medium confidence — config check pending). POSITIVE: after CB trip backend returns correct 503 + degraded body, no false-healthy. Inspector finding G (no visual differentiation) CONTRADICTED by Pilot screenshot (yellow banner + clock icon) — returned to inspector for re-verification. Excerpts: logs/P1-S3-health-poll.log, logs/P1-S3-backend-circuit-breaker.log.
[2026-06-10T19:14:10-03:00] BugRegistrar | discovery | P1.S3 registration complete — BUG-034 (CRITICAL/Frontend), BUG-035 (MAJOR/Backend), BUG-036 (MAJOR/Frontend); 3 bugs registered; next-bug-id.txt=BUG-037; 2 candidates pending (G visual-differentiation re-verification; CB cooldown 65s config check)
[2026-06-10T19:15:35-03:00] Orchestrator | finding | Two P1.S3 candidates DISMISSED with evidence: (1) CB cooldown 65s-vs-30s — NOT a bug; backend/config.py:88 sets circuit_breaker_cooldown_secs=60 as deliberate spec-26 FR-009 override of Constitution 30s with documented rationale; observed 65s = 60s cooldown + ~5s on-demand half-open trigger (qdrant_client.py:38-49, no periodic probe by design). Residual: Constitution §Reliability vs spec-26 doc inconsistency — note only, no bug file. (2) qwen2.5:7b missing-model risk — NOT a bug; ollama /api/tags confirms qwen2.5:7b installed (11 models total incl. qwen3:14b, nomic-embed-text:latest). Phase 3 entry risk cleared.
[2026-06-10T19:16:18-03:00] FrontendInspector | finding | Finding G (no visual differentiation) RETRACTED — inspector's CSS comparison read the outer container className only; color/icon switching lives in inline style props (StatusBanner.tsx:54-73, color-mix amber + Clock icon for degraded). Pilot screenshot evidence confirmed real differentiation. NOT registered. Source review yielded: BUG-036 root cause source-confirmed (StatusBanner.tsx:18 returns "Vector database is starting up." for ALL qdrant error states); BUG-034 root cause source-confirmed (delay upstream in BackendStatusProvider polling cadence, banner reacts immediately to provider state); one new residual a11y candidate (aria-live polite) registered separately.
[2026-06-10T19:16:50-03:00] BugRegistrar | discovery | P1.S3 follow-up registration — BUG-037 (MINOR/Frontend); BUG-034 + BUG-036 Notes enriched with source-confirmed root causes; next-bug-id.txt=BUG-038
[2026-06-10T19:19:15-03:00] Pilot | observation | P1.S4 — `docker compose restart backend` executed (~19:19:05 local); docker ps at +6s shows backend "health: starting", all other services unaffected. Relayed by Lead from raw terminal output.
[2026-06-10T19:20:50-03:00] FrontendInspector | finding | P1.S4 timeline at 2s resolution — backend restart window ~4s; Next.js /api/health proxy returned HTTP 500 (null body) ×2 polls; banner stayed "Backend connected" with ready-state primary tint THROUGHOUT (zero visual/textual change); backend healthy again at t+6s (≤15s budget PASS on raw health). Candidate finding (H) pending log-analyst correlation: HTTP 5xx with unparseable body produces NO provider state change — BackendStatusProvider transitions only on fetch throws ("unreachable") or parsed qdrant-error JSON ("degraded"); raw HTTP error codes are a blind spot [MAJOR-suggested, BUG-034 variant, same root family]. Console: 2× "Failed to load resource: 500". No network-level errors (proxy kept connection alive).
[2026-06-10T19:22:22-03:00] LogAnalyst | finding | P1.S4 backend restart correlation — SIGTERM graceful (exit 143, in-flight flushed); down period 22:18:51→22:19:00Z (~10.04s log-measured shutdown→startup-complete; 12s observed at 3s poll granularity); cross-encoder reranker load = 8.65s of the restart (dominant cost, reloaded from disk every restart); first 200 at 22:19:03. BUDGET ≤15s: BORDERLINE PASS (~2.2s headroom). NO new signals — all restart warnings identical to cold-start set (BUG-030/031/032 re-fired as expected). NOTE (log-only, no bug): 15s restart budget has no safety buffer — cold page cache or slower disk would blow it. Direct :8000 clients see connection-refused during the window; browser at :3000 sees HTTP 500 via the live Next.js proxy — reconciles inspector and analyst views.
[2026-06-10T19:22:55-03:00] BugRegistrar | discovery | P1.S4 registration complete — BUG-038 (MAJOR/Frontend); next-bug-id.txt=BUG-039
[2026-06-10T19:30:59-03:00] Pilot | observation | P1 closing — 15 findings registered, dashboard healthy, banner "Backend connected"
[2026-06-10T19:30:59-03:00] Orchestrator | phase-transition | Phase 1 closed → Phase 2 ready. 15 findings registered: BUG-024 (MAJOR), BUG-025 (MINOR), BUG-026 (MAJOR), BUG-027 (MAJOR), BUG-028 (COSMETIC), BUG-029 (MINOR), BUG-030 (MINOR), BUG-031 (MINOR), BUG-032 (COSMETIC), BUG-033 (MINOR), BUG-034 (CRITICAL), BUG-035 (MAJOR), BUG-036 (MAJOR), BUG-037 (MINOR), BUG-038 (MAJOR). Scenarios 4/4 exercised; 2 candidates dismissed with evidence; 1 finding retracted; 2 playbook errata logged.
<!-- [YYYY-MM-DD HH:MM:SS] Orchestrator | phase-transition | Phase 1 (Cold Start) opened -->
<!-- [YYYY-MM-DD HH:MM:SS] Orchestrator | phase-transition | Phase 1 closed | scenarios: N | bugs: [IDs] -->

<!-- [YYYY-MM-DD HH:MM:SS] Orchestrator | phase-transition | Phase 2 (Ingestion) opened -->
<!-- [YYYY-MM-DD HH:MM:SS] Orchestrator | phase-transition | Phase 2 closed | scenarios: N | bugs: [IDs] -->

<!-- [YYYY-MM-DD HH:MM:SS] Orchestrator | phase-transition | Phase 3 (Chat Happy Path) opened -->
<!-- [YYYY-MM-DD HH:MM:SS] Orchestrator | phase-transition | Phase 3 closed | scenarios: N | bugs: [IDs] -->

<!-- [YYYY-MM-DD HH:MM:SS] Orchestrator | phase-transition | Phase 4 (Chat Edge Cases) opened -->
<!-- [YYYY-MM-DD HH:MM:SS] Orchestrator | phase-transition | Phase 4 closed | scenarios: N | bugs: [IDs] -->

<!-- [YYYY-MM-DD HH:MM:SS] Orchestrator | phase-transition | Phase 5 (Settings & Providers) opened -->
<!-- [YYYY-MM-DD HH:MM:SS] Orchestrator | phase-transition | Phase 5 closed | scenarios: N | bugs: [IDs] -->

<!-- [YYYY-MM-DD HH:MM:SS] Orchestrator | phase-transition | Phase 6 (Observability) opened -->
<!-- [YYYY-MM-DD HH:MM:SS] Orchestrator | phase-transition | Phase 6 closed | scenarios: N | bugs: [IDs] -->

<!-- [YYYY-MM-DD HH:MM:SS] Orchestrator | phase-transition | Phase 7 (Recovery & State) opened -->
<!-- [YYYY-MM-DD HH:MM:SS] Orchestrator | phase-transition | Phase 7 closed | scenarios: N | bugs: [IDs] -->

<!-- [YYYY-MM-DD HH:MM:SS] Orchestrator | phase-transition | Phase 8 (Closure) opened -->
<!-- [YYYY-MM-DD HH:MM:SS] Orchestrator | closure-step | Hunt closed. <severity counts>. Registry frozen. -->
