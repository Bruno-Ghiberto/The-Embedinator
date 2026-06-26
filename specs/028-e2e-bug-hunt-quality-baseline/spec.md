# Feature Specification: E2E Bug Hunt & Quality Baseline (Pre-v1.0.0)

**Feature Branch**: `028-e2e-bug-hunt-quality-baseline`
**Created**: 2026-04-23
**Status**: Draft
**Input**: User description: `"Read @docs/PROMPTS/spec-28-E2E-v01/28-specify.md"` — a time-boxed, methodology-blended pre-v1.0.0 quality pass that finds every critical bug, misfunction, missing feature, and quality regression before the first public portfolio release. The test suite is the vehicle; the curated bug list is the deliverable.

---

## Overview

The Embedinator is about to cross from `v0.3.0` (released 2026-04-21) into `v1.0.0` — its first public, portfolio-facing release, targeted for a Tuesday 9am EST Hacker News launch on a two-week timeline. Before that moment, the product must withstand three kinds of scrutiny the current suite has never applied end-to-end: (1) a scripted regression pass that proves core user journeys still work, (2) an unstructured exploratory pass that finds what scripts cannot, and (3) a numeric quality baseline on the real demo corpus so that the README can make a defensible claim about retrieval and answer quality. This spec merges what was originally two specs (spec-28 E2E + spec-29 RAGAS) into a single gated bug-hunt effort. Its success is measured by bugs *found*, not bugs *absent*.

---

## Clarifications

### Session 2026-04-23

- Q: Browser coverage for the scripted E2E suite (FR-029)? → A: Chromium only. Rationale: portfolio demo project on a two-week timeline, solo developer with no prior triage history on Firefox/WebKit-specific flakes, and the published demo runs on Chromium. Tri-browser would triple both CI minutes and the stabilization scope for the sixteen pre-existing failures.
- Q: Golden dataset authorship (FR-019)? → A: Hybrid split — the user hand-authors the three highest-bias pairs (1 ambiguous + 2 out-of-scope) and reviews/accepts/edits scaffolded candidates for the remaining seventeen (10 factoid + 4 analytical + 3 follow-up). Rationale: preserves human authorship exactly where reviewer bias would most distort the RAGAS measurement, while keeping total user effort inside the two-week launch window.
- Q: Fault-injection blast radius (FR-012)? → A: Run fault-injection scenarios against the normal local stack, governed by a documented preflight checklist (save open work, confirm no other processes are holding the stack, snapshot data volumes if desired). Rationale: solo developer on a dedicated dev machine — the throwaway-stack option adds ~15–20 minutes of port/project juggling per scenario for protection against an edge case that barely applies, and using the real stack makes the failure modes more representative.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Scripted E2E regression suite (Priority: P1)

As a developer preparing v1.0.0, I need a scripted end-to-end regression suite that covers the core happy-path user journeys and runs in continuous integration on every pull request, so that critical flows cannot silently regress between now and launch.

**Why this priority**: Regression protection is the cheapest, longest-lived output of this spec. Once landed, it gates every future change. The existing six E2E specs are in a known-broken state (ten passing, sixteen failing as of 2026-04-22) after a four-week period during which an infrastructure issue masked the failures. This user story MUST first stabilize the existing suite before adding new flows — otherwise the baseline it establishes is worthless.

**Independent Test**: A reviewer can clone the branch, open a trivial no-op pull request against `develop`, and observe that the aggregate CI roster runs the scripted suite, all flows pass, and a failing assertion in any flow blocks the merge.

**Acceptance Scenarios**:

1. **Given** the full scripted suite on `develop` HEAD, **When** it is run in CI, **Then** every flow passes and a Playwright trace artifact is produced.
2. **Given** a pull request that deliberately breaks a core flow (e.g., removes the citation tooltip handler), **When** CI runs the suite, **Then** the corresponding flow fails with a clear assertion error and the PR cannot be merged under the branch protection ruleset.
3. **Given** the sixteen pre-identified failing tests in the existing suite, **When** the spec is complete, **Then** each failure is either (a) fixed by updating the selector/assertion to the current UI, (b) fixed by repairing an app bug revealed by the test, or (c) explicitly deleted with a written justification captured in the session log.

---

### User Story 2 — Charter-driven exploratory session (Priority: P1)

As a developer who knows that scripted tests only catch the bugs they were written to catch, I need a single four-hour charter-driven exploratory session against a fully-seeded local instance, so that defect categories scripts cannot find (visual drift, surprising flows, latency cliffs, unexpected empty states) are surfaced before users see them.

**Why this priority**: Exploratory testing finds a different class of bug than scripted testing. Skipping it would leave a blind spot at exactly the moment the product goes public. Four hours is the thorough option over two hours because the corpus is specialized (Spanish-language gas regulation) and the surface area includes streaming chat, hybrid retrieval, and multi-page navigation — two hours would only cover chat.

**Independent Test**: The session can be reviewed after the fact by reading `docs/E2E/YYYY-MM-DD-bug-hunt/session-log.md` end-to-end and confirming that every finding has the seven mandatory fields (severity, layer, reproduction steps, expected, actual, artifacts, root-cause hypothesis) without replaying the session.

**Acceptance Scenarios**:

1. **Given** a freshly seeded local instance with the gas-regulation corpus ingested, **When** the four-hour charter session runs, **Then** findings are logged live to `session-log.md` and individual bug markdowns are created under `bugs-raw/` as they are discovered.
2. **Given** a Blocker-severity finding during the session, **When** it is logged, **Then** the orchestrator prompts an F/D/P gate (fix now / defer / pause + investigate) and the decision is recorded in the bug markdown and the session log before the session resumes.
3. **Given** the session clock reaches four hours, **When** the session closes, **Then** every open finding has severity, layer, reproduction steps, and root-cause hypothesis populated — no bug may leave the session unassigned.

---

### User Story 3 — Targeted fault injection (Priority: P1)

As a developer who wants to ship a product that degrades gracefully, I need between three and five targeted fault-injection scenarios against the live container stack, so that the failure-mode behavior of the system is known rather than assumed before launch.

**Why this priority**: Every prior quality pass has run on the happy path. Container crashes, model unavailability, and backpressure are the exact conditions a first-visitor might hit if traffic arrives faster than expected. Knowing how the product behaves there is a launch prerequisite.

**Independent Test**: For each executed scenario, an independent reviewer can read the session log, see the exact fault command issued, see the observed user-facing outcome, and judge whether the remediation note is honest and actionable.

**Acceptance Scenarios**:

1. **Given** a running local stack, **When** the inference container (Ollama) is killed mid-chat-stream, **Then** the user-facing outcome is a graceful error message (not a silent hang) and the remediation note captures the observed behavior plus the fix plan if needed.
2. **Given** a running local stack, **When** the vector store (Qdrant) is put under simulated backpressure, **Then** either retrieval degrades gracefully to a documented fallback or the failure is logged as a new bug with severity assigned in-session.
3. **Given** at least three fault-injection scenarios executed, **When** the session closes, **Then** each scenario has a pass/fail verdict plus a remediation note in the session log.

---

### User Story 4 — RAGAS-scored quality baseline on the real corpus (Priority: P1)

As a portfolio author preparing to publish numbers in the README, I need a RAGAS-scored quality baseline on a twenty-pair golden Q&A dataset curated from the Argentine gas regulatory corpus, so that the README can make a defensible "quality X of Y" claim rather than a subjective one.

**Why this priority**: A public portfolio project without a published quality number is indistinguishable from a toy. The numeric floor this establishes also becomes the regression bar for every future change — quality that would have passed a subjective eyeball test now has to beat the committed baseline.

**Independent Test**: A reviewer can open `quality-metrics.md` after the session and see numeric scores for retrieval precision, answer relevance, citation faithfulness, and context recall across the five question categories, plus the raw golden dataset committed alongside so the numbers can be reproduced.

**Acceptance Scenarios**:

1. **Given** the twenty-pair golden dataset committed to the repository, **When** the RAGAS evaluation is run against a clean local stack, **Then** scores are produced for retrieval precision, answer relevance, citation faithfulness, and context recall, and the numbers are published in `quality-metrics.md`.
2. **Given** the five question categories (ten factoid, four analytical, three follow-up, two out-of-scope, one ambiguous), **When** the baseline is published, **Then** every category has at least one representative pair and the per-category average is reported alongside the overall number.
3. **Given** the hypotheses pre-registered in this spec (Spanish-on-English embedder degradation, PDF table extraction edges, citation cross-reference grounding, out-of-scope graceful decline), **When** the baseline runs, **Then** each hypothesis is either confirmed or refuted by the numbers, and both outcomes are recorded in `quality-metrics.md` as informative results.

---

### User Story 5 — Structured bug log as primary deliverable (Priority: P2)

As a future reviewer (including future-me) who will look at this session's output weeks or months later, I need a structured bug log with reproducible steps, severity, layer, root-cause hypothesis, and links to the trace/log/screenshot artifacts, so that every finding is actionable without needing to replay the live session.

**Why this priority**: The bug list — not the test suite — is the explicit deliverable of this spec. It determines which bugs block v1.0.0 and which get deferred to v1.1. A poorly captured bug is worse than none because it creates the illusion of coverage while being unactionable.

**Independent Test**: Pick any bug file at random from `bugs-raw/`, read it cold, and confirm that a second engineer could reproduce the bug with nothing but the file's contents and a fresh checkout.

**Acceptance Scenarios**:

1. **Given** a completed session, **When** a reviewer opens any file in `bugs-raw/`, **Then** every bug has all seven mandatory fields populated.
2. **Given** a Blocker-severity bug in the bug list, **When** the session closes, **Then** the promotion gate has either (a) opened a GitHub issue linking to the bug markdown or (b) recorded an explicit defer rationale in the bug file.
3. **Given** the final `SUMMARY.md`, **When** a stakeholder reads it cold, **Then** they can count bugs by severity, see which blockers were fixed in-session versus deferred, and follow links to the underlying bug files.

---

### User Story 6 — F/D/P gate protocol for live blockers (Priority: P2)

As the session orchestrator, I need a simple three-way gate (fix now / defer / pause + investigate) prompted at every Blocker-severity finding, so that the session cannot drown in bug intake while ignoring fixes, nor sink into unplanned debugging at the expense of coverage.

**Why this priority**: Without an explicit gate, a four-hour session reliably degrades into either "all intake, no fixes" or "one bug consumed the whole session." The F/D/P gate is how the session stays productive on both axes.

**Independent Test**: Read the session log and confirm that every Blocker has a corresponding F, D, or P decision with a one-sentence rationale recorded inline.

**Acceptance Scenarios**:

1. **Given** a Blocker surfaces mid-session, **When** it is logged, **Then** the orchestrator prompts F/D/P before the session resumes.
2. **Given** a `P` decision is taken, **When** the investigation concludes, **Then** a follow-up decision (F or D) is recorded before the session continues.
3. **Given** the session closes, **When** the log is audited, **Then** no Blocker is left in an unassigned state.

---

### Edge Cases

- **Corpus language mismatch**: The default embedding model is English-primary; the corpus is Spanish. If retrieval precision comes back unusably low, the baseline must still be published (low numbers are informative) and the remediation (embedding-model swap) must be captured as a v1.1 item rather than scope-creeping into v1.0.0.
- **Flaky Playwright tests**: A flake that cannot be stabilized within the session is logged as a bug and the underlying test is marked quarantined (not silently deleted). Quarantine count is reported in `SUMMARY.md`.
- **Live container kill affects unrelated work**: Fault injection is destructive by design. If the user happens to have unrelated work open against the local stack, the session pauses for the user to save or migrate. This is documented in the session preflight checklist.
- **Golden dataset ambiguity pair regressing for valid reasons**: If the ambiguous question flips between runs because the model is non-deterministic, the baseline records the observed variance rather than a single score.
- **Bug found in observability itself**: If a bug is not reproducible because traces or logs are missing, that missing instrumentation is itself filed as a bug (severity decided by blast radius).
- **Fault-injection scenario discovers an app bug that the scripted suite also misses**: The bug is filed under exploratory / fault-injection (whichever surfaced it first) and an additional ticket is opened to extend the scripted suite after v1.0.0.
- **Session runs long**: If the four-hour session runs over, the orchestrator closes intake at the four-hour mark and the remaining time is spent triaging Blockers via the F/D/P gate. No new exploration after the clock.

---

## Requirements *(mandatory)*

### Functional Requirements

**Scripted regression (US1)**

- **FR-001**: A scripted end-to-end regression suite MUST cover five critical happy-path user journeys: chat (ingest → query → cite), collection lifecycle (create → query), document lifecycle (upload → list → delete), settings update, and a cross-page workflow that ties the first four together.
- **FR-002**: Before any new flow is written, the existing six scripted specs MUST be brought to a green state — each of the sixteen known failing tests MUST be resolved via selector fix, app-bug fix, or explicit deletion with written justification.
- **FR-003**: The scripted suite MUST run in continuous integration on every pull request targeting `develop` or `main`, and MUST be enforced by the branch-protection aggregate check so that a failing flow blocks merge.
- **FR-004**: The scripted suite MUST produce, on failure, a trace artifact and a screenshot bundle that is retained long enough to support post-hoc debugging (seven days minimum).
- **FR-005**: After stabilization, the `frontend-e2e` continuous-integration job MUST NOT have `continue-on-error: true` — a failed run must fail the job.

**Exploratory session (US2)**

- **FR-006**: A single four-hour charter-driven exploratory session MUST be executed against a fully-seeded local instance with the gas-regulation corpus loaded.
- **FR-007**: Findings MUST be logged live during the session — no batched end-of-session catch-up write-up.
- **FR-008**: Every finding MUST have the seven mandatory fields populated (severity, layer, steps to reproduce, expected, actual, artifact paths, root-cause hypothesis) before the session closes.
- **FR-009**: The session MUST occur on the committed corpus (not a synthetic stand-in) so that language and domain realism are preserved.

**Fault injection (US3)**

- **FR-010**: Between three and five targeted fault-injection scenarios MUST be executed against the live container stack during or adjacent to the exploratory session.
- **FR-011**: Each scenario MUST record the exact fault command or action, the observed user-facing outcome, a pass/fail verdict, and a remediation note.
- **FR-012**: Fault-injection MUST run against the normal local container stack, gated by a documented preflight checklist that MUST be completed before the session begins (items: save open work, confirm no other processes are actively using the stack, optional volume snapshot if the user wants additional safety). Spawning a throwaway parallel stack is explicitly out of scope for v1.0.0.

**Quality baseline (US4)**

- **FR-013**: A golden Q&A dataset of exactly twenty pairs MUST be curated from the committed gas-regulation corpus and committed to the repository under the session documentation directory.
- **FR-014**: The golden dataset MUST cover all five question categories: ten factoid, four analytical, three follow-up, two out-of-scope, one ambiguous.
- **FR-015**: The dataset MUST be Spanish-language (matching the corpus) — no English-translated proxies allowed.
- **FR-016**: Quality scores MUST be produced for retrieval precision, answer relevance, citation faithfulness, and context recall.
- **FR-017**: Numeric results MUST be published in `quality-metrics.md` under the session documentation directory, including per-category averages and overall averages.
- **FR-018**: Each of the four pre-registered hypotheses MUST be explicitly marked confirmed or refuted by the baseline.
- **FR-019**: Dataset authorship MUST follow a hybrid split: the user hand-authors the three highest-bias pairs (the one ambiguous pair and the two out-of-scope pairs) in their entirety; the remaining seventeen pairs (ten factoid, four analytical, three follow-up) MAY be scaffolded from the corpus and MUST be reviewed, edited as needed, and accepted by the user before the baseline runs.

**Documentation trail (US5)**

- **FR-020**: A dated session documentation directory MUST be created under `docs/E2E/YYYY-MM-DD-bug-hunt/` and contain: `session-log.md`, `bugs-found.md`, a `bugs-raw/` directory with one markdown per bug, `scenarios-executed.json`, `quality-metrics.md`, a `traces/` directory, a `screenshots/` directory, and a final `SUMMARY.md`.
- **FR-021**: The `SUMMARY.md` MUST include a severity treemap rendered from the bug data and MUST be linked from the top-level README.
- **FR-022**: The bug markdown template MUST follow the seven-field schema (severity / layer / steps to reproduce / expected / actual / artifacts / root-cause hypothesis).

**Gate protocol (US6)**

- **FR-023**: An F/D/P decision (fix now / defer / pause + investigate) MUST be recorded for every Blocker-severity bug before the session resumes past that finding.
- **FR-024**: A `P` (pause + investigate) decision MUST eventually resolve to either F or D before session close.
- **FR-025**: At session close, every Blocker MUST have a promoted GitHub issue OR an explicit defer rationale captured in the bug file.

**Scope boundaries**

- **FR-026**: The Makefile MUST remain unchanged (fourteen targets per prior spec contracts). Any new automation lives in launcher scripts or the session runbook, never in new Makefile targets.
- **FR-027**: No existing shipped feature may be regressed as a side effect of this spec's changes — specifically: the frontend redesign polish, chat streaming and citation rendering, GPU-accelerated performance characteristics of warm queries, and the CI/CD gate roster.
- **FR-028**: The gas-regulation corpus directory (currently untracked in the working tree) MUST be committed to the repository as part of this spec, because it is the authoritative fixture for the baseline and the exploratory session.
- **FR-029**: The scripted suite MUST run in Chromium only. Firefox and WebKit coverage are explicitly out of scope for v1.0.0; re-introducing them is a v1.1 decision.

### Key Entities *(include if feature involves data)*

- **Session Documentation Directory**: A single dated directory under `docs/E2E/` that contains the full audit trail of the session. One session, one directory. All other entities in this spec live inside it.
- **Bug Record**: A single markdown file in `bugs-raw/` per discovered bug. Has seven mandatory fields. Its severity drives gate behavior and promotion to a GitHub issue.
- **Scenario Execution Log**: A machine-readable list of every scripted, exploratory, and fault-injection scenario executed, with pass/fail and timing — enables later analysis without re-reading prose.
- **Golden Q&A Pair**: A Spanish-language question anchored to a specific passage in the gas-regulation corpus, with a reference answer and a category tag. Twenty pairs total.
- **Quality Metric Row**: A numeric score per (question category, metric) tuple, plus overall averages. Lives in `quality-metrics.md`.
- **Severity Decision**: An F/D/P verdict on a Blocker bug with a timestamp and one-sentence rationale.
- **Gas Regulation Corpus**: The eleven Argentine gas regulatory PDFs that constitute the demo dataset. Currently untracked; committed by this spec.

---

## Assumptions

These are reasonable defaults adopted for items the upstream prompt left open. Any can be reversed by the user during clarification or planning, but none block spec completion.

- **Session scheduling**: The four-hour exploratory session runs as a single uninterrupted block rather than two two-hour sessions, because context-switching cost on exploratory work is high and the charter is continuous.
- **Quality-measurement approach**: The baseline uses the established RAGAS library rather than a hand-rolled similarity pipeline, because RAGAS is the de-facto standard for this measurement and the dependency is additive only.
- **GitHub issue promotion gate**: Only Blocker-severity bugs auto-promote to GitHub issues at session close. Major and below remain in the local bug log and are triaged separately for v1.1 planning. This is the conservative default; broadening later is cheap.
- **Session timing**: The session is treated as a single calendar day's work. If unavoidable interruptions arise, the session pauses and resumes on the same day — no cross-day splits.
- **Quarantined tests**: A scripted test that cannot be stabilized within this spec is marked quarantined (not deleted) with an inline comment linking to the filed bug. Quarantine count is surfaced in `SUMMARY.md`. No quarantined tests ship to main without an explicit user decision.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The scripted end-to-end suite runs in continuous integration on every pull request, and all flows pass on `develop` HEAD at session close.
- **SC-002**: Exactly one four-hour exploratory session has executed, and every finding logged in `bugs-raw/` has all seven mandatory fields populated.
- **SC-003**: Quality scores are published for a twenty-pair golden dataset covering all five question categories, with per-category and overall averages visible in `quality-metrics.md`.
- **SC-004**: One hundred percent of bugs filed during the session have severity, layer, reproduction steps, and root-cause hypothesis populated.
- **SC-005**: Every Blocker-severity bug has been triaged in-session via the F/D/P gate; no Blocker leaves the session in an unassigned state.
- **SC-006**: A final `SUMMARY.md` is written, linked from the top-level README, and includes a severity treemap.
- **SC-007**: At least three fault-injection scenarios have been executed, each with a pass/fail verdict and a remediation note.
- **SC-008**: The gas-regulation corpus is committed to the repository, and the golden dataset covers all five question categories.
- **SC-009**: The four pre-registered quality hypotheses are each marked confirmed or refuted in `quality-metrics.md`, regardless of direction.
- **SC-010**: The Makefile is unchanged at session close — verified by diff against `develop` HEAD at session start.
- **SC-011**: The sixteen previously failing scripted tests are all resolved — fixed, repaired via app change, or explicitly deleted with written rationale — and zero silently quarantined without a filed bug.

---

## Non-Goals *(explicit)*

- This spec does not ship v1.0.0 itself. It produces the bug list and the quality baseline that v1.0.0 consumes.
- This spec does not rewrite prior verification reports. It produces a single new canonical `bugs-found.md` that supersedes earlier scattered lists.
- This spec does not introduce a production-grade test framework. The toolkit is bounded to scripted E2E runs, pytest for the quality pipeline, and destructive container-level faults.
- This spec does not address observability or tracing gaps. If a missing trace breaks a bug's reproducibility, that missing instrumentation is itself a filed bug rather than a scope expansion.
- Property-based testing, mutation testing, visual-regression snapshots, multi-browser coverage beyond Chromium, embedding-model swap, and production-load soak tests are all deferred to v1.1 or later.
