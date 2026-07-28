# Resume apply-2 — Spec-30 Round-1 Bug Hunt (overnight pause 2026-06-10)

> **How to use (Pilot)**: re-attach the tmux session. In the Lead pane, if the previous Claude session
> is dead, launch `claude`, paste `docs/E2E/2026-05-28-round-1-bug-hunt/process/lead-prompt.md` FIRST (it is the
> contract), then say: **"read docs/E2E/2026-05-28-round-1-bug-hunt/process/resume-apply-2.md and resume apply-2"**.
> If the Lead session is still alive with context intact, just say "resume apply-2".

---

## 1. State at pause (2026-06-10 ~23:00 -03:00)

| Item | State |
|---|---|
| Phase 1 | ✅ CLOSED — commit `cff56ad`, 15 findings (BUG-024..038), verify-1 PASS (adjudicated) |
| Phase 2 (Ingestion, US2) | **OPEN — scenarios 0/6 exercised. Resume AT P2-S1** (Pilot paused before creating the collection) |
| Bugs registered | 16 total: BUG-024..BUG-039. `next-bug-id.txt` = **BUG-040** |
| BUG-039 (this phase) | MINOR — 3 orphaned qdrant collections (`emb-0bbcfc45`/`emb-9d465858`/`emb-0ea45e41`, 7083 stranded vectors, no cross-store atomicity, no GC). Found at entry baseline |
| Uncommitted | BUG-039 file + Phase-2 session-log entries are on disk, NOT committed (phase-2 commit happens at phase close per lead-prompt §3) |
| Team | `spec30-hunt` — config at `~/.claude/teams/spec30-hunt/config.json`. Panes likely dead after overnight; re-spawn per §3 below |

**Phase 2 entry baselines (locked, verified)**:
- SQLite: documents=73, ingestion_jobs=73, parent_chunks=1783
- Backend API: 19 collections, `hunt-pdfs` NOT present
- Qdrant: 22 collections (19 matched + 3 orphans = BUG-039)
- Expected P2-S1 delta: +1 document, +1 job, +X parent_chunks, +1 new `emb-*` namespace
- Corpus: `data/Collection-Docs/` (NAG-200.pdf confirmed present)

**Phase 2 errata (carry into scenarios)**:
- Playbook P2-S6 says `docker kill embedinator-backend-1` → actual container is `embedinator-backend` (no suffix; same for all services)
- Health endpoint is `/api/health` (NOT `/healthz`, which 404s)

---

## 2. Orchestrator resume steps (Lead — do these in order)

1. Run the PREFLIGHT block from lead-prompt.md (tmux, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, docker stack up, branch `030-e2e-test-v3`, playbook exists). If docker is down: Pilot runs `sudo systemctl start docker && ./embedinator.sh` (system engine, NOT Docker Desktop).
2. Read resume state (lead-prompt §0):
   - `mem_search(query: "sdd/single-round-bug-hunt/apply-progress", project: "the-embedinator")` → `mem_get_observation(id)` — confirms the CHECKPOINT "phase-2 in progress — PAUSED OVERNIGHT".
   - `tail docs/E2E/2026-05-28-round-1-bug-hunt/session-log.md` — last entry should be the overnight-pause observation.
3. Do NOT re-register BUG-024..BUG-039. Phase 2 resumes at **P2-S1**.
4. Re-spawn teammates per §3. Wait for all three online confirmations before any scenario.
5. Brief the Pilot with the Phase 2 scenario card (playbook `## Phase 2`, lines ~154-221) and run the relay loop per lead-prompt §2.

---

## 3. Team re-spawn protocol (with engram memory loading)

Check `test -f ~/.claude/teams/spec30-hunt/config.json` — it EXISTS, so SKIP TeamCreate. Re-spawn the three teammates (Agent tool, `team_name: "spec30-hunt"`, names below, **all `model: sonnet`**, roster locked R-005). Spawn all three in ONE response.

Each spawn prompt MUST include, in this order:
1. Identity + team + project root `<repo-root>`.
2. **"RECOVERY MODE: read session-log.md before continuing"** (per lead-prompt §1).
3. Read its instruction file (below), then `specs/030-e2e-test-v3/{spec,phase-playbook}.md`.
4. **Load its own engram memory**: `mem_search(query: "<topic_key below>", project: "the-embedinator")` → `mem_get_observation(id)` for the FULL content (search results are truncated). The memory contains its working methods AND "## Phase 2 state at pause".
5. Its access constraints (below) + "confirm online via ONE SendMessage to team-lead, then idle".

| Teammate | subagent_type | engram topic_key to load | instruction file | access |
|---|---|---|---|---|
| `log-analyst` | python-expert | `sdd/single-round-bug-hunt/team-context/log-analyst` | `docs/E2E/2026-05-28-round-1-bug-hunt/process/agents/A1-log-analyst-instructions.md` | read-only; captures → `/tmp/spec30-captures/` |
| `frontend-inspector` | frontend-architect | `sdd/single-round-bug-hunt/team-context/frontend-inspector` | `docs/E2E/2026-05-28-round-1-bug-hunt/process/agents/A2-frontend-inspector-instructions.md` | read-only; captures → `/tmp/spec30-captures/` (re-create dir + re-baseline: /tmp likely wiped) |
| `bug-registrar` | technical-writer | `sdd/single-round-bug-hunt/team-context/bug-registrar` | `docs/E2E/2026-05-28-round-1-bug-hunt/process/agents/A3-bug-registrar-instructions.md` | **SOLE writer** to `docs/E2E/2026-05-28-round-1-bug-hunt/` (R-005-A); confirms next ID = BUG-040 from `next-bug-id.txt` |

Standing discipline (re-state in every spawn prompt): analyst/inspector write NOTHING tracked — findings via SendMessage, captures to /tmp, registrar moves artifacts into the session dir. Never edit production code, Makefile, embedinator.sh/.ps1. No nested teams/agents. Bug registration only after Lead correlation ("register once, correctly").

---

## 4. Engram topic-key map (project: `the-embedinator`)

| Topic key | Content |
|---|---|
| `sdd/single-round-bug-hunt/apply-progress` | Canonical resume checkpoint (phase-0 ✓, phase-1 ✓, phase-2 paused) |
| `sdd/single-round-bug-hunt/discoveries-phase-1` | Phase-1 architecture findings (provider blind spot, health probe gap, CB 60s-by-design…) |
| `sdd/single-round-bug-hunt/team-context/{log-analyst,frontend-inspector,bug-registrar}` | Per-teammate working contexts + Phase-2 pause state |
| `sdd/single-round-bug-hunt/verify-report-phase-1` (#3444) + gate decision (#3445) | verify-1 PASS, adjudicated; carry-forwards |
| `sdd/single-round-bug-hunt/{spec,design,tasks,proposal,state}` | SDD planning artifacts (read-only reference) |

Carry-forwards from verify-1 (do not lose): (hard) verify-7 must enforce real GitHub issue URLs for all MAJOR+ before apply-8; (soft) true `-v` cold start re-run OR warm-measured caveat before LAUNCH-DECISION.md.

---

## 5. Phase 2 scenario card (Pilot reference)

| Scenario | Pilot action | Budget / fail criteria |
|---|---|---|
| P2-S1 | UI: create `hunt-pdfs`, upload `data/Collection-Docs/NAG-200.pdf` | ≤60s; status pending→parsing→chunking→indexing→ready, no skips; spot-check `curl localhost:8000/api/collections/hunt-pdfs/stats` |
| P2-S2 | Upload one each: PDF, MD, TXT | same machine, all queryable |
| P2-S3 | `head -c 100 data/Collection-Docs/NAG-200.pdf > /tmp/broken.pdf` → upload | readable error ≤10s; collection usable after |
| P2-S4 | `dd if=/dev/zero of=/tmp/oversized.pdf bs=1M count=101` → upload | clear cap error (100MB stated), not 500/silent |
| P2-S5 | Re-upload S1's PDF to same collection | documented duplicate policy; none surfaced in UI = MAJOR |
| P2-S6 | Start 10-50MB upload, within 2s `docker kill embedinator-backend`, wait 5s, `docker compose up -d backend` | no orphan blocks future uploads; recovery ≤30s. **Cross-check: analyst watches for fresh orphan emb-* namespace (BUG-039 mechanism live repro)** |

Observation grammar: `observation: P2.S<M> — <one sentence>`. Exit: all 6 exercised, ≥1 doc queryable, Pilot relays `observation: P2 closing — <N> findings; <M> documents queryable`.

— End of resume-apply-2.md
