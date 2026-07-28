# Resume apply-3 — Spec-30 Round-1 Bug Hunt (EOD pause 2026-06-11)

> **How to use (Pilot)**: open tmux, launch `claude` in the Lead pane, paste
> `docs/E2E/2026-05-28-round-1-bug-hunt/process/lead-prompt.md` FIRST (the contract), then say:
> **"read docs/E2E/2026-05-28-round-1-bug-hunt/process/resume-apply-3.md and resume apply-3"**.
> Everything below is the Lead's morning runbook — the Pilot only acts where marked **[PILOT]**.
> Supersedes `resume-apply-2.md` (historical).

> **✅ 2026-06-26 EOD — READ FIRST (newest; THIS is the resume pointer — supersedes the 2026-06-26 morning banner below).**
> apply-3 Phase 3 (Chat Happy Path, US3) advanced this session; PAUSED mid-P3-S4. Team re-spawned RECOVERY, confirmed 40 bugs/next-id BUG-064, SKIPPED §2 (smoke PASS, P0 closed). Work done:
> - **P3-S3 batch registered** (the long-pending 2026-06-18 batch): BUG-055 retitled→"All warm queries breach spec-26 latency p50 (2nd research-loop iteration)" (analytical trace 618fb649 = 31.6s/+97.3% over p50); BUG-062 negative-score variant (logits -0.15/-1.22/-1.51/-1.54 → -15%/-122%/-151%/-154%; CitationHoverCard.tsx:62-68 no clamp); **BUG-064** MAJOR/FE (chat session_id NOT restored from URL on reload → multi-turn history lost; useStreamChat.ts:11/38-40, page.tsx:80 separate ref); **BUG-065** MINOR/FE (no research-phase progress feedback; onStatus no-op useStreamChat.ts:41); **BUG-066** MINOR/Obs (chunks_retrieved_json inflated 4× vs unique chunks within a turn).
> - **P3-S3 (scroll) CLOSED**: auto-scroll LIVE-confirmed; **BUG-067** MINOR/FE registered (long-answer auto-scroll snaps back once on scroll-up — async IntersectionObserver vs sync per-token scroll race, ChatPanel.tsx:43-65; code-confirmed HIGH, live snap-back not reproduced — answers too short to overflow; no clipping risk).
> - **Registry now: 44 bugs (BUG-024..067), next-bug-id = BUG-068.** Files written to disk on `030-e2e-test-v3` @ 68d6b33, **NOT yet committed** (phase-close commit deferred to Phase-3 close).
>
> **⏸ PAUSED MID-P3-S4 (multi-turn) — 3 findings CORRELATED (log-analyst HIGH) but NOT registered → REGISTER FIRST tomorrow.** Pilot ran 3 organic turns in hunt-pdfs (NO reload): T1 "Explica detalladamente…NAG-200", T2 "Necesito una respuesta mas larga", T3 "Con respuesta más larga me refiero a la primer pregunta…". ALL on one continuous session `c5ffb174` (traces f88056f6/2b9065af/d8cd8ef9, qwen2.5:7b). **KEY INVERSION: conversation context IS retained & accumulates — and it POISONS the pipeline (NOT amnesia):**
> 1. **Intent MISROUTING** — T2 conversational meta-request classified intent=rag_query → literally vectorized + Qdrant-searched against the corpus (ignored the prior turn). Mechanism defect. Severity TBD (MAJOR?).
> 2. **Intent classifier HARD-FAIL under accumulated context** — T3 intent parse returned the PRIOR turn's Q&A instead of IntentClassification → silent `default→rag_query`, stage_timings intent_classification.failed=true. Distinct from BUG-056 (rewrite fallback). Severity TBD (MAJOR?).
> 3. **Unbounded citation/chunk accumulation across turns** — chunks_retrieved_json never reset/deduped: 20→70→170 formatted citations (+50-100/turn, THOUSANDS by turn 5-6 → NDJSON payload bloat). Related to BUG-066 (within-turn 4×) but DISTINCT (across-turn). **DECISION PENDING (Lead+Pilot): broaden BUG-066 vs new MAJOR/Performance ID.**
> (Out of scope A-003: the model's hedging/declining answer quality is NOT a bug.)
>
> **TOMORROW resume order (at P3-S4):** (1) verify stack 4/4 on **system GPU** (`docker context show` = default); SKIP §2 entirely; §3 re-spawn the 3 teammates RECOVERY (they read session-log + their `…/team-context/{name}`). (2) **Register the 3 P3-S4 findings above** (decide severities + BUG-066-broaden-vs-new with Pilot; IDs from BUG-068). (3) **Run the CLEAN 2-turn S4 probe** the Pilot didn't reach: new chat → "¿Cuál es el diámetro mínimo de las cañerías en redes de distribución según NAG-200?" → no-reload follow-up "y para gas natural específicamente?"; observe user-visible context retention + prior-turn citation navigability; frontend-inspector captures T2 NDJSON citation count. (4) Close P3-S4 → **P3-S5** (Spanish accents Q-007) → **P3-S6** (mid-stream nav P3-Q-C) → **close Phase 3** (commit docs/E2E/ + MERGE phase-3 into canonical apply-progress #3227) → verify-3 gate. Engram: interim `sdd/single-round-bug-hunt/apply-3-interim` (#3574) + a session summary this date; #3686 smoke-resolved; #3227 canonical phases 0-2 (DO NOT overwrite until Phase 3 closes).
>
> **✅ 2026-06-26 (morning) — context only (smoke/P0 facts below remain valid; superseded as the resume pointer by the EOD banner above).**
> The 2026-06-25 `rewrite_query` stall was a **POST-FREEZE TRANSIENT — RESOLVED.** A fresh backend-direct chat
> now COMPLETES cleanly: `hunt-pdfs` / "What is NAG-200 about?" → grounded answer + citation + **confidence 92%**
> + `done` in 55.7s (HTTP 200 NDJSON, trace_id `8b89692e`). So **the §2 morning CHAT SMOKE TEST PASSES** and the
> audit **P0 is CLOSED** (`query_traces` 987→988, fresh row `2026-06-26T18:18` in `/data/embedinator.db` — the
> pre-freeze inode; DB write-path proven). Stack is UP on the **system GPU engine** (`default` context), 4/4
> healthy, `cuda_available=True`, BUG-045 fix live (0 config warnings). **ON RESUME: SKIP §2 steps 1–6 entirely**
> — do NOT re-merge develop, do NOT rebuild, do NOT re-run the smoke. Go straight to **§3 (re-spawn the 3
> teammates, RECOVERY mode)** → **§4 + resume P3-S3** (register the pending P3-S3 batch in the 2026-06-18 note
> below). Caveat: the 55.7s latency is the already-documented **BUG-055/056** (wasteful 2nd research-loop
> iteration), NOT a new finding. Engram: `…/apply-3-smoke-resolved` (#3686). Registry unchanged: **40 bugs
> (BUG-024..063), `next-bug-id` = BUG-064**, all committed on `030-e2e-test-v3` @ `68d6b33` (which now also holds
> the previously-uncommitted in-flight P3-S3 docs).

> **⚠️ 2026-06-24 — READ FIRST (supersedes all earlier banners; the 2026-06-18 hunt-progress notes
> below are still accurate — this banner is infra-only).** The 2026-06-24 session did NOT advance the
> hunt — it was a full infra recovery after a ~1-week machine freeze. Registry unchanged: **40 bugs
> (BUG-024..063), `next-bug-id.txt` = BUG-064.** Three things you MUST know before relaunching:
>
> 1. **USE THE SYSTEM DOCKER ENGINE (GPU), NOT DOCKER DESKTOP.** The freeze left the stack accidentally on
>    Docker Desktop (`desktop-linux` context, CPU-only → `cuda_available=False`, invalid for Phase-3 latency
>    work). `docker context show` MUST print `default`. If the daemon is down: `sudo systemctl start docker`.
> 2. **LAUNCH WITH THE GPU OVERLAY:** `docker compose -f docker-compose.yml -f docker-compose.gpu-nvidia.yml up -d`.
>    Fresh-daemon network race (firewalld): if containers come up `Healthy` but with NO eth0 / empty
>    resolv.conf / ports unpublished / `/api/health` "circuit breaker open" → `docker compose down && up`
>    ONCE (no sudo). Then verify `cuda_available=True` (RTX 4070 Ti) before any hunt work.
> 3. **Qdrant was recovered losslessly** (post-freeze WAL `PermissionDenied` errno 13 crash-loop). Root cause
>    was a **Docker Desktop virtiofs file-sharing fault** on pre-freeze inodes — NOT btrfs corruption. Fix was
>    `cp -a` swap onto fresh inodes; the original is kept as `data/qdrant_db.corrupt` (213M, gitignored; can't
>    be `rm`'d without sudo/btrfs — clean up later). 24 collections intact, hunt-pdfs = 1135 points.
>
> **STILL PENDING (resume here):** the **chat smoke test was never run** — it closes the audit's last open P0
> (prove the backend persists a fresh `query_traces` row to the pre-freeze `embedinator.db` inode; latest row
> was 2026-06-18T19:46). UI: hunt-pdfs → "What is NAG-200 about?" → grounded answer + citations. Then resume
> at **P3-S3** per the 2026-06-18 banner below. Engram refs: #3654 launch checklist · #3649 root-cause audit ·
> #3646 cp-swap recovery · #3574 mid-P3-S3 checkpoint · #3227 canonical apply-progress (phases 0-2).

> **2026-06-18 EOD UPDATE (hunt progress — still current; infra notes superseded by the 2026-06-24 banner above)**: We are MID-Phase-3 of
> apply-3. §2 morning runbook is DONE (HEAD `5fac6e5`, BUG-045 fix LIVE, smoke PASSED earlier) — do NOT
> re-merge develop or rebuild. teammateMode is `"tmux"` (split panes working). Progress this session:
>
> - **P3-S1 (factoid streaming) ✅ CLOSED** — 9 findings: 3 UPDATE (BUG-047→MAJOR model-not-honored,
>   BUG-048 trace_id, BUG-025 health tag) + 6 NEW (BUG-055 latency, BUG-056 OutputParserException,
>   BUG-057 ranking-0ms, BUG-058 sidebar hygiene, BUG-059 orphaned-dot, BUG-060 citation a11y). Verdict
>   PASS happy-path. `verify_groundedness` OFF = DISMISSED (intentional, config.py:85 spec-26 FR-005).
> - **P3-S2 (citation interaction) ✅ CLOSED** — 5 findings: 3 NEW (BUG-061 MAJOR citation-click dead-end:
>   `document_id` is a parent-chunk UUID used as `collection_id`, NO passage-highlight route exists;
>   BUG-062 MAJOR relevance_score = raw CrossEncoder logit shown 400-700% AND negative; BUG-063 MINOR
>   `/api/documents` 200-not-404) + 2 UPDATE (BUG-042 raw-UUID breadcrumb, BUG-024 hydration #418).
>   Verdict FAIL citation reachability. Next.js skills wired into the frontend-inspector spawn doc
>   (boot step 5, engram #3567).
> - **P3-S3 (long-answer scroll) IN PROGRESS — PAUSED here.**
>
> **Registry: 40 bugs (BUG-024..063), `next-bug-id.txt` = BUG-064.**
>
> **PENDING P3-S3 registration (NOT yet written — do this BEFORE S4):**
> 1. **BUG-055 RETITLE/broaden** to "all warm queries" — log-analyst confirmed the systemic root: the
>    research loop ALWAYS runs a wasteful 2nd iteration (~16s, `agent_loop_exit_tool_exhaustion`, re-reads
>    chunks, finds nothing) → 2-3× latency across factoid+analytical (32.2s / 45.2s / 31.6s).
> 2. **BUG-062 ADD negative-score variant** — analytical query scores `+1.78, -0.15, -1.22, -1.51, -1.54`
>    → FE displays 178% / -15% / -122% / -151% / -154% (negative % worse than >100%).
> 3. **Scroll auto-scroll/manual-override behavior STILL TBD** — frontend-inspector was mid-code-inspection.
> 4. **Long-answer 2-min "stall" — RESOLVED = HARNESS ARTIFACT (do NOT register as a stall).** The POST
>    DID fire (reqid 668, POST /api/chat → HTTP 200 NDJSON, x-trace-id `fab6a045`, correct body); submission
>    was genuine (click + type_text char-by-char + Enter). The 2-min no-token freeze was the
>    frontend-inspector's OWN 90s `evaluate_script` polling loop blocking Chrome's event loop →
>    `ERR_NETWORK_IO_SUSPENDED` killed the NDJSON stream. NOT a product stall. **NB discrepancy to re-check
>    tomorrow:** FE saw uvicorn 200 + trace id `fab6a045`, but log-analyst saw no chat events / no
>    query_traces row — likely the client-abort killed the request before the research loop/Ollama fired.
> 5. **NEW candidate — session_id not restored from URL (MAJOR? — verify + register tomorrow):** POST body
>    had `session_id: null` despite URL `?session=931817be`. `useStreamChat.sessionIdRef` starts null,
>    seeded only via the `onSession` callback, never pre-populated from the URL on page load → reloading a
>    session and asking a new question spawns a NEW backend session (conversation history LOST). Path:
>    chat/page.tsx → useStreamChat.ts sessionIdRef. **Directly impacts P3-S4 (multi-turn).**
> 6. **NEW candidate — no research-phase progress feedback (MINOR/MAJOR?):** `onStatus: () => {}` no-op at
>    useStreamChat.ts:41 → status events never reach stage state → `PipelineStageIndicator` never renders →
>    user sees a static skeleton with ZERO progress text for the entire (up to 2min+) research phase.
> 7. **BUG-048 + BUG-051 RE-CONFIRMED** on the "Stream read error: network error" toast (no trace_id, no
>    elapsed; unconditional Retry) — UPDATE evidence, no new IDs.
> 8. **Scroll auto-scroll/manual-override behavior STILL TBD** — never observed cleanly (the long probe
>    self-destructed); re-run tomorrow with a SHORT question that overflows + snapshot-between-pauses (NO
>    long evaluate_script loops — that was what killed the stream).
>
> (Teammate engram saves: log-analyst #3440, bug-registrar #3441, frontend-inspector #3442 — all upserted
> on their `…/team-context/{name}` topics.)
>
> **Engram backups (resume aids):** Lead interim **#3574** (topic `sdd/single-round-bug-hunt/apply-3-interim`)
> + a session summary; teammates `…/team-context/{log-analyst #3440, bug-registrar #3441, frontend-inspector}`.
> Canonical apply-progress **#3227 still = phases 0-2** — do NOT bump it until Phase 3 CLOSES. Bug IDs from
> **BUG-064**. Out-of-scope (A-003): chat answer correctness / content-gap (the Medium-54% hedge is NOT a bug).
>
> **TOMORROW (resume order):** (1) docker likely DOWN + Ollama COLD after sleep → bring the stack up
> (`./embedinator.sh` if needed), confirm 4/4 healthy, skip the develop-merge/rebuild (already done);
> first real query eats ~8-10s cold model-load. (2) Re-spawn the 3 teammates (§3, RECOVERY mode — they
> read session-log.md first). (3) RESUME at **P3-S3**: resolve the long-answer fork → register the pending
> P3-S3 batch above → continue S3 scroll → S4 (multi-turn) → S5 (Spanish accents) → S6 (mid-stream nav)
> → close Phase 3 (commit + apply-progress phase-3 MERGE) → verify-3 gate.

---

## 1. State at pause (2026-06-11 ~19:45 -03:00)

| Item | State |
|---|---|
| Phases 0-2 | ✅ CLOSED — P1: `cff56ad` (15 findings), P2: `e3b873f` + `63b33f7` (16 findings). verify-1 + verify-2 both PASS (adjudicated) |
| Registry | **31 bugs** (BUG-024..054): 1 BLOCKER / 2 CRITICAL / 11 MAJOR / 14 MINOR / 3 COSMETIC. `next-bug-id.txt` = **BUG-055**. All committed, all schema-pass |
| BUG-045 (BLOCKER, chat outage) | **FIXED on develop** — PR #101 MERGED (`d9107cb`): `Optional[RunnableConfig]` ×12 signatures + regression test `tests/unit/test_graph_config_injection.py`. Adversarial review MERGE-OK 7/7 |
| PR #102 | MERGED (`9d1a79d`) — pip-audit ignores CVE-2025-3000 (torch 2.12.0, no fixed release; dated comment; REMOVE when patched torch ships) |
| Branch `030-e2e-test-v3` | at `63b33f7` — does **NOT** yet contain the fix (develop merge is morning step 2c) |
| Team `spec30-hunt` | Dead with the session (always — config doesn't survive). Re-create per §3. Spawn docs ALREADY UPDATED for apply-3 |
| Engram contexts | Lead: `…/apply-progress` (#3227) · teammates: `…/team-context/{log-analyst,frontend-inspector,bug-registrar}` — all checkpointed at EOD |
| Next phase | **apply-3 = Phase 3, Chat Happy Path (US3)** — gated on the morning smoke test below |

**Carry-forwards (do not lose)**: (HARD, verify-7) real GitHub issue URLs for ALL MAJOR+ before apply-8 · (SOFT, LAUNCH-DECISION.md) true cold-start re-run OR warm-measured caveat · remove the CVE-2025-3000 pip-audit ignore when torch ships a fix.

---

## 2. Morning runbook (Lead — execute IN ORDER before any team spawn)

1. **[PILOT if docker down]** `sudo systemctl start docker && ./embedinator.sh` (system engine).
2. Lead PREFLIGHT (from lead-prompt.md): tmux ✓ · `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` ✓ ·
   branch `030-e2e-test-v3` ✓ · `phase-playbook.md` exists ✓ · stack 4/4 healthy.
3. **Bring the fix into the hunt branch**:
   `git fetch origin && git merge origin/develop -m "chore(spec-30-r1): merge develop — BUG-045 fix (PR #101) + pip-audit ignore (PR #102)"`
   (Expect clean merge; the branch previously merged develop@3a5fe6b.)
4. **Rebuild the backend image** (no source bind-mount — restart alone does NOTHING):
   `docker compose build backend && docker compose up -d backend`
5. **Verify the fix is live** (both must hold):
   - `docker compose logs backend --since 2m | grep -i "config.*parameter"` → **ZERO** UserWarnings
     (previously fired at conversation_graph.py:53/54/62 + research_graph.py:49/52/54/55).
   - `curl -s localhost:8000/api/health` → 200 healthy.
6. **[PILOT] CHAT SMOKE TEST**: in the UI, chat against `hunt-pdfs` ("What is NAG-200 about?").
   PASS = streamed answer with citations, no "Unable to process your request".
   Lead cross-checks: a NEW `query_traces` row exists (first since 2026-05-05) and Ollama logs
   show a real inference call. **If SERVICE_UNAVAILABLE reappears: STOP — check for the BUG-045
   log signature (agent_classify_intent_failed + 'NoneType' with_structured_output); the fix
   regressed or the image didn't rebuild.**
7. `npx gitnexus analyze` (index is stale vs the merged fix) — run in background.
8. Read resume state per lead-prompt §0: `mem_search("sdd/single-round-bug-hunt/apply-progress")`
   → `mem_get_observation` · `tail docs/E2E/2026-05-28-round-1-bug-hunt/session-log.md`.

---

## 3. Team spawn (after §2 passes — NOT before)

> **Claude Code v2.1.178+**: `TeamCreate`/`TeamDelete` no longer exist. Use the `Agent` tool directly —
> with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` set this IS Agent Teams spawning (shared task list,
> `SendMessage`, tmux panes). NOT the same as plain subagents. The team config is session-derived and
> removed at session end, so teammates always need re-spawning per apply run.

Spawn all 3 in **ONE response** (three `Agent` tool calls in the same message — parallelism):

| Teammate | `subagent_type` | `model` | spawn doc |
|---|---|---|---|
| `log-analyst` | `python-expert` | `sonnet` | `docs/E2E/2026-05-28-round-1-bug-hunt/process/spawn/spawn-log-analyst.md` |
| `frontend-inspector` | `frontend-architect` | `sonnet` | `docs/E2E/2026-05-28-round-1-bug-hunt/process/spawn/spawn-frontend-inspector.md` |
| `bug-registrar` | `technical-writer` | `sonnet` | `docs/E2E/2026-05-28-round-1-bug-hunt/process/spawn/spawn-bug-registrar.md` |

Spawn prompt per teammate (minimal):
```
"You are `<name>` on team `spec30-hunt`. Project root: <repo-root>. Your team-lead is named `team-lead`. Read docs/E2E/2026-05-28-round-1-bug-hunt/process/spawn/<spawn-doc>.md FIRST and follow it exactly — it is your boot contract."
```

Roster LOCKED (R-005). Wait for all 3 online confirmations (`bug-registrar` must confirm: 31 bugs on
disk, next ID BUG-055).

---

## 4. Open Phase 3

1. Route to bug-registrar: `[<ISO-8601 local -03:00>] Orchestrator | phase-transition | Phase 3 (Chat Happy Path) opened`
   — plus an observation line noting the develop merge SHA, rebuild, and smoke-test PASS.
2. Brief the Pilot with the Phase 3 scenario card from `specs/030-e2e-test-v3/phase-playbook.md`
   `## Phase 3`, then run the relay loop per lead-prompt §2. Observation grammar: `observation: P3.S<M> — …`.
3. Bug IDs from **BUG-055**. Severity decisions: Lead + Pilot. Register once, correctly.
4. Chat-adjacent OPEN bugs (new evidence = UPDATE, not new ID): BUG-046 health-blind ·
   BUG-047 model-badge hardcoded · BUG-048 trace_id dropped · BUG-050 detail-envelope mismatch ·
   BUG-051 unconditional retry · BUG-054 30s proxy timeout.

---

## 5. Engram topic-key map (project: `the-embedinator`)

| Topic key | Content |
|---|---|
| `sdd/single-round-bug-hunt/apply-progress` | Canonical resume checkpoint (#3227, phases 0-2 ✓ + verify-2 ✓) |
| `sdd/single-round-bug-hunt/team-context/{log-analyst,frontend-inspector,bug-registrar}` | Per-teammate EOD contexts |
| `sdd/single-round-bug-hunt/verify-report-phase-2` (#3500) + `verify-gate-2-decision` (#3502) | verify-2 PASS, adjudicated |
| `spec-30/round-1/chat-outage-pep563-langgraph` | BUG-045 root cause + fix recipe |
| `spec-30/round-1/bug-045-fix-implementation` + `bug-045-fix-review` | Fix evidence + MERGE-OK review |
| `spec-30/round-1/spawn-docs` | Spawn-doc system rationale + team-config-mortality discovery |
| `sdd/single-round-bug-hunt/{spec,design,tasks,proposal,state}` | SDD planning artifacts (read-only) |

— End of resume-apply-3.md
