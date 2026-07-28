# Triage — Round 1 Bug Hunt (spec-30)

**Registry**: 106 records, `BUG-024`–`BUG-129`, contiguous.
**Frozen**: 2026-07-28, branch `030-e2e-test-v3`. Zero production files changed during the hunt.
**Purpose**: this is the working input to the spec-31 fix wave.

Every `BLOCKER` / `CRITICAL` / `MAJOR` record carries a triage decision, a rationale, and a live
GitHub issue. `MINOR` and `COSMETIC` records are registered and searchable but are not triaged
here — they are backlog, not sprint scope.

---

## 1. Severity census

| Severity | Count | Triaged |
|---|---:|---|
| BLOCKER | 1 | yes |
| CRITICAL | 11 | yes |
| MAJOR | 43 | yes |
| MINOR | 45 | no — backlog |
| COSMETIC | 6 | no — backlog |
| **Total** | **106** | **55 triaged (MAJOR+)** |

## 2. Distribution

| Layer | Findings | | Phase | Findings |
|---|---:|---|---|---:|
| Backend | 48 | | P1 Cold Start | 15 |
| Frontend | 40 | | P2 Ingestion | 16 |
| Ingestion | 6 | | P3 Chat Happy Path | 22 |
| Reasoning | 4 | | P4 Chat Edge Cases | 12 |
| Infrastructure | 3 | | P5 Settings & Providers | 13 |
| Observability | 3 | | P6 Observability | 16 |
| Retrieval | 2 | | P7 Recovery & State | 12 |

## 3. The split

**39 `v1.0-fix` · 16 `v1.1-defer`** across the 55 triaged records.
All 55 have live GitHub issues, `#123`–`#177`, verified 1:1 against the registry — 55 distinct
issue numbers, no duplicates, no gaps, each issue's severity and decision labels matching its
record.

One of the 39 — `BUG-045`, the hunt's only BLOCKER — was **already fixed on `develop` during the
hunt** (PR #101, commit `d9107cb`); its issue was filed and closed the same day. It is retained at
BLOCKER severity because severity grades impact at discovery, not remediation state. **Outstanding
v1.0-fix scope is therefore 38 records.**

---

## 4. `v1.0-fix` scope, by layer, ordered by blast radius

Ordering within each layer is by blast radius — how much of the system the defect reaches and how
many other findings it subsumes or unblocks — not by ID. Fixing top-down means later items
frequently shrink or disappear.

### 4.1 Backend — 15 items (1 BLOCKER, 7 CRITICAL, 7 MAJOR)

| # | ID | Sev | Statement | Issue |
|---|---|---|---|---|
| 1 | BUG-045 | BLOCKER | PEP 563 union annotation broke LangGraph config injection — 100% of chats failed with `llm=None`. **Already fixed** on `develop`. | [#132](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/132) |
| 2 | BUG-126 | CRITICAL | With the LLM unreachable the orchestrator never issues a retrieval call, so the user is told their *documents* are inadequate. | [#174](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/174) |
| 3 | BUG-095 | CRITICAL | The `settings` table is read by nothing at runtime; seven load-bearing knobs are inert, one of which gates an entire verification stage. | [#158](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/158) |
| 4 | BUG-098 | CRITICAL | No embedder/collection compatibility check — the reproduced dimension mismatch is the lucky case; same-dimension/different-model is silent garbage. | [#160](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/160) |
| 5 | BUG-088 | CRITICAL | In-flight LLM call has no enforced timeout; the backend hangs unbounded and leaks the task. | [#156](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/156) |
| 6 | BUG-082 | CRITICAL | Unbounded ambiguous-intent loop hangs the request with no answer and no recovery. | [#152](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/152) |
| 7 | BUG-083 | CRITICAL | Zero prompt-injection defense across all 19 prompt constants; an embedded instruction was obeyed verbatim. | [#153](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/153) |
| 8 | BUG-089 | CRITICAL | Cloud providers are unconfigurable — no create path exists, and the README claims otherwise. | [#157](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/157) |
| 9 | BUG-107 | MAJOR | `validate_citations` is a 100% no-op: the reranker parameter is never bound, so citation QA never runs. | [#164](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/164) |
| 10 | BUG-121 | MAJOR | The graceful-shutdown path is structurally unreachable; SIGKILL always wins during a chat turn. | [#171](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/171) |
| 11 | BUG-070 | MAJOR | Citations and chunks accumulate unbounded across conversation turns. | [#144](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/144) |
| 12 | BUG-078 | MAJOR | The append-only `sub_answers` reducer never resets, corrupting answer text from turn 2 onward. | [#150](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/150) |
| 13 | BUG-087 | MAJOR | `DELETE /api/documents` leaves Qdrant vectors orphaned; a deleted document is still cited. | [#155](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/155) |
| 14 | BUG-062 | MAJOR | Citation `relevance_score` emits the raw CrossEncoder logit; the UI renders bars at 400–700%. | [#140](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/140) |
| 15 | BUG-026 | MAJOR | Aggregate health reports `healthy` (and the UI stays green) while a model availability flag is `false`. | [#124](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/124) |

### 4.2 Frontend — 17 items (2 CRITICAL, 15 MAJOR)

| # | ID | Sev | Statement | Issue |
|---|---|---|---|---|
| 1 | BUG-074 | CRITICAL | A stream that closes without a `done` event leaves the chat stuck streaming forever — no client-side watchdog anywhere. | [#148](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/148) |
| 2 | BUG-034 | CRITICAL | Silent health-lie window — the banner stays green while `/api/health` is returning 503. | [#126](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/126) |
| 3 | BUG-119 | MAJOR | A working conversation and a permanently dead one render as the same screen, and global chrome recovers to "healthy" over the dead one. | [#169](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/169) |
| 4 | BUG-097 | MAJOR | The citation renderer block-wraps every text fragment, shattering multi-citation answers. | [#159](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/159) |
| 5 | BUG-047 | MAJOR | A hardcoded `DEFAULT_LLM` overrides the backend on every request, so the saved model never runs. | [#134](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/134) |
| 6 | BUG-050 | MAJOR | `throwApiError` misses the FastAPI `detail` envelope, so real error messages and trace ids are lost. | [#135](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/135) |
| 7 | BUG-120 | MAJOR | Reload discards the interrupted conversation, and no API can read a thread back. | [#170](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/170) |
| 8 | BUG-124 | MAJOR | Post-recovery lockout of 31–60s — SWR's exponential backoff overrides the configured 5s poll interval. | [#173](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/173) |
| 9 | BUG-064 | MAJOR | The backend `session_id` has no persistence across chat page remounts. | [#141](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/141) |
| 10 | BUG-077 | MAJOR | "New Chat" does not reset the backend session — context leaks forward into the next conversation. | [#149](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/149) |
| 11 | BUG-072 | MAJOR | Mid-stream navigation silently aborts the answer with no feedback and no recovery. | [#146](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/146) |
| 12 | BUG-061 | MAJOR | Clicking a citation dead-ends on an empty collection page; there is no source-passage view. | [#139](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/139) |
| 13 | BUG-038 | MAJOR | A backend restart is invisible to the UI: an HTTP 5xx with a null body changes no state. | [#129](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/129) |
| 14 | BUG-036 | MAJOR | A circuit-breaker-open state is shown to users as "Vector database is starting up." | [#128](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/128) |
| 15 | BUG-102 | MAJOR | The stage-timings chart drops bare-number stages, hiding the dominant 18s bottleneck. | [#162](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/162) |
| 16 | BUG-112 | MAJOR | Query Analytics distributions are computed from the 20-row page, not from all queries. | [#167](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/167) |
| 17 | BUG-040 | MAJOR | Upload cap drift — the UI hardcodes 50 MB while the backend enforces 100 MB. | [#130](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/130) |

### 4.3 Infrastructure — 1 item (1 CRITICAL)

| # | ID | Sev | Statement | Issue |
|---|---|---|---|---|
| 1 | BUG-054 | CRITICAL | A ~30s proxy idle timeout silently cuts large uploads and any chat whose first node is slow — including the first chat after startup. | [#137](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/137) |

### 4.4 Ingestion — 2 items (1 CRITICAL, 1 MAJOR)

| # | ID | Sev | Statement | Issue |
|---|---|---|---|---|
| 1 | BUG-052 | CRITICAL | Non-atomic re-upload deletes the old document's vectors before the new ingest succeeds — 2,025 vectors were permanently lost live, with no rollback and no notification. | [#136](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/136) |
| 2 | BUG-128 | MAJOR | The ingestion pause on dependency outage is unbounded, with no escape hatch and no operator recourse. | [#176](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/176) |

### 4.5 Reasoning — 2 items (2 MAJOR)

| # | ID | Sev | Statement | Issue |
|---|---|---|---|---|
| 1 | BUG-129 | MAJOR | Conversation history is restored into state but never reaches the answer-generation prompt — there is no path, not a path that is ignored. | [#177](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/177) |
| 2 | BUG-076 | MAJOR | Unregistered msgpack types in the checkpointer will block future LangGraph versions and force a slow fallback today. | [#175](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/175) |

### 4.6 Retrieval — 2 items (2 MAJOR)

| # | ID | Sev | Statement | Issue |
|---|---|---|---|---|
| 1 | BUG-085 | MAJOR | Child-chunk dedup keys on `parent_id` only, silently dropping distinct sibling chunks. | [#154](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/154) |
| 2 | BUG-071 | MAJOR | An indexed document is unreachable by its own filename when the body text omits the identifier. | [#145](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/145) |

---

## 5. Suggested sequencing for the fix wave

The 38 outstanding `v1.0-fix` items are not 38 independent tasks. They cluster, and the clusters
have an order.

**Cluster A — the demo path.** `BUG-054` and `BUG-126` are the two findings a first-time user is
most likely to hit, and both fail silently or misleadingly. `BUG-074` and `BUG-119` are what turn
`BUG-054` from a slow request into a permanently dead screen. Fixing `BUG-054` at the proxy and
`BUG-074` at the reader loop removes the whole visible failure, and `BUG-119`, `BUG-123` and
`BUG-124` shrink considerably. Do this cluster first.

**Cluster B — configuration honesty.** `BUG-095` (settings never read), `BUG-047` (frontend
override), `BUG-089` (no provider create path) and `BUG-096` are one story told four ways: the
product accepts configuration it does not honour. `BUG-095` and `BUG-047` must be fixed together —
either alone leaves the wrong model running.

**Cluster C — data integrity.** `BUG-052` (cascade delete before ingest), `BUG-087` (orphaned
vectors on delete) and `BUG-085` (sibling chunks dropped) are all missing cross-store
transactional discipline. `BUG-052` is the only finding in the registry that destroyed user data
during the hunt.

**Cluster D — the unreachable mechanisms.** `BUG-107`, `BUG-121` and (deferred) `BUG-118` are
correct code that nothing calls. Each is a small, well-scoped fix with no design work required —
good candidates to parallelise against the harder clusters.

**Cluster E — observability.** `BUG-102` and `BUG-112` make the performance surface actively
misleading, which matters most while the rest of this list is being worked. Fix them early enough
that they can be used to verify the other fixes.

---

## 6. `v1.1-defer` — 16 items

Deferred means the finding is real and the rationale for waiting is recorded on the record. It
does not mean disputed.

| ID | Sev | Layer | Statement | Issue |
|---|---|---|---|---|
| BUG-035 | MAJOR | Backend | Health endpoint hangs ~18s on a Qdrant TCP stall — no per-probe sub-timeout. | [#127](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/127) |
| BUG-055 | MAJOR | Backend | All warm queries breach the spec-26 latency p50, driven by a second research-loop iteration. | [#138](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/138) |
| BUG-073 | MAJOR | Backend | The streaming handler swallows `CancelledError`, so cancelled requests die invisibly. | [#147](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/147) |
| BUG-079 | MAJOR | Backend | No language-mirroring instruction — Spanish queries are answered in English. | [#151](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/151) |
| BUG-099 | MAJOR | Backend | The circuit breaker counts Qdrant 4xx as failures, so one bad collection degrades all retrieval. | [#161](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/161) |
| BUG-103 | MAJOR | Backend | The trace `ranking` stage always reads 0ms — it measures a dead node while the real rerank is untimed. | [#163](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/163) |
| BUG-108 | MAJOR | Backend | `rewrite_query` has no stage timing, hiding 15–47% of each request's latency. | [#165](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/165) |
| BUG-118 | MAJOR | Backend | The inference circuit breaker is unreachable dead code behind a disabled flag. | [#168](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/168) |
| BUG-024 | MAJOR | Frontend | React hydration error #418 on every cold-start first load. | [#123](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/123) |
| BUG-027 | MAJOR | Frontend | No per-service health badges on the dashboard — one coarse banner only. | [#125](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/125) |
| BUG-109 | MAJOR | Frontend | Ingest errors dead-end: the UI drops the job id, document id, timestamp and trace id the API returned. | [#166](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/166) |
| BUG-123 | MAJOR | Infrastructure | **UNCONFIRMED** — the proxy may hold the client stream open after the upstream socket dies. Registered with its evidence-against stated; needs an isolation probe. | [#172](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/172) |
| BUG-041 | MAJOR | Ingestion | The ingestion status state machine's specified states do not exist in the implementation. | [#131](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/131) |
| BUG-046 | MAJOR | Observability | The health surface is blind to agent-graph execution — 21 consecutive 200 OKs through a 160s wedged turn. | [#133](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/133) |
| BUG-068 | MAJOR | Reasoning | Conversational meta-requests are misrouted as `rag_query` by the intent classifier. | [#142](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/142) |
| BUG-069 | MAJOR | Reasoning | The intent classifier hard-fails under accumulated multi-turn context. | [#143](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/143) |

---

## 7. Open questions carried to spec-31

Recorded so they are not mistaken for untested gaps.

1. **`BUG-123` proxy-EOF isolation** — a controlled probe holding query and turn state fixed,
   killed twice (once proxied, once direct to `:8000`), to confirm or retract the UNCONFIRMED
   record.
2. **`BUG-069` turn-depth series** — a controlled series varying conversation depth with model and
   corpus fixed. The escalation to CRITICAL was audited and **declined** on a two-point evidence
   base; this series would settle it.
3. **WAL-ordering hypothesis** — withdrawn as unproven rather than shipped. One run skipped the
   block; the other measured on the wrong side of the restart boundary.
4. **Semaphore-exhaustion probe** — skipped by explicit decision, not omitted. No verdict is
   claimed for it.

## 8. Not in scope here

`MINOR` (45) and `COSMETIC` (6) records carry full reproduction steps, expected/actual and a
root-cause hypothesis, but no triage decision and no GitHub issue. Several were deliberately
scoped narrow so they would not duplicate a triaged finding, and belong to the same root-cause
family as one — `BUG-127` sits with `BUG-110` (ingestion jobs never record a terminal reason),
and `BUG-125` was scoped as a perceived-progress defect specifically to keep it out of `BUG-055`'s
latency territory. Read the record before scheduling one.
