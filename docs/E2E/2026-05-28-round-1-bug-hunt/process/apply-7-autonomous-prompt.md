# apply-7 (AUTONOMOUS) — Phase 7 Recovery & State Hunt, US7

**Change**: `single-round-bug-hunt` · **Branch**: `030-e2e-test-v3` · **Date**: 2026-07-28
**Supersedes**: `apply-7-launch-prompt.md` (human-Pilot variant, never executed)
**Governed by**: engram `sdd/single-round-bug-hunt/spec` (#3218) + **amendment R-007** (#4078)
**Precondition**: verify-6 PASS (report #3993, decision #3994). apply-7 UNBLOCKED.

This is the **final hunt phase**. After it: verify-7 → apply-8 closure → verify-8 → archive.

---

## 0. What changed vs the human-Pilot design

Under **R-007** the Pilot role is delegated to the Lead agent for phases 7–8. Concretely:

| Was | Now |
|---|---|
| Pilot drives Chrome, types `observation:` lines | `frontend-inspector` drives **Playwright MCP** (a separate browser, not the Pilot's Chrome) |
| Pilot approves each `docker kill/stop/down` (HAZARD 4) | Standing enumerated authorization, R-007-B; harness deny-list blocks everything else |
| Pilot consents per ingestion (HAZARD 2) | Standing authorization bounded to `p7s3-scratch`, R-007-C |
| BLOCKER-PATCHED Y/N gate | **SUSPENDED entirely** (R-007-D) — no inline fixes, every finding is filed |
| 3 teammates on Sonnet | 3 teammates on **Opus** (R-007-E) — roles/count/boundaries unchanged |
| tmux panes | Headless `Agent` spawns (R-007-F) |

Everything auditable is unchanged: same scenarios, same schema, same R-002 gate, same SC set.

---

## 1. Facts that override stale documents

**Container names have NO `-1` suffix.** Confirmed 2026-07-28 via
`docker compose ps --format '{{.Name}}'`:
`embedinator-backend` · `embedinator-frontend` · `embedinator-qdrant` · `embedinator-ollama`.
The playbook's `embedinator-backend-1` etc. are stale. **Using them makes every kill target a
nonexistent container, so the scenario silently does not execute and you record a phantom
recovery PASS.** This is the single highest false-result risk of the phase.

**`AsyncSqliteSaver` IS wired.** `backend/main.py:575-577` runs
`AsyncSqliteSaver.from_conn_string(checkpoint_path)` → `.setup()`, and `:640-642` passes that
checkpointer into `build_conversation_graph(checkpointer=...)`. `MemorySaver()` is only the test
fallback (`conversation_graph.py:91`, `checkpointer or MemorySaver()`). The playbook's
"MemorySaver default → automatic CRITICAL" branch (`phase-playbook.md:524`) is **stale and
neutralized**. P7-S5's job is to VALIDATE resume, not to flag missing persistence.

**Health endpoint is `/api/health`** (`/healthz` 404s on the backend; it is the *frontend's*
health path). The first `/api/health` after any backend restart returns
`{"status":"starting","services":[]}` — **call it twice** after every restart in this phase.

**Backend edits do not hot-reload** in the prod image; irrelevant here (SC-006 forbids edits)
but relevant if you think a restart "picked up" something. It didn't.

**Registry at phase open**: 94 bugs (BUG-024..117), `next-bug-id.txt` = **BUG-118**.
Mix: 1 BLOCKER / 8 CRITICAL / 36 MAJOR / 43 MINOR / 6 COSMETIC.

---

## 2. Standing authorizations (R-007-B / R-007-C / R-007-H)

**Permitted lifecycle commands — this exact list, nothing else:**

```
docker kill  embedinator-{backend|frontend|qdrant|ollama}
docker stop  embedinator-{backend|frontend|qdrant|ollama}
docker start embedinator-{backend|frontend|qdrant|ollama}      # PREFERRED for per-service restart
docker compose -f docker-compose.yml -f docker-compose.gpu-nvidia.yml down    # P7-S4 ONLY
docker compose -f docker-compose.yml -f docker-compose.gpu-nvidia.yml up -d   # P7-S4 ONLY
```

> **CORRECTION (2026-07-28, mid-phase — supersedes the original `docker compose up -d [service]`
> and bare `docker compose down` in this list).** Caught by `frontend-inspector` during P7-S1.
> This stack was composed from **two** files — `docker inspect` reports
> `com.docker.compose.project.config_files = docker-compose.yml,docker-compose.gpu-nvidia.yml` —
> and **both `embedinator-backend` and `embedinator-ollama` hold an NVIDIA device request**
> (`HostConfig.DeviceRequests[].Driver = "nvidia"`). There is no `docker-compose.override.yml`
> and `COMPOSE_FILE` is unset.
>
> A bare `docker compose up -d <svc>` therefore loads only the base file, detects configuration
> drift, and **recreates the container without the GPU** — silently degrading every remaining
> scenario, invalidating any latency evidence gathered afterward, and leaving the operator's
> stack degraded after the hunt ends. The failure is silent: the container comes up healthy.
>
> Rules now: use **`docker start <container>`** for any single-service restart (config-preserving,
> already permitted). Use the **explicit two-file form** for P7-S4's full-stack cycle, which needs
> a real `down` + `up` to prove data lives in volumes rather than container filesystems.
> `-v` remains forbidden in every form, including the two-file one, and is denied at the harness.

**Forbidden, and blocked at the harness:** `-v` / `--volumes` on any `down`, `docker volume rm`,
`docker volume prune`, `docker system prune`, `make clean`, `make clean-all`, `rm -rf`.

`-v` would wipe the named volumes — i.e. destroy exactly the persistence P7-S4 exists to prove
survives. It is banned three ways: this clause, the deny-list, and the P7-S4 card below.

**Ingestion**: only into the throwaway collection `p7s3-scratch`. `nag-corpus-spec28`,
`nag-corpus-bm25`, `nag-corpus-bge-m3` are untouchable — `nag-corpus-spec28` is the shared
Round-1 fixture that phases 3–6 depend on.

**Secrets**: `sk-test-PLACEHOLDER-DO-NOT-COMMIT` is the only key string that may ever be typed.
The `providers` table holds a real Fernet ciphertext (`gAAAAA…`) for the seeded `openai` row —
it is BUG-098's live repro and **must never appear in a bug file, a commit, or a GitHub issue**.

---

## 3. Roster and dispatch

| Teammate | Profile | Model | Boot contract |
|---|---|---|---|
| `log-analyst` | python-expert | **Opus** | `spawn/spawn-log-analyst.md` |
| `frontend-inspector` | frontend-architect | **Opus** | `spawn/spawn-frontend-inspector.md` |
| `bug-registrar` | technical-writer | **Opus** | `spawn/spawn-bug-registrar.md` |

The spawn docs are **pinned at apply-3** (they claim "31 bugs / next-id BUG-055"). Treat the
Identity, Boot Sequence, Scope and capture-path sections as current; treat the State Pins and
"This spawn: apply-3" line as superseded by §1 above.

**Two documented overrides to the frontend-inspector spawn doc:**
1. It says `chrome-devtools` is PASSIVE-ONLY because it shares the Pilot's Chrome. **Use
   Playwright MCP instead** — a genuinely separate browser, which is the doc's own sanctioned
   escape hatch for ACTIVE inspection. Active driving via Playwright is permitted; chrome-devtools
   stays passive-only and is not used at all this phase.
2. Its Scope table lists `docker commands` as forbidden. **R-007-H overrides this for the single
   enumerated lifecycle command belonging to the scenario it is driving** — because the P7-S1
   kill must land *mid-stream*, and only one agent's sequential tool stream can hit that window.
   No other docker command, ever.

**Capture discipline (unchanged from phases 1–6, stricter than R-007-G):** analyst and inspector
write captures to `/tmp/spec30-captures/` and write **nothing** under `docs/E2E/`. They hand
paths to the Lead; `bug-registrar` moves what is needed into `screenshots/ logs/ traces/` and is
the sole writer to every tracked path.

---

## 4. Scenarios

**Binding standard, carried from phases 4–6:** a clean recovery counts as PASS only if you can
cite the code that engineers it. *"It happened to come back"* is emergent, not engineered — and
must be framed that way in the record. Phases 4–6 established this after two injection "PASSes"
turned out to be luck.

**Dedup rule:** before minting any ID, `bug-registrar` dedup-checks against all 94 existing
records. Recovery findings plausibly overlap **BUG-110** (`finished_at` never stamped on any
job), **BUG-099** (circuit breaker counts client errors), **BUG-055** (latency/timeout).
Cross-reference and UPDATE; do not re-mint.

### P7-S1 — Backend kill mid-stream
1. Playwright: open `localhost:3000`, pick `nag-corpus-spec28`, send a question that takes
   ≥15s (analytical, multi-source — warm p50 is ~19.5s so there is a wide window).
2. **Screenshot the mid-stream state before killing** — P7-S5 compares against it.
3. While the NDJSON stream is still open: `docker kill embedinator-backend`.
4. Wait 5s. `docker compose up -d backend`. Poll `/api/health` **twice**.
5. Observe the UI without reloading, then reload.

**PASS**: the conversation either resumes from the LangGraph checkpoint or closes with a
user-visible explanation, within ~30s of restart. **FAIL**: half-rendered answer, silent stall,
or a dead spinner with no explanation.
**Never** call a `getResponseBody`-backed read against the in-flight stream (HAZARD 1: 1800s wedge).

### P7-S2 — Ollama unavailable
1. `docker stop embedinator-ollama`. 2. Attempt a chat. 3. Observe. 4. `docker start embedinator-ollama`.

**PASS**: an actionable error inside the timeout (`max_loop_seconds=300` per `config.py:70`);
no indefinite hang; chat recovers or offers a clear retry.

> **CORRECTION — grade against 60s, not 30s.** The playbook card and `retrieval/searcher.py:51`'s
> inline comment both say a 30s cooldown. Both are **stale**. Ground truth is
> `config.py:87-88`: `circuit_breaker_failure_threshold = 5`, `circuit_breaker_cooldown_secs = 60`
> (raised deliberately in spec-26 FR-009 to give Ollama reload time). Grading against 30s would
> manufacture a false "cooldown overrun" finding.
>
> **There are TWO independent circuit breakers, not one.** Qdrant's is at
> `retrieval/searcher.py:48-69`; **inference (Ollama) has its own** at `nodes.py:120`
> `_inf_circuit_open` / `:127` `_check_inference_circuit()`, with a half-open probe at `:135-141`.
> P7-S2 exercises the *inference* breaker; the Qdrant one sits downstream of research and may
> never be reached. Watch BUG-099 (breaker counts client errors) — but note a stopped container
> produces connection errors, not client errors, so BUG-099's miscounting may not change
> behaviour here. Confirm empirically rather than assuming either way.
**FAIL**: infinite spinner, or an error that names nothing the user can act on.
Dedup against BUG-099 before minting.

### P7-S3 — Qdrant unavailable mid-ingestion
1. Create collection **`p7s3-scratch`** (never a `nag-corpus-*`). 2. Start ingesting
`tests/fixtures/sample.pdf`. 3. Mid-ingestion: `docker stop embedinator-qdrant`. 4. Wait 30s.
5. `docker start embedinator-qdrant`. 6. Inspect the job's terminal state via
`GET /api/collections/{id}/ingest/{job_id}` **and** the `ingestion_jobs` table.

**PASS**: ingestion pauses with a resume path, or fails into an observable quarantined state.
**FAIL**: silently dropped, or terminal state unobservable. BUG-110 already says `finished_at`
is never stamped on any outcome — watch whether the interrupted job's state is even readable,
and UPDATE BUG-110 rather than minting a duplicate.

### P7-S4 — Full stack restart with persistent data
Preconditions, all verified present 2026-07-28: the seeded `openai` provider row with its
encrypted key (**do not clean it up**), `nag-corpus-spec28`, and ≥1 prior conversation
(100 checkpoint threads / 1008 traces exist).

1. `docker compose down` — **bare. Never `-v`.** 2. `docker compose up -d`. 3. Wait for 4/4
healthy. 4. Playwright: verify collections list, prior conversation history, settings values,
and that the provider key is still present-and-encrypted (via `GET /api/providers`, which must
never return plaintext — SC-012).

**PASS**: all four survive. **FAIL**: any loss, or a key that comes back readable.
Run `python scripts/smoke_test.py` (13 checks) after this scenario.

### P7-S5 — Checkpoint resume validation
Force-resume the interrupted P7-S1 conversation; compare against the pre-kill screenshot.

**PASS**: coherent continuation — *semantic* match, not byte-equal (LLMs are nondeterministic),
and the checkpoint's presence is attributable to `main.py:575`.
**FAIL only if** resume is broken *despite* `AsyncSqliteSaver` being wired — e.g. checkpoint
written but never restored, `thread_id` lost, UI stuck half-rendered. That is a recovery defect
graded on real user impact, **not** an automatic CRITICAL.
**Do not file "checkpoint persistence is missing."** It isn't. See §1.

Optional deep check: `config={"configurable":{"thread_id":"<id>"}}; snapshot = await
graph.aget_state(config); assert snapshot is not None`.

---

## 5. Phase close

1. **Schema completeness** — every finding has severity, layer, phase, scenario_id,
   discovered_at, ≥1 reproduction step, ≥1 non-null artifact path, and `title` ≤80 chars
   *excluding* the `BUG-NNN: ` prefix. CRITICAL/MAJOR with a missing field fails the gate.
2. **Carry-forward edits from verify-6** — one bundled `bug-registrar` pass, **no new IDs**:
   - BUG-107 `## Notes` still says "UNCONFIRMED" → record the adjudicated conclusion
     **BY-DESIGN STUB** (git-confirmed: `build_conversation_graph` never accepted a `reranker`
     param; the node was scaffolded and never wired).
   - BUG-070 `## Actual` / `## Root-cause hypothesis` still contradict its retraction Note.
3. **Session-log phase-transition** (registrar writes):
   `[<ISO-8601>] Orchestrator | phase-transition | Phase 7 closed → final hunt phase complete.
   <K> findings registered: <IDs + severities>. verify-7 next, then apply-8 closure.`
4. **Commit** — one clean commit, session dir only:
   `git add docs/E2E/2026-05-28-round-1-bug-hunt/ && git commit -m "chore(spec-30-r1): close hunt phase 7 — <K> findings"`
5. **MERGE `apply-progress`** (topic `sdd/single-round-bug-hunt/apply-progress`, type
   `architecture`, `capture_prompt: false`). Phases 0–6 must survive **verbatim**. Append
   `CHECKPOINT: phase-7 complete` with phase number, scenario count, bug IDs, and the final
   session-log timestamp (R-001-A).

Do **not** advance to apply-8 in this run. verify-7 is the gate, and apply-8 is additionally
blocked on the MAJOR+ GitHub-issue-URL backfill.

---

## 6. Recovery

If this run aborts: re-read `apply-progress` and the tail of `session-log.md`, determine the
last closed `P7-S<M>`, resume at `M+1`, and do not re-register bugs already present in `bugs/`.
Re-spawn teammates (team config is session-derived and does not survive a Lead restart).
