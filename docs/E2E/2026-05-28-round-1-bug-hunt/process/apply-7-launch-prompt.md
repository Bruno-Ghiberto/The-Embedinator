# apply-7 launch prompt — Spec-30 Round-1 Bug Hunt, Phase 7 (Recovery & State Hunt, US7) — FINAL HUNT PHASE

> **How to use (Pilot)**: Only AFTER verify-6 has PASSED (it has — report #3993, decision #3994).
> Open tmux, launch `claude` in a fresh Lead pane, `/model opus`, and paste EVERYTHING below the line into the pane.
> Wait for the 5-line status, then say "go".
> **This is the LAST hunt phase.** After P7 closes → verify-7 → then apply-8 closure (which is gated on the 45-bug GitHub-issue-URL backfill).

---

You are `team-lead`, the Lead orchestrator for the Spec-30 Round-1 live bug hunt (SDD Shape-D′, Agent Teams + tmux, human-in-the-loop with me as Pilot). This is **apply-7 = Phase 7 (Recovery & State Hunt, US7)** — the **final hunt phase**.

**PRECONDITION**: verify-6 PASSED (0 CRITICAL / 1 WARNING / 3 SUGGESTION; engram `sdd/single-round-bug-hunt/verify-report-phase-6` #3993, decision `sdd/single-round-bug-hunt/verify-gate-6-decision` #3994). apply-7 is UNBLOCKED.

**DO NOT type `/sdd-apply` or `/speckit.implement`** — you execute the contract directly; those load a delegate-only Strict-TDD executor that WILL derail the hunt.

**STEP 1 — Read these, IN THIS ORDER, before doing anything else:**
1. `docs/E2E/2026-05-28-round-1-bug-hunt/process/lead-prompt.md` — your full phase-scoped operating contract (team lifecycle §1, per-phase relay loop §2, phase close §3, BLOCKER-PATCHED gate §5, inline fallback §6, PROHIBITED list). Follow it exactly.
2. Engram: `mem_search(query: "sdd/single-round-bug-hunt/apply-progress", project: "the-embedinator")` → `mem_get_observation` on the hit (#3227). The canonical checkpoint records **phases 0–6 complete**. Do NOT overwrite phases 0–6 when you close Phase 7 — **MERGE**.
3. `tail docs/E2E/2026-05-28-round-1-bug-hunt/session-log.md` — confirm the last phase-transition (Phase 6 CLOSED → Phase 7 ready) and any trailing post-close `Orchestrator | observation` addendum line.
4. `specs/030-e2e-test-v3/phase-playbook.md` → `## Phase 7 — Recovery & State Hunt (US7)` (lines 472–532) — your scenario cards (P7-S1..S5), reproduced below.

**CURRENT STATE (authoritative):**
- Phases 0–6 CLOSED. Phase 6 committed at `e9425f9`. **verify-6 PASSED.**
- Registry = **94 bugs (BUG-024..117)**, next-bug-id = **BUG-118**. Mix: **1 BLOCKER / 8 CRITICAL / 36 MAJOR / 43 MINOR / 6 COSMETIC**.
- Branch `030-e2e-test-v3`. Stack must be UP on the **SYSTEM GPU engine**. Check `docker context show` = **`default`** — it silently flips to `desktop-linux`, where `docker compose ps` returns an EMPTY list and the stack looks "down" while actually running fine. If it flipped, `docker context use default` before concluding anything.
- If genuinely down: `docker compose -f docker-compose.yml -f docker-compose.gpu-nvidia.yml up -d`. Expect 4/4 healthy.
- **Uncommitted, expected, not drift**: a trailing `session-log.md` observation line; `.claude/skills/gitnexus/*/SKILL.md` mods (5); untracked `docs/superpowers/`.

---

## ⚠️ CONTAINER NAMES — STALE PLAYBOOK, READ THIS FIRST

Every P7 scenario is a `docker kill` / `docker stop` command. **The playbook's container names carry a stale `-1` suffix** (`embedinator-backend-1`, `embedinator-ollama-1`, `embedinator-qdrant-1`). The REAL names have **NO suffix**:

- `embedinator-backend`  ·  `embedinator-ollama`  ·  `embedinator-qdrant`  ·  `embedinator-frontend`

Confirm with `docker compose ps --format '{{.Name}}'` before the first kill. **If you use the `-1` names, every kill/stop silently targets a nonexistent container and the scenario does not actually execute** — you would record a phantom "recovery PASS" against a stack that was never perturbed. This is the single highest false-result risk of the phase.

---

## HAZARDS — read before touching anything

**HAZARD 1 (CRITICAL THIS PHASE) — chrome-devtools MCP wedges on in-flight streams, and P7-S1 kills the backend MID-STREAM.**
The `chrome-devtools` MCP shares the Pilot's Chrome/CDP connection. Calling `get_network_request` (or anything triggering CDP `Network.getResponseBody`) on an **in-flight** `POST /api/chat` NDJSON stream blocks until the stream closes — a **1800s / 30-minute hang that wedges EVERY subsequent devtools call**, Pilot included. P7-S1 and P7-S5 revolve around interrupting a live stream, so this is the most dangerous phase for it.
**RULE FOR P7: prefer the `frontend-inspector` driving Playwright over the Lead holding the CDP lock.** Per the apply-6 hand-off, in P7 the Lead does NOT need the CDP lock unless inspecting a *completed* request. Let frontend-inspector own browser state/screenshots via Playwright; the Lead takes CDP only for a specific completed-request inspection, never against a streaming or about-to-be-killed request.

**HAZARD 2 — P7-S3 ingestion + kill can poison the shared corpus.** P7-S3 starts an ingestion then kills Qdrant mid-way; this WILL leave a partial/failed document. Run it against a **throwaway scratch collection**, NEVER `nag-corpus-spec28` (that corpus is Round-1's shared fixture and verify-6 flagged re-confirming its integrity before this phase). Get my explicit consent before any ingestion.

**HAZARD 3 — never paste a real API key.** If P7-S4 re-enters a provider key, use only the literal placeholder `sk-test-PLACEHOLDER-DO-NOT-COMMIT`. A real key in this repo's logs or session dir is an incident, not a finding.

**HAZARD 4 — destructive `docker` commands hit MY machine.** `docker kill`, `docker stop`, and especially `docker compose down` in P7-S4 tear down live services. Announce each destructive command and get my go before running it. NEVER add `-v` to `docker compose down` (P7-S4 says `down`, not `down -v`) — `-v` wipes the named volumes and destroys all persisted state, which is the exact thing P7-S4 is supposed to prove SURVIVES.

---

## STATE DEPENDENCIES (P7 validates recovery, so it needs prior state to recover)

- **P7-S4 needs the P5-S1 encrypted key present.** The out-of-band seeded `openai` provider row (is_active=0, BUG-098's live repro) is still live and is exactly the persisted-key artifact P7-S4 checks. **Do NOT clean it up before P7-S4 runs.** After P7 (demo-prep), the rollback is `DELETE FROM providers WHERE name='openai'`.
- **P7-S4 needs a collection + a prior conversation.** `nag-corpus-spec28` supplies the collection; run at least one chat first so there is a conversation + checkpoint to test persistence against.
- **P7-S1 → P7-S5 chain**: P7-S5 force-resumes the SAME interrupted chat from P7-S1, so have frontend-inspector capture a pre-kill screenshot at the moment of the P7-S1 kill.

---

## P7-S5 — checkpoint persistence is ALREADY WIRED (do not file a false CRITICAL)

The playbook says: "If `AsyncSqliteSaver` is NOT injected (i.e. `MemorySaver()` is the default), checkpoint resume across restarts is impossible — that's a CRITICAL finding." **I already verified the code: it IS injected.** `backend/main.py:575-577` runs `AsyncSqliteSaver.from_conn_string(checkpoint_path)` → `.setup()`, and line 640-642 passes that `checkpointer` into `build_conversation_graph(checkpointer=checkpointer)`. `MemorySaver()` is only the *test-default fallback* inside `build_conversation_graph` (`conversation_graph.py:91` `checkpointer or MemorySaver()`), never the production path.
**So P7-S5's job is to VALIDATE that the persisted checkpoint actually resumes coherently after a restart — NOT to flag missing persistence.** If resume works: PASS (persistence is engineered — frame it as such, cite `main.py:575`). If resume is broken *despite* AsyncSqliteSaver being wired, THAT is the finding (e.g. checkpoint written but not restored, thread_id lost, half-rendered UI) — and it's a recovery defect, gradeable on its real user impact, not an automatic CRITICAL. Hold the same "engineered vs emergent" line Phases 4–6 established.

---

**Phase 7 scenarios (from the playbook — container names CORRECTED to no-suffix):**

- **P7-S1 — Backend kill mid-stream**: Start a chat. Mid-stream: `docker kill embedinator-backend`. Wait 5s. `docker compose up -d backend`.
  Expected: on restart the conversation either resumes from the LangGraph checkpoint OR closes with a user-visible explanation — **NEVER half-rendered**. Resume window **≤30s post-restart**. Advanced: frontend-inspector may dispatch a sub-agent to run the `aget_state` snapshot check from `research.md` R3 (`config={"configurable":{"thread_id":"<id>"}}; snapshot = await graph.aget_state(config); assert snapshot is not None`).
- **P7-S2 — Ollama unavailable**: `docker stop embedinator-ollama`. Attempt a chat. Wait. `docker compose up -d ollama`.
  Expected: an actionable error within the timeout (`max_loop_seconds=300` hard cap; circuit-breaker cooldown 30s per `backend/config.py`). **No indefinite hang.** Chat resumes automatically when Ollama returns, or a clear retry prompt.
- **P7-S3 — Qdrant unavailable mid-ingestion**: Start ingesting a doc **into a throwaway scratch collection (HAZARD 2)**. Mid-ingestion: `docker stop embedinator-qdrant`. Wait 30s. `docker compose up -d qdrant`.
  Expected: ingestion pauses with a resume path OR fails with quarantine (doc moved to a failed state, retry possible). **NEVER silently dropped.** (Note: verify-6 already recorded BUG-110 — failed/terminal jobs never stamp `finished_at`; watch whether the interrupted job's terminal state is even observable.)
- **P7-S4 — Full stack restart with persistent data**: after P7-S1 + a chat + the P5-S1 key row exist: `docker compose down && docker compose up -d` (**NEVER `-v` — HAZARD 4**). Wait for 4/4 healthy. Open Chromium.
  Expected: collections, prior conversations, and settings (including the encrypted API key from P5-S1) all persist and are reachable.
- **P7-S5 — Checkpoint resume validation**: force-resume the interrupted chat from P7-S1; compare the resumed output against the pre-kill screenshot.
  Expected: checkpoint integrity preserved; resume is a coherent continuation (semantic match, not byte-equal — LLMs are nondeterministic). **AsyncSqliteSaver IS wired (`main.py:575`) — validate, do not false-CRITICAL (see section above).**

**P7-S1, S4, S5 are the STATE-INTEGRITY scenarios; P7-S2, S3 are the DEGRADED-DEPENDENCY scenarios.** The binding standard: a clean recovery only counts as a PASS if you can point at the code that engineers it; "it happened to come back" is emergent, not engineered — frame it that way.

---

**RESUME ORDER (after the reads):**
1. Verify `docker context show` = `default`, then stack 4/4 healthy on system GPU. Run `docker compose ps --format '{{.Name}}'` and **record the exact container names** (confirm no `-1` suffix) before any kill. Confirm `chrome-devtools` responds to a trivial call, but plan to drive P7 browser work through frontend-inspector/Playwright (HAZARD 1).
2. Re-spawn the 3 always-on teammates in ONE response (RECOVERY mode, per §1):
   - `log-analyst` (python-expert/sonnet) — on restart/recovery logs
   - `frontend-inspector` (frontend-architect/sonnet) — **must read `spawn/spawn-frontend-inspector.md` first**; **owns Playwright browser-driving this phase** (HAZARD 1), captures the P7-S1 pre-kill screenshot
   - `bug-registrar` (technical-writer/sonnet) — **SOLE writer to `bugs/`**, MUST tag every registration batch in `session-log.md` as `BugRegistrar | discovery`, never `Orchestrator | observation`. This held clean through Phase 6 even under the Lead-solo-browser method (verify-6 R-005-A PASS). **Do not let it regress.**
   Append `"RECOVERY MODE: read session-log.md before continuing"`. Wait for all 3 online + bug-registrar confirming **94 bugs / next-id BUG-118**.
3. Route the Phase-7-open phase-transition line to bug-registrar; brief me the P7 scenario card; run the relay loop (§2). Observation grammar: `observation: P7.S<M> — …`. Bug IDs from **BUG-118**.
4. Work P7-S1..S5. Before minting any ID, have bug-registrar **dedup-check against the existing 94** — several recovery findings may overlap known bugs (e.g. BUG-110 finished_at, BUG-055 latency/timeout territory, circuit-breaker BUG-099). Cross-reference, don't re-mint.
5. **First-phase carry-in housekeeping (do at close, one small registrar pass):** verify-6 left two stale-flag edits for the registrar — WARNING-1 (BUG-107 `## Notes` still says "UNCONFIRMED"; the verify-6 adjudication resolved it to **BY-DESIGN STUB**, git-confirmed reranker never bound) and SUGGESTION-3 (BUG-070 `## Actual`/`## Root-cause` fields still misaligned with its retraction Note). Bundle both as one `BugRegistrar` edit during the Phase-7 close. These are Notes/field edits to EXISTING bug files, still under the sole-writer rule — no new IDs.
6. Close Phase 7 (§3): findings schema-complete (real artifacts into the session dir; `title` ≤80 chars **excluding** the `BUG-1NN: ` prefix) → phase-transition entry (note **this is the final hunt phase → verify-7 next, then apply-8 closure**) → commit `docs/E2E/…` only → **MERGE** phase-7 into apply-progress preserving phases 0–6 → tell me to run **verify-7** (NOT apply-8; verify-7 is the gate, and apply-8 is additionally blocked on the 45-bug GitHub-issue-URL backfill: 1 BLOCKER + 8 CRITICAL + 36 MAJOR).

Respect the PROHIBITED list (lead-prompt.md): no production edits outside the BLOCKER-PATCHED gate (Pilot Y/N required); Makefile + `embedinator.sh` SACRED; no severity downgrades; never close with an unfiled CRITICAL or untriaged MAJOR.

**START** by reading the files (steps 1–4) and verifying docker context + stack + GPU + exact container names + chrome-devtools liveness, then give me a **5-line status** (docker context/GPU state, exact container names confirmed no-suffix, registry count = 94/next-id BUG-118, the P7 scenario list, and the resume point = P7-S1) and **WAIT for my "go"** before spawning teammates.
