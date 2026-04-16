# Spec-25 Forensic Analysis: From PaperclipAI Failure to Agent Teams Battle Plan

**Date**: 2026-04-09
**Branch**: `025-master-debug`
**Analyst**: Orchestrator (Opus 4.6)
**Scope**: Full system autopsy + redesign strategy

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [What Failed with PaperclipAI](#2-what-failed-with-paperclipai)
3. [Cross-Spec Failure Patterns (Specs 21-24)](#3-cross-spec-failure-patterns)
4. [Complete Bug Inventory](#4-complete-bug-inventory)
5. [What Actually Works](#5-what-actually-works)
6. [GPU + Model Recommendations (RTX 4070 Ti)](#6-gpu--model-recommendations)
7. [New Spec-25 Agent Teams Design](#7-new-spec-25-agent-teams-design)
8. [Artifact Structure (speckit/implement prompts)](#8-artifact-structure)
9. [MCP Tool Strategy](#9-mcp-tool-strategy)
10. [Debug Priority Queue](#10-debug-priority-queue)
11. [What NOT To Do](#11-what-not-to-do)

---

## 1. Executive Summary

**The PaperclipAI spec-25 found 15 bugs but fixed ZERO.** It was a forensic audit, not a debug session. 11 agents, 5 waves, 98 tasks, ~8 hours of execution to produce a report. The app remains broken in the same way it was before spec-25 started.

The fundamental problem: **the app has never worked end-to-end as a RAG system**. Specs 21-24 each found critical architectural bugs, fixed some, deferred others, and passed the baton. The bugs compound:

| Layer | Status | Blocking? |
|-------|--------|-----------|
| Docker infrastructure | WORKS | No |
| Backend startup + health | WORKS | No |
| Frontend page rendering | WORKS | No |
| Document ingestion | WORKS (basic) | No |
| Chat streaming (NDJSON) | PARTIAL - token streaming works (spec-24 fix) | Yes |
| Citation display | BROKEN - events never emitted | Yes |
| Groundedness check | BROKEN - result never streamed | Yes |
| Confidence scoring | BROKEN - always returns 0 | Yes |
| Multi-turn conversation | BROKEN - checkpoint serialization error | Yes |
| Research loop termination | BROKEN - no wall-clock timeout | Yes |
| Concurrent requests | BROKEN - crashes at ~10 requests | Yes |

**Bottom line**: The plumbing works. The RAG brain is broken. We need to fix 7 specific bugs in 4 specific files to make this a functional system.

---

## 2. What Failed with PaperclipAI

### 2.1 The Approach

PaperclipAI used a "CEO orchestrator" pattern:
- 1 CEO agent (Opus) directing 7 specialist agents + 3 support agents
- Goals hierarchy requiring "Board approval" before execution
- wakeOnDemand activation with 60s/120s heartbeat polling
- Engram persistence after EVERY phase
- NFR-001: **ZERO production code changes allowed**

### 2.2 Why It Failed

| Problem | Impact | Root Cause |
|---------|--------|------------|
| **11 agents for a test spec** | Context explosion, coordination overhead | Over-engineered role specialization. DevOps agent for infra AND chaos? Security engineer for 7 curl commands? |
| **Zero code fixes (NFR-001)** | Found 15 bugs, fixed 0. App still broken after 8 hours | Philosophy mismatch. A "master debug" that can't debug is just an audit |
| **Human-in-the-loop bottleneck** | Browser tests serialized behind human availability | CEO needed human to click through pages. No Playwright automation for verification |
| **Board approval ceremony** | Added 30+ min of overhead before any real work | PaperclipAI governance model is designed for teams, not solo dev |
| **Engram as hard blocker** | Gate checks depended on Engram reads; if slow/missing, everything stalls | No fallback to file-based state. Single point of failure |
| **5 sequential waves with hard gates** | Killed parallelism. Wave 3 couldn't start until Gate 2 closed | Infrastructure verification doesn't need to gate security testing |
| **7 model combos tested** | 3+ hours on model matrix alone | Interesting data but not actionable while core bugs exist |

### 2.3 What It DID Accomplish

To be fair, the PaperclipAI run produced valuable intelligence:
- **Model scorecard**: 7 LLM+embedding combos ranked with VRAM/latency data
- **Bug catalog**: 15 bugs with reproduction steps and fix recommendations
- **Security audit**: 7 probes, all PASS (no P0-CRITICAL vulnerabilities)
- **Chaos recovery**: 5/6 scenarios recover (only full-restart SLA exceeded by 25s)
- **Performance baseline**: TTFT, throughput, VRAM profiles established

The problem is: all that intelligence sits in a report while the app remains non-functional.

---

## 3. Cross-Spec Failure Patterns

### 3.1 Pattern: Bugs Found But Never Fixed

| Spec | Bugs Found | Bugs Fixed | Carryover |
|------|-----------|------------|-----------|
| Spec 21 | 22 + 3 known issues | 22 | 3 architectural (confidence=0, meta-reasoning disabled, response synthesis fallback) |
| Spec 23 | 3 runtime + 3 CRITICAL arch | 2 runtime | 3 CRITICAL LangChain bugs → deferred to spec-24 |
| Spec 24 | 5 bugs | 3 (uncertain: 2 more) | BUG-016 (CallLimit), BUG-017 (citation dedup) — status unclear |
| Spec 25 | 15 bugs | 0 | ALL 15 carry forward |

**The same bugs keep appearing across specs**:
- Confidence = 0 → found in spec-21, still broken in spec-25
- Citations not displayed → found in spec-23, still broken in spec-25
- Multi-turn conversation fails → found in spec-25, never attempted fix

### 3.2 Pattern: Diagnosis Without Action

Specs 23 and 25 both spent significant time diagnosing without fixing:
- Spec 23: LangChain audit found 3 CRITICAL bugs → deferred to spec-24
- Spec 25: 10 phases of testing → zero fixes

**Lesson**: The new spec-25 must have a **fix loop**: find bug → fix it → verify fix → next bug.

### 3.3 Pattern: Over-Scoping

| Spec | Planned Scope | Completed | Completion % |
|------|---------------|-----------|--------------|
| Spec 21 | 10 phases | 10 phases (but deferred SonarQube) | ~90% |
| Spec 23 | 11 phases | 3 phases (audit revealed showstoppers) | ~27% |
| Spec 24 | 7 phases | ~5 phases (2 bugs uncertain) | ~71% |
| Spec 25 | 12 phases, 98 tasks | 10 phases (report only) | 100% of audit, 0% of fixes |

**Lesson**: Scope to what you can FIX in one session, not what you can AUDIT.

### 3.4 What Actually Worked Well Across Specs

1. **Wave parallelism with zero file overlap** (Spec 21): A1 (Docker) + A2 (Python) in parallel → fastest execution
2. **Diagnosis-first architecture** (Spec 24): Navigator observes → Researcher investigates → Orchestrator synthesizes → Agents fix
3. **Real-time logs.md** (Spec 23): Every check, bug, fix, gate recorded live → best handoff
4. **Surgical fixes** (Spec 21): Average 1-5 line changes per bug. No refactoring. Just fix and move on
5. **Hybrid manual/automated** (Spec 23-24): curl for API, Playwright for browser, user confirms gates

---

## 4. Complete Bug Inventory

### 4.1 P1-HIGH: Must Fix (Core RAG Broken)

| ID | Bug | File(s) | Fix Estimate | Spec Found |
|----|-----|---------|-------------|------------|
| **BUG-007** | Session continuity hang — Citation unregistered in LangGraph checkpoint | `backend/main.py` | 1 line (add Citation to allowed_msgpack_modules) | Spec-25 |
| **BUG-010** | Research loop exhausts at iteration 8, confidence always 0 | `backend/agent/research_nodes.py` | Medium (fix message compression ValueError) | Spec-25 |
| **BUG-009** | Citation NDJSON events never emitted (all models, all queries) | `backend/api/chat.py` | Low-Medium (wire state to NDJSON stream) | Spec-25 |
| **BUG-002** | Groundedness NDJSON event never emitted | `backend/api/chat.py` | Low (same fix pattern as BUG-009) | Spec-25 |
| **BUG-015** | Backend crashes under ~10 concurrent requests | `backend/api/chat.py` | Very Low (asyncio.Semaphore) | Spec-25 |
| **BUG-008** | No wall-clock timeout on research loop | `backend/agent/research_nodes.py` or `research_edges.py` | Low (add time check in should_continue_loop) | Spec-25 |
| **BUG-004** | GET /api/models/embedding returns 404 | `backend/api/` (new endpoint) | Low (mirror existing /api/models pattern) | Spec-25 |

### 4.2 P2-MEDIUM: Should Fix (UX/Quality)

| ID | Bug | File(s) | Fix Estimate |
|----|-----|---------|-------------|
| BUG-001 | Health endpoint model name `:latest` suffix | `backend/api/` | Very Low |
| BUG-003 | DELETE collection by name returns 404 | `backend/api/` | Low |
| BUG-005 | Binary file ingest returns invalid JSON | `backend/api/` | Low |
| BUG-006 | Empty file (0 bytes) silently accepted | `backend/api/` | Very Low |
| BUG-011 | aria-prohibited-attr accessibility | Frontend | Very Low |
| BUG-012 | WCAG color contrast in light mode | Frontend CSS | Low |
| BUG-013 | Collection card not keyboard-accessible | Frontend | Low |
| BUG-014 | Observability horizontal overflow at 768px | Frontend CSS | Very Low |

### 4.3 Architectural (from Spec-23 LangChain Audit — May Be Partially Fixed by Spec-24)

| ID | Issue | Status | Notes |
|----|-------|--------|-------|
| CRIT-001 | route_fan_out never wired | **NEEDS VERIFICATION** — spec-24 commit `17426e5` may address | Multi-question decomposition |
| CRIT-002 | collect_answer outputs wrong schema | **NEEDS VERIFICATION** — spec-24 commit `17426e5` may address | SubAnswer schema mismatch |
| CRIT-003 | Meta-reasoning cycle protection broken | **NEEDS VERIFICATION** — META_REASONING_MAX_ATTEMPTS=0 in docker-compose | Disabled by default anyway |

### 4.4 Uncertain (Spec-24 — Unclear if Executed)

| ID | Bug | Status |
|----|-----|--------|
| BUG-016 | CallLimitCallback instantiation with old hardcoded limits | Tasks T042-T044 drafted but no execution log |
| BUG-017 | Citations duplicated 4x (no dedup by passage_id) | Same — no execution evidence |

---

## 5. What Actually Works

Let's be clear about what IS functional:

| Component | Status | Evidence |
|-----------|--------|----------|
| Docker Compose (4 services) | WORKS | All services start healthy (spec-25 Phase 1 PASS) |
| NVIDIA GPU passthrough | WORKS | nvidia-smi accessible from Ollama container, 7B models use 56-60% of 12GB |
| Qdrant vector search | WORKS | Dense + BM25 hybrid search returns results |
| SQLite WAL storage | WORKS | Documents, collections, traces persisted |
| Document ingestion | WORKS (basic) | PDF/MD/TXT upload → chunk → embed → store. Binary/empty file validation missing |
| Frontend page rendering | WORKS | All 5 pages render in both themes (spec-25 Phase 7 PASS) |
| Chat streaming (NDJSON) | WORKS (basic) | Token-by-token streaming functional after spec-24 fix |
| Security posture | WORKS | 7 security probes PASS (spec-25 Phase 6) |
| Chaos recovery (5/6) | WORKS | Kill Ollama/Qdrant → services recover. Only full-restart SLA exceeded by 25s |
| Cross-encoder reranking | WORKS | Model loaded at startup, reranks hybrid search results |
| Hybrid search (dense+BM25) | WORKS | Returns chunks with scores |

**The foundation is solid.** Infrastructure, storage, retrieval, and frontend all work. The broken part is the **LangGraph agent layer** — the part that takes a user question, runs the research loop, collects citations, scores confidence, and streams the result back.

---

## 6. GPU + Model Recommendations (RTX 4070 Ti)

### 6.1 Hardware Budget

| Resource | Available | Budget |
|----------|-----------|--------|
| VRAM | 12,282 MiB (12 GB) | Target: <80% utilization = 9,825 MiB |
| System RAM | Varies | Reranker ~400 MB + Embedder ~300 MB in Python process |
| Ollama concurrent models | 2 (configured) | 1 LLM + 1 embedding model |

### 6.2 Model Scorecard (from PaperclipAI Testing)

| Rank | LLM | Embedding | Score | TTFT | Peak VRAM | % of 12GB |
|------|-----|-----------|-------|------|-----------|-----------|
| 1 | **deepseek-r1:8b** | nomic-embed-text | 2.87 | 97s | 7,276 MiB | 59% |
| 2 | **qwen2.5:7b** | nomic-embed-text | 2.80 | 60s | 6,940 MiB | 56% |
| 3 | llama3.1:8b | mxbai-embed-large | 2.79 | 107s | 7,030 MiB | 57% |
| 4 | llama3.1:8b | nomic-embed-text | 2.74 | 83s | 7,156 MiB | 58% |
| 5 | qwen2.5:7b | mxbai-embed-large | 2.67 | 81s | 7,170 MiB | 58% |
| 6 | phi4:14b | nomic-embed-text | 2.48 | 60s | 10,939 MiB | **89%** |
| DISQ | mistral:7b | nomic-embed-text | 1.67 | 186s | 7,255 MiB | 59% |

### 6.3 Recommendation: Gemma 4 26B MoE as Primary Model

**Primary LLM: `gemma4:26b`** (Mixture of Experts)

| Property | Value | Why It Matters |
|----------|-------|----------------|
| Total params | 25.2B | Deep knowledge encoding — outperforms dense 7B models |
| Active params | **3.8B** | Inference speed comparable to a 4B model |
| Architecture | MoE (Mixture of Experts) | Only active experts computed per token — GPU-efficient |
| Context window | **256K tokens** | 8x more than qwen2.5:7b (32K). Eliminates BUG-010 message compression crash |
| Function calling | Native | Designed for agentic tool-use (86.4% on tau2-bench). Better for ResearchGraph tool loop |
| Languages | 140 | Excellent for Spanish ARCA corpus |
| Multimodal | Text + Image | Future capability for document images |
| Download | 18 GB | Google designed this variant specifically for consumer GPUs (12-16GB VRAM) |
| Benchmarks | MMLU 85.2%, LiveCodeBench 80.0%, GPQA 84.3% | Frontier-class intelligence at consumer hardware budget |

**Why Gemma 4 26B over the previous scorecard winners:**

1. **vs qwen2.5:7b** (previous fastest): Gemma 4 has 256K context (vs 32K), native function calling, and 26B knowledge (vs 7B). The MoE architecture means inference is only marginally slower despite 3.6x more total parameters.

2. **vs deepseek-r1:8b** (previous best quality): Gemma 4 26B has 3x more total knowledge, 8x more context, and native tool-use. DeepSeek-R1 was a "thinking" model that added latency with chain-of-thought. Gemma 4 should be more direct.

3. **The 256K context window is a game-changer**: BUG-010 (confidence=0) is caused by message compression crashing at research loop iteration 8 because context overflows at ~32K tokens. With 256K, the research loop can run 8x more iterations without compression, potentially eliminating this entire bug class.

**Embedding model: `nomic-embed-text`** (start), upgrade to **`mxbai-embed-large`** after verification.

**Critical finding from spec-25**: `mxbai-embed-large` retrieved 112-159 chunks where `nomic-embed-text` retrieved only 1 chunk for the same factual query. This is a massive quality difference. Consider switching default embedding to `mxbai-embed-large` after core bugs are fixed and gemma4:26b is validated.

**Fallback**: If gemma4:26b doesn't fit in 12GB VRAM, fall back to `gemma4:e4b` (4.5B effective, 9.6GB, 128K context) or `qwen2.5:7b` (proven baseline).

**DO NOT use**:
- `mistral:7b` — disqualified, 591s research loop timeout
- `phi4:14b` — 89% VRAM, too close to OOM on 12GB card

### 6.4 Models to Pull

For the new spec-25 debug session:
```bash
# Primary LLM — Gemma 4 26B MoE (Google's consumer GPU pick)
ollama pull gemma4:26b

# Embedding — start with default, upgrade later
ollama pull nomic-embed-text

# Fallback LLM (if 26B doesn't fit in 12GB)
ollama pull gemma4:e4b         # 4.5B effective, 128K context, multimodal
ollama pull qwen2.5:7b         # Proven baseline from spec-25 testing

# Quality upgrade (after bugs fixed)
ollama pull mxbai-embed-large  # 1024-dim, 100x better retrieval than nomic
```

---

## 7. New Spec-25 Agent Teams Design

### 7.1 Philosophy Change

| Old (PaperclipAI) | New (Agent Teams) |
|--------------------|-------------------|
| 11 agents, 5 waves, 98 tasks | **4 agents + 1 orchestrator** |
| Zero code changes (audit only) | **Fix bugs as you find them** |
| Human-in-the-loop browser testing | **Playwright/Chrome DevTools automated** |
| Sequential wave gates | **Debug loop: find → fix → verify → next** |
| Model matrix testing (7 combos) | **One model, make it work** |
| Engram persistence every phase | **Engram at session boundaries only** |
| CEO/Board governance | **Direct orchestrator delegation** |

### 7.2 Agent Roster

| Agent | Role | Model | MCP Tools | Scope |
|-------|------|-------|-----------|-------|
| **Orchestrator** | Coordinator + Docker ops | Opus 4.6 | Docker, Bash, Engram | Start stack, pull models, gate checks, bug triage, Engram saves |
| **A1 — Backend Surgeon** | Backend bug fixes | Sonnet 4.6 | Bash, Serena, GitNexus | Fix LangGraph nodes, state, streaming, API endpoints |
| **A2 — Frontend Surgeon** | Frontend bug fixes | Sonnet 4.6 | Bash, Context7 | Fix NDJSON consumption, citation display, UI bugs |
| **A3 — Navigator** | Live verification | Sonnet 4.6 | Playwright, Chrome DevTools, Browser Tools | Verify fixes in real browser, capture evidence |

**Why only 4 agents:**
- A1 covers all Python/LangGraph work (no need for separate "Python Expert" + "Backend Architect")
- A2 covers all Next.js/React work (no need for separate "Frontend Architect" + "QA")
- A3 replaces the human-in-the-loop — fully automated browser testing
- Orchestrator handles Docker/infra (no need for separate DevOps agent)

### 7.3 Execution Model: The Debug Loop

```
Orchestrator:
  1. Start Docker stack (make up)
  2. Pull models (make pull-models)
  3. Verify health (curl /api/health)
  4. Pick highest-priority bug from queue
  5. Delegate to A1 or A2 (based on layer)
  6. After fix committed: delegate to A3 (verify in browser)
  7. A3 reports PASS/FAIL
     - PASS → mark bug fixed, pick next bug
     - FAIL → send A3's evidence back to A1/A2 for re-fix
  8. After all P1 bugs fixed: run full E2E smoke test via A3
  9. Save session summary to Engram

A1 (Backend):
  Read bug description → Read affected file(s) → Fix → Rebuild container
  
A2 (Frontend):
  Read bug description → Read affected file(s) → Fix → Rebuild container

A3 (Navigator):
  Navigate to chat page → Send test query → Wait for response → 
  Verify: tokens stream? citations display? confidence > 0? 
  groundedness shows? → Screenshot → Report PASS/FAIL with evidence
```

### 7.4 Tmux Layout

```
┌─────────────────────────────┬─────────────────────────────┐
│                             │                             │
│     Orchestrator (Opus)     │    A3 — Navigator           │
│     Docker ops, triage      │    Playwright verification  │
│                             │                             │
├─────────────────────────────┼─────────────────────────────┤
│                             │                             │
│     A1 — Backend Surgeon    │    A2 — Frontend Surgeon    │
│     Python/LangGraph fixes  │    Next.js/React fixes      │
│                             │                             │
└─────────────────────────────┴─────────────────────────────┘
```

---

## 8. Artifact Structure

### 8.1 What Each Speckit Artifact Should Contain

#### `spec.md` — The Specification

**Purpose**: Define WHAT we're fixing and SUCCESS CRITERIA.

```markdown
# Spec-25: Master Debug (Agent Teams)

## Goal
Make The Embedinator a functional Agentic RAG system. Fix the 7 P1-HIGH 
bugs blocking core functionality. Verify with automated browser testing.

## User Stories
- US-1: User sends a query and receives a streamed response with citations
- US-2: User sees confidence score and groundedness check for each response
- US-3: User has multi-turn conversations without session hangs
- US-4: System handles concurrent users without crashing

## Functional Requirements
- FR-001: Citation NDJSON events emitted during chat stream
- FR-002: Groundedness NDJSON event emitted after citations
- FR-003: Confidence score > 0 for queries with matching documents
- FR-004: Multi-turn conversation works (follow-up queries don't hang)
- FR-005: Research loop terminates within 120s wall-clock timeout
- FR-006: Backend handles 10 concurrent chat requests without crashing
- FR-007: GET /api/models/embedding returns available embedding models

## Non-Functional Requirements
- NFR-001: Fixes must be surgical (1-20 lines per bug, no refactoring)
- NFR-002: All fixes verified via automated Playwright testing
- NFR-003: No new test failures introduced

## Success Criteria
- SC-001: Chat E2E works — user sends query, receives streamed tokens + citations + confidence + groundedness
- SC-002: Multi-turn — follow-up query in same session receives response
- SC-003: Backend survives 10 concurrent /api/chat requests
- SC-004: All 7 P1 bugs verified FIXED via browser testing
```

**Key principle**: Short. Focused. No model matrix. No chaos engineering. No UX audit. Just: make the RAG work.

#### `plan.md` — The Implementation Plan

**Purpose**: Define HOW we'll fix it — agent assignments, waves, gates.

```markdown
# Plan: Spec-25 Master Debug

## Execution Model
Debug loop: Orchestrator triages → A1/A2 fix → A3 verifies → repeat

## Wave Structure

### Wave 0: Infrastructure (Orchestrator solo, ~20 min)
- Start Docker stack
- Pull models: `gemma4:26b` + `nomic-embed-text` (fallback: `qwen2.5:7b` if 26B doesn't fit VRAM)
- Update `backend/config.py` default_llm_model to `gemma4:26b`
- Verify 4 services healthy
- Seed test collection if needed
- GATE 0: /api/health returns 200, models loaded, `gemma4:26b` responds to test prompt

### Wave 1: Core Backend Fixes (A1, ~2-3 hours)
- BUG-007: Citation checkpoint registration (1 line)
- BUG-010: Research loop confidence reset (message compression fix)
- BUG-009 + BUG-002: Citation + groundedness NDJSON emission
- BUG-008: Wall-clock timeout on research loop
- BUG-015: Concurrency semaphore
- BUG-004: Embedding models endpoint
- After each fix: A3 verifies in browser
- GATE 1: Chat returns tokens + citations + confidence > 0 + groundedness

### Wave 2: Frontend Fixes (A2, ~1 hour, parallel with Wave 1 tail)  
- Verify NDJSON events render correctly in chat UI
- Fix any frontend-side citation/confidence display issues
- BUG-011, BUG-012, BUG-013, BUG-014 (P2 UX bugs)
- After each fix: A3 verifies
- GATE 2: Full chat UX works — citations clickable, confidence visible

### Wave 3: Full E2E Smoke Test (A3, ~30 min)
- Multi-turn conversation test
- Document ingestion → query → verified citations
- Concurrent request test (10 parallel curl)
- All 5 pages render without errors
- GATE 3 (FINAL): All SC-001 through SC-004 PASS
```

#### `implement.md` — The Execution Instructions

**Purpose**: The prompt the orchestrator reads to know exactly what to do.

This is the MOST IMPORTANT artifact. It should contain:

1. **Agent spawn instructions** (exact prompts for each agent)
2. **Bug details** (file paths, line numbers, fix recommendations)
3. **Verification scripts** (curl commands, Playwright scenarios)
4. **Gate check criteria** (what to verify at each gate)
5. **Docker rebuild commands** (exact commands to rebuild after fixes)
6. **MCP tool usage** (which tools each agent should use)

Structure:
```markdown
# Implement: Spec-25 Master Debug

## Pre-Launch Checklist
- [ ] tmux session with 4 panes
- [ ] Docker Desktop running
- [ ] NVIDIA GPU accessible
- [ ] Branch: 025-master-debug

## Agent Instruction Files
- A1: specs/025-master-debug/agents/A1-backend-surgeon.md
- A2: specs/025-master-debug/agents/A2-frontend-surgeon.md
- A3: specs/025-master-debug/agents/A3-navigator.md

## Wave 0: Infrastructure Setup (Orchestrator)
[exact commands]

## Wave 1: Backend Fixes (A1 + A3 verify loop)
### Bug Priority Queue:
1. BUG-007 → file, line, fix → A3 verify scenario
2. BUG-010 → file, line, fix → A3 verify scenario
...

## Wave 2: Frontend Fixes (A2 + A3 verify loop)
...

## Wave 3: Full E2E (A3 solo)
...

## Session Close
- mem_session_summary with all findings
- Git commit with all fixes
```

#### Agent Instruction Files

Each agent gets a dedicated `.md` file in `specs/025-master-debug/agents/`:

```
agents/
  A1-backend-surgeon.md    # Bug list, file paths, fix patterns, rebuild commands
  A2-frontend-surgeon.md   # Bug list, file paths, fix patterns, rebuild commands
  A3-navigator.md          # Verification scenarios, Playwright commands, evidence capture
```

These files should be **self-contained** — an agent spawned fresh reads ONLY their instruction file and can execute immediately.

### 8.2 What Each Artifact Should NOT Contain

| Artifact | Should NOT Include |
|----------|-------------------|
| spec.md | Model matrix testing, chaos engineering, security probing, UX audit, performance profiling |
| plan.md | More than 3 waves. More than 4 agents. Board approval. Engram saves after every task |
| implement.md | Inline spec content (agents read their own files). PaperclipAI goals hierarchy. wakeOnDemand config |
| Agent files | References to other agents' work. Cross-agent dependencies within a wave |

---

## 9. MCP Tool Strategy

### 9.1 Tool Assignment Matrix

| Agent | Tool | Purpose | When |
|-------|------|---------|------|
| **Orchestrator** | Docker MCP | `docker compose up/down/ps/logs` | Wave 0, rebuilds, health checks |
| **Orchestrator** | Bash | `curl`, `docker exec`, `git` | API probes, model pulls, commits |
| **Orchestrator** | Engram | `mem_save`, `mem_session_summary` | Session boundaries only |
| **A1** | Bash | Read/edit backend files, run pytest | Bug fixes, unit test verification |
| **A1** | Serena | Symbolic code navigation | Understanding call graphs before fixing |
| **A1** | GitNexus | Impact analysis | Pre-fix blast radius check |
| **A2** | Bash | Read/edit frontend files, npm build | Bug fixes, build verification |
| **A2** | Context7 | Next.js/React docs | Pattern lookup when fixing streaming |
| **A3** | Playwright | `browser_navigate`, `browser_snapshot`, `browser_fill_form`, `browser_click` | Full page navigation and interaction |
| **A3** | Chrome DevTools | `list_network_requests`, `list_console_messages`, `take_screenshot` | NDJSON stream inspection, error capture |
| **A3** | Browser Tools | `getConsoleErrors`, `runAccessibilityAudit` | Error detection, a11y verification |

### 9.2 Playwright Verification Scenarios

These are the exact test flows A3 should execute:

**Scenario 1: Basic Chat E2E**
```
1. Navigate to http://localhost:3000/chat
2. Select test collection from sidebar
3. Type: "What are the main concepts in the uploaded documents?"
4. Click Send
5. VERIFY: Streaming tokens appear (not skeleton bars)
6. VERIFY: Citation markers [1], [2] appear in response
7. VERIFY: Confidence score > 0 displayed
8. VERIFY: Groundedness indicator displayed
9. Screenshot → evidence
```

**Scenario 2: Multi-Turn Conversation**
```
1. After Scenario 1 completes
2. Type: "Can you elaborate on the first point?"
3. Click Send
4. VERIFY: Response streams (no hang/timeout)
5. VERIFY: Session maintained (not a fresh conversation)
6. Screenshot → evidence
```

**Scenario 3: Concurrent Stress**
```
1. From Bash: 10 parallel curl requests to /api/chat
2. VERIFY: All return HTTP 200 or 429 (not connection refused)
3. VERIFY: Backend container still running (docker compose ps)
```

---

## 10. Debug Priority Queue

Ordered by impact (fix the most blocking bug first):

| Priority | Bug | Why First | Estimated Effort |
|----------|-----|-----------|-----------------|
| **1** | BUG-007: Citation checkpoint | Blocks ALL multi-turn conversations. 1-line fix. Highest ROI. | 15 min |
| **2** | BUG-010: Confidence always 0 | Makes RAG quality scoring useless. Moderate fix in research_nodes.py | 1-2 hours |
| **3** | BUG-009: Citation events not emitted | Users never see what sources were used. Fix in chat.py streaming loop | 1-2 hours |
| **4** | BUG-002: Groundedness not emitted | Same pattern as BUG-009, fix in same file | 30 min (after BUG-009) |
| **5** | BUG-008: No research loop timeout | Prevents runaway queries (mistral 591s). Add time check | 30 min |
| **6** | BUG-015: Concurrent crash | Production risk. Add asyncio.Semaphore(5) | 15 min |
| **7** | BUG-004: Missing embedding endpoint | API completeness. Mirror existing pattern | 30 min |

**Total estimated: 4-6 hours of focused work.**

After P1 fixes, if time remains:
- P2 frontend bugs (BUG-011 through BUG-014): ~1 hour
- P2 backend bugs (BUG-001, 003, 005, 006): ~1 hour

---

## 11. What NOT To Do

Based on everything we've learned from specs 21-25:

| Anti-Pattern | Why | What To Do Instead |
|-------------|-----|-------------------|
| Test 7 model combos | Core bugs make all combos fail the same way | Fix bugs with default model, test alternatives later |
| Run chaos engineering | Infrastructure already proven (5/6 PASS) | Skip — not blocking functionality |
| Run security probes | Already PASS (spec-25 Phase 6) | Skip — not blocking functionality |
| Run performance profiling | Can't profile a broken system | Profile AFTER bugs are fixed |
| Run UX journey audit | Pages render fine; chat is broken | Fix chat, then audit UX |
| Use 11 agents | Coordination overhead > work done | 4 agents. No more |
| Require human browser testing | Serializes everything | Playwright + Chrome DevTools automated |
| Write 14-section report | Report doesn't fix bugs | Fix bugs. Short status summary |
| Use PaperclipAI governance | Board approval, goals hierarchy, wakeOnDemand | Direct Agent Teams with tmux |
| Save to Engram after every task | Overhead. Context pollution | Save at session boundaries only |
| Create new test suites | Existing 1487 tests + browser verification sufficient | Use existing tests + Playwright scenarios |
| Refactor while fixing | Scope creep | Surgical fixes only (1-20 lines per bug) |

---

## Summary

**The Embedinator has solid foundations** — Docker, storage, retrieval, frontend rendering, security all work. What's broken is the LangGraph agent layer: the part that makes it a RAG system instead of just a chat UI.

**7 specific bugs in ~4 files** are blocking the entire RAG experience. Fix them in priority order with a tight debug loop (find → fix → verify), and we have a functional Agentic RAG system.

The new spec-25 should be:
- **4 agents** (Backend Surgeon, Frontend Surgeon, Navigator, + Orchestrator)
- **3 waves** (infra setup, backend fixes, frontend fixes + E2E verification)
- **~6 hours** total estimated execution time
- **Agent Teams with tmux** (proven pattern from specs 17-22)
- **Debug loop** (not audit loop) — fix as you go

The PaperclipAI approach gave us great intel. Now we use that intel to actually fix the app.
