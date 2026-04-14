# Quickstart — Spec 26 Performance Debug

**Feature**: Performance Debug and Hardware Utilization Audit
**Branch**: `026-performance-debug`
**Audience**: implementer, reviewer, future contributor validating spec-26 deliverables

This quickstart shows how to reproduce the validation benchmark, read the audit artifacts, and confirm the supported-model gate is live. It replaces the formal `contracts/` directory (no new API surfaces in this spec).

---

## 1. Prerequisites

```bash
# You should be on the feature branch
git checkout 026-performance-debug

# Docker stack up and healthy
docker compose up -d
docker compose ps                    # all services "healthy" or "running"

# Reference workstation (for SC-004/005 verification)
#   Intel i7-12700K / 64 GB DDR5 / RTX 4070 Ti 12 GB / NVMe SSD / Fedora 43 (or similar)
# Weaker hardware can run the harness but SCs are not gated there.

# Inside a tmux session (spec-26 implementation requires it)
[ -n "$TMUX" ] && echo "OK: in tmux" || tmux new-session -s embedinator-26

# Agent Teams feature flag (for implementation; not required to run benchmarks)
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

---

## 2. Seed the Reference Corpus

The benchmark harness operates on a fixed seeded corpus so runs are comparable.

```bash
# Seed the demo collection (idempotent — safe to run repeatedly)
python scripts/seed_data.py --base-url http://localhost:8000

# Capture the collection ID from the output
COLLECTION_ID=$(curl -sf http://localhost:8000/api/collections | \
  python -c "import sys, json; print(json.load(sys.stdin)[0]['id'])")
echo "$COLLECTION_ID"
```

---

## 3. Confirm the Supported-Model Gate (FR-004)

```bash
# Check the default LLM — MUST be qwen2.5:7b after spec-26 ships
curl -sf http://localhost:8000/api/settings | jq '.llm.model'
#   → "qwen2.5:7b"

# Inspect the supported-model allowlist
curl -sf http://localhost:8000/api/settings | jq '.llm.supported_models'
#   → ["qwen2.5:7b", "llama3.1:8b", "mistral:7b"]
#   (exact list may be refined by Wave 4 A8 — see docs/performance.md)

# Verify fail-fast on an unsupported thinking model
EMBEDINATOR_LLM_MODEL=gemma4:e4b docker compose up backend 2>&1 | grep -i "unsupported model"
#   → "Configured LLM 'gemma4:e4b' is not supported in this release. ..."
#   → container exits non-zero (healthcheck never passes)
```

---

## 4. Run the Benchmark Harness (FR-002, SC-004, SC-005)

### 4a. Smoke run (fast, for sanity checks)

```bash
python scripts/benchmark.py \
  --factoid-n 5 --analytical-n 2 \
  --priming-queries 1 \
  --output /tmp/bench-smoke.json \
  --base-url http://localhost:8000 \
  --collection-id "$COLLECTION_ID"

# Inspect the structure
jq 'keys' /tmp/bench-smoke.json
#   → ["cold_start_ms", "cold_vs_warm_ratio", "manifest", "overall_p50",
#      "stage_timings_p50", "variance_cv", "warm_state_p50", "warm_state_p90",
#      "warm_state_p99"]
```

### 4b. Validation run (the one that gates SC-004 / SC-005)

```bash
python scripts/benchmark.py \
  --factoid-n 30 --analytical-n 10 \
  --priming-queries 1 \
  --repeat 3 \
  --output "docs/benchmarks/$(git rev-parse --short HEAD)-gate3.json" \
  --base-url http://localhost:8000 \
  --collection-id "$COLLECTION_ID"

# Check the headline SCs
BENCH=docs/benchmarks/$(git rev-parse --short HEAD)-gate3.json
jq '.warm_state_p50.factoid_ms,    .warm_state_p50.analytical_ms' "$BENCH"
#   Target (spec-26):   < 4000 factoid    < 12000 analytical
#   Long-term (spec-14): < 1200 factoid   < 5000 analytical
#   Constitution target: < 800 first-token (Phase 1 actual); spec-26 documents the gap

# Reproducibility (NFR-003) — must be ≤ 0.15
jq '.variance_cv' "$BENCH"
#   → 0.08 or so; if > 0.15, investigate noise (other GPU workload, thermal throttling, etc.)

# Cold-start cost (reported, not gated)
jq '.cold_start_ms, .cold_vs_warm_ratio' "$BENCH"
```

### 4c. Concurrency run (SC-006)

```bash
python scripts/benchmark.py \
  --concurrent 5 --factoid-n 5 \
  --priming-queries 1 \
  --output /tmp/conc.json \
  --base-url http://localhost:8000 \
  --collection-id "$COLLECTION_ID"

# Zero CircuitOpenError is PASS
jq '.errors | map(select(.type == "CircuitOpenError")) | length' /tmp/conc.json
#   → 0

# All 5 completed with a done event
jq '.completions.done_count' /tmp/conc.json
#   → 5
```

---

## 5. Read the Audit Artifacts

Spec-26 produces two authoritative audit reports committed to `specs/026-performance-debug/` during Wave 1.

### 5a. Hardware audit (`audit.md`)

```bash
less specs/026-performance-debug/audit.md
```

Sections to spot-check:

- **CPU** — which processes consumed time under a chat query? Is the Python backend single- or multi-threaded? Was Qdrant's thread pool saturated?
- **GPU** — VRAM headroom during inference; was `nomic-embed-text` on GPU or CPU? Cross-encoder reranker's device placement.
- **RAM** — backend RSS at idle / 1 query / 5 concurrent; host headroom.
- **Disk/I/O** — SQLite WAL on; Qdrant memmap.
- **Cold-start vs warm-state** — measured first-query VRAM load cost.
- **Config changes** — before/after table populated by A6 in Wave 3.

### 5b. Framework audit (`framework-audit.md`)

```bash
less specs/026-performance-debug/framework-audit.md
```

Every finding carries (file:line, LangGraph/LangChain doc URL, recommendation). Sections:

- **LangGraph primitives** — reducers, checkpointer, conditional edges, `Send()` fan-out, `recursion_limit`, `interrupt()`.
- **LangChain primitives** — `trim_messages`, `bind_tools`, `PydanticOutputParser` / `JsonOutputParser`, retry wrappers.
- **Agent methodology** — orchestrator stop signals, confidence threshold wiring, meta-reasoning efficacy, groundedness/citation validation cost.

### 5c. Audit synthesis (`audit-synthesis.md`)

Written by the orchestrator at Gate 1 using Sequential Thinking. Names the top-1 latency contributor that A6 targets in Wave 3 for FR-005.

### 5d. Validation report (`validation-report.md`)

Written by the orchestrator at Gate 4. All 12 SCs evaluated with PASS / FAIL / WAIVED and evidence citations.

---

## 6. Validate the Stage-Timings Contract (FR-008, SC-007)

After any benchmark run, the `query_traces.stage_timings_json` rows are populated. Verify the contract holds:

```bash
# Quick manual check
docker compose exec backend sqlite3 /data/embedinator.db \
  "SELECT stage_timings_json FROM query_traces ORDER BY created_at DESC LIMIT 5;" \
  | jq '.'

# The formal test (gate at Wave 4)
zsh scripts/run-tests-external.sh -n sc007 tests/unit/test_stage_timings_validation.py
cat Docs/Tests/sc007.status   # PASSED
cat Docs/Tests/sc007.summary
```

Expected:
- Every row is non-null and non-empty.
- Keys are a stable set (e.g., `rewrite`, `retrieve`, `rerank`, `generate`, `verify`).
- Per-stage sum is within ±5% of the row's `latency_ms`.

---

## 7. Read the Public Performance Doc (FR-010, SC-010)

```bash
less docs/performance.md
grep -c 'performance.md' README.md   # must be ≥ 1
```

The doc is linked from the README so anyone visiting the project on GitHub can see honest, reference-hardware numbers before deciding whether to install.

---

## 8. Confirm No Regressions (NFR-005, SC-011)

```bash
# Full sweep vs baseline (established at branch start — 025-master-debug HEAD)
zsh scripts/run-tests-external.sh -n spec26-final --no-cov tests/
cat Docs/Tests/spec26-final.status       # PASSED (or matches baseline failure count)
cat Docs/Tests/spec26-final.summary

# Count of failures (should equal baseline, ~39 known pre-existing)
grep -c "^FAILED" Docs/Tests/spec26-final.log
```

---

## 9. Confirm the Makefile Is Sacred (NFR-002, SC-012)

```bash
# Must be exactly 0
git diff --stat -- Makefile | wc -c
#   → 0
```

---

## 10. Read the Bug Registry Disposition (Clarification 2)

Spec-26 triaged every open bug from specs 21–25:

```bash
less docs/bug-registry-spec26.md
```

Table columns: Bug ID, Severity (P1/P2/P3), Disposition (`fixed-in-spec` with commit SHA, or `deferred` with rationale + follow-up spec pointer).

Expected:
- All P1/P2 bugs: `fixed-in-spec`.
- P3 opportunistic wins (e.g., BUG-023 `embed_max_workers` bump): `fixed-in-spec`.
- P3 complex (BUG-021, BUG-022 if not cheap wins): `deferred` with rationale.

---

## What NOT to Do

- Do **not** run `pytest` inline — always use `zsh scripts/run-tests-external.sh` (NFR-005).
- Do **not** modify the `Makefile` (NFR-002, SC-012).
- Do **not** run the benchmark on weaker hardware and expect SCs to gate — SC-004/005 target the reference workstation.
- Do **not** configure a thinking model (`gemma4:e4b`, `qwen3-thinking`, `deepseek-r1`) — the supported-model gate will refuse startup (Clarification 1, FR-004).
- Do **not** delete `docs/benchmarks/*.json` — those are commit-pinned evidence for SC-004, SC-005, SC-010.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Backend won't start, log says "not supported in this release" | Tried to configure a thinking model or a name not in `supported_llm_models` | `export EMBEDINATOR_LLM_MODEL=qwen2.5:7b` and restart |
| Benchmark p50 looks absurdly low (< 500 ms) | Harness measured the priming query only, or stack cached | Verify `--priming-queries 1` ran; re-run with `--repeat 3` |
| Benchmark p50 looks absurdly high (> 60 s) | Ollama model not loaded; GPU contention from another workload | Check `nvidia-smi` during run; confirm `qwen2.5:7b` is pulled |
| `variance_cv` > 0.15 | Thermal throttling, unrelated GPU load, or system noise | Close browser / chat apps; run harness with no concurrent foreground work |
| `CircuitOpenError` during 5-concurrent run | Fix from BUG-018 not effective; parser exceptions still leaking into counter | Check `logs` for `fallback` messages; revisit A5's work |
| Test runner shows new failures | Regression introduced; check diff against branch baseline | Compare `Docs/Tests/*.status` to baseline; identify responsible commit |

---

## Reproducing the Validation Benchmark for the Public README

The benchmark file committed alongside the spec-26 validation commit is the one quoted in the public README / `docs/performance.md`. To reproduce it:

```bash
# 1. Check out the exact validation commit
git log --oneline --grep='^feat: validation' specs/026-performance-debug/ | head -1
# (or use the commit SHA referenced in docs/performance.md)
git checkout <sha>

# 2. Run the harness with identical arguments
python scripts/benchmark.py \
  --factoid-n 30 --analytical-n 10 \
  --priming-queries 1 --repeat 3 \
  --output /tmp/repro.json \
  --base-url http://localhost:8000 \
  --collection-id "$COLLECTION_ID"

# 3. Compare to the committed result
jq -S . "docs/benchmarks/${(git rev-parse --short HEAD)}-gate3.json" > /tmp/committed.json
jq -S . /tmp/repro.json > /tmp/reproduced.json
diff /tmp/committed.json /tmp/reproduced.json
# Differences in absolute numbers are expected (±15% per NFR-003); keys and structure must match.
```
