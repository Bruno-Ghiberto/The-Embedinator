# Spec-30 Round-1 Bug Hunt — SDD-Native Lead Prompt (phase-scoped)

> **How to use**: Paste this entire file into the Lead Claude pane at the start of EACH live apply
> run (apply-1 … apply-7). **Do NOT type `/sdd-apply`** — execute THIS prompt directly; the Pilot
> names the phase number to begin. It is PHASE-SCOPED: the Pilot tells you the phase number; you drive
> exactly that one hunt phase, then close it. apply-0 (bootstrap) and apply-8 (closure) do NOT use this
> prompt — they run in a plain Claude context against the per-phase apply playbook in the design artifact.
>
> Recommended: `/model opus` + max thinking in this pane. Opus is for synthesis, BLOCKER-PATCHED
> judgment, and plan-approval calls. Teammates run on Sonnet (except `root-cause-investigator` = Opus).
>
> Official Agent Teams reference (read if unfamiliar): https://code.claude.com/docs/en/agent-teams
> Authoritative spec: `specs/030-e2e-test-v3/spec.md` + `phase-playbook.md` (read-only).
> SDD contract: spec `sdd/single-round-bug-hunt/spec` (R-001..R-006). Resume state lives in engram topic
> `sdd/single-round-bug-hunt/apply-progress`.

---

## 0. First action EVERY run: read resume state (R-004-C)

> **Invocation**: This prompt is EXECUTED DIRECTLY by the Lead pane — there is NO `/sdd-apply` slash
> command. Typing `/sdd-apply` loads a delegate-only code-executor skill (with a Strict-TDD gate) that
> will derail the hunt. The Pilot simply names the phase number; you run the steps below. Verify gates
> run as delegated `sdd-verify` sub-agents from an orchestrator session — never typed in a pane.

Before dispatching ANY teammate:

1. `mem_search(query: "sdd/single-round-bug-hunt/apply-progress", project: "the-embedinator")` → if found,
   `mem_get_observation(id)`. This tells you the last completed phase + last observed scenario.
2. Read `docs/E2E/2026-05-28-round-1-bug-hunt/session-log.md` (tail) to confirm the last `phase-transition`
   entry and any in-flight observations.
3. Determine YOUR phase number N from the Pilot's directive (e.g. "run apply-3 / Phase 3 / US3").
4. If apply-progress shows phase N already partially done, resume from the last recorded scenario — do NOT
   re-register bugs already in `bugs/`. If it shows phase N not started, begin at its first scenario.

The session directory `docs/E2E/2026-05-28-round-1-bug-hunt/` is FIXED (R-003). Never create or continue
`docs/E2E/2026-05-15-round-1-bug-hunt/` (dormant, historical only).

---

```text
╔═══════════════════════════════════════════════════════════════════════════════╗
║  PROHIBITED (lifted verbatim from 30-implement.md — invariant)                ║
║    - Production code edits outside the BLOCKER-PATCHED narrow exception       ║
║      (≤5min, zero-risk, MINOR/COSMETIC scope, Pilot Y/N confirmed) — FR-010   ║
║    - Autonomous BLOCKER-PATCHED fixes without explicit Pilot Y/N in pane 2    ║
║      (FR-011, SC-005)                                                         ║
║    - Promoting any screenshot/log to `public-evidence/` without verifying     ║
║      no secrets/PII visible AND documenting the verification (FR-028, SC-012) ║
║    - Severity downgrade because a BLOCKER-PATCHED fix was applied (FR-013)    ║
║    - Closing the hunt with unfiled CRITICALs or untriaged MAJORs (FR-014,     ║
║      FR-015)                                                                  ║
║    - Starting the fix wave (spec-31) before this hunt's registry closes       ║
║      (Assumption A-004)                                                       ║
║    - Editing Makefile (SACRED — spec-17 + spec-19 contracts)                  ║
║    - Editing embedinator.sh / embedinator.ps1 (SACRED — spec-19 contract)     ║
║    - Re-baselining chat answer correctness — out of scope (Assumption A-003)  ║
║    - Spawning nested teams from teammates (forbidden by Agent Teams)          ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

```text
╔═══════════════════════════════════════════════════════════════════════════════╗
║  PREFLIGHT (lifted verbatim from 30-implement.md — run before team work)       ║
║    $ [ -n "$TMUX" ] || { echo "ERROR: must be inside tmux"; exit 1; }         ║
║    $ env | grep -q CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 \                   ║
║        || { echo "ERROR: Agent Teams flag not set"; exit 1; }                 ║
║    $ docker compose ps | grep -E 'qdrant|ollama|backend|frontend' \           ║
║        || { echo "ERROR: docker stack must be up before cold-start phase";    ║
║             echo "(Phase 1 will bring stack down then up; this only checks    ║
║             baseline readiness)"; exit 1; }                                   ║
║    $ git rev-parse --abbrev-ref HEAD | grep -q "^030-e2e-test-v3$" \          ║
║        || { echo "ERROR: must be on 030-e2e-test-v3 branch"; exit 1; }        ║
║    $ test -f specs/030-e2e-test-v3/phase-playbook.md \                        ║
║        || { echo "ERROR: phase-playbook.md must exist (created in plan)";     ║
║             exit 1; }                                                          ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

If the Agent Teams flag check fails OR the team cannot spawn, fall back to **Inline mode** (§6).

---

## 1. Team lifecycle (every apply run — teammates always re-spawn per apply session)

> **Claude Code v2.1.178+**: `TeamCreate` and `TeamDelete` no longer exist. The `Agent` tool IS the
> Agent Teams spawning mechanism when `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is set. With that flag,
> `Agent` calls create proper teammates — each gets its own tmux pane (when `teammateMode: "tmux"`),
> shares the task list, and communicates via `SendMessage`. This is **not** the same as plain subagents,
> which only report back to the caller and have no inter-agent messaging. The `team_name` parameter is
> accepted by the Agent tool but silently ignored; do not pass it.
>
> Team config is session-derived and **removed when the session ends** — teammates do not persist across
> Lead restarts. Spawn all 3 teammates at the start of EVERY apply run. There is no "reuse" across
> apply-1..7; re-spawn is always required.

Spawn the 3 always-on teammates in **ONE response** (three `Agent` tool calls in the same message).
Each reads its spawn doc FIRST, confirms online via `SendMessage(to: "team-lead", ...)`, then idles.

| Teammate | `subagent_type` | `model` | access | spawn doc |
|---|---|---|---|---|
| `log-analyst` | `python-expert` | `sonnet` | read-only | `docs/E2E/2026-05-28-round-1-bug-hunt/process/spawn/spawn-log-analyst.md` |
| `frontend-inspector` | `frontend-architect` | `sonnet` | read-only | `docs/E2E/2026-05-28-round-1-bug-hunt/process/spawn/spawn-frontend-inspector.md` |
| `bug-registrar` | `technical-writer` | `sonnet` | **sole writer to `bugs/`** | `docs/E2E/2026-05-28-round-1-bug-hunt/process/spawn/spawn-bug-registrar.md` |

**Spawn pattern** (three calls in ONE response — parallelism is the point):
```
Agent(
  name: "log-analyst",
  subagent_type: "python-expert",
  model: "sonnet",
  prompt: "You are `log-analyst` on team `spec30-hunt`. Project root: <repo-root>. Your team-lead is named `team-lead`. Read docs/E2E/2026-05-28-round-1-bug-hunt/process/spawn/spawn-log-analyst.md FIRST and follow it exactly — it is your boot contract."
)
Agent(
  name: "frontend-inspector",
  subagent_type: "frontend-architect",
  model: "sonnet",
  prompt: "You are `frontend-inspector` on team `spec30-hunt`. Project root: <repo-root>. Your team-lead is named `team-lead`. Read docs/E2E/2026-05-28-round-1-bug-hunt/process/spawn/spawn-frontend-inspector.md FIRST and follow it exactly — it is your boot contract."
)
Agent(
  name: "bug-registrar",
  subagent_type: "technical-writer",
  model: "sonnet",
  prompt: "You are `bug-registrar` on team `spec30-hunt`. Project root: <repo-root>. Your team-lead is named `team-lead`. Read docs/E2E/2026-05-28-round-1-bug-hunt/process/spawn/spawn-bug-registrar.md FIRST and follow it exactly — it is your boot contract."
)
```

Roster is LOCKED (R-005). No additions, removals, or model swaps. `bug-registrar` is **Sonnet** (the
2026-05-15 Haiku registrar aborted — schema-fidelity failure). Since teammates do not survive a Lead
restart, always re-spawn all 3 at the start of each apply run. If a specific pane dies mid-phase,
re-spawn only that teammate with `"RECOVERY MODE: read session-log.md before continuing"` appended
to its prompt.

---

## 2. Per-phase relay loop (the core of every apply-1..7 run)

You drive exactly ONE phase. Find its scenarios in `specs/030-e2e-test-v3/phase-playbook.md` under
`## Phase N`. The Pilot executes browser/docker actions in their pane and types observations to you.

**Observation grammar** (from the playbook):
```
observation: P<N>.S<M> — <one-sentence description>
```

**Dispatch decision tree** for each `observation:` line:

1. **Echo to session-log FIRST**:
   `SendMessage(to: "bug-registrar", summary: "log observation",
   message: "Append to session-log.md: [<ISO-8601 now>] Pilot | observation | <verbatim text>")`
2. **Backend/log signal** (`/healthz`, 5xx, timeout, "console", stacktrace, "error"):
   `SendMessage(to: "log-analyst", ...)` with the observation + a time-window correlation request.
3. **Frontend/UI signal** (render, hover, stall, layout, citation, scroll, click):
   `SendMessage(to: "frontend-inspector", ...)` with a DOM/console/network capture request.
4. **Both plausible** → dispatch log-analyst AND frontend-inspector in the SAME response (two
   `SendMessage` calls — async parallelism is the point; do not serialize).
5. **Unambiguous / Pilot says "register"** → route bug fields straight to `bug-registrar`
   (per `data-model.md` Entity 1; `bugs-registry-schema.json` is the field contract).
6. **Both report "no evidence" / cross-layer** → spawn on-demand `root-cause-investigator`
   (root-cause-analyst, Opus, RO) per A4; route its hypothesis to bug-registrar; then `shutdown_request` it.
7. **Severity BLOCKER, hunt cannot continue** → enter §5 BLOCKER-PATCHED gate.

**Wait for teammate findings before registering.** Register once, correctly, after correlation — never
pre-register and amend. The `bug-registrar` is the ONLY writer to `docs/E2E/2026-05-28-round-1-bug-hunt/`
(R-005-A); analyst + inspector emit findings via `SendMessage`, they write nothing tracked.

Bug IDs start at **BUG-024** (R-003). `bug-registrar` reads `next-bug-id.txt`, allocates, increments it
atomically before committing the bug file.

---

## 3. Phase close (end of every apply-1..7 run)

When all the phase's playbook scenarios are exercised (or explicitly marked "not reached" with
justification):

1. Confirm every finding this phase has: severity, ≥1 reproduction step, ≥1 non-null artifact path
   (`screenshots/` | `logs/` | `traces/`). CRITICAL/MAJOR with a missing field WILL fail the verify gate.
2. Write the phase-transition entry:
   `SendMessage(to: "bug-registrar", message: "Append to session-log.md: [<ISO-8601 now>]
   Orchestrator | phase-transition | Phase N closed → Phase N+1 ready. <K> findings registered:
   <BUG-IDs + severities>.")`
3. Commit the phase close (lead-owned Bash):
   `git add docs/E2E/2026-05-28-round-1-bug-hunt/ && git commit -m "chore(spec-30-r1): close hunt phase N — <K> findings"`
4. **Save resume state** — `mem_save` with `topic_key: "sdd/single-round-bug-hunt/apply-progress"`,
   `type: "architecture"`, `project: "the-embedinator"`, `capture_prompt: false`. Content MUST record:
   phase number, scenario count observed, bug IDs registered this run, final session-log entry timestamp,
   and the line `CHECKPOINT: phase-N complete` (R-001-A). MERGE with prior apply-progress — do not
   overwrite earlier phases.
5. Tell the Pilot: "Phase N closed, K findings. apply-N done — run the verify-N gate as a delegated
   `sdd-verify` sub-agent from an orchestrator session, then launch apply-N+1 by re-pasting this prompt."

Do NOT advance to phase N+1 in this run. Each apply is one phase. The verify gate (R-002) runs between.

---

## 4. Teammate lifecycle between apply runs

Teammates are tied to the Lead session. When the Lead session ends (phase close, crash, or restart),
teammates terminate and the team config is removed automatically — no `TeamDelete` needed or available
(removed in v2.1.178). At the start of the NEXT apply run, re-paste this prompt and re-spawn all 3
teammates per §1.

If the Lead session crashes mid-phase: re-attach tmux → re-launch `claude` inside tmux → re-paste THIS
prompt → name phase N again to the Lead (no `/sdd-apply`) → §0 reads apply-progress + session-log to
resume → §1 re-spawns teammates.

---

## 5. BLOCKER-PATCHED gate (official plan_approval primitive)

Fires ONLY when ALL are true: severity BLOCKER · hunt cannot continue · a ≤5-min, zero-risk,
MINOR/COSMETIC fix exists · the bug is ALREADY registered in `bugs/` (FR-013). If any fails: register the
BLOCKER, descope or close the phase per FR-015 — do NOT spawn a fixer.

1. **Spawn `inline-fixer`** (architect/Sonnet, write-only, on-demand) with
   `"Require plan approval before making any changes."` Its plan must state: exact file path, diff sketch
   ≤20 lines, scope (MINOR|COSMETIC), time (≤5 min), zero-risk argument. It submits a `plan_approval_request`.
2. **Reformat** the plan into the verbatim `data-model.md` Entity 5 / `blocker-patched-gate-contract.md`
   template, display in THIS pane, and ask the Pilot `Y / N`.
3. **On Pilot Y**: log the gate Y entry via bug-registrar, then
   `SendMessage(to: "inline-fixer", message={type: "plan_approval_response", request_id: <id>, approve: true})`.
   **Pass `message` as a DICT, never a JSON-stringified string** — serialising it silently breaks the gate.
   After the fixer reports its commit SHA, tell bug-registrar to set `blocker_patched.applied=true`,
   `commit_sha`, `pilot_authorization_timestamp` (= the Pilot Y line timestamp), `patch_summary`.
   Severity STAYS BLOCKER (FR-013).
4. **On Pilot N**:
   `SendMessage(to: "inline-fixer", message={type: "plan_approval_response", request_id: <id>, approve: false, feedback: "<rationale>"})`,
   log the N entry, leave severity BLOCKER. Decide: descope the phase or close the hunt early.
5. **Shutdown the fixer** after the episode (Y or N):
   `SendMessage(to: "inline-fixer", message={type: "shutdown_request", reason: "BLOCKER-PATCHED closed for BUG-XXX"})`.
   Future episodes spawn a fresh fixer.

---

## 6. Shape-D fallback — inline mode (A-007)

If `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is unavailable, the flag breaks, or the team cannot spawn:
collapse to **inline execution**. You (the Lead) personally run log analysis and frontend inspection — no
async teammates. You write bug files, session-log entries, and `next-bug-id.txt` yourself, following the
same `data-model.md` schemas and the same per-phase relay/close steps (§2–§3). The BLOCKER-PATCHED gate
becomes a direct edit after Pilot Y (still log it, still set `blocker_patched` fields, still no downgrade).
Async parallelism is lost; correctness and the registry contract are preserved. Note the degradation in the
session-log opening entry of the affected phase.

---

## 7. References

- Spec (authoritative): `specs/030-e2e-test-v3/spec.md`, `phase-playbook.md`, `data-model.md`,
  `quickstart.md`, `contracts/{bug-registry-schema.json,session-directory-contract.md,blocker-patched-gate-contract.md}`
- SDD contract: engram `sdd/single-round-bug-hunt/spec` (R-001..R-006), `…/design` (apply playbook)
- Resume state: engram `sdd/single-round-bug-hunt/apply-progress`
- Roster instruction files: `docs/E2E/2026-05-28-round-1-bug-hunt/process/agents/A1-A5-*.md`
- Project standards: `CLAUDE.md` (auto-loaded by Lead + every teammate)

— End of lead-prompt.md.
