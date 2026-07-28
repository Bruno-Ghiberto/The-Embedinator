# Quickstart — Spec-30 Bug Hunt Operational Guide

**Spec**: 030-e2e-test-v3
**Audience**: Pilot (and future Pilots running this methodology)
**Phase**: 1

How to spawn the 5-pane tmux layout, run preflight, invoke `/speckit.implement`, relay observations to the lead, and close the registry. This is the Pilot's session-start runbook.

---

## Prerequisites

Verify before starting:

```bash
git rev-parse --abbrev-ref HEAD                       # → 030-e2e-test-v3
docker compose ps                                     # → 4 services Healthy
test -f specs/030-e2e-test-v3/phase-playbook.md       # → exists
test -f specs/030-e2e-test-v3/plan.md                 # → exists
test -f specs/030-e2e-test-v3/contracts/bug-registry-schema.json  # → exists
gh auth status                                        # → logged in (for Phase 8 issue creation)
which convert magick                                  # → /usr/bin/{convert,magick} (ImageMagick)
which jsonschema 2>/dev/null || python -c "import jsonschema"  # → schema validator available
```

Block any failure before continuing. Missing `gh` auth blocks Phase 8 step 1. Missing ImageMagick blocks Phase 8 step 2. Missing playbook blocks Phase 0.

---

## Spawning the 5-pane tmux layout

The 5-pane layout MUST exist before invoking `/speckit.implement`. Pilot spawns it manually.

```bash
# Create the session and split into 5 panes:
tmux new-session -d -s spec30
tmux split-window -h -t spec30          # 2 panes: 1 | 2
tmux split-window -v -t spec30:0.1      # 3 panes: 1 | 2 over 3
tmux split-window -v -t spec30:0.0      # 4 panes: 1 over 4 | 2 over 3
tmux split-window -h -t spec30:0.3      # 5 panes — adjust geometry per preference
tmux attach -t spec30
```

Suggested geometry:

```
┌──────────────────┬──────────────────┐
│                  │                  │
│   Pane 1: Pilot  │ Pane 2: Lead     │
│   (browser +     │ (this Claude,    │
│    terminal)     │  Opus, Teams)    │
│                  ├──────────────────┤
│                  │ Pane 3: Log Anly │
├──────────────────┼──────────────────┤
│  Pane 4: FE Insp │ Pane 5: Bug Reg. │
└──────────────────┴──────────────────┘
```

Confirm: `tmux list-panes | wc -l` → 5.

---

## Running the hunt — pane-by-pane

### Pane 1 — Pilot (you, the human)

You stay in your normal shell. Your tools:

- Real Chromium browser (open `localhost:3000`).
- Terminal for `docker compose` lifecycle, `gh` commands, `git` checks.
- Chrome DevTools (F12) for manual frontend inspection.
- A second monitor or split for `session-log.md` open in your editor (read-only — Bug Registrar writes it).

You do NOT run a Claude instance in pane 1. You may launch ad-hoc claude sessions for narrow tasks (e.g., generating a redaction command), but the persistent agents live in panes 2–5.

### Pane 2 — Lead (always-on)

In pane 2, start a Claude session and run:

```text
/speckit.implement
```

The implement command reads `specs/030-e2e-test-v3/spec.md`, `plan.md`, `tasks.md`, `phase-playbook.md` and runs the Agent Teams lead protocol described in `docs-Bruno/PROMPTS/spec-30-E2E-test-v3/30-implement.md`. The lead will:

1. Run the Phase 0 preflight script (per enforcement banner in plan.md).
2. Create the dated session directory per `contracts/session-directory-contract.md`.
3. Prompt YOU (Pilot, pane 1) to begin Phase 1.
4. Dispatch sub-agents to panes 3–5 as observations come in.
5. Gate at BLOCKER-PATCHED proposals (per `contracts/blocker-patched-gate-contract.md`).
6. Manage phase transitions until Phase 8 closes the registry.

### Panes 3, 4, 5 — on-demand sub-agents

Panes 3–5 sit idle until the lead dispatches a sub-agent. When it does, you'll see the Claude instance start in the assigned pane, do its work, and return. Between dispatches, the pane is empty.

You do NOT manually start claude sessions in panes 3–5 unless explicitly recovering from a session crash.

---

## Pilot relay protocol — how you tell the lead what you see

You drive the browser. The lead doesn't have eyes. Relay observations to pane 2 in a structured way so the lead can dispatch the right sub-agent.

### Relay template

In pane 2, type a single line message:

```
observation: <phase>.<scenario> — <one-sentence what you see>
```

Example:
```
observation: P1.S1 — Dashboard health badge green but /healthz returns 503 for backend
observation: P3.S2 — Citation hover stalls 4s+ on Spanish accents; console shows undefined property
observation: P5.S1 — Added fake key; sidebar shows "OpenAI · Configured" but next chat 401s
```

The lead:
1. Echoes your observation into `session-log.md` with category `observation`.
2. Decides whether to dispatch Log Analyst, Frontend Inspector, both, or jump straight to Bug Registrar.
3. Returns to you with the next step (continue scenario, capture additional artifact, or "we have enough — registering bug").

### When the lead wants something from you

Watch pane 2 for prompts. The most consequential is the BLOCKER-PATCHED gate. Per `contracts/blocker-patched-gate-contract.md`:

- The lead shows you a full patch proposal with file paths, scope, time estimate, risk justification.
- Your response is exactly `Y` or `N` (optional `— <one-line rationale>`).
- The lead will NOT proceed without your response.
- Take your time. The 12h budget pauses during gate deliberation.

### Capturing screenshots and traces yourself

Per `contracts/session-directory-contract.md`, you (Pilot) capture screenshots; Frontend Inspector annotates them. To capture:

```bash
# Screenshot via OS tool (Fedora: GNOME Screenshot, flameshot, etc.)
flameshot full -p docs/E2E/<DATE>-round-1-bug-hunt/screenshots/BUG-XXX.png

# OR via Chrome DevTools: F12 → Cmd Palette (Ctrl+Shift+P) → "Capture full size screenshot"
mv ~/Downloads/screenshot.png docs/E2E/<DATE>-round-1-bug-hunt/screenshots/BUG-XXX.png

# DevTools trace:
# F12 → Performance → record → reproduce → stop → save profile to traces/BUG-XXX.trace.zip
```

Tell pane 2: `observation: P<N>.S<M> — screenshot saved to screenshots/BUG-XXX.png`.

---

## Phase 8 — closing the registry

When Phase 7 exits, the lead runs Phase 8 closure (per `contracts/session-directory-contract.md` and `data-model.md`). Your involvement:

### Step 1 — Triage decisions

For every MAJOR-or-higher bug, the lead presents:

```
BUG-XXX (CRITICAL, Frontend, P3-S2): <title>
  Triage [v1.0-fix / v1.1-defer]?
```

You answer with the decision plus a one-line rationale. Lead runs `gh issue create` per the configuration in `research.md` R2.

### Step 2 — Public-evidence curation

For every CRITICAL bug and selected MAJOR bugs, the lead asks you to review the captured artifacts. For each:

1. Open the screenshot/log in question.
2. Identify any secrets (API keys, decrypted credentials, PII).
3. If clean: copy to `public-evidence/` and tell pane 2 "promoted clean: <path>".
4. If contains secrets: redact via:

```bash
# Black rectangle over a secret region
convert screenshots/BUG-XXX.png \
  -fill black -draw "rectangle X1,Y1 X2,Y2" \
  public-evidence/BUG-XXX-redacted.png

# For log files: open in editor, replace each secret with [REDACTED], save as:
# public-evidence/BUG-XXX-log-snippet.md (paste-only, NOT a symlink)
```

5. Tell pane 2: `secret-scan-verify: BUG-XXX promoted to public-evidence/BUG-XXX-redacted.png; redacted region [X1,Y1]-[X2,Y2]; verified no other secrets`.

The lead writes the `secret-scan-verify` session-log entry verbatim.

### Step 3 — Summary peer review

The lead drafts `SUMMARY.md`. Per SC-007, a non-technical reviewer must be able to read it cold. Either:

- You ask a non-technical friend / family member to read it and report comprehensibility.
- You self-review by reading the SUMMARY cold an hour later without referencing other artifacts.

Tell pane 2: `summary-peer-review: <pass/fail> — <attestation note>`.

### Step 4 — Final SC checks

The lead runs:

```bash
# SC-006: zero production code touched outside BLOCKER-PATCHED
git diff develop -- backend/ frontend/ ingestion-worker/

# SC-012: zero secrets in tracked artifacts
rg -i 'sk-(test|live|proj)|api[_-]?key\s*=' docs/E2E/<DATE>-round-1-bug-hunt/ \
  --glob '!logs/' --glob '!screenshots/' --glob '!traces/'

# SC-008: bug registry schema-valid
python -c "import json, jsonschema; \
  data = json.load(open('docs/E2E/<DATE>-round-1-bug-hunt/bugs-registry.json')); \
  schema = json.load(open('specs/030-e2e-test-v3/contracts/bug-registry-schema.json')); \
  jsonschema.validate(data, schema); print('VALID')"
```

Each must pass. Any failure: lead pauses, surfaces the issue to pane 2, awaits your direction.

### Step 5 — README link + commit

Lead updates `README.md` with one link line; commits everything; tells you the SHA.

You stop.

---

## Recovering from a pane crash

If a Claude instance in pane 2–5 crashes mid-hunt:

1. **Pane 2 (lead)**: Re-launch Claude in the same pane, paste `30-implement.md` again, run `/speckit.implement` — the lead reads `session-log.md` and the in-flight artifacts to recover state (see §"Recovery from Crashes" in `30-implement.md` for the full team-recreation steps).
2. **Panes 3–5 (on-demand)**: No action needed. The next lead dispatch will spawn a fresh agent in the assigned pane.

If your terminal (pane 1) crashes: ssh/tmux re-attach with `tmux attach -t spec30`. Your browser session in a separate window is unaffected.

---

## Common pitfalls

- **Spawning the lead outside tmux**: the Phase 0 preflight `[ -n "$TMUX" ]` check will fail. Always attach to the tmux session before invoking `/speckit.implement`.
- **Skipping the playbook check**: the lead preflight verifies `phase-playbook.md` exists. Don't try to start the hunt without it.
- **Multiple observation relays in one message**: lead parses one observation at a time. Send each on its own message.
- **Trying to fix a bug yourself outside BLOCKER-PATCHED**: violates FR-010 + SC-006. If you're tempted, ask the lead to register the bug; spec-31 will fix it. The discipline insight is non-negotiable.
- **Closing the hunt with un-triaged MAJOR findings**: FR-015 blocks closure. Lead will refuse Phase 8 step 9 commit until triage complete.

---

## What "done" looks like

When you see this in pane 2:

```
[<ISO-8601>] Lead | closure-step | Hunt closed.
   BLOCKER: 0 / CRITICAL: X / MAJOR: Y / MINOR: Z / COSMETIC: W
   v1.0-fix: A / v1.1-defer: B
   BLOCKER-PATCHED: N entries
   Registry frozen at docs/E2E/<DATE>-round-1-bug-hunt/bugs-registry.json
   SUMMARY linked from README at commit <SHA>
   SC-001 PASS (12h budget): elapsed <H:MM:SS>
   SC-006 PASS, SC-008 PASS, SC-012 PASS
```

…the hunt is done. Spec-31 picks it up from `bugs-registry.json`.

The next step for you: `git push origin 030-e2e-test-v3` and open the PR. The PR description is `SUMMARY.md` content + link to the registry. The PR is the merge of the hunt artifacts into develop — production code is unchanged outside any BLOCKER-PATCHED commits.
