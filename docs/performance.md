# Performance

The Embedinator is a local-first agentic RAG system designed for a single developer workstation.
This document records measured performance on the reference hardware described below and explains
how the system behaves on weaker machines.

## Reference Hardware

| Component | Specification |
|-----------|---------------|
| CPU       | Intel Core i7-12700K (12 cores / 20 threads) |
| RAM       | 64 GB DDR5 |
| GPU       | NVIDIA RTX 4070 Ti (12 GB VRAM) |
| Storage   | NVMe SSD |
| OS        | Fedora Linux 43 (native Docker daemon) |
| Software  | Python 3.14, LangGraph 1.0.x, LangChain 1.2.x, Qdrant 1.17.x, Ollama 0.20.x |

## Measured Performance

All measurements are warm-state p50 (first query after model load excluded — see
[Cold-start](#cold-start)). Numbers come from the benchmark harness
(`python scripts/benchmark.py`) committed alongside the spec-26 validation at
`docs/benchmarks/fa3bbc8-wave3-iter2-final.json`.

| Query type | Warm-state p50 | Warm-state p90 | Warm-state p99 |
|------------|----------------|----------------|----------------|
| Factoid | 19,528 ms | 30,903 ms | 51,427 ms |
| Analytical (2–3 sub-questions) | 15,963 ms | 31,225 ms | 46,268 ms |

Cold-start (first query after `docker compose up`): 13,159 ms.  
Reproducibility: coefficient of variation across 3 independent runs = 0.107 (NFR-003 budget: ≤ 0.15). ✓  
Benchmark completions: 120/120 with 0 errors.

### Improvement vs. Pre-Fix Baseline

Spec-26 reduced warm-state p50 compared to the pre-fix baseline
(`627178e-pre-spec26.json`, same corpus, same hardware):

| Query type | Pre-fix p50 | Post-fix p50 | Change |
|------------|-------------|--------------|--------|
| Factoid    | 30,627 ms   | 19,528 ms    | −36%   |
| Analytical | 33,524 ms   | 15,963 ms    | −52%   |

### Stage Breakdown (p50, warm-state)

The stage-timing instrumentation added in commit `aa9c875` shows where time is spent:

| Stage | p50 |
|-------|-----|
| `research_orchestrator_ms` | 12,777 ms (3 calls × ~4,259 ms each) |
| `answer_generation` | 1,399 ms |
| `intent_classification` | 957 ms |
| `research_tools_ms` | 855 ms |
| `embedding` | 169 ms |

Research orchestrator calls account for approximately 65% of warm-state p50. Each call is a full
LLM inference pass on qwen2.5:7b. With the 3-iteration cap in place (commit `fa3bbc8`), three
such calls represent the practical floor for any query that enters the research loop.

## GPU Launch Requirement

The backend container requires GPU access to reach the numbers above. The NVIDIA GPU overlay
provides it:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu-nvidia.yml up -d
```

Using `./embedinator.sh` (or `.\embedinator.ps1` on Windows) is equivalent — the launcher
auto-detects the available GPU and merges the correct overlay. Plain `docker compose up -d`
without the overlay silently loses GPU access for the backend container, which locks the
cross-encoder reranker to CPU and increases reranking latency.

## Supported Models

The backend validates the configured LLM against an allowlist at startup. Configuring a model
outside this list causes the backend to refuse to start with a clear error message that names
the supported alternatives.

| Model | Status | Notes |
|-------|--------|-------|
| `qwen2.5:7b` | ✅ default, tested | Balanced quality/speed on 12 GB VRAM |
| `llama3.1:8b` | ✅ tested | Slightly larger context; good tool-calling |
| `mistral:7b` | ✅ tested | Broadly tested; lower VRAM footprint |

### Unsupported (current release)

Thinking models — models that emit internal reasoning tokens (e.g., `<think>…</think>`) before
their answer — are not supported in this release. These include `gemma4:e4b`, `gemma4:26b`,
`qwen3-thinking`, and `deepseek-r1:*`. The structured-output parsers in the agent graph require
clean JSON; thinking tokens break them, trigger fallback paths, and open the circuit breaker
under light load.

The backend refuses to start with an unsupported model configured and names the supported
alternatives in the error. Supporting thinking models is a future-spec concern tracked as a
candidate for spec-27 or later.

## Behavior on Weaker Hardware

The numbers above are for the reference hardware. On weaker machines:

- **VRAM below 12 GB**: `qwen2.5:7b` requires approximately 7 GB VRAM. Below 8 GB, Ollama
  offloads portions of the model to CPU, roughly doubling token generation latency.
- **CPU below 12 threads**: reranking and embedding coordination slow down; not catastrophic.
- **RAM below 16 GB**: Qdrant memory-mapping and SQLite cache efficiency degrade; p90 latency
  widens.
- **Spinning disk**: SQLite WAL and Qdrant I/O become a bottleneck; not recommended.

## Cold-start

The first query after backend startup takes approximately 13,159 ms longer than warm-state
queries. This is model weight loading into VRAM — an expected one-time cost, not a bug. The
benchmark harness uses a priming query to separate this loading penalty from warm-state
statistics so that the published numbers reflect steady-state usage.

If cold-start matters for your workflow, keep the backend running between sessions. Ollama
caches model weights in VRAM until evicted by memory pressure.

## Known Limitations

### SC-004 / SC-005 Targets Not Met

Spec-26 success criteria defined:

- **SC-004**: warm-state factoid p50 ≤ 4,000 ms
- **SC-005**: warm-state analytical p50 ≤ 12,000 ms

The iteration-2 final benchmark does not meet these targets:
- Factoid: 19,528 ms — 4.88× above SC-004
- Analytical: 15,963 ms — 1.33× above SC-005

Both spec-26 optimization iterations were applied and exhausted the iteration budget:

- **Iter 1** (`d21d3a7`): gated `verify_groundedness` behind a feature flag, saving approximately
  1 s per query.
- **Iter 2** (`fa3bbc8`): capped `max_iterations` from 10 to 3, saving approximately 3.6 s per
  query.

Instrumentation (commit `aa9c875`) revealed that research orchestrator LLM calls dominate
latency (~12,777 ms, 65% of warm-state p50). With qwen2.5:7b on the reference GPU generating
at approximately 4,259 ms per call and a 3-iteration cap, the research loop alone floors at
approximately 12.8 s. The remaining ~3.2 s is split across answer generation, intent
classification, tool calls, and embedding (not yet fully instrumented).

Further reduction below SC-004 and SC-005 requires architectural changes outside spec-26 scope.
See [§Spec-27 Candidates](#spec-27-candidates) below.

### Thinking Models

Thinking models are unsupported in the current release. See [Supported Models](#supported-models).

### Citation Deduplication

The `Send()` fan-out in the research graph can produce duplicate citations with different
`passage_id` values but identical text. This is visible in some responses. Tracked as BUG-017
in `docs/bug-registry-spec26.md`; deferred to spec-27 (requires reducer changes in `state.py`).

## Spec-27 Candidates

These changes are the most promising paths toward closing the SC-004 and SC-005 gap:

1. **Model swap** — largest single lever. Test `qwen2.5:3b`, `llama3.2:3b`, or `phi3:mini`
   against the same corpus. A 3B-class model may achieve approximately 5–6 s factoid p50.
2. **Orchestrator prompt reduction** — the `ORCHESTRATOR_SYSTEM` prompt embeds up to 10 chunk
   summaries per iteration. Trimming to top-3 or compressing reduces input tokens and shortens
   each LLM call proportionally.
3. **Factoid fast-path** — `intent_classification` already tags factoid vs. analytical queries.
   A bypass that skips the research loop for factoid queries with high initial retrieval
   confidence eliminates the 3-call floor for that query class.
4. **`collect_answer` + graph-scheduling instrumentation** — close the remaining ~3.2 s
   un-instrumented gap to confirm no hidden bottleneck before model-swap tests.
5. **Cross-encoder GPU migration (BUG-021)** — the backend container now has GPU access (commit
   `5bae5e2`). Moving the cross-encoder from CPU to GPU requires approximately 90 MiB VRAM.
   Deferred from spec-26 to keep SC-004/SC-005 attribution clean; apply in spec-27.

## Reproducing These Numbers

See [`specs/026-performance-debug/quickstart.md`](../specs/026-performance-debug/quickstart.md)
for step-by-step instructions to reproduce the benchmark on the reference hardware.
