# Contract: Gate Check Procedures

**Version**: 1.0 | **Spec**: 025-master-debug

## Purpose

Gate checks are verification checkpoints between waves. They prevent advancing to the next wave of testing when prerequisites are not met. The Self Review agent (S2) and CEO execute gate checks jointly.

## Gate 1: Infrastructure Foundation

**When**: After Phase 1 completes (end of Wave 1)
**Who**: S2 (Self Review) + CEO
**Blocks**: Wave 2 (P2 + P3)

| # | Check | Command/Method | Pass Criteria |
|---|-------|----------------|---------------|
| 1 | All 4 services healthy | `docker compose ps` | qdrant, ollama, backend, frontend all "healthy" or "running" |
| 2 | Backend health endpoint | `curl localhost:8000/api/health` | HTTP 200 with all dependencies "operational" |
| 3 | Frontend serves pages | `curl localhost:3000` | HTTP 200 response |
| 4 | GPU accessible | `docker compose exec ollama nvidia-smi` | GPU listed with VRAM info |
| 5 | Baseline models available | `curl localhost:11434/api/tags` | qwen2.5:7b + nomic-embed-text present |
| 6 | Seed data present | `curl localhost:8000/api/collections` | >= 1 collection with ingested documents |
| 7 | No startup errors | `docker compose logs --tail 50` | No ERROR-level entries |

**On failure**: BLOCK Wave 2. CEO documents failures. If infrastructure is broken, testing cannot proceed --- escalate to human for manual investigation.

---

## Gate 2: Core Testing Baseline

**When**: After Phases 2 and 3 complete (end of Wave 2)
**Who**: S2 (Self Review) + CEO
**Blocks**: Wave 3 (P4 + P5 + P6)

| # | Check | Pass Criteria |
|---|-------|---------------|
| 1 | Chat works E2E via UI | Streaming response with citations and confidence (SC-002) |
| 2 | Chat works via API | Complete NDJSON stream with all event types |
| 3 | Collection CRUD works | Create + delete via both UI and API |
| 4 | Document ingestion works | Upload completes, status = "completed" |
| 5 | >= 5/7 model combos tested | Scorecard has >= 5 rows with scores (SC-003) |
| 6 | Baseline scores recorded | Combo 1 (qwen2.5:7b + nomic-embed-text) fully scored |
| 7 | All API endpoints respond | models, stats, traces, settings return valid data |

**On failure**:
- If chat does not work E2E: BLOCK Wave 3. This is the minimum requirement.
- If model testing fell short (< 5 combos): PROCEED with caveats. Document which combos were not tested and why.
- If API endpoints fail: Document failures but PROCEED (Wave 3 does not depend on all endpoints).

---

## Gate 3: Stress and Security Clear

**When**: After Phases 4, 5, and 6 complete (end of Wave 3)
**Who**: S2 (Self Review) + CEO
**Blocks**: Wave 4 (P7 + P8 + P9)

| # | Check | Pass Criteria |
|---|-------|---------------|
| 1 | Data quality measured | Citation accuracy, calibration, consistency recorded (SC-006) |
| 2 | All 6 chaos scenarios executed | Before/during/after documented for each (SC-004) |
| 3 | System healthy after chaos | All services healthy, data intact (NFR-005) |
| 4 | Security probes complete | All 7 probes executed with results (SC-005) |
| 5 | No CRITICAL vulnerabilities | No XSS execution, no SQL injection, no data exposure |
| 6 | System in baseline state | Ready for Wave 4 testing (all services healthy) |

**On failure**:
- If system is NOT healthy after chaos: RESTORE before proceeding. Run recovery commands.
- If CRITICAL vulnerabilities found: Escalate to S3 (CTO) for priority triage. Document but PROCEED.
- If data quality not fully measured: PROCEED with caveats. Document what was missed.

---

## Gate 4: Coverage Complete

**When**: After Phases 7, 8, and 9 complete (end of Wave 4)
**Who**: S2 (Self Review) + CEO
**Does NOT block**: Wave 5 (P10) always proceeds.

| # | Check | Pass Criteria |
|---|-------|---------------|
| 1 | UX journey audited | All 5 audit items (FR-063 to FR-067) completed (SC-010) |
| 2 | Regression sweep done | >= 9/11 regression items pass (SC-008) |
| 3 | Performance baselines recorded | TTFT with 5+ samples, GPU profiles for 3+ combos (SC-009) |
| 4 | All findings persisted | Each phase has Engram topic with structured data |
| 5 | Bug reports complete | Every bug has full structured entry (NFR-006) |

**On failure**: PROCEED to Phase 10 regardless. The final report documents what was completed and what was not. Gate 4 failure affects report completeness, not report generation.

---

## Gate Check Execution Protocol

1. CEO announces gate check: "Starting Gate {N} verification."
2. CEO creates a task for S2: "Gate {N} verification --- check all items."
3. S2 executes each check sequentially, posting results as task comments.
4. CEO reviews S2 results and makes the PASS/FAIL determination.
5. If PASS: CEO announces "Gate {N} PASSED. Advancing to Wave {N+1}."
6. If FAIL: CEO documents failures, applies the on-failure action, and either blocks or proceeds with caveats.
7. Gate results are persisted to the preceding phase's Engram topic key (e.g., Gate 1 results go in `spec-25/p1-infrastructure`).

## Makefile Integrity Check

At every gate, verify the Makefile has not been modified:

```bash
git diff HEAD -- Makefile
# Expected: empty output (no changes)
```

This is a standing check that applies to all gates. If the Makefile shows changes, BLOCK and investigate.
