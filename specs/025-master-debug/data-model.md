# Data Model: Spec 25 --- Master Debug Battle Test

**Date**: 2026-03-31
**Note**: This spec produces NO database schema changes. All entities below describe the testing domain model --- the structured data that flows through PaperclipAI tasks, Engram persistence, and the final report. These are documentation structures, not database tables.

## Entity Relationship Overview

```
TestPhase (10) --1:N--> TestTask (62)
TestPhase (10) --1:1--> PhaseSummary (10)
TestTask  --0:N--> BugReport (variable)
ModelCombination (7) --1:5--> QueryResult (35)
ModelCombination (7) --1:1--> ScorecardEntry (7)
ChaosScenario (6) --1:1--> ChaosResult (6)
SecurityProbe (7) --1:1--> ProbeResult (7)
GateCheck (4) --1:N--> GateCheckItem (variable)
QueryArchetype (5) --used by--> QueryResult (per combo)
```

## Entities

### TestPhase

A sequential block of related test activities. 10 phases total, organized into 5 waves.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| phase_id | string | P1-P10, unique | Phase identifier |
| name | string | required | Phase name (e.g., "Infrastructure Verification") |
| wave | integer | 1-5, required | Which wave this phase belongs to |
| status | enum | NOT_STARTED / IN_PROGRESS / COMPLETED / BLOCKED | Current phase status |
| assigned_agents | string[] | required | Agent IDs assigned (e.g., ["A1"], ["A2", "CEO"]) |
| prerequisites | string[] | optional | Gate IDs that must pass before this phase starts |
| fr_coverage | string[] | required | List of FR IDs covered (e.g., ["FR-001", "FR-002"]) |
| sc_coverage | string[] | required | List of SC IDs covered |
| started_at | datetime | set on transition to IN_PROGRESS | When phase testing began |
| completed_at | datetime | set on transition to COMPLETED | When phase testing finished |
| engram_topic_key | string | required | Engram key for persistence (e.g., "spec-25/p1-infrastructure") |
| pass_count | integer | >= 0 | Number of tests passed in this phase |
| fail_count | integer | >= 0 | Number of tests failed in this phase |
| bug_count | integer | >= 0 | Number of bugs found in this phase |

**State Transitions**:
```
NOT_STARTED --> IN_PROGRESS  (prerequisite gates passed, wave started)
IN_PROGRESS --> COMPLETED    (all tasks executed, phase summary persisted)
IN_PROGRESS --> BLOCKED      (critical failure, requires human intervention)
BLOCKED     --> IN_PROGRESS  (human resolved blocking issue)
```

**Validation Rules**:
- Phase cannot transition to COMPLETED without a PhaseSummary being persisted to Engram.
- Phase cannot transition to IN_PROGRESS if prerequisite gates have not passed.
- Phase P10 (Final Report) cannot start until Gate 4 is evaluated (regardless of pass/fail).

---

### ModelCombination

A pairing of one LLM model and one embedding model to be tested as a unit.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| combo_id | integer | 1-7, unique | Combination number |
| llm_model | string | required | LLM model name (e.g., "qwen2.5:7b") |
| embedding_model | string | required | Embedding model name (e.g., "nomic-embed-text") |
| approx_vram_gb | float | > 0 | Approximate VRAM usage in GB |
| requires_reingestion | boolean | required | True if embedding dimensions differ from baseline |
| status | enum | NOT_TESTED / TESTING / COMPLETED / VRAM_EXCEEDED / SKIPPED | Testing status |
| pull_time_seconds | float | nullable | Time to pull model into Ollama |
| model_size_gb | float | nullable | Model size on disk |
| peak_vram_mb | integer | nullable | Peak observed VRAM usage during inference |
| idle_vram_mb | integer | nullable | VRAM usage at idle after model load |
| reingestion_time_seconds | float | nullable | Time to re-ingest documents (combos 6-7 only) |
| overall_score | float | nullable, 1.0-5.0 | Weighted overall score from rubric |
| notes | string | optional | Free-text notes (OOM details, anomalies) |

**State Transitions**:
```
NOT_TESTED    --> TESTING       (model switched, queries starting)
TESTING       --> COMPLETED     (all 5 queries scored)
TESTING       --> VRAM_EXCEEDED (OOM detected, documented with memory figures)
NOT_TESTED    --> SKIPPED       (blocked by prior failure, documented)
```

**Validation Rules**:
- Combos 1-5 share nomic-embed-text; they reuse existing collections (requires_reingestion = false).
- Combos 6-7 use mxbai-embed-large; they require new collections and re-ingestion (requires_reingestion = true).
- A combo marked VRAM_EXCEEDED must have peak_vram_mb populated.
- overall_score is null for VRAM_EXCEEDED and SKIPPED combos.

---

### QueryResult

The result of running one query archetype against one model combination.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| combo_id | integer | FK -> ModelCombination | Which combo was tested |
| archetype_id | integer | 1-5 | Which query archetype (Q1-Q5) |
| query_text | string | required | Exact query sent |
| response_text | string | required | Full response received |
| citation_count | integer | >= 0 | Number of citations returned |
| confidence_score | integer | 0-100 | Confidence score from metadata frame |
| groundedness | string | nullable | Groundedness verdict |
| ttft_ms | integer | > 0 | Time to first token in milliseconds |
| total_latency_ms | integer | > 0 | Total response time in milliseconds |
| tokens_per_second | float | nullable | Streaming throughput |
| answer_quality | integer | 1-5 | Rubric: relevance, completeness, coherence |
| citation_accuracy | integer | 1-5 | Rubric: citations match and support answer |
| response_coherence | integer | 1-5 | Rubric: clarity, structure, no contradictions |
| streaming_smoothness | integer | 1-5 | Rubric: consistent token flow vs bursty |
| instruction_following | integer | 1-5 | Rubric: precisely addresses query intent |

**Validation Rules**:
- Each combo should have exactly 5 QueryResults (one per archetype), unless VRAM_EXCEEDED.
- All rubric dimensions scored 1-5 (integer, no fractional scores).
- ttft_ms derived from log timestamps (first "chunk" event minus request timestamp).

---

### ScorecardEntry

A ranked row in the model comparison scorecard, derived from QueryResult averages.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| rank | integer | 1-7, unique | Rank by overall score (1 = best) |
| combo_id | integer | FK -> ModelCombination | Which combo |
| llm_model | string | required | LLM model name |
| embedding_model | string | required | Embedding model name |
| overall_score | float | 1.0-5.0 | Weighted average across all dimensions |
| avg_answer_quality | float | 1.0-5.0 | Mean across 5 queries |
| avg_citation_accuracy | float | 1.0-5.0 | Mean across 5 queries |
| avg_response_coherence | float | 1.0-5.0 | Mean across 5 queries |
| latency_score | float | 1.0-5.0 | Normalized: 5 = fastest combo, 1 = slowest |
| vram_efficiency_score | float | 1.0-5.0 | Normalized: 5 = lowest VRAM, 1 = highest |
| avg_streaming_smoothness | float | 1.0-5.0 | Mean across 5 queries |
| avg_ttft_ms | float | > 0 | Mean TTFT across 5 queries |
| peak_vram_mb | integer | > 0 | Peak VRAM from ModelCombination |
| is_recommended | boolean | required | True for the recommended default configuration |
| tradeoff_notes | string | required | Quality vs latency vs VRAM analysis |

**Derivation**:
```
overall_score = (avg_answer_quality * 0.30) +
                (avg_citation_accuracy * 0.25) +
                (avg_response_coherence * 0.15) +
                (latency_score * 0.15) +
                (vram_efficiency_score * 0.10) +
                (avg_streaming_smoothness * 0.05)
```

---

### BugReport

A structured finding discovered during testing.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| bug_id | string | BUG-001 through BUG-NNN, unique | Sequential bug ID |
| severity | enum | P0-CRITICAL / P1-HIGH / P2-MEDIUM / P3-LOW | Severity classification |
| phase | string | required | Phase where discovered (e.g., "P2: Core Functionality") |
| component | enum | Backend / Frontend / Infrastructure / Inference Service / Vector Database | Affected component |
| affected_spec | string | required | Which spec introduced the functionality (e.g., "Spec-02") |
| title | string | required | Descriptive title |
| steps_to_reproduce | string[] | min 2 items | Numbered reproduction steps |
| expected_behavior | string | required | What should happen |
| actual_behavior | string | required | What actually happened |
| log_evidence | string | optional | Relevant log lines with timestamps |
| root_cause_analysis | string | required | Best assessment ("Unknown" triggers S1 assignment) |
| fix_recommendation | string | required | Concrete suggestion for resolution |
| regression_test | string | required | What automated test should prevent recurrence |
| screenshots | string[] | optional | Screenshot file paths if applicable |

**Severity Classification**:
| Severity | Definition | Action |
|----------|-----------|--------|
| P0-CRITICAL | Core functionality broken, data loss, security vulnerability | Escalate to CTO (S3). Blocks release. |
| P1-HIGH | Major feature broken, significant UX degradation | High priority fix. Documented prominently in report. |
| P2-MEDIUM | Feature partially broken, workaround exists | Normal priority. Fix recommended but not blocking. |
| P3-LOW | Cosmetic or minor annoyance | Low priority. Fix at convenience. |

**Validation Rules**:
- Every bug must have all required fields populated (NFR-006).
- root_cause_analysis of "Unknown" triggers assignment to S1 (Root Cause Analyst).
- P0-CRITICAL bugs are escalated to S3 (CTO) immediately upon discovery.
- Bug IDs are globally sequential across all phases (not per-phase).

---

### PhaseSummary

A per-phase synthesis of findings persisted to Engram before advancing.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| phase_id | string | P1-P10, FK -> TestPhase | Which phase |
| phase_name | string | required | Phase name |
| status | enum | PASS / PARTIAL_PASS / FAIL | Overall phase outcome |
| sc_results | object[] | required | SC evaluations: {sc_id, status, notes} |
| fr_results | object[] | required | FR evaluations: {fr_id, status, notes} |
| bugs_found | string[] | optional | Bug IDs found in this phase |
| key_findings | string[] | required, min 1 | Bullet-point findings |
| recommendations | string[] | optional | Action items for future work |
| engram_topic_key | string | required | Where this was persisted |
| persisted_at | datetime | required | When saved to Engram |

**Validation Rules**:
- Must be persisted BEFORE the phase transitions to COMPLETED (NFR-003).
- Must include PASS/FAIL status for every applicable SC in the phase.
- Must reference all bugs found during the phase by bug_id.

---

### ChaosScenario

A deliberate infrastructure failure test with defined protocol.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| scenario_id | string | T052-T057 | Task ID from plan |
| name | string | required | Descriptive name (e.g., "Kill Ollama mid-query") |
| fr_id | string | required | Functional requirement covered |
| inject_command | string | required | Docker command to inject the fault |
| expected_behavior | string | required | What the system should do during the fault |
| recovery_command | string | required | Command to restore the service |
| pre_condition_check | string | required | Health verification before injection |
| status | enum | NOT_TESTED / INJECTED / OBSERVED / RECOVERED / FAILED_RECOVERY | Scenario status |
| behavior_during_fault | string | nullable | What actually happened during the fault |
| recovery_time_seconds | float | nullable | Time from restore command to healthy |
| data_loss | boolean | nullable | Whether data was lost during the scenario |
| circuit_breaker_activated | boolean | nullable | Whether circuit breaker tripped |
| bugs_found | string[] | optional | Bug IDs found during this scenario |

**State Transitions**:
```
NOT_TESTED      --> INJECTED        (fault command executed)
INJECTED        --> OBSERVED        (behavior documented)
OBSERVED        --> RECOVERED       (service restored, health verified, query succeeds)
OBSERVED        --> FAILED_RECOVERY (recovery exceeded 120s or data lost)
```

**Validation Rules**:
- System MUST be verified healthy before injection (pre_condition_check).
- System MUST be restored to healthy after every scenario (NFR-005).
- recovery_time_seconds > 120 triggers FAILED_RECOVERY status.

---

### SecurityProbe

A security test with payloads and expected behavior.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| probe_id | string | T059-T065 | Task ID from plan |
| name | string | required | Descriptive name (e.g., "Prompt injection --- system prompt") |
| fr_id | string | required | Functional requirement covered |
| payloads | string[] | required, min 1 | Attack payloads sent |
| expected_result | string | required | What SHOULD happen (e.g., "LLM does not reveal prompt") |
| actual_result | string | nullable | What actually happened |
| status | enum | NOT_TESTED / PASS / FAIL / PARTIAL | Test outcome |
| vulnerability_severity | enum | NONE / LOW / MEDIUM / HIGH / CRITICAL | If a vulnerability was found |
| bugs_found | string[] | optional | Bug IDs if vulnerability found |

---

### QueryArchetype

One of 5 standardized query types used across all model combinations.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| archetype_id | integer | 1-5, unique | Archetype number |
| name | string | required | Archetype name (e.g., "Simple factual lookup") |
| purpose | string | required | What this archetype tests |
| coverage_target | string | required | What quality dimension it primarily measures |
| query_template | string | required | Pattern for crafting the actual query |
| actual_query | string | nullable | Exact query crafted by CEO at runtime |

**Fixed Values**:
| # | Name | Purpose | Coverage Target |
|---|------|---------|-----------------|
| 1 | Simple factual lookup | Single-document, direct answer retrieval | Retrieval accuracy |
| 2 | Multi-hop reasoning | Synthesize across multiple documents | Reasoning depth |
| 3 | Comparison question | Compare/contrast from different sources | Cross-document retrieval |
| 4 | Out-of-domain | Topic not in any document | Hallucination resistance |
| 5 | Vague/ambiguous | Underspecified query | Clarification handling |

---

### GateCheck

A verification checkpoint between waves.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| gate_id | integer | 1-4, unique | Gate number |
| name | string | required | Gate name (e.g., "Infrastructure Foundation") |
| when | string | required | When this gate runs (e.g., "After Phase 1") |
| assigned_to | string[] | required | Agent IDs (e.g., ["S2", "CEO"]) |
| checks | GateCheckItem[] | required | Individual checks within this gate |
| status | enum | NOT_EVALUATED / PASS / FAIL | Gate outcome |
| on_failure_action | string | required | What happens if gate fails |

### GateCheckItem

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| check_number | integer | required | Sequential within gate |
| description | string | required | What is being checked |
| command_or_method | string | required | How to verify |
| pass_criteria | string | required | What constitutes a pass |
| status | enum | NOT_CHECKED / PASS / FAIL | Individual check outcome |
| notes | string | optional | Observations |
