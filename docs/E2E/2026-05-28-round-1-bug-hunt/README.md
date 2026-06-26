# E2E Bug Hunt — Round 1

> A structured, full-stack end-to-end test pass against the running product.
> The goal was not to prove the system works — it was to find every way it
> *doesn't*, document each defect reproducibly, and triage it by severity.
> **40 findings** across **5 layers** came out of a single round.

This directory is the public record of that hunt. It is here on purpose: shipping
real software means finding, documenting, and prioritising defects with discipline
— not hiding them behind a green badge.

## Method

The hunt followed a spec-driven test plan ([`specs/`](../../../specs/)) executed as a
live, human-in-the-loop session. The running stack (Qdrant + Ollama + FastAPI
backend + Next.js frontend) was exercised end to end, one user-journey phase at a
time:

| Phase | Journey under test |
|-------|--------------------|
| P1 | App startup & health surface |
| P2 | Document ingestion pipeline |
| P3 | Chat happy path (retrieval → answer → citations) |
| … | Error handling, observability, performance budgets |

Every observation that reproduced was written up as a single `BUG-NNN` file with a
fixed schema:

- **Severity / Layer / Phase** — classification for triage
- **Steps to Reproduce** — deterministic, copy-pasteable
- **Expected vs. Actual** — the contract that was violated
- **Root-cause hypothesis** — a first technical theory, not just a symptom
- **Artifacts** — screenshot / log / trace references

Raw artifacts (`logs/`, `screenshots/`, `traces/`) are gitignored per the test
spec; the findings, the session log, and the triage are committed.

## Findings at a glance

| Severity | Count |
|----------|-------|
| 🔴 Blocker | 1 |
| 🔴 Critical | 2 |
| 🟠 Major | 15 |
| 🟡 Minor | 18 |
| ⚪ Cosmetic | 4 |
| **Total** | **40** |

| Layer | Count |
|-------|-------|
| Frontend | 18 |
| Backend | 14 |
| Ingestion | 4 |
| Observability | 2 |
| Infrastructure | 2 |

A recurring theme worth calling out: several of the highest-severity findings are
**honesty-of-state bugs** — the UI reporting "Backend connected" while `/api/health`
returns 503 (BUG-034), health staying green while a model flag is false (BUG-026),
a backend restart being invisible to the UI (BUG-038). Surfacing those is exactly
the kind of defect a single-shot "does it load?" check never catches.

## All findings (by severity)

| Severity | ID | Layer | Title |
|----------|----|-------|-------|
| 🔴 BLOCKER | [BUG-045](bugs/BUG-045-pep563-union-annotation-breaks-langgraph-config-injection.md) | Backend | PEP 563 union annotation breaks LangGraph config injection |
| 🔴 CRITICAL | [BUG-034](bugs/BUG-034-health-banner-silent-lie-during-503.md) | Frontend | Silent health-lie window — banner shows "Backend connected" while /api/health returns 503/degraded |
| 🔴 CRITICAL | [BUG-052](bugs/BUG-052-non-atomic-re-upload-cascade-deletes-vectors-before-ingest.md) | Ingestion | Non-atomic re-upload deletes old vectors before ingest succeeds |
| 🟠 MAJOR | [BUG-024](bugs/BUG-024-react-hydration-error-418.md) | Frontend | React hydration error #418 on every cold-start first load |
| 🟠 MAJOR | [BUG-026](bugs/BUG-026-health-silent-lie-model-flag.md) | Backend | Overall health stays "healthy" and UI shows "Backend connected" while a model flag is false |
| 🟠 MAJOR | [BUG-027](bugs/BUG-027-no-per-service-health-badges.md) | Frontend | No per-service health badges on dashboard — single coarse "Backend connected" banner only |
| 🟠 MAJOR | [BUG-035](bugs/BUG-035-health-endpoint-hang-18s-no-probe-timeout.md) | Backend | Health endpoint hangs ~18s when qdrant TCP stalls — no per-service probe sub-timeout |
| 🟠 MAJOR | [BUG-036](bugs/BUG-036-degradation-message-misleading-cb-open.md) | Frontend | Misleading degradation message — "Vector database is starting up." shown while backend reports "Qdrant circuit breaker is open" |
| 🟠 MAJOR | [BUG-038](bugs/BUG-038-backend-restart-invisible-ui-5xx-no-state-change.md) | Frontend | Backend restart invisible to UI — HTTP 5xx with unparseable body produces no banner state change |
| 🟠 MAJOR | [BUG-040](bugs/BUG-040-upload-cap-drift-ui-50mb-backend-100mb.md) | Frontend | Upload cap drift — UI hardcodes 50 MB, backend enforces 100 MB |
| 🟠 MAJOR | [BUG-041](bugs/BUG-041-ingestion-status-states-spec-mismatch.md) | Ingestion | Ingestion status state machine — spec states do not exist in implementation |
| 🟠 MAJOR | [BUG-046](bugs/BUG-046-health-surface-blind-to-agent-graph-execution.md) | Observability | Health surface blind to agent-graph execution path |
| 🟠 MAJOR | [BUG-047](bugs/BUG-047-frontend-default-llm-hardcoded-not-synced.md) | Frontend | Frontend DEFAULT_LLM hardcoded — never synced with backend settings |
| 🟠 MAJOR | [BUG-050](bugs/BUG-050-throwapierror-misses-fastapi-detail-envelope.md) | Frontend | throwApiError misses FastAPI detail envelope; error messages lost |
| 🟠 MAJOR | [BUG-054](bugs/BUG-054-large-ui-uploads-fail-30s-proxy-timeout.md) | Infrastructure | Large UI uploads fail at 30-second proxy timeout |
| 🟠 MAJOR | [BUG-055](bugs/BUG-055-warm-factoid-chat-latency-65pct-over-spec26-p50.md) | Backend | Warm factoid chat latency 32.2s exceeds spec-26 19.5s p50 by 65% |
| 🟠 MAJOR | [BUG-061](bugs/BUG-061-citation-click-dead-ends-empty-collection-no-source-passage-view.md) | Frontend | Citation click dead-ends on empty collection page; no source-passage view |
| 🟠 MAJOR | [BUG-062](bugs/BUG-062-citation-relevance-score-raw-crossencoder-logit-400-700pct.md) | Backend | Citation relevance_score emits raw CrossEncoder logit; bar shows 400-700% |
| 🟡 MINOR | [BUG-025](bugs/BUG-025-health-nomic-embed-tag-mismatch.md) | Backend | /api/health reports nomic-embed-text=false despite model being installed — tag-suffix mismatch |
| 🟡 MINOR | [BUG-029](bugs/BUG-029-form-field-missing-id.md) | Frontend | Form field element missing id and name attributes — a11y violation |
| 🟡 MINOR | [BUG-030](bugs/BUG-030-idle-memory-exceeds-budget.md) | Backend | Backend idle RSS 610.8 MiB exceeds SC-005 600 MB budget — warning fires on every cold start |
| 🟡 MINOR | [BUG-031](bugs/BUG-031-langgraph-runnableconfig-warnings.md) | Backend | LangGraph RunnableConfig type-annotation UserWarnings ×6 on every cold start |
| 🟡 MINOR | [BUG-033](bugs/BUG-033-frontend-healthcheck-vacuous.md) | Infrastructure | Frontend Docker healthcheck is vacuous — wget --spider exits 0 on 404, confirms only TCP port open |
| 🟡 MINOR | [BUG-037](bugs/BUG-037-status-banner-aria-live-polite-for-degradation.md) | Frontend | Health-degradation banner uses aria-live="polite" — screen readers defer degradation announcements |
| 🟡 MINOR | [BUG-039](bugs/BUG-039-orphaned-qdrant-collections-no-gc.md) | Backend | Orphaned Qdrant collections — no cross-store atomicity, no GC |
| 🟡 MINOR | [BUG-042](bugs/BUG-042-breadcrumb-raw-uuid-dead-documents-link.md) | Frontend | Header breadcrumb renders raw UUID + dead /documents link |
| 🟡 MINOR | [BUG-043](bugs/BUG-043-stats-endpoint-missing-404.md) | Backend | /api/collections/{id}/stats endpoint does not exist (playbook cites it) |
| 🟡 MINOR | [BUG-044](bugs/BUG-044-ingestion-jobs-finished-at-null.md) | Ingestion | ingestion_jobs.finished_at never written — NULL on all completed jobs |
| 🟡 MINOR | [BUG-048](bugs/BUG-048-ndjson-error-trace-id-not-surfaced-in-ui.md) | Frontend | NDJSON error trace_id never surfaced in UI |
| 🟡 MINOR | [BUG-049](bugs/BUG-049-raw-worker-stderr-passthrough-user-error-message.md) | Ingestion | Raw worker stderr + exit code passed unsanitized to user-facing error message |
| 🟡 MINOR | [BUG-051](bugs/BUG-051-try-again-offered-for-deterministic-errors.md) | Frontend | Retry offered unconditionally for deterministic upload errors |
| 🟡 MINOR | [BUG-056](bugs/BUG-056-output-parser-exception-rewrite-query-adds-fallback-latency.md) | Backend | OutputParserException x2 on rewrite_query node adds ~4.3s via fallback |
| 🟡 MINOR | [BUG-057](bugs/BUG-057-ranking-stage-timing-zero-despite-reranker-running.md) | Observability | ranking stage timing reports 0.0ms despite reranker executing |
| 🟡 MINOR | [BUG-058](bugs/BUG-058-sidebar-duplicate-and-orphan-conversations.md) | Frontend | Sidebar lists duplicate-title and empty 'New Chat' orphan conversations |
| 🟡 MINOR | [BUG-060](bugs/BUG-060-citation-chip-non-semantic-not-focusable-link.md) | Frontend | Citation [1] chip is non-semantic StyledText, not a focusable link |
| 🟡 MINOR | [BUG-063](bugs/BUG-063-get-api-documents-200-empty-unknown-collection-not-404.md) | Backend | GET /api/documents returns 200 empty for unknown collection_id, not 404 |
| ⚪ COSMETIC | [BUG-028](bugs/BUG-028-favicon-ico-404.md) | Frontend | favicon.ico returns 404 — console/network error on every page load |
| ⚪ COSMETIC | [BUG-032](bugs/BUG-032-hf-hub-unauth-warning-reranker.md) | Backend | HuggingFace Hub unauthenticated-request warning on reranker load each cold start |
| ⚪ COSMETIC | [BUG-053](bugs/BUG-053-spec08-fr011-duplicate-response-contract-mismatch.md) | Backend | spec-08 FR-011 duplicate-response contract mismatch |
| ⚪ COSMETIC | [BUG-059](bugs/BUG-059-orphaned-period-glyph-below-citation-chip.md) | Frontend | Orphaned '.' glyph rendered below [1] citation chip |

## Related

- [`session-log.md`](session-log.md) — the running log of the hunt session
- [`specs/`](../../../specs/) — the specifications the product was tested against
- [Engineering Process](../../../README.md#engineering-process) — how this fits the overall workflow
