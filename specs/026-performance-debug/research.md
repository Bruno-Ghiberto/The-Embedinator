# Phase 0 Research — Spec 26 Performance Debug

**Feature**: Performance Debug and Hardware Utilization Audit
**Branch**: `026-performance-debug`
**Date**: 2026-04-13
**Status**: All Technical Context unknowns resolved; no `NEEDS CLARIFICATION` markers remain.

---

## Research Objectives

Phase 0 exists to resolve the two candidate dependency decisions flagged in `plan.md` (`tiktoken` for FR-007, GPU audit tooling for A1), lock the benchmark harness protocol (priming query + variance), and pre-fetch the framework documentation A2 will cite. Research does not run the audit itself — that's Wave 1 work — but it fixes the *how* so agents don't re-litigate choices mid-wave.

---

## Decision 1 — Token counter for `trim_messages` (FR-007)

**Decision**: Use LangChain's `model.count_tokens()` when the bound chat model exposes it (LangChain ≥ 1.2); fall back to `tiktoken` with a model-to-encoder mapping (default `cl100k_base`). Expose the counter via a small helper in `backend/agent/research_nodes.py`; do NOT introduce a `count_tokens.py` module (YAGNI per Constitution Principle VII).

**Rationale**:
- `token_counter=len` on a list of `BaseMessage` objects counts **messages**, not tokens; on a string it counts **characters**. Neither is remotely correct. This is the root of BUG-019.
- LangChain 1.2+ standardized `.count_tokens()` on the base chat model interface (`BaseChatModel`). Where the underlying provider exposes a tokenizer (OpenAI via `tiktoken`, Anthropic via their SDK tokenizer, Google via SentencePiece), this is the authoritative counter.
- Ollama models return Hugging Face tokenizers via Ollama's API; LangChain's Ollama integration exposes these via `model.count_tokens()`. Verified via Context7 docs for `langchain-ollama` ≥ 0.2. Needs empirical check during Wave 2 A3 to confirm Ollama + `qwen2.5:7b` returns non-None here.
- If `count_tokens()` returns `None` or raises, fall back to `tiktoken.get_encoding("cl100k_base").encode()`. The overestimate (BPE encoding does not exactly match Qwen's actual tokenizer, but is within ~15% for English) is acceptable because `trim_messages` is a safety cut, not a precise budget tool.
- `tiktoken` is a small, well-maintained dependency (no C compiler needed; wheels for every platform). Pinning `tiktoken >= 0.8` is safe.

**Alternatives considered**:
- **Exact Qwen tokenizer via `transformers`**: accurate but pulls a 500+ MB dep chain. Rejected on Constitution VII (simplicity).
- **Character heuristic (documented)**: keep `token_counter=len` on strings with a documented safety margin (e.g., `max_chars = max_tokens * 3.5`). Rejected because BUG-019 is listed in the spec as a real bug; papering over it with "documented heuristic" defers the fix to some future spec while the audit asks for a real answer.
- **OpenAI `tiktoken` only** (no provider-aware path): works but wastes the ability to be precise on providers that offer their tokenizer. Rejected.
- **Pyjnius / custom wrapper**: over-engineered. Rejected on YAGNI.

**Action for A3**:
1. Import guard: `try: import tiktoken` with fallback raise-at-use if neither path resolves.
2. Helper signature: `def count_message_tokens(messages: list[BaseMessage], model: BaseChatModel) -> int` that first tries `model.count_tokens()`, then `tiktoken.cl100k_base`.
3. Unit test (`tests/unit/test_research_nodes_trim.py`): build a 10,000-token conversation using a known encoder, assert the counter returns ≥ 9,500 and ≤ 10,500, assert `trim_messages(max_tokens=6000, ...)` returns a list whose summed count is ≤ 6,000.

---

## Decision 2 — GPU utilization tooling for A1 audit (FR-001)

**Decision**: Use `nvidia-smi` subprocess calls for the audit. Do NOT add `pynvml` / `nvidia-ml-py` as a runtime dependency.

**Rationale**:
- A1's audit is a one-shot measurement exercise that runs on the reference workstation during Wave 1. The results go into `audit.md`; the tooling is not retained as a runtime dependency.
- `nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits -l 1` provides sampling at 1 Hz and is sufficient for spec-26 questions (VRAM under chat query, utilization %, kernel time is not needed).
- `nvidia-smi dmon -s u -c 30` captures a 30-second utilization window that can be committed as a text attachment or embedded in `audit.md`.
- Adding `pynvml` as a backend runtime dep violates Constitution VII (no new deps for one-shot tooling) and creates a cross-platform concern (pynvml requires CUDA drivers at Python import time — would break test runs on machines without GPUs).
- `nvtop` provides an interactive view but cannot be scripted for commit-safe snapshots; A1 may use it live during measurement but saves CSV from `nvidia-smi` for the audit artifact.

**Alternatives considered**:
- **`pynvml` / `nvidia-ml-py`**: programmatic access to NVML; rejected on runtime-dep cost.
- **`gpustat`**: friendlier CLI than `nvidia-smi` but adds a dependency; rejected on YAGNI.
- **`nsight-sys` / `nsight-compute`**: CUDA kernel profiling; overkill for spec-26 (we need utilization %, not kernel-level analysis). Rejected.
- **Docker stats alone**: measures container-level CPU/RAM but does NOT expose GPU per-process utilization. Rejected as insufficient.

**Action for A1**:
1. Baseline commands to capture in `audit.md`:
   - `nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader` (one-shot, for manifest)
   - `nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv -l 1 | tee audit-gpu-processes.csv` during 60-second chat-query session
   - `nvidia-smi dmon -s u -c 30 | tee audit-gpu-utilization.txt` during benchmark harness warm-up
2. Attach the CSV/text outputs to `specs/026-performance-debug/audit/` subdirectory (A1 creates) or embed verbatim in `audit.md`.

---

## Decision 3 — Benchmark harness priming-query protocol (FR-002)

**Decision**: Single priming query (1 factoid against the seeded collection) executed BEFORE the measured set. Timing of the priming query is captured in a separate `cold_start_ms` field but is NOT included in warm-state p50/p90/p99. The backend is NOT restarted between measured queries within a run. Between independent runs (NFR-003 reproducibility), the full Docker stack is NOT torn down — only the backend container is restarted via `docker compose restart backend` to produce a fresh cold-start on run 1, then subsequent repeats retain the warm model.

**Rationale**:
- The Edge Case bullet in `spec.md` requires distinguishing cold-start from warm-state. The simplest correct implementation is a priming query — industry standard for ML inference benchmarks (see: MLPerf inference harness, huggingface transformers `benchmark.py`).
- One priming query is enough: `qwen2.5:7b` loads ~6 GB to VRAM on first inference. After that, subsequent queries reuse the loaded weights. Two priming queries would be wasted tokens; zero priming queries means the first measured query always reads as an outlier.
- Cold-start measured separately (not baked into p50) matches the clarified SC-004/005 contract (warm-state p50 gates; cold-start reported but does not block).
- Repeat-runs without full stack tear-down: spec-14 and prior benchmarks showed that Qdrant and SQLite warmup is negligible; only LLM VRAM load dominates cold-start. Restarting only the backend between reproducibility runs gives a true cold-start while keeping Qdrant stable (avoids corpus re-indexing noise).

**Alternatives considered**:
- **No priming query**: produces misleading p50 (always first-run dominated). Rejected.
- **3+ priming queries**: wasted Ollama invocations; no measurable variance reduction past 1. Rejected.
- **Tear down full stack between each run**: adds ~30 seconds per run (Qdrant start + index load); creates false variance from Qdrant cold-start that we don't care about. Rejected.
- **Two-tier harness (cold run + warm run as separate invocations)**: more complex CLI; rejected in favor of single-invocation harness with `cold_start_ms` + `warm_state_*` fields.

**Action for A4**:
1. CLI flag: `--priming-queries 1` (default). Settable to `0` for debugging. Document that `0` invalidates warm-state statistics.
2. JSON output schema (partial):
   ```json
   {
     "manifest": {"commit_sha": "...", "corpus_fingerprint": "...", "model": "qwen2.5:7b", "timestamp": "..."},
     "cold_start_ms": 18245,
     "warm_state_p50": {"factoid_ms": 3821, "analytical_ms": 10433},
     "warm_state_p90": {"factoid_ms": 4902, "analytical_ms": 14102},
     "warm_state_p99": {"factoid_ms": 5210, "analytical_ms": 18711},
     "overall_p50": {"factoid_ms": 3890, "analytical_ms": 10680},
     "stage_timings_p50": {"rewrite": 421, "retrieve": 87, "rerank": 234, "generate": 3090},
     "variance_cv": 0.08,
     "cold_vs_warm_ratio": 4.8
   }
   ```
3. Variance across repeat runs: harness calls itself 3× internally if `--repeat 3` is passed, computes coefficient of variation across the three p50 values, emits `variance_cv`. NFR-003 requires `variance_cv <= 0.15`.

---

## Decision 4 — Supported-model allowlist composition (FR-004)

**Decision**: Initial allowlist: `["qwen2.5:7b", "llama3.1:8b", "mistral:7b"]`. All are non-thinking models. The final list is negotiated between A3 (implementing the validator) and A8 (writing `docs/performance.md`) in Wave 4 — A8 may prune based on actual tested-and-recommended evidence from the benchmark runs.

**Rationale**:
- `qwen2.5:7b` is the target default — verified on the reference workstation in prior specs and already present in user's Ollama. Balanced quality vs speed for 7 GB VRAM footprint.
- `llama3.1:8b` is a well-known sibling; slightly larger but proven to work with LangChain tool binding. Listed as an alternative for users who prefer Llama.
- `mistral:7b` is the oldest in this class; broadly tested, good tool-calling support. Listed for users with VRAM constraints or Mistral preference.
- Thinking models explicitly excluded: `gemma4:e4b`, `gemma4:26b`, `qwen3-thinking`, `deepseek-r1`. Listed in `docs/performance.md` as unsupported.
- Embedding models (`nomic-embed-text`, etc.) are NOT governed by this allowlist — `supported_llm_models` targets the generation LLM only.

**Alternatives considered**:
- **Single model (`qwen2.5:7b` only)**: simplest, but rejects users who cannot download Qwen or prefer Llama/Mistral. Rejected on user-friendliness.
- **Open allowlist (any Ollama-tag-matching regex)**: too permissive; thinking models with `-think` suffixes would slip through. Rejected on the explicit thinking-model-unsupported contract.
- **Dynamic allowlist fetched from a registry**: over-engineered; adds network dependency; rejected on Constitution I (local-first) and VII (simplicity).

**Action for A3**:
1. `backend/config.py` adds `supported_llm_models: list[str] = ["qwen2.5:7b", "llama3.1:8b", "mistral:7b"]  # spec-26: non-thinking models only, see docs/performance.md`.
2. Startup validator raises a custom `UnsupportedModelError(model, supported)` from `backend/errors.py` (extend if needed; constitution V requires all custom errors inherit base class).
3. Error message format: `f"Configured LLM {model!r} is not supported in this release. Supported: {', '.join(supported)}. Thinking models are explicitly unsupported — see docs/performance.md."`.

---

## Decision 5 — Framework documentation pre-fetch targets (A2 support)

**Decision**: A2 pre-fetches documentation URLs via Context7 for these framework primitives and cites them inline in `framework-audit.md`:

| Primitive | Library | Context7 doc target |
|-----------|---------|---------------------|
| State reducers (`operator.add`, `add_messages`) | LangGraph 1.0.x | `langgraph/reference/types/#channels` |
| `StateGraph.add_conditional_edges` | LangGraph 1.0.x | `langgraph/reference/graphs/#stategraph` |
| `Send` fan-out | LangGraph 1.0.x | `langgraph/concepts/low_level/#send` |
| `AsyncSqliteSaver` checkpointer | langgraph-checkpoint-sqlite 2.x | `langgraph/reference/checkpoints/#asyncsqlitesaver` |
| `trim_messages` | LangChain Core 1.2.x | `langchain/reference/langchain_core.messages.utils.trim_messages` |
| `.with_structured_output()` | LangChain Core 1.2.x | `langchain/how_to/structured_output/` |
| `bind_tools` + Ollama format | langchain-ollama 0.2.x | `langchain-ollama/reference/ChatOllama.bind_tools` |
| `recursion_limit` configuration | LangGraph 1.0.x | `langgraph/concepts/low_level/#recursion-limit` |
| `interrupt()` / resume | LangGraph 1.0.x | `langgraph/how-tos/human_in_the_loop/` |
| `PydanticOutputParser` | LangChain Core 1.2.x | `langchain/reference/langchain_core.output_parsers.pydantic` |
| `tenacity` retry wrappers | tenacity 9.x | `tenacity/api/` |

**Rationale**: The framework-audit deliverable requires every finding to cite a documentation URL. A2 spends less time mid-audit hunting for docs if the target URLs are known at Phase 0. Context7 is the canonical doc fetcher per project convention (global CLAUDE.md: "Prefer this over web search for library docs"). Actual URLs may shift between LangChain/LangGraph minor releases — A2 runs `resolve-library-id` first to lock the versioned URL at audit time.

**Alternatives considered**:
- **Web search for each finding**: slower, non-deterministic, violates the Context7 preference.
- **Shipping a pinned-doc snapshot in the repo**: over-engineered; Context7 is the right abstraction.
- **Skipping doc citations entirely**: violates FR-001's "cites exact source location and links to the framework documentation that justifies the configuration choice".

**Action for A2**: before writing any finding, execute `resolve-library-id` for each target library, then `query-docs` for each primitive. Cache URLs in a short section at the top of `framework-audit.md` so later findings can reference them by anchor.

---

## Decision 6 — Seed data and reference corpus (FR-002 input)

**Decision**: Reuse the existing `scripts/seed_data.py` (created in spec-21) without modification. The seeded corpus is "Sample Knowledge Base" with `tests/fixtures/sample.md`. Benchmark harness targets the resulting collection by ID.

**Rationale**: Spec-21 already validated this seeding script end-to-end. Creating a new larger corpus for spec-26 would introduce variables (corpus size, document mix, chunk count) that the audit would have to disentangle from performance findings. Reusing the same 14-document seed keeps spec-26's measurements directly comparable to any spec-21 numbers already committed.

**Alternatives considered**:
- **Expand corpus to 100+ documents**: provides more realistic load but violates the "seed from existing `scripts/seed_data.py`" spec contract and invalidates reproducibility against historical numbers.
- **Synthetic corpus generator**: over-engineering.

**Action for A4**: `scripts/benchmark.py` has a required `--collection-id <id>` flag; caller (orchestrator or user) runs `python scripts/seed_data.py` first, captures the created collection ID from stdout, and passes it to the harness.

---

## Decision 7 — Orchestrator mandatory MCP tool — Sequential Thinking at Gate 1

**Decision**: Gate 1 (audit synthesis) explicitly requires the orchestrator to use `mcp__sequential-thinking__sequentialthinking` to rank the top-3 latency contributors. The output is committed to `audit-synthesis.md`.

**Rationale**: Top-1 contributor selection is a judgment call with multiple inputs (CPU time, GPU time, wall-clock, framework-overhead from A2). A one-shot analysis produces brittle rankings. Sequential Thinking's iterative-hypothesis pattern is well-suited: start with "which stage has the largest p50?", probe "is that stage's time dominated by LLM generation or retrieval?", refine "is it fixable without architectural rewrite?". This reasoning trace IS the commitable artifact.

**Alternatives considered**:
- **Deterministic ranking by raw p50**: misses architectural nuance (e.g., two stages each 40% of latency — both need attention). Rejected.
- **Ask A2 to rank**: A2 is already the framework auditor; asking them to also synthesize hardware + framework crosses the orchestrator/agent boundary. Rejected.

**Action for orchestrator**: at Gate 1, after reading both audits, invoke Sequential Thinking with a 5–8-thought session; commit the thought trace (or a distilled version) to `audit-synthesis.md`.

---

## Unknowns & Deferrals

- **BUG-010 root cause**: deliberately unresolved at Phase 0. Prior forensic analysis (spec-25) speculated three candidates; A5 does the actual investigation in Wave 3 because the fix is inseparable from the diagnosis. Phase 0 research resolves *how* A5 will investigate (Serena for caller graph, GitNexus for impact), not *what* the fix will be.
- **FR-005 top-1 latency contributor**: unknowable before Wave 1 audit runs. Phase 0 locks the protocol (Sequential Thinking at Gate 1) but not the target.
- **Opportunistic P3 disposition**: BUG-021 (cross-encoder-to-GPU) and BUG-022 (embedding device placement) dispositions depend on VRAM headroom numbers from A1's audit. Resolved in Wave 3 by A6.

---

## Summary

All Technical Context unknowns have a committed decision and rationale. No blockers to Phase 1.

| Decision | Outcome |
|----------|---------|
| Token counter | LangChain native → `tiktoken` fallback |
| GPU audit tooling | `nvidia-smi` subprocess (no new deps) |
| Benchmark priming | 1 priming query, backend-only restart between repeats |
| Supported-model allowlist | `qwen2.5:7b`, `llama3.1:8b`, `mistral:7b` (initial) |
| Framework doc pre-fetch | 11 primitives mapped to Context7 targets |
| Seed corpus | Reuse spec-21 `scripts/seed_data.py` |
| Gate 1 synthesis method | Mandatory Sequential Thinking |

Phase 0 complete.
