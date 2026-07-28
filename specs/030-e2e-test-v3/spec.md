# Feature Specification: E2E Test v3 — Single-Round Human-in-the-Loop Bug Hunt (Pre-v1.0.0)

**Feature Branch**: `030-e2e-test-v3`
**Created**: 2026-05-15
**Status**: Draft
**Input**: User description: "Read @docs-Bruno/PROMPTS/spec-30-E2E-test-v3/30-specify.md"

## Overview

A **time-boxed, single-round** end-to-end bug hunt over the running product surface, driven by a human Pilot in a real browser while supporting roles observe logs, screenshots, and graph state asynchronously. Discovery only — no production code changes during the hunt (those belong to a later fix wave). The deliverable is a **public, defensible bug registry**: a triaged list of findings with severity, reproduction steps, supporting artifacts, and v1.0-fix-or-v1.1-defer decisions for every MAJOR or higher finding.

The hunt is the last pre-launch validation gate for v1.0.0. It exists because shipping a portfolio-quality release requires evidence of human-driven discovery, not just CI green checks — and because the loop-until-clean alternative ("zero new MAJOR") is asymptotic and never decidable in finite time for a solo developer.

## Clarifications

### Session 2026-05-15

- Q: How should screenshots and log excerpts captured during the hunt be persisted, given they may contain API keys, decrypted secrets, or other sensitive material? → A: Hybrid — bug records, triage document, final summary, machine-readable registry, and session log are tracked in the public repo; raw screenshots and captured log excerpts are gitignored by default; the Pilot manually promotes a curated, redacted subset to a tracked `public-evidence/` sub-directory after verifying no sensitive material is present.
- Q: How should "documented X budget" references in acceptance scenarios (startup, latency, timeouts, status states, UX) resolve to concrete pass/fail values? → A: Hybrid — cite existing project-level budgets from spec-14 (performance budgets) and spec-26 (latency p50/p95) where the dimension is already covered; the phase-playbook defines new concrete values for dimensions not yet covered (startup readiness, ingestion progress, document status transitions); the playbook MUST enumerate every "documented X" reference with its concrete source.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Cold Start Hunt (Priority: P1)

The Pilot brings up a clean stack from a fully stopped state and validates that every readiness signal, health check, and first-paint dashboard renders correctly. The supporting roles capture every startup message, every health-check transition, and every first-paint screenshot for the registry.

**Why this priority**: A broken cold start blocks every other phase. Any defect found here is almost always BLOCKER or CRITICAL — the app cannot start cleanly, which means no user can reach the rest of the product. This is the foundation phase; without it, the hunt cannot proceed.

**Independent Test**: Stop the running stack, bring it up via the documented start procedure (e.g., `make demo` or container orchestration), and observe whether the dashboard reaches "fully ready" state with all health indicators green. Any failure to reach that state is a registered bug.

**Acceptance Scenarios**:

1. **Given** the stack is fully stopped, **When** the Pilot runs the documented start procedure, **Then** every service reaches its ready state within the documented startup budget AND the dashboard renders without console errors AND all visible health indicators turn green.
2. **Given** any service fails to reach ready state during cold start, **When** the Pilot observes the failure, **Then** the failure is registered with severity assigned, reproduce steps, captured logs, and a screenshot of the broken state.
3. **Given** the dashboard renders but shows a degraded health indicator, **When** the Pilot inspects the indicator, **Then** the discrepancy between "rendered" and "actually healthy" is registered as a finding.

---

### User Story 2 — Ingestion Hunt (Priority: P1)

The Pilot creates one or more collections, uploads documents of each supported file type, and observes worker logs and progress UI in real time. Adversarial cases are included: malformed file, oversized file, duplicate upload, and mid-upload backend kill. Status transitions and final chunk counts are validated against expectations.

**Why this priority**: No chat phase can be hunted without ingested content. Ingestion failures are CRITICAL because they cut off the entire downstream product. The phase also exposes worker behavior under adversarial input, which has historically been a high-defect-density surface.

**Independent Test**: Starting from a clean stack with at least one collection created, upload one document of each supported file type and verify each reaches "fully ingested + queryable" state within the documented ingestion budget. Inject the adversarial cases one at a time and verify graceful handling for each.

**Acceptance Scenarios**:

1. **Given** a fresh collection exists, **When** the Pilot uploads a valid document of each supported file type, **Then** each document transitions through the documented status states without skipping or stalling AND reaches a "queryable" state AND the parent + child chunk counts shown in the UI match what the backend persisted.
2. **Given** a malformed file is uploaded, **When** the worker processes it, **Then** the system surfaces a user-readable error within the documented timeout AND does not enter an inconsistent state AND a retry without crash is possible.
3. **Given** a backend process is killed mid-upload, **When** the stack returns to ready, **Then** the partial state is either resumed cleanly or cleaned up — never left as an orphan that blocks future uploads.
4. **Given** the same document is uploaded twice, **When** the second upload is initiated, **Then** the system handles the duplicate per its documented policy (reject, replace, or version) without data corruption.

---

### User Story 3 — Chat Happy Path Hunt (Priority: P1)

The Pilot asks a curated set of corpus-grounded questions, observes the streaming response, validates citations, and checks the trace surface. Includes multi-turn conversations and citation hover/click behaviors. The chat question set is hybrid: questions from the existing quality baseline (known-good answers, known-decline, Spanish/English mix) plus probes specifically designed to exercise rendering, streaming, and citation UX.

**Why this priority**: Chat is the primary product surface. Any defect on the happy path is at minimum MAJOR and likely CRITICAL because it lands on the user's very first interaction. Answer correctness is already validated by the existing quality baseline (85% ± 5%); this phase's focus is the rendering/streaming/citation surface.

**Independent Test**: With at least one fully ingested document available, ask each curated happy-path question through the chat UI. For each, verify that the response streams without stalling, citations render and resolve, and the multi-turn context is preserved across follow-ups.

**Acceptance Scenarios**:

1. **Given** a queryable corpus exists, **When** the Pilot asks a happy-path question, **Then** the response begins streaming within the documented latency budget AND completes without stalling AND every cited source is reachable when interacted with.
2. **Given** a streamed response includes citations, **When** the Pilot interacts with a citation (hover or click), **Then** the source content displays correctly AND the highlighted span matches the cited passage AND the trace surface shows the retrieval path that produced it.
3. **Given** a long-answer response exceeds the visible viewport, **When** the response continues streaming, **Then** the scroll behavior matches the documented UX (auto-scroll or manual control) without losing position or clipping content.
4. **Given** a multi-turn conversation, **When** the Pilot asks a follow-up that references a prior turn, **Then** the model retains the conversational context AND citations from the prior turn remain navigable from the new response.

---

### User Story 4 — Chat Edge Case Hunt (Priority: P2)

The Pilot probes adversarial chat prompts: out-of-scope questions, ambiguous prompts, mixed-language input (Spanish/English), prompt-injection attempts, and scenarios that trigger tool timeouts. The decline behavior and fallback responses are validated.

**Why this priority**: Edge case defects are typically MINOR–MAJOR. They matter for portfolio quality (they make up the "obvious to the first 100 visitors" surface) but they don't block launch on their own. Lower priority than happy path because a broken happy path is worse than a brittle edge case.

**Independent Test**: With the happy path validated, run the adversarial prompt set one at a time and verify each elicits a documented, defensible behavior (decline, fallback, clarification request, or graceful error).

**Acceptance Scenarios**:

1. **Given** a question is clearly out-of-corpus, **When** the model responds, **Then** it declines explicitly rather than hallucinating an answer AND the decline message is user-readable AND no fabricated citation is produced.
2. **Given** a prompt-injection attempt embedded in a question, **When** the model processes it, **Then** the system instructions are preserved AND the injection does not redirect the model's behavior.
3. **Given** an ambiguous question, **When** the model receives it, **Then** either a clarification is requested OR the response acknowledges the ambiguity and presents the most defensible interpretation.
4. **Given** a tool call times out mid-research, **When** the timeout fires, **Then** the user receives a defensible response (partial answer with disclosure or graceful failure) AND the trace surface shows the timeout point.

---

### User Story 5 — Settings & Providers Hunt (Priority: P2)

The Pilot exercises the model picker, API key storage, embedding model swap, and provider switching. Encrypted key storage, configuration persistence across restarts, and provider-registry behavior are all validated.

**Why this priority**: Settings/provider defects are usually MAJOR — they affect configurability and trust signals (e.g., a key visibly leaking would be CRITICAL). Lower priority than chat because most users won't touch settings on first visit, but a broken settings panel undermines the customizability story.

**Independent Test**: From a stable chat state, swap the active model via the picker, observe that the next chat uses the new model. Add a provider API key, restart the stack, verify the key persists and decrypts correctly. Swap the embedding provider and verify ingestion continues to work.

**Acceptance Scenarios**:

1. **Given** the Pilot adds a provider API key through the settings UI, **When** the stack is restarted, **Then** the key persists across the restart AND is never visible in plaintext in any logged or rendered surface AND chat continues to authenticate against that provider.
2. **Given** the Pilot swaps the active chat model, **When** the next chat is initiated, **Then** the new model is used for that response AND the change is reflected in observable surfaces (trace, status indicator).
3. **Given** the Pilot swaps the embedding provider mid-session, **When** new content is ingested, **Then** either the swap is correctly applied OR the user is given a clear path forward (re-ingest required, etc.) — no silent inconsistency.

---

### User Story 6 — Observability Hunt (Priority: P3)

The Pilot opens traces, performance charts, and logs. Validates that what the system *generates* is also *user-readable*: trace navigation works, stage timings visualize correctly, error codes surface with actionable context.

**Why this priority**: Observability defects are mostly MINOR or COSMETIC — the system still works, but diagnosis is harder. They matter for portfolio credibility (a half-built observability surface looks unfinished) but they rarely block launch.

**Independent Test**: After at least one happy-path chat has completed and at least one error has been surfaced, open each observability surface (trace viewer, performance chart, log surface) and verify the recent events are navigable, the timings are coherent, and any error is reachable from the originating user action.

**Acceptance Scenarios**:

1. **Given** a chat has just completed, **When** the Pilot opens the trace for that chat, **Then** every stage of the pipeline is visible AND each stage shows its timing AND clicking into a stage reveals its inputs and outputs.
2. **Given** an error has been surfaced to the user, **When** the Pilot opens the related diagnostic surface, **Then** the error code, timestamp, and originating operation are all present AND the user can navigate from the error message to its detailed context in one click.
3. **Given** the performance budget chart is opened, **When** the Pilot inspects the most recent operations, **Then** the chart is interpretable without prior knowledge of the internals AND any budget breach is visually distinguishable from a within-budget operation.

---

### User Story 7 — Recovery & State Hunt (Priority: P2)

The Pilot kills processes mid-stream, restarts the stack, validates checkpoint resume, session continuity, and dirty-state cleanup. Validates behavior when supporting infrastructure (inference engine, vector store) becomes unavailable.

**Why this priority**: Resilience defects are usually MAJOR — they don't block the happy path but they cause data loss, stuck sessions, or unrecoverable states that visibly degrade the product. Lower priority than the discovery phases because resilience is best tested AFTER core flows are validated.

**Independent Test**: With a chat in progress and an ingestion in progress, kill the orchestrating process. Restart the stack. Verify the chat session is recoverable (or cleanly closed with no orphan state) and the ingestion either resumes or surfaces as failed without poisoning future ingestions.

**Acceptance Scenarios**:

1. **Given** a streaming chat is mid-response, **When** the backend process is killed, **Then** on restart either the conversation resumes from its last checkpoint OR the session is cleanly closed with a user-visible explanation — never left half-rendered.
2. **Given** the inference engine becomes unavailable, **When** the Pilot attempts a chat, **Then** the user receives an actionable error within the documented timeout AND the system does not hang indefinitely AND chat resumes automatically when the engine returns.
3. **Given** an ingestion is in progress, **When** the vector store becomes unavailable, **Then** the ingestion is either paused with a clear resume path OR fails with the document quarantined for retry — never silently dropped.
4. **Given** the stack is restarted between sessions, **When** the Pilot returns, **Then** every previously persisted artifact (collections, prior conversations, settings) is still present AND reachable from the UI.

---

### Edge Cases

- **Hunt-cannot-continue blocker is found early in a phase**: A minimum-viable inline unblock-fix is allowed (≤5 minutes, zero-risk, MINOR or COSMETIC scope only) but ONLY after explicit Pilot Y/N confirmation. The blocker is still registered with full reproduction steps regardless of whether it was patched, so it can be properly re-fixed in the later fix wave.
- **Severity disagreement between Pilot and supporting role**: The Pilot's call is final during the hunt. Supporting roles may flag the disagreement in the bug record's notes section for later review.
- **Same defect surfaces in multiple phases**: The defect is registered once with the original BUG ID; subsequent phase observations are linked to the same record rather than creating duplicate entries.
- **Pilot cannot reproduce a defect that was visible earlier**: The defect is still registered with whatever artifacts were captured at first observation, marked as "intermittent — last seen at [timestamp]", and triaged accordingly.
- **The hunt's time-box is reached but phases remain**: Remaining phases are descoped to a future round; the registry reflects what was actually hunted. Closing the hunt before reaching the time-box is allowed if all 7 phases complete early.
- **A supporting role becomes unresponsive**: The Pilot continues solo on the affected phase, logging observations in plain text for retrospective integration. The hunt does not pause for tooling issues.
- **A finding has unclear severity**: Default to the higher of the two candidate severities (more conservative). Severity can be downgraded during the closing triage step with explicit justification.
- **The fix wave for the registry is already starting before the hunt closes**: The hunt MUST close the registry before the fix wave consumes it. Any parallel work on findings is forbidden to keep triage uncontaminated by pre-judging severity mid-hunt.

## Requirements *(mandatory)*

### Functional Requirements

#### Hunt scope and timing

- **FR-001**: The hunt MUST be time-boxed to 1.5 working days (approximately 12 hours), splittable across 2 calendar days.
- **FR-002**: The hunt MUST be executed as a single round; no loop, no second round within this specification.
- **FR-003**: The hunt MUST cover the seven defined product-surface phases (cold start, ingestion, chat happy path, chat edge cases, settings and providers, observability, recovery and state) in the defined order.
- **FR-004**: Each phase MUST have a documented entry condition and a documented exit signal; a phase cannot be entered until the prior phase's exit signal is observed.

#### Discovery and registration

- **FR-005**: Every defect MUST be registered with a unique sequential identifier; IDs MUST persist across any future hunt rounds.
- **FR-006**: Every registered defect MUST include severity, affected layer, reproduction steps, expected behavior, actual behavior, supporting artifacts (screenshot or log excerpt as applicable), and a root-cause hypothesis if one is offered.
- **FR-007**: Severity MUST be assigned from a fixed five-level framework: BLOCKER, CRITICAL, MAJOR, MINOR, COSMETIC.
- **FR-008**: Every defect's severity MUST be assigned during the hunt, not deferred to the closing triage step.
- **FR-009**: The hunt MUST produce both a human-readable session log (chronological timeline of observations) and a machine-readable bug registry (consumable by the later fix wave).

#### Discipline boundary

- **FR-010**: No production code MUST be modified during the hunt except for the BLOCKER-PATCHED exception defined below.
- **FR-011**: A BLOCKER-PATCHED inline fix is permitted ONLY when (a) the defect blocks hunt continuation, (b) the fix takes ≤5 minutes, (c) the fix is zero-risk, (d) the fix scope is MINOR or COSMETIC, and (e) the Pilot has explicitly confirmed GO via Y/N gate.
- **FR-012**: Every BLOCKER-PATCHED fix MUST be registered with full reproduction steps for the original defect, with a clear note that the fix was a temporary unblock; the registered defect remains in scope for the later fix wave.
- **FR-013**: Severity MUST NOT be downgraded by the existence of a BLOCKER-PATCHED fix.

#### Exit and closure

- **FR-014**: The hunt MUST NOT close until every CRITICAL finding has a complete record (severity, reproduction, artifacts).
- **FR-015**: The hunt MUST NOT close until every MAJOR finding has a triage decision recorded: either v1.0-fix (referenced by public issue) or v1.1-defer (referenced by public issue).
- **FR-016**: The hunt MUST NOT close until every BLOCKER-PATCHED inline fix has documented Pilot Y/N authorization captured in the session log.
- **FR-017**: The closing triage step MUST produce a human-readable summary that a non-technical stakeholder can read and understand without needing access to the codebase.

#### Scope and coverage

- **FR-018**: The hunt MUST be executed in Chromium (no multi-browser matrix).
- **FR-019**: The hunt MUST exercise the existing corpus; corpus substitution is out of scope for this round.
- **FR-020**: The chat question set MUST be hybrid: a subset drawn from the existing quality baseline plus probes designed specifically to exercise UI behavior (rendering, streaming, citation interaction).
- **FR-021**: The adversarial chat set MUST cover at minimum: out-of-scope questions, ambiguous prompts, mixed-language input, prompt-injection attempts, and induced tool timeouts.

#### Artifact persistence

- **FR-022**: All hunt artifacts MUST be persisted to a single dated session directory under the project's E2E documentation tree, with a tracked-vs-untracked split: bug records, triage document, final summary, machine-readable registry, and session log MUST be tracked in the public repository; raw screenshots and captured log excerpts MUST be gitignored by default.
- **FR-023**: The machine-readable bug registry MUST be valid against a documented schema so that the later fix wave can consume it programmatically.
- **FR-024**: Bug records MUST cross-reference any supporting artifacts (screenshots, log excerpts) by file path, not by inline duplication; the referenced paths MAY point to either gitignored or tracked locations depending on the artifact's curation status.

#### Methodology repeatability

- **FR-025**: The hunt methodology MUST be repeatable: a second Pilot following the same playbook on a comparable build MUST be able to produce a registry of equivalent structure and rigor.
- **FR-026**: The exit criterion (all CRITICAL filed, all MAJOR triaged) MUST be a deterministic, finite-time decidable check, not an asymptotic target.

#### Secret hygiene and evidence curation

- **FR-027**: A `public-evidence/` sub-directory within the session directory MUST be tracked in the public repository; the Pilot MUST manually promote a curated, redacted subset of screenshots and log excerpts into it for portfolio defensibility, with at least one tracked piece of evidence per CRITICAL finding when feasible.
- **FR-028**: Before promoting any artifact to `public-evidence/`, the Pilot MUST verify that no API keys, decrypted secrets, personally identifiable information, or other sensitive material is visible in the artifact; verification MUST be documented in the session log entry that promotes the artifact.

#### Acceptance criteria sourcing

- **FR-029**: Every reference to a "documented" budget, timeout, status set, or UX behavior in this specification's acceptance scenarios (e.g., "documented startup budget", "documented latency budget", "documented timeout", "documented status states", "documented UX", "documented ingestion budget") MUST resolve to a concrete, citable source in the companion `phase-playbook.md`. The playbook MUST enumerate every such reference and bind it to either (a) an existing project-level budget from spec-14 (performance budgets) or spec-26 (latency p50/p95 work) when the dimension is already covered, or (b) a playbook-defined concrete value for dimensions not yet covered by prior specs (startup readiness, ingestion progress, document status transitions, citation interaction UX).

### Key Entities

- **Bug Record**: A single registered defect. Attributes: unique ID, severity, affected layer/surface, reproduction steps, expected behavior, actual behavior, supporting artifacts (paths to screenshots and log excerpts), root-cause hypothesis (optional), triage decision (for MAJOR and higher), public issue link (for triaged findings), BLOCKER-PATCHED note (if applicable), observation timestamps. One file per record in the session directory.
- **Session Log**: Chronological timeline of every observation made during the hunt. Every entry is timestamped and references the bug record(s) it generated (if any).
- **Triage Document**: Rollup of severity counts plus the v1.0-fix-or-v1.1-defer decision for every MAJOR or higher finding, including the public issue link for each.
- **Bug Registry (machine-readable)**: A structured representation of the full bug record set, consumable by the later fix wave. MUST validate against a documented schema.
- **Phase Playbook** (companion file, created in planning phase): Concrete per-phase scenarios — the operational checklist the Pilot works through during each phase. Conceptual in this specification; concrete in the playbook.
- **Final Summary**: Human-readable closing document that a non-technical stakeholder can read to understand what was hunted, what was found, what is being fixed for v1.0, and what is deferred. Linked from the project README after the fix wave closes.
- **Launch Decision**: One-page Pilot decision document (GO / NO-GO / GO-WITH-CONDITIONS) recorded at hunt closure, referencing the bug registry and final summary as its evidence base. Carries the Pilot's signature and date. This is the SC-011 evidence artifact — the registry plus the final summary together must be sufficient for this go/no-go call without requiring additional investigation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The hunt completes its full seven-phase coverage within the 1.5-day time-box (no more than 12 working hours).
- **SC-002**: 100% of CRITICAL findings have a complete bug record before the hunt closes (severity, reproduction steps, expected vs. actual, supporting artifacts).
- **SC-003**: 100% of MAJOR or higher findings have a triage decision recorded with a public issue link (v1.0-fix or v1.1-defer).
- **SC-004**: 100% of registered bug records include all required attributes: unique ID, severity, layer, reproduction steps, expected behavior, actual behavior, supporting artifact references.
- **SC-005**: 100% of BLOCKER-PATCHED inline fixes have documented Pilot Y/N authorization in the session log.
- **SC-006**: 0 production code modifications occur during the hunt outside of authorized BLOCKER-PATCHED exceptions.
- **SC-007**: The final summary document is reviewable and comprehensible by a non-technical stakeholder (validated by a peer-review pass that does not reference the codebase).
- **SC-008**: The machine-readable bug registry validates against its documented schema (0 schema violations).
- **SC-009**: A second Pilot following the same playbook on the same build can reproduce at minimum 80% of the registered findings (methodology repeatability target).
- **SC-010**: All seven product-surface phases (cold start, ingestion, chat happy, chat edge, settings, observability, recovery) are entered, executed, and exited with their exit signals observed.
- **SC-011**: The hunt is the basis for a v1.0.0 launch decision: the registry plus the final summary together provide enough evidence for a go/no-go call without requiring additional investigation.
- **SC-012**: 0 secrets (API keys, decrypted credentials, personally identifiable information) appear in any artifact committed to the public repository across the entire hunt session.

## Assumptions

- **A-001**: The pre-hunt baseline is the stabilized develop branch (after the visibility-only CI jobs were brought green); no known active product-surface CRITICAL defects are present at hunt start. Anything the hunt surfaces is therefore new evidence.
- **A-002**: The existing corpus remains in place for this round; corpus licensing substitution is a separate workstream scheduled before the demo polish phase, not gating this hunt.
- **A-003**: The chat answer-correctness baseline (from the existing quality work) is the reference point for any "is retrieval or LLM regressing?" comparison; this hunt does not re-baseline correctness, only UI behavior around correctness.
- **A-004**: The fix wave that consumes this hunt's registry is strictly sequential — it MUST NOT start until the hunt closes its registry, to keep triage uncontaminated by pre-judging severity mid-hunt.
- **A-005**: The Pilot has full operational control of the local environment (stack lifecycle, file system, browser) for the duration of the hunt; supporting roles are read-only on production code outside the BLOCKER-PATCHED exception.
- **A-006**: The known pre-existing test failures and type-check warnings on develop are not in scope for this hunt; the hunt targets the running product surface, not internal CI signal.

## Dependencies

- The stabilized develop branch (with visibility-only CI jobs brought green) must be the basis for the hunt.
- The companion phase playbook (created in the planning phase of this specification's workflow) must define the concrete scenarios for each of the seven phases before hunt execution begins.
- The fix-wave specification (the next specification in sequence) depends on this hunt's machine-readable bug registry as its primary input; it cannot begin until this hunt closes.

## Out of Scope

- A second or subsequent hunt round; this specification is single-round.
- Code fixes for findings (deferred to the next specification — the fix wave).
- Multi-browser matrix testing (Chromium only).
- Property-based testing, mutation testing, visual regression testing.
- Load testing, soak testing, chaos engineering beyond the seven defined phases.
- Embedding model swap evaluation (already a known finding from prior quality work; deferred to v1.1).
- Model management UX redesign (deferred to v1.1 unless the hunt surfaces a CRITICAL).
- Branch protection or CI configuration changes (the pre-hunt baseline is taken as-is).
- Test framework additions or migrations (the hunt drives the real running app, not new test infrastructure).
