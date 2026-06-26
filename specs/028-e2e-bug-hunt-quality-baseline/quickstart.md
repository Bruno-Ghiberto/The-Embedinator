# Quickstart: E2E Bug Hunt & Quality Baseline

**Feature**: spec-28
**Date**: 2026-04-23

How to run every part of this spec without re-reading the spec. Each section is independent — jump to what you need.

---

## Prerequisites (one-time)

- Linux or macOS (Windows users: use WSL).
- `docker` + `docker compose` v2 installed.
- `tmux` installed.
- Project cloned, `develop` up to date (at minimum `691bbad` post-PR #55).
- On branch `028-e2e-bug-hunt-quality-baseline`.
- `~/.claude` set up with Opus + Sonnet access.
- MCP servers available per the session requirements (see below).

---

## Spawn the tmux 4-pane layout

Run from the repo root:

```bash
tmux new-session -d -s spec28 -n main
tmux split-window -h -t spec28:main
tmux split-window -v -t spec28:main.0
tmux split-window -v -t spec28:main.1
tmux select-pane -t spec28:main.0
tmux attach -t spec28
```

Pane arrangement after the commands above:

```
┌────────────────┬────────────────┐
│ Pane 0:        │ Pane 2:        │
│ Orchestrator   │ Scribe         │
│ (Opus)         │ (Sonnet)       │
├────────────────┼────────────────┤
│ Pane 1:        │ Pane 3:        │
│ Test Runner    │ Log Watcher    │
│ (Sonnet)       │ (Sonnet)       │
└────────────────┴────────────────┘
```

In each pane, launch a Claude session with the intended model:

```bash
# Pane 0 — Orchestrator
claude --model claude-opus-4-7

# Pane 1 — Test Runner
claude --model claude-sonnet-4-6

# Pane 2 — Scribe
claude --model claude-sonnet-4-6

# Pane 3 — Log Watcher
claude --model claude-sonnet-4-6
```

Then in Pane 0 (the Orchestrator):

```
/speckit.implement "Read @docs/PROMPTS/spec-28-E2E-v01/28-implement.md"
```

This kicks off the session. The implement prompt will instruct the other panes via the user as the relay.

### MCP allocation per pane

The session requires specific MCP tools per pane. Ensure each pane's Claude has at minimum:

| Pane | Required MCPs |
|------|---------------|
| Orchestrator | sequential-thinking, engram, serena, gitnexus |
| Test Runner | playwright, chrome-devtools, docker |
| Scribe | rust-mcp-filesystem (or similar), gitnexus, serena |
| Log Watcher | docker, rust-mcp-filesystem (for tail_file / regex), browser-tools |

Ad-hoc (any pane): sonarqube, mcp-chart, context7.

---

## Run the stabilized Playwright suite locally

After Phase 1 stabilization:

```bash
# From repo root — the whole docker stack must be up first
docker compose up -d
# Wait until frontend is healthy (http://localhost:3001)

cd frontend
npm install  # only if deps changed
npm run e2e -- --reporter=line
```

Expected outcome: all specs pass. If any fail after Phase 1, that is a regression and should be filed as a bug (not silently ignored).

### Run a single spec file

```bash
cd frontend
npm run e2e -- tests/e2e/chat.spec.ts --reporter=line
```

### Inspect a failed trace

```bash
cd frontend
npx playwright show-trace test-results/chat-test-name/trace.zip
```

---

## Re-run the RAGAS baseline

**Prerequisites**: docker stack up, corpus ingested via the standard ingestion flow, the golden dataset exists at `docs/E2E/<YYYY-MM-DD>-bug-hunt/golden-qa.yaml`.

```bash
# Primer query (warms the stack — recommended for consistent baseline)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "NAG-200 diámetro mínimo", "collection_id": "default"}' | head -n 5

# Run the RAGAS harness (external runner per CLAUDE.md testing policy)
zsh scripts/run-tests-external.sh -n spec28-ragas tests/quality/test_ragas_baseline.py

# Poll status
cat Docs/Tests/spec28-ragas.status   # RUNNING | PASSED | FAILED | ERROR

# Read summary (~20 lines)
cat Docs/Tests/spec28-ragas.summary

# Read full log if needed
less Docs/Tests/spec28-ragas.log
```

The harness writes results to `docs/E2E/<YYYY-MM-DD>-bug-hunt/quality-metrics.md` on completion. A `FAILED` status means the file write failed, not that the scores are bad (scores are informational, never gating).

### Judge LLM choice at run time

The harness supports two judge LLM options via environment variable:

```bash
# Default: local Ollama (self-bias risk, documented in quality-metrics.md)
RAGAS_JUDGE=local zsh scripts/run-tests-external.sh -n spec28-ragas tests/quality/test_ragas_baseline.py

# Opt-in: cloud judge (neutral; requires an API key already configured)
RAGAS_JUDGE=openrouter zsh scripts/run-tests-external.sh -n spec28-ragas tests/quality/test_ragas_baseline.py
```

The cloud judge run is reproducible by anyone with an API key — the baseline's Reproduction section names the judge used.

---

## Reproduce a specific bug from `bugs-raw/` cold

Every bug file in `docs/E2E/*/bugs-raw/` has a `## Steps to Reproduce` section. To reproduce:

```bash
# 1. Check out the session's starting commit
cat docs/E2E/<session-dir>/session-log.md | grep "git head:" | head -n 1
# e.g. "git head: 691bbad"

git checkout 691bbad

# 2. Bring up the stack
docker compose up -d

# 3. Follow the bug's Steps to Reproduce section verbatim
cat docs/E2E/<session-dir>/bugs-raw/BUG-XXX-short-slug.md

# 4. Compare your observed behavior to the bug's "Actual" line
# 5. If it reproduces, you have a valid starting point for the fix
# 6. If it does not reproduce, note why and file a comment on the bug markdown
```

For bugs with Playwright traces:

```bash
cd frontend
npx playwright show-trace ../docs/E2E/<session-dir>/traces/BUG-XXX.zip
```

---

## Fault-injection preflight checklist

Before Phase 4, the Orchestrator runs this checklist with the user. Each item must be checked off.

- [ ] **I have saved any open work against the local stack** (uncommitted code, open browser sessions, etc.).
- [ ] **No other processes are actively reading or writing the SQLite DB, Qdrant volumes, or Ollama model files** (`lsof data/embedinator.db` returns empty; no external tools using the stack).
- [ ] **I acknowledge the listed scenarios will kill containers and may briefly leave the stack in a broken state** until the relevant container is restarted.
- [ ] **Container names are verified** (`docker compose ps --format json` matches the catalog).
- [ ] **(Optional) I have taken a volume snapshot** if I want extra safety beyond the container-level isolation:
  ```bash
  docker run --rm -v embedinator_qdrant-data:/data -v $(pwd):/backup alpine tar czf /backup/qdrant-pre-injection.tgz -C /data .
  cp data/embedinator.db data/embedinator-pre-injection.db
  ```
- [ ] **Branch is `028-e2e-bug-hunt-quality-baseline`** (`git rev-parse --abbrev-ref HEAD`).

Once all items check, the Test Runner may issue the first fault command.

---

## The fault-injection commands

Mandatory (FI-01 to FI-03):

```bash
# FI-01: Ollama killed mid-stream
# Start a chat stream in the UI; while it's streaming, run:
docker kill embedinator-ollama-1
# Observe UI behavior. After observation, restart:
docker compose start ollama

# FI-02: Qdrant down at query time
docker stop embedinator-qdrant-1
# Submit a query in the UI. Observe behavior. Restart:
docker compose start qdrant

# FI-03: Backend crash mid-stream
# Start a chat stream in the UI; while streaming, run:
docker kill embedinator-backend-1
# Observe UI behavior. Restart:
docker compose start backend
```

Opportunistic (FI-04, FI-05 — run only if the mandatory three complete in under 45 minutes):

```bash
# FI-04: Docker network partition
docker network disconnect embedinator_default embedinator-ollama-1
# Submit a query. Observe. Reconnect:
docker network connect embedinator_default embedinator-ollama-1

# FI-05: LLM context-length exceeded
# Paste the full NAG-200 text into the chat input. Observe whether the UI
# truncates, errors clearly, or 500s. No cleanup needed — refresh the page.
```

Each scenario's outcome is recorded in `scenarios-executed.json` via the append-on-scenario rule (see session-directory-contract.md).

---

## The F/D/P gate — what to expect

When a Blocker-severity bug surfaces in Phase 3 (exploratory), the Orchestrator prompts:

```
[ORCHESTRATOR — F/D/P GATE]
BUG-XXX surfaced: <one-line summary>
Severity: Blocker
Layer: <layer>
Discovered via: <channel>

Decision needed:
  [F]ix now — pause the current activity, fix in-session, commit, continue
  [D]efer  — log, tag "defer to v1.1", continue immediately
  [P]ause+investigate — 15-minute timeboxed investigation; must resolve to F or D

Your choice [F/D/P]:
```

Answer with a single letter. For `F`, be prepared to pause exploration and cycle through: understand the bug, write a regression test if feasible, make the fix, commit, and resume. For `D`, give a one-sentence rationale so Phase 6 can promote or not promote to GitHub issue. For `P`, the Orchestrator will return with investigation findings after 15 minutes and re-prompt for F or D — you cannot P twice on the same bug.

Full contract: [contracts/fdp-gate-contract.md](./contracts/fdp-gate-contract.md).

---

## Phase 6 wrap-up commands

At session close, the Orchestrator runs (in pane 1):

```bash
# Aggregate bugs
# (done by the Orchestrator directly — produces bugs-found.md)

# Render severity treemap via mcp-chart MCP
# (done by the Orchestrator via the mcp-chart tool, output embedded into SUMMARY.md)

# Verify Makefile unchanged
git diff develop -- Makefile
# expect: (empty output)

# Verify SACRED files unchanged
git diff develop -- embedinator.sh embedinator.ps1
# expect: (empty output)

# Promote Blockers to GitHub issues
for bug in docs/E2E/<dir>/bugs-raw/BUG-*.md; do
  if grep -q "^- \*\*Severity\*\*: Blocker" "$bug" && \
     grep -q "^- \*\*F/D/P decision\*\*: D" "$bug"; then
    title=$(head -n 1 "$bug" | sed 's/^# //')
    gh issue create \
      --title "$title" \
      --body "$(cat "$bug")" \
      --label "bug,severity:blocker,from:spec-28" \
      --milestone "v1.0.0"
  fi
done

# Add SUMMARY.md link to README
echo "- [Spec-28 Bug Hunt Summary](docs/E2E/$(date -u +%F)-bug-hunt/SUMMARY.md)" >> README.md
```

---

## Troubleshooting

### Playwright suite hangs on a single test
Check `docker compose ps` — the backend or frontend container may have died. Restart with `docker compose restart`.

### RAGAS harness returns `nan` for many pairs
The backend is returning empty responses — check `docker compose logs backend`. Out-of-scope pairs returning `nan` on retrieval metrics is expected; `nan` on all pairs indicates a config issue.

### Tmux pane crashed mid-session
The panes are independent. Losing pane 2, 3, or 4 is recoverable: re-launch Claude in the pane with the same model. Pane 1 loss is more serious — the F/D/P queue is in that pane's context; recovery requires reading `session-log.md` to re-establish open gates.

### Session ran out of the 4-hour budget
Per spec Edge Case: close intake at 4h, spend remaining time triaging open Blockers via F/D/P. No new exploration after the clock.

### Found a bug that the session process itself caused (e.g., the tmux spawn or an MCP tool)
File it. Layer: Infrastructure. Severity: Minor unless it actively blocks the session, in which case Blocker. These meta-bugs are informative for future spec-28 re-runs.

---

## Post-session expectations

- `docs/E2E/<YYYY-MM-DD>-bug-hunt/SUMMARY.md` exists and is linked from `README.md`.
- Every Blocker has either a GitHub issue or an explicit defer rationale.
- The Playwright suite is green on `develop` HEAD at close.
- `git diff develop -- Makefile` is empty.
- Branch `028-e2e-bug-hunt-quality-baseline` is ready for PR review.

If any of these is not true, the session has not closed. Go back to the relevant phase and finish it.
