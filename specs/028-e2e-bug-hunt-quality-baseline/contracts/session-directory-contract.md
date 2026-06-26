# Contract: Session Directory Layout

**Feature**: spec-28
**Date**: 2026-04-23

This contract fixes the file layout under `docs/E2E/YYYY-MM-DD-bug-hunt/` and assigns ownership of each file to a single pane. The layout is versioned v1; changes require a new ADR.

---

## Directory root

The root directory is `docs/E2E/<YYYY-MM-DD>-bug-hunt/` where `<YYYY-MM-DD>` is the UTC date the session starts. Exactly one session per day; if the session spans UTC midnight (4-hour block starting before midnight), the start date wins.

Example: a session starting 2026-05-02 14:00 UTC creates `docs/E2E/2026-05-02-bug-hunt/`.

---

## File manifest and ownership

| Path | Owner pane | Write mode | Created by | Closed at |
|------|-----------|-----------|-----------|-----------|
| `session-log.md` | Scribe (pane 3) | live append | Scribe at Phase 3 start | Phase 6 end |
| `bugs-raw/BUG-XXX-*.md` | Scribe (pane 3) | one-shot per bug | Scribe per finding | Bug's F/D/P gate resolution |
| `bugs-found.md` | Scribe (pane 3) | one-shot aggregate | Scribe at Phase 6 | Phase 6 |
| `scenarios-executed.json` | Test Runner (pane 2) | append-on-scenario | Test Runner at Phase 1 start | Phase 6 |
| `quality-metrics.md` | Test Runner (pane 2) via RAGAS harness | one-shot | RAGAS harness at Phase 5 completion | Phase 5 |
| `golden-qa.yaml` | Test Runner (pane 2) + user (pane 1) | hybrid — scaffolded by Test Runner, user edits in pane 1 | Test Runner at Phase 5 start | Phase 5 (before RAGAS run) |
| `traces/BUG-XXX.zip` | Test Runner (pane 2) | one-shot per bug | Playwright / manual trace capture | Bug filing |
| `screenshots/BUG-XXX.png` | Test Runner (pane 2) or Scribe (pane 3) | one-shot per bug | On finding for Frontend bugs | Bug filing |
| `logs/BUG-XXX.log` | Log Watcher (pane 4) | one-shot per bug | On finding | Bug filing |
| `SUMMARY.md` | Orchestrator (pane 1) | one-shot | Orchestrator at Phase 6 | Phase 6 |

**Ownership rules**:
- No pane writes a file owned by another pane.
- If pane X needs information held by pane Y, communication is either (a) through `session-log.md` (the canonical shared channel), or (b) the user relaying the message verbally.
- The Orchestrator (pane 1) MAY read any file for decision-making but only writes `SUMMARY.md` and its own F/D/P decisions into each bug's markdown and into `session-log.md`.

---

## session-log.md — living narrative

Structure:

```markdown
# Session Log — 2026-04-XX Bug Hunt

## 14:00 UTC — Session start
- Preflight: tmux ✓ | docker stack ✓ | branch ✓ | git head: <sha>
- Pane 2, 3, 4 confirmed alive.

## 14:05 UTC — Phase 0: Corpus commit
- Committed docs/Collection-Docs/ (11 PDFs, 14 MB) — commit <sha>.
- Primer query: "NAG-200 diámetro mínimo" — returned relevant chunk in 22s (warm).

## 14:30 UTC — Phase 1: Playwright stabilization
- Ran suite: 10 pass, 16 fail (matches 2026-04-22 baseline).
- Categorizing failures…
  - chat.spec.ts: 4 fail — chunk event assertion (migrated)
  - workflow.spec.ts:19: strict-mode — getByRole migration
  - …

## 15:42 UTC — Phase 3: Exploratory charter #1
- Charter: "citation rendering on cross-referenced NAG-200↔NAG-214 articles"
- Logged BUG-001 (citation offset, Major), BUG-002 (tooltip overflow, Cosmetic).

## 15:58 UTC — F/D/P gate: BUG-001
- Severity: Major (downgraded from initial Blocker assessment after reproduction).
- Decision: D (defer to v1.1).
- Rationale: frontend-only visual offset; does not affect grounding correctness.

…

## 18:30 UTC — Phase 6 close
- SUMMARY.md written. README linked. Makefile diff empty.
- Blocker promotions: BUG-007, BUG-012 → issues #101, #102.
- Session closed.
```

**Rules**:
- Every phase transition logs a new `## HH:MM UTC — Phase N: <label>` header.
- Every F/D/P gate logs a `## HH:MM UTC — F/D/P gate: BUG-XXX` header with Severity + Decision + Rationale.
- Entries are append-only during the session; no retroactive edits except correcting factual typos.
- Timestamps are UTC with minute precision.

---

## bugs-raw/ — one file per bug

Schema: per `data-model.md` §2.

**Rules**:
- Filename: `BUG-XXX-short-slug.md` (see data-model.md §2 "File naming").
- IDs are sequential across the session (BUG-001 → BUG-NNN). Zero-padded 3 digits.
- Scribe creates the file at discovery time. All 7 fields must be populated by session close.
- F/D/P decision for Blockers MUST be recorded inline in the file AND echoed to `session-log.md` with timestamp.

---

## scenarios-executed.json — machine-readable append log

Schema: per `data-model.md` §3.

**Rules**:
- Test Runner appends one entry per scenario. No partial entries allowed — commit on scenario completion, not start.
- JSON must remain valid after each append (single array write, not streaming JSONL). On session close, Scribe validates via `jq . scenarios-executed.json > /dev/null`.

---

## quality-metrics.md — Phase 5 RAGAS output

Schema: per `data-model.md` §4.

**Rules**:
- Written by the RAGAS harness as a one-shot at Phase 5 completion. Handwritten edits after that MUST only be in the "Hypotheses" and "Failure inspection" sections.
- Numeric table rows are machine-generated; do not alter them except to fix a clear harness bug (which itself becomes a filed bug).

---

## SUMMARY.md — the top-level deliverable

Schema:

```markdown
# Spec-28 Bug Hunt Summary — 2026-04-XX

## Bug counts by severity

<severity-treemap rendered by mcp-chart, embedded as PNG or SVG>

| Severity | Count | F (fixed in-session) | D (defer to v1.1) |
|----------|-------|----------------------|--------------------|
| Blocker  | X     | X                    | X                  |
| Major    | X     | X                    | X                  |
| Minor    | X     | X                    | X                  |
| Cosmetic | X     | X                    | X                  |
| **Total**| X     | X                    | X                  |

## Blockers promoted to GitHub issues

- BUG-XXX → #issue ("<title>")
- BUG-YYY → #issue ("<title>")
- (for each Blocker with D decision, show defer rationale inline instead)

## Quality baseline

| Metric | Overall score | Best category | Worst category |
|--------|--------------|---------------|----------------|
| Retrieval precision | 0.XX | factoid (0.XX) | analytical (0.XX) |
| Answer relevance | 0.XX | … | … |
| Citation faithfulness | 0.XX | … | … |
| Context recall | 0.XX | … | … |

Hypotheses H1–H4 status: [CONFIRMED | REFUTED] × 4 → see [quality-metrics.md](./quality-metrics.md).

## Fault injection verdicts

| Scenario | Pass/Fail | Remediation |
|----------|-----------|-------------|
| FI-01 Ollama kill | pass | (none) |
| FI-02 Qdrant stop | pass | Consider shorter fallback UI latency (v1.1) |
| FI-03 Backend crash | pass | (none) |

## Artifacts

- Raw bugs: [bugs-raw/](./bugs-raw/)
- Session log: [session-log.md](./session-log.md)
- Playwright traces: [traces/](./traces/)
- Screenshots: [screenshots/](./screenshots/)
- Golden dataset: [golden-qa.yaml](./golden-qa.yaml)
- Quality metrics: [quality-metrics.md](./quality-metrics.md)
- Scenarios executed: [scenarios-executed.json](./scenarios-executed.json)

## Next steps

- v1.0.0 ships with the <N> Blocker-F fixes landed in this session.
- v1.1 triage queue: <N> deferred Blockers + <N> Major items.
- Quality baseline is the floor for future PR regression checks.
```

**Rules**:
- Severity treemap rendered via `mcp-chart` and embedded. If rendering fails, use a Markdown table fallback and file the failure as a Cosmetic bug.
- All artifact links are relative to `SUMMARY.md` and resolve from the session directory root.
- The link to `SUMMARY.md` in top-level `README.md` uses the path form `docs/E2E/<YYYY-MM-DD>-bug-hunt/SUMMARY.md`.

---

## Enforcement

The Orchestrator's Phase 6 gate explicitly validates:

```bash
# in pane 1 at Phase 6 close
DIR=docs/E2E/$(date -u +%F)-bug-hunt
test -f "$DIR/session-log.md" && \
test -f "$DIR/bugs-found.md" && \
test -d "$DIR/bugs-raw" && \
test -f "$DIR/scenarios-executed.json" && \
test -f "$DIR/quality-metrics.md" && \
test -f "$DIR/golden-qa.yaml" && \
test -d "$DIR/traces" && \
test -d "$DIR/screenshots" && \
test -f "$DIR/SUMMARY.md" && \
grep -q "$DIR/SUMMARY.md" README.md && \
echo "Phase 6 gate: PASS"
```

If any file is missing, the gate fails and the session does not close.
