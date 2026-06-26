# Data Model: E2E Bug Hunt & Quality Baseline — Phase 1 Output

**Feature**: spec-28
**Date**: 2026-04-23

Four schemas: Golden Q&A pair, Bug markdown, Scenarios Executed log, Quality Metrics file. Each is prescriptive; deviation invalidates the SC evaluation matrix in `plan.md`.

---

## 1. Golden Q&A pair

**File**: `docs/E2E/YYYY-MM-DD-bug-hunt/golden-qa.yaml`
**Count**: exactly 20 pairs
**Distribution** (per FR-014, locked):

| Category | Count | Notes |
|----------|-------|-------|
| factoid | 10 | Straight retrieval precision tests; single-article answers |
| analytical | 4 | Require reasoning across multiple passages or tables |
| follow-up | 3 | Require prior-turn context (test session continuity) |
| out-of-scope | 2 | Should elicit graceful decline, not hallucination |
| ambiguous | 1 | Genuine interpretation options; tests uncertainty handling |

**Authorship split** (per FR-019 clarification, locked):

| Authored by | Categories | Count |
|-------------|-----------|-------|
| user (hand-authored) | ambiguous + out-of-scope | 3 |
| scaffold-reviewed (Test Runner drafts; user reviews and accepts/edits in pane 1) | factoid + analytical + follow-up | 17 |

### Schema (YAML)

```yaml
# golden-qa.yaml — committed under docs/E2E/YYYY-MM-DD-bug-hunt/
- id: Q-001                                         # string; format: Q-NNN; sequential; unique
  category: factoid                                  # enum: factoid | analytical | follow-up | out-of-scope | ambiguous
  question_es: "¿Cuál es el diámetro mínimo de la red de distribución domiciliaria según NAG-200?"
  reference_answer_es: "Según NAG-200 §4.1, el diámetro mínimo para red domiciliaria es…"
  source_doc: "NAG-200.pdf"                          # exact PDF filename from docs/Collection-Docs/
  source_section: "§4.1"                             # citation granularity: section, article, table, or page
  notes: "Single-article factoid; tests retrieval precision on explicit article references."
  authored_by: "scaffold-reviewed"                   # enum: user | scaffold-reviewed
  follow_up_of: null                                 # for category: follow-up only — reference prior Q id (e.g., Q-015)
  expected_behavior: "answer"                        # enum: answer | decline | disambiguate
                                                     #   - answer: category factoid/analytical/follow-up/ambiguous
                                                     #   - decline: category out-of-scope (must refuse with "no está en los documentos")
                                                     #   - disambiguate: category ambiguous (must ask clarifying Q or enumerate interpretations)
```

### Validation rules

- `id` is unique across the file; sequential (Q-001 → Q-020).
- `category` count per the distribution table above (10+4+3+2+1 = 20).
- `question_es` and `reference_answer_es` are Spanish-language strings (FR-015). No English-translated proxies.
- For `category: follow-up`, `follow_up_of` MUST reference a valid earlier Q id. For others, `follow_up_of` MUST be `null`.
- For `category: out-of-scope`, `source_doc` and `source_section` MUST be `null` (the corpus does not contain the answer), and `expected_behavior` MUST be `decline`.
- For `category: ambiguous`, `expected_behavior` MUST be `disambiguate`.
- For `authored_by: user`, the file's git blame for that entry MUST show a single-author commit (the user), not the scaffold commit.

### Example (one per category)

```yaml
- id: Q-001
  category: factoid
  question_es: "¿Cuál es el diámetro mínimo de la red de distribución domiciliaria según NAG-200?"
  reference_answer_es: "NAG-200 §4.1 establece un diámetro mínimo de …"
  source_doc: "NAG-200.pdf"
  source_section: "§4.1"
  notes: "Retrieval precision on explicit article reference."
  authored_by: "scaffold-reviewed"
  follow_up_of: null
  expected_behavior: "answer"

- id: Q-011
  category: analytical
  question_es: "¿Cómo se relacionan los requisitos de inspección de NAG-235 con las especificaciones de materiales de NAG-214?"
  reference_answer_es: "NAG-235 §3 referencia explícitamente NAG-214 §6.3 para los materiales admitidos en inspección inicial; la relación es…"
  source_doc: "NAG-235.pdf,NAG-214.pdf"
  source_section: "§3, §6.3"
  notes: "Cross-document reasoning; H3 test case."
  authored_by: "scaffold-reviewed"
  follow_up_of: null
  expected_behavior: "answer"

- id: Q-015
  category: follow-up
  question_es: "¿Y si la instalación es industrial?"
  reference_answer_es: "Para instalaciones industriales se aplica NAG-204 §2; la diferencia respecto al caso domiciliario es…"
  source_doc: "NAG-204.pdf"
  source_section: "§2"
  notes: "Session continuity test; depends on Q-014 having established the domestic context."
  authored_by: "scaffold-reviewed"
  follow_up_of: "Q-014"
  expected_behavior: "answer"

- id: Q-018
  category: out-of-scope
  question_es: "¿Cuál es la capital de Francia?"
  reference_answer_es: "La información no está en los documentos cargados."
  source_doc: null
  source_section: null
  notes: "H4 — out-of-scope graceful decline. Must refuse, not hallucinate."
  authored_by: "user"
  follow_up_of: null
  expected_behavior: "decline"

- id: Q-020
  category: ambiguous
  question_es: "¿Cuánta presión es la adecuada?"
  reference_answer_es: "La pregunta es ambigua — ¿se refiere a presión de servicio, de prueba, o nominal? NAG-216 distingue…"
  source_doc: "NAG-216.pdf"
  source_section: "§1–§3"
  notes: "Tests whether the agent asks for disambiguation vs picking one interpretation."
  authored_by: "user"
  follow_up_of: null
  expected_behavior: "disambiguate"
```

---

## 2. Bug markdown

**File**: `docs/E2E/YYYY-MM-DD-bug-hunt/bugs-raw/BUG-XXX-short-slug.md` (one per bug)
**Mandatory**: All 7 top-level fields MUST be present and populated before session close (FR-008, SC-004).

### Schema (Markdown)

```markdown
# BUG-XXX: <short title>

- **Severity**: Blocker | Major | Minor | Cosmetic              # enum, required
- **Layer**: Frontend | Backend | Ingestion | Retrieval | Reasoning | Infrastructure | Observability  # enum, required
- **Discovered**: 2026-04-XX HH:MM via [Playwright | Exploratory | Fault-injection | RAGAS]           # ISO-date + time + discovery channel
- **F/D/P decision**: F (fixed in-session, commit <SHA>) | D (defer to v1.1, rationale: <...>) | P→F (<SHA>) | P→D (<rationale>)  # required for Blocker; Major/Minor/Cosmetic may omit

## Steps to Reproduce
1. <step>
2. <step>
...

## Expected
<one-sentence expected behavior>

## Actual
<one-sentence observed behavior, plus verbatim error message or stack trace if any>

## Artifacts
- Trace: `traces/BUG-XXX.zip` (Playwright only — omit if not available)
- Screenshot: `screenshots/BUG-XXX.png` (required for Frontend layer bugs)
- Log excerpt:
  ```
  <paste structlog JSON lines or backend stdout>
  ```
  OR
- Log file: `logs/BUG-XXX.log`

## Root-cause hypothesis
<1–3 sentences: what you think caused it, what signals support the hypothesis, what a next-step investigation would do>
```

### Validation rules

- `Severity`, `Layer`, `Discovered`, `Steps to Reproduce`, `Expected`, `Actual`, `Root-cause hypothesis` are ALL required.
- `F/D/P decision` is required for `Severity: Blocker`. For non-Blocker severities, it MAY be omitted but if present MUST follow the schema.
- `Steps to Reproduce` MUST contain at least 2 steps.
- `Expected` and `Actual` MUST be distinct — identical sentences flag the bug as invalid.
- `Artifacts` section MUST be present with at least one artifact type unless `Layer: Observability` (the missing instrument IS the artifact).
- `Root-cause hypothesis` MUST NOT be `"TBD"` or `"unknown"` at session close — the hypothesis can be tentative but must be substantive.

### File naming

`BUG-XXX-short-slug.md`:
- `XXX` is a zero-padded 3-digit sequential id (BUG-001, BUG-002, …)
- `short-slug` is kebab-case, 2–5 words, describes the bug in ~30 characters or fewer
- Examples: `BUG-001-citation-tooltip-offset.md`, `BUG-007-ollama-kill-silent-hang.md`

---

## 3. Scenarios Executed log

**File**: `docs/E2E/YYYY-MM-DD-bug-hunt/scenarios-executed.json`
**Purpose**: Machine-readable record of every scripted, exploratory charter, fault-injection scenario, and RAGAS run — enables programmatic SC evaluation (SC-007) without reading prose.

### Schema (JSON)

```json
{
  "session_id": "2026-04-XX-bug-hunt",
  "session_started_at": "2026-04-XXTHH:MM:SSZ",
  "session_ended_at": "2026-04-XXTHH:MM:SSZ",
  "git_head_at_start": "<sha>",
  "entries": [
    {
      "id": "string",                        // e.g. "FI-01", "EXPL-CHARTER-003", "PLAYWRIGHT-chat.spec.ts"
      "type": "scripted | exploratory | fault-injection | ragas",
      "name": "human-readable label",
      "started_at": "ISO-8601 UTC",
      "completed_at": "ISO-8601 UTC",
      "command": "exact shell command (fault-injection, ragas) OR null (exploratory)",
      "charter": "exploratory charter sentence OR null (non-exploratory)",
      "observed_outcome": "one-sentence user-facing outcome description",
      "pass_fail": "pass | fail | n/a",
      "remediation": "one-sentence remediation note OR null",
      "bugs_filed": ["BUG-XXX", "BUG-YYY"]    // array of bug ids filed during this scenario
    }
  ]
}
```

### Validation rules

- `session_id` matches the directory name under `docs/E2E/`.
- `entries` has at least one entry per type: at least 1 scripted (covering Phase 1 green-run), at least 1 exploratory charter, at least 3 fault-injection, exactly 1 ragas.
- Each `entry.id` is unique within the session.
- `started_at < completed_at` for every entry.
- `pass_fail: fail` entries MUST have at least one `bugs_filed` reference.
- `command` is required for `fault-injection` and `ragas` types; `null` for `scripted` and `exploratory`.
- `charter` is required for `exploratory` type; `null` for others.
- `remediation` is required when `pass_fail: fail`; may be `null` on pass.

### Example entries

```json
{
  "id": "FI-01",
  "type": "fault-injection",
  "name": "Ollama killed mid-stream",
  "started_at": "2026-04-XXT14:02:17Z",
  "completed_at": "2026-04-XXT14:08:42Z",
  "command": "docker kill embedinator-ollama-1",
  "charter": null,
  "observed_outcome": "UI surfaces 'inference unavailable' after ~12s; circuit breaker trips after 3 retries; user can retry after container restart.",
  "pass_fail": "pass",
  "remediation": "Current behavior acceptable. Consider shorter circuit-breaker window for faster UX recovery (v1.1 item).",
  "bugs_filed": []
}
```

```json
{
  "id": "EXPL-CHARTER-003",
  "type": "exploratory",
  "name": "Spanish accent handling in chat input",
  "started_at": "2026-04-XXT15:10:00Z",
  "completed_at": "2026-04-XXT15:34:22Z",
  "command": null,
  "charter": "Probe citation rendering, input tokenization, and clarification flow when questions use Spanish diacritics and punctuation.",
  "observed_outcome": "Two rendering issues found on citations that span lines with accents; no input issues.",
  "pass_fail": "fail",
  "remediation": "Filed as BUG-014 and BUG-015. BUG-014 Major (citation offset off by 1 char); BUG-015 Cosmetic (tooltip truncation).",
  "bugs_filed": ["BUG-014", "BUG-015"]
}
```

---

## 4. Quality Metrics file

**File**: `docs/E2E/YYYY-MM-DD-bug-hunt/quality-metrics.md`
**Purpose**: Human-readable + reviewer-verifiable RAGAS baseline with hypothesis evaluation.

### Schema (Markdown)

```markdown
# Quality Baseline — 2026-04-XX

## Per-category scores

| Category     | Pairs | Retrieval precision | Answer relevance | Citation faithfulness | Context recall |
|--------------|-------|---------------------|------------------|-----------------------|----------------|
| Factoid      | 10    | 0.XX                | 0.XX             | 0.XX                  | 0.XX           |
| Analytical   | 4     | 0.XX                | 0.XX             | 0.XX                  | 0.XX           |
| Follow-up    | 3     | 0.XX                | 0.XX             | 0.XX                  | 0.XX           |
| Out-of-scope | 2     | N/A (declined)      | 0.XX             | N/A                   | N/A            |
| Ambiguous    | 1     | 0.XX                | 0.XX             | 0.XX                  | 0.XX           |
| **Overall**  | 20    | 0.XX                | 0.XX             | 0.XX                  | 0.XX           |

## Hypotheses

- **H1 — Spanish-on-English-embedder degradation**: [CONFIRMED | REFUTED] — <evidence: e.g., "Overall retrieval precision 0.52, vs. ~0.70–0.80 reported on comparable English corpora with nomic-embed-text. Degradation visible; confirms H1.">
- **H2 — PDF table extraction edges**: [CONFIRMED | REFUTED] — <evidence: e.g., "Q-005 (pipe-diameter table) returned malformed numeric cells; confirms H2 on at least one table.">
- **H3 — Citation cross-reference grounding**: [CONFIRMED | REFUTED] — <evidence: e.g., "Q-011 analytical NAG-235↔NAG-214 pair cited only NAG-235; cross-reference skipped; confirms H3.">
- **H4 — Out-of-scope graceful decline**: [CONFIRMED | REFUTED] — <evidence: e.g., "Q-018 (capital of France) elicited 'no está en los documentos' as expected; refutes the pessimistic prior — out-of-scope handling works.">

## Failure inspection

For each pair with a score below a documented reference floor (e.g., retrieval precision < 0.3 or answer relevance < 0.4), list the pair id, the failure mode, and whether it triggered a filed bug.

| Pair id | Metric | Score | Failure mode | Bug filed |
|---------|--------|-------|--------------|-----------|
| Q-XXX   | …      | 0.XX  | e.g., "citation missing" | BUG-XXX |

## Reproduction

- **Dataset**: `golden-qa.yaml`
- **Command**: `zsh scripts/run-tests-external.sh -n spec28-ragas tests/quality/test_ragas_baseline.py`
- **Stack state at run time**: warm (one primer query issued before the evaluation sweep)
- **Judge LLM**: <e.g., "Ollama `qwen2.5:7b` — same model as the backend; documents self-bias risk"> OR <e.g., "OpenRouter `anthropic/claude-sonnet-4-6` — neutral judge; requires EMBEDINATOR_OPENROUTER_KEY">
- **Backend git SHA**: <sha>
- **Session id**: 2026-04-XX-bug-hunt
- **Run duration**: <X minutes>

## Ship-gate note

These scores are the v1.0.0 baseline. Per FR-018 and spec Assumptions, the baseline is **informational, not a ship gate** — no score floor blocks v1.0.0. Future PRs run the same harness; regressions against this baseline are flagged for review.
```

### Validation rules

- All 5 category rows present; row counts match Q&A distribution (10/4/3/2/1).
- `Overall` row present and is the weighted-or-unweighted average documented in the Reproduction section.
- H1–H4 each have an explicit CONFIRMED or REFUTED verdict — no "TBD" or "partial".
- Reproduction section names the exact judge LLM (and if a cloud judge was used, the env var name is disclosed so a reader can reproduce).
- "Failure inspection" may be empty if all pairs scored above the floor — empty is a valid state, not a missing section.

---

## Cross-schema relationships

- A `BUG-XXX` filed in a Bug markdown is referenced by `scenarios-executed.json[].bugs_filed` and by the relevant section of `SUMMARY.md` (written at Phase 6 close).
- A `Q-XXX` in `golden-qa.yaml` is referenced in `quality-metrics.md` "Failure inspection" table only when its score falls below a documented floor.
- `SUMMARY.md` references both the bug list and the quality metrics, forming the single entry point from `README.md`.

---

## Schema versioning

All four schemas are v1 as of 2026-04-23. Schema changes require a new ADR (or a new spec) because downstream tooling (`scripts/validate-bug-records.sh`, the RAGAS harness, and the README link from `SUMMARY.md`) hard-codes these field names.
