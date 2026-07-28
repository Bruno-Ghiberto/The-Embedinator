# Research — Spec-30 (E2E Test v3, Single-Round Bug Hunt)

**Phase**: 0 (outline & research)
**Date**: 2026-05-15
**Status**: complete — all 5 open design questions resolved

Resolves the open design questions raised in `docs-Bruno/PROMPTS/spec-30-E2E-test-v3/30-plan.md` and binds the FR-029 "documented X" references to concrete sources for the phase-playbook.

---

## R1 — mcp-chart availability for severity treemap

**Decision**: Use `mcp__mcp-chart__generate_treemap_chart` for the Phase 8 severity treemap. Fall back to a hand-written markdown table inside `SUMMARY.md` if the MCP call fails at session time.

**Rationale**: The `mcp-chart` server is registered in this session's available MCP roster (confirmed via the deferred-tools listing at session start — see `mcp__mcp-chart__generate_treemap_chart` in the registry). It produces a PNG suitable for embedding in `SUMMARY.md`. The MCP server is a project-level convenience, not a hard dependency — a fallback exists so a missing or broken MCP server cannot block hunt closure.

**Alternatives considered**:

- Hand-write the treemap as raw SVG: rejected — pixel-precise control isn't needed and the maintenance cost vs. PNG output is high.
- Use a Python script with matplotlib via `tests/quality/`: rejected — introduces a Python tool dependency for a documentation artifact; violates Principle VII (Simplicity by Default).
- Skip the treemap entirely: rejected — the treemap gives the SUMMARY a single-glance visual that a non-technical reviewer (SC-007) finds far more digestible than a numeric table.

**Operational note**: If the chart MCP returns an error during Phase 8, the orchestrator falls back to a markdown severity table:

```markdown
| Severity | Count |
|---|---|
| BLOCKER | X |
| CRITICAL | X |
| MAJOR | X |
| MINOR | X |
| COSMETIC | X |
```

---

## R2 — `gh issue create` body length limits and inline-vs-link choice

**Decision**: Pass the **full bug markdown** as the body of `gh issue create` via `--body-file bugs/BUG-XXX-short-slug.md`. Include a tail-link back to the in-repo path: `Source: docs/E2E/2026-05-NN-round-1-bug-hunt/bugs/BUG-XXX-short-slug.md`.

**Rationale**: GitHub's hard limit for issue body content is 65,536 characters (64 KB). Bug records following the spec-30 template land in the 500–2,500 char range — three orders of magnitude under the cap. Inline bodies make GitHub Issues self-contained for browsers landing from external links (HN, X, search), which matters for portfolio defensibility (SC-011). The tail-link gives the in-repo permanent reference for anyone wanting the captured artifacts.

**Alternatives considered**:

- Link-only issues (`Source: bugs/BUG-XXX.md` and nothing else): rejected — fails portfolio purpose (a visitor on the issue page can't read the bug without clicking through).
- Truncate at first 8 KB and link to full file: rejected — premature complexity; bug records are nowhere near the cap.
- Use GitHub Discussions instead of Issues: rejected — Issues are the standard triage surface and `spec-31` (the fix wave) consumes issue URLs, not discussion threads.

**Operational note**: The Phase 8 closure runbook in `quickstart.md` uses:

```bash
gh issue create \
  --title "[$severity] $short_title (BUG-$id)" \
  --body-file "docs/E2E/2026-05-NN-round-1-bug-hunt/bugs/BUG-$id-$slug.md" \
  --label "spec-30-hunt,$severity"
```

The orchestrator captures the returned URL and writes it back into `bugs-registry.json` and the bug's markdown `triage.github_issue` field.

---

## R3 — LangGraph checkpoint inspection method (P7-S5 validation)

**Decision**: Use `graph.aget_state(config)` to inspect the checkpoint state for an interrupted chat session, then resume via `astream` with the same config. Compare resumed output against the captured pre-kill state.

**Rationale**: `backend/agent/conversation_graph.py` uses `MemorySaver()` by default (test path) or an `AsyncSqliteSaver` injected by `backend/main.py` at production runtime. Both implement the LangGraph `BaseCheckpointSaver` interface, which exposes `aget_state(config)` returning a `StateSnapshot` with `values`, `next`, `tasks`, and `checkpoint_id`. The state snapshot is sufficient to verify that a checkpoint exists for a given thread_id and that its `values` match what the UI rendered up to the kill point.

**Alternatives considered**:

- Direct SQLite query on the checkpoint DB (`data/checkpoints.db`): rejected — requires understanding the LangGraph checkpoint schema, fragile across LangGraph versions, and the public API does what we need.
- Skip P7-S5 validation entirely and treat checkpoint resume as a qualitative "did it work or not?": rejected — checkpoint integrity is a Constitution II commitment (three-layer agent with persistence), and SC-002 requires CRITICAL findings (which a broken checkpoint would be) to have evidence.
- Write a new admin endpoint to expose checkpoint state: rejected — violates Principle VII; checkpoint inspection is a debugging concern, not a product feature.

**Operational note (for `phase-playbook.md` §7.S5)**:

```python
# From a Python shell or one-off pytest fixture in the hunt session:
config = {"configurable": {"thread_id": "<thread-id-from-killed-session>"}}
snapshot = await graph.aget_state(config)
assert snapshot is not None, "checkpoint missing — resume impossible"
assert snapshot.values["messages"][-1].content == "<expected-content-at-kill>"
# Then resume:
async for event in graph.astream(None, config):
    ...
```

The Pilot does not need to run this themselves — Frontend Inspector (pane 4) can dispatch a sub-agent to execute it and report.

---

## R4 — Public-evidence redaction tooling

**Decision**: Use **ImageMagick** (`convert` / `magick` CLI) for screenshot redaction. Use manual line-edit (or `sd` if available) for log excerpt redaction.

**Rationale**: ImageMagick is installed on the Pilot's Fedora 44 workstation (verified: `/usr/bin/convert`, `/usr/bin/magick`, RPM `ImageMagick-7.1.2.13-2.fc44.x86_64`). It is a system-level dependency that requires no Python venv, no Node module, no MCP server — the simplest possible operational path. Black-rectangle redaction over secret regions is sufficient for the SC-012 requirement (zero secrets in tracked artifacts) without specialized tooling.

**Alternatives considered**:

- Python script using Pillow: rejected — adds a Python-level dependency and editor loop for a one-off operation; ImageMagick CLI is simpler.
- GIMP CLI (`gimp --no-interface --batch ...`): rejected — heavier dependency, batch syntax is awkward, and GIMP is not part of the standard Fedora server profile.
- Manual MS Paint / preview: rejected — not reproducible, no audit trail, fails the methodology repeatability target (SC-009 future round).

**Operational note**: The standard redaction invocation (recorded in `phase-playbook.md` Phase 8 step 2) is:

```bash
convert screenshots/BUG-024.png \
  -fill black -draw "rectangle 120,340 540,380" \
  public-evidence/BUG-024-redacted.png
```

For log excerpts: open in editor, replace secret values with `[REDACTED]`, save as `public-evidence/BUG-024-log.md.snippet` (paste-only, not symlinked). Orchestrator captures both actions in `session-log.md` with category `secret-scan-verify`.

---

## R5 — "Documented timeout" exact source binding

**Decision**: There is **no single spec-26 §timeout-config anchor**. The FR-029 "documented timeout" references resolve to a small set of authoritative configuration sites:

- **Research-loop wall-clock timeout** (US7 AC2 Ollama unavailable / induced tool timeout): `backend/config.py::Settings.max_loop_seconds = 300` (added during spec-26's BUG-008 fix; documented in `specs/026-performance-debug/audit.md`).
- **Ingestion-error surface timeout** (US2 AC2 malformed PDF error within timeout): no central config — error surfacing is handled by FastAPI's standard request lifecycle plus the parsing worker's per-file timeout (`backend/ingestion/worker.py` — verify exact constant in playbook). Default expectation: error surfaces within ≤10s.
- **Stack restart recovery timeout** (US7 AC2 reconnect after Ollama returns): no central config — driven by the circuit-breaker cooldown (30s, per Constitution §Reliability Standards) plus the next retry attempt.

**Rationale**: Earlier draft of 30-plan.md assumed a single canonical `§timeout-config` section in spec-26 docs. Inspection of `specs/026-performance-debug/` shows timeouts are documented across `audit.md` (research-loop only) and inferred from `backend/config.py` for the rest. This is the actual ground truth — spec-30's playbook MUST enumerate each "documented timeout" reference and bind it to its concrete config site, NOT to a non-existent anchor.

**Alternatives considered**:

- Create a new `docs/performance.md§timeouts` consolidation doc as part of spec-30: rejected — out of scope (spec-30 is a hunt, not a config-documentation cleanup); also would defer hunt start.
- Block the playbook on confirming every timeout's canonical site before Phase 0: rejected — the playbook is allowed to evolve mid-hunt (see spec FR-029, last sentence); discovered-timeout updates can land in the playbook in-session.
- Treat all "documented timeout" references as qualitative ("within a reasonable time"): rejected — fails FR-029's "concrete, citable source" requirement; reverts to spec-layer ambiguity.

**Operational note**: The `phase-playbook.md` FR-029 binding table reproduces the three timeout sites above with file:line pointers verified at playbook creation.

---

## FR-029 Budget Sourcing Map (resolved)

This table is the canonical answer to "where does the Pilot find concrete values for each 'documented X' reference?". The phase-playbook reproduces it; bindings updated here propagate there.

| Spec reference | Phase scenario | Source binding (resolved) |
|----------------|----------------|---------------------------|
| "documented startup budget" (US1 AC1) | P1-S1 | Constitution §Performance Budgets (UI cold load <2s, `/health` <50ms) PLUS playbook §1.S1 service-level defaults (90s total / 30s per service) |
| "documented status states" (US2 AC1) | P2-S1, P2-S2 | playbook §2 canonical state machine: `pending → parsing → chunking → indexing → ready` plus `failed` terminal (sourced from `backend/storage/` schema inspection at playbook creation) |
| "documented timeout" (US2 AC2 malformed PDF) | P2-S3 | Backend ingestion worker per-file timeout (verify constant in playbook); default expectation ≤10s |
| "documented latency budget" (US3 AC1) | P3-S1, P3-S2, P3-S5 | spec-26 measured baseline: warm factoid p50 ≈ 19.5s, analytical p50 ≈ 16.0s (after PR #2 merge). Constitution: first-token <500ms target / <800ms Phase 1 actual |
| "documented UX" (US3 AC3 long-answer scroll) | P3-S3 | spec-22 frontend-pro auto-scroll behavior — playbook §3.S3 captures the concrete behavior (auto-scroll vs manual control choice locked in spec-22 implementation) |
| "documented timeout" (US7 AC2 Ollama unavailable) | P7-S1, P7-S2 | `backend/config.py::Settings.max_loop_seconds = 300` (per R5 above); circuit-breaker cooldown 30s per Constitution |
| "documented ingestion budget" (derived) | P2-S1, P2-S2 | playbook §2.S1 default: ≤60s for ≤5MB PDF, scaled linearly per MB above |
| "documented startup readiness" (derived) | P1-S1 | playbook §1.S1 (default 90s total, 30s per service after start) |
| Citation interaction UX (US3 AC2) | P3-S2 | playbook §3.S2 (tooltip ≤200ms, click navigation to source content ≤1s) |

---

## References

- Constitution: `.specify/memory/constitution.md` (v1.1.0, ratified 2026-03-10)
- Spec-14 (performance budgets): `specs/014-performance-budgets/` — referenced for first-token latency, UI cold-load budgets
- Spec-22 (frontend-pro): `specs/022-Frontend-PRO/` — referenced for auto-scroll UX policy
- Spec-26 (performance-debug): `specs/026-performance-debug/audit.md` — `max_loop_seconds=300` source
- Spec-28 (E2E + quality baseline): `specs/028-e2e-bug-hunt-quality-baseline/` — golden Q&A reused for P3
- `backend/config.py` — central config; `max_loop_seconds` lives here
- `backend/agent/conversation_graph.py` — LangGraph compile + checkpointer config (referenced in R3)
