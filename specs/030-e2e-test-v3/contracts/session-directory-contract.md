# Contract — Session Directory Layout

**Spec**: 030-e2e-test-v3
**Phase**: 1
**Status**: locked

Defines the canonical file layout under `docs/E2E/YYYY-MM-DD-round-1-bug-hunt/`. Created by orchestrator at Phase 0. Frozen at Phase 8 closure.

## Directory tree

```text
docs/E2E/YYYY-MM-DD-round-1-bug-hunt/
├── .gitignore                       # TRACKED — declares the gitignored subdirs
├── session-log.md                   # TRACKED — chronological timeline (Entity 3)
├── bugs/                            # TRACKED — one file per registered bug
│   ├── BUG-024-citation-tooltip-stalls.md
│   ├── BUG-025-malformed-pdf-no-error.md
│   └── ...                          # one .md per BUG-NNN (Entity 1)
├── bugs-registry.json               # TRACKED — Phase 8 close; spec-31 input (Entity 2)
├── triage.md                        # TRACKED — Phase 8 close; severity rollup (Entity 4)
├── SUMMARY.md                       # TRACKED — Phase 8 close; non-technical readable
├── LAUNCH-DECISION.md               # TRACKED — Phase 8 close; SC-011 evidence
├── public-evidence/                 # TRACKED — Pilot-curated redacted artifacts (FR-027)
│   ├── BUG-024-redacted.png
│   ├── BUG-025-log-snippet.md       # paste-only, NOT a symlink to logs/
│   ├── severity-treemap.png         # mcp-chart output OR markdown table fallback
│   └── ...
│
│   ── GITIGNORED BELOW ──
├── logs/                            # raw log excerpts (FR-022 split)
│   ├── BUG-024.log
│   └── ...
├── screenshots/                     # raw screenshots (FR-022 split)
│   ├── BUG-024.png
│   └── ...
└── traces/                          # raw browser DevTools traces (FR-022 split)
    ├── BUG-024.trace.zip
    └── ...
```

## `.gitignore` content (verbatim)

```gitignore
# Raw artifacts — gitignored per spec-30 FR-022
logs/
screenshots/
traces/
```

This .gitignore lives INSIDE the session directory. It does NOT belong in the repo-root .gitignore — the repo-root .gitignore should NOT mention this session directory at all (other than the existing `docs/E2E/` rules from prior specs, which already permit tracked subdirs).

## File ownership

| Path | Author (pane) | Write window |
|---|---|---|
| `.gitignore` | Orchestrator (pane 2) | Phase 0 only |
| `session-log.md` | Bug Registrar primary; Orchestrator + Pilot may append | All phases, append-only |
| `bugs/BUG-NNN-*.md` | Bug Registrar (pane 5) | At discovery; updated on triage + BLOCKER-PATCHED |
| `bugs-registry.json` | Bug Registrar | Phase 8 close only |
| `triage.md` | Orchestrator (pane 2) | Phase 8 close only |
| `SUMMARY.md` | Orchestrator (pane 2) | Phase 8 close only |
| `LAUNCH-DECISION.md` | Pilot via Orchestrator dispatch | Phase 8 close only |
| `public-evidence/*` | Pilot promotes; Orchestrator records | Phase 8 close only |
| `logs/*` | Log Analyst (pane 3) | All phases as needed |
| `screenshots/*` | Pilot captures; Frontend Inspector annotates | All phases as needed |
| `traces/*` | Frontend Inspector (pane 4) | All phases as needed |

## Tracked vs gitignored split (FR-022, FR-027)

**TRACKED (committed to public repo):**
- `.gitignore`, `session-log.md`, `bugs/*.md`, `bugs-registry.json`, `triage.md`, `SUMMARY.md`, `LAUNCH-DECISION.md`, `public-evidence/*`

**GITIGNORED (Pilot's workstation only):**
- `logs/*`, `screenshots/*`, `traces/*`

The Pilot promotes a curated, redacted subset of GITIGNORED artifacts into TRACKED `public-evidence/` at Phase 8 — see `blocker-patched-gate-contract.md` is NOT involved here; `public-evidence/` curation is its own Phase 8 step.

## Phase 0 creation steps (orchestrator)

1. Compute session date (`date -u +%Y-%m-%d`); resolve `<DATE>` placeholder.
2. `mkdir -p docs/E2E/<DATE>-round-1-bug-hunt/{bugs,public-evidence,logs,screenshots,traces}`.
3. Write `.gitignore` with the three rules above.
4. `git add docs/E2E/<DATE>-round-1-bug-hunt/.gitignore docs/E2E/<DATE>-round-1-bug-hunt/bugs/.gitkeep docs/E2E/<DATE>-round-1-bug-hunt/public-evidence/.gitkeep` (use `.gitkeep` to track the empty dirs).
5. Write `session-log.md` with header + first entry:

```markdown
# Session Log — Spec-30 Round 1 Bug Hunt

**Session opened**: <ISO-8601 timestamp UTC>
**Pilot**: Bruno Ghiberto
**Branch**: 030-e2e-test-v3
**develop HEAD at session start**: <git rev-parse develop>
**spec/plan/playbook SHAs**: <git log -1 --format=%H -- specs/030-e2e-test-v3/{spec,plan,phase-playbook}.md>
**Next free BUG ID**: BUG-NNN (computed from prior spec history)

---

[<ISO-8601>] Orchestrator | phase-transition | Phase 0 opened
```

6. Commit the Phase 0 scaffolding: `git commit -m "chore(spec-30): open bug-hunt session directory"`.

## Phase 8 closure steps (orchestrator)

1. For every MAJOR-or-higher bug record: ensure `triage` block populated; `gh issue create` invoked; URL recorded.
2. For every CRITICAL bug record: review artifacts; Pilot curates redacted versions into `public-evidence/`; orchestrator writes `secret-scan-verify` session-log entry per artifact.
3. Generate severity treemap via `mcp-chart` → `public-evidence/severity-treemap.png` (fallback markdown table embedded in SUMMARY if MCP fails per research.md R1).
4. Write `triage.md` (Entity 4 in data-model).
5. Write `SUMMARY.md`: severity counts, treemap embed/table, MAJOR+ triage decisions with issue links, BLOCKER-PATCHED log, notable findings paragraph, link to `bugs-registry.json`. Pass cold-read peer review (SC-007).
6. Write `bugs-registry.json` (Entity 2) — schema-validate per `bug-registry-schema.md`.
7. Write `LAUNCH-DECISION.md`: 1-page Pilot decision referencing registry + SUMMARY (SC-011).
8. Update root `README.md` with one-line link to `docs/E2E/<DATE>-round-1-bug-hunt/SUMMARY.md`.
9. Closure-gate checks (FR-014, FR-015, FR-016, SC-006, SC-012); session-log final entry:

```
[<ISO-8601>] Orchestrator | closure-step | Hunt closed. <severity counts>. Registry frozen.
```

10. Commit closure: `git commit -m "feat(spec-30): close bug-hunt round 1 — N bugs registered, M triaged"`.

## Invariants (across all phases)

- The session directory MUST exist for exactly one calendar-date stamp (single round, FR-002).
- All TRACKED files MUST be free of secrets, plaintext API keys, decrypted credentials, PII (SC-012).
- `logs/`, `screenshots/`, `traces/` MUST remain gitignored at all phases (FR-022); promotion to `public-evidence/` requires the redaction + verification step in `secret-scan-verify`.
- Bug IDs are globally unique across all hunt rounds — verify next free ID against prior spec history at Phase 0.
