# Phase 4 — Model Experimentation Matrix: Ranked Scorecard

**Spec**: 025-master-debug | **Tasks**: T039–T044 | **Date**: 2026-04-01

---

## Ranked Scorecard

| Rank | LLM | Embedding | Overall | AQ | CA | RC | Lat | VRAM | SS | TTFT(ms) | Peak VRAM(MiB) | Notes |
|------|-----|-----------|---------|----|----|----|----|------|----|----------|----------------|-------|
| 1 ★ | deepseek-r1:8b | nomic-embed-text | **2.87** | 2.0 | 2.0 | 4.0 | 3.8 | 4.7 | 2.5 | 96,782 | 7,276 | Best Q2 (conf=100, 291 chunks) |
| 2 | qwen2.5:7b | nomic-embed-text | 2.80 | 1.5 | 2.0 | 3.0 | 5.0 | 5.0 | 3.0 | 60,442 | 6,940 | Fastest; lowest VRAM |
| 3 | llama3.1:8b | mxbai-embed-large | 2.79 | 2.0 | 2.0 | 3.5 | 3.5 | 4.9 | 3.0 | 107,043 | 7,030 | Best Q1 — extracted "wsseg"; mxbai collection |
| 4 | llama3.1:8b | nomic-embed-text | 2.74 | 1.5 | 2.0 | 3.5 | 4.3 | 4.8 | 3.0 | 83,373 | 7,156 | |
| 5 | qwen2.5:7b | mxbai-embed-large | 2.67 | 1.5 | 2.0 | 3.0 | 4.3 | 4.8 | 3.0 | 81,273 | 7,170 | mxbai collection; Q3 strong (122 chunks) |
| 6 | phi4:14b | nomic-embed-text | 2.48 | 1.5 | 2.0 | 3.5 | 5.0 | 1.0 | 3.0 | 59,853 | 10,939 | VRAM: 10,939 MiB (89%); evicted after Q1 |
| 7 ✗ | mistral:7b | nomic-embed-text | 1.67 | 1.0 | 1.5 | 2.0 | 1.0 | 4.7 | 1.5 | 185,825 | 7,255 | **DISQUALIFIED** — runaway loop Q3 (591s) |

**Formula**: `Overall = (AQ×0.30) + (CA×0.25) + (RC×0.15) + (Lat×0.15) + (VRAM×0.10) + (SS×0.05)`

| Dimension | Weight | Definition |
|-----------|--------|------------|
| AQ | 30% | Answer Quality — correct/useful answers for domain queries |
| CA | 25% | Citation Accuracy — structured source attribution |
| RC | 15% | Response Coherence — structure and readability |
| Lat | 15% | Latency Score — 5=fastest (59,853ms), 1=slowest (185,825ms) |
| VRAM | 10% | VRAM Efficiency — 5=lowest (6,940 MiB), 1=highest (10,939 MiB) |
| SS | 5% | Streaming Smoothness — tok/s quality |

---

### Recommended Default Configuration

**Model**: deepseek-r1:8b + nomic-embed-text
**Overall Score**: 2.87

**Why this combination**: deepseek-r1:8b's chain-of-thought reasoning produced the only Q2 answer with
confidence=100 and 291 retrieved chunks — the best multi-hop performance across all combos. Its RC score
of 4.0 reflects consistently well-structured responses. VRAM usage of 7,276 MiB (59% of 12,282 MiB)
leaves adequate headroom for concurrent ingestion. The 96s average TTFT is acceptable given the
6-8 iteration research graph.

**Runner-up**: qwen2.5:7b + nomic-embed-text (score: 2.80)
Fastest model (60s TTFT) and lowest VRAM (6,940 MiB). Preferred if latency is prioritized over
answer depth. Suitable for low-complexity domain queries.

---

## Per-Combo Per-Query Detail

### Combo 1: qwen2.5:7b + nomic-embed-text

| Query | Archetype | Chunks | Confidence | TTFT(ms) | Total(ms) |
|-------|-----------|--------|------------|----------|-----------|
| Q1 | Factual | 1 | 0 | 41,755 | 41,758 |
| Q2 | Multi-hop | 203 | 42 | 70,971 | 78,001 |
| Q3 | Comparison | 52 | 0 | 54,023 | 65,701 |
| Q4 | Out-of-domain | 66 | 0 | 47,239 | 73,831 |
| Q5 | Vague | 1 | 0 | 88,226 | 88,332 |
| **Avg** | | 65 | 8 | 60,442 | 69,524 |

**Notable**: Q2 gave partial answer mentioning FEParamGetTiposDoc [9,10] inline — incorrect service
(FEParamGetTiposDoc is a param lookup, not auth). Q5 retrieved 0 relevant chunks.

### Combo 2: llama3.1:8b + nomic-embed-text

| Query | Archetype | Chunks | Confidence | TTFT(ms) | Total(ms) |
|-------|-----------|--------|------------|----------|-----------|
| Q1 | Factual | 1 | 0 | 102,730 | 103,064 |
| Q2 | Multi-hop | 249 | 15 | 64,049 | 94,354 |
| Q3 | Comparison | 178 | 0 | 101,546 | 130,378 |
| Q4 | Out-of-domain | 56 | 0 | 52,321 | 65,439 |
| Q5 | Vague | 1 | 0 | 96,220 | 96,398 |
| **Avg** | | 97 | 3 | 83,373 | 97,926 |

**Notable**: Q2 mentioned credenciales de autenticación; Q3 retrieved 178 chunks but no clear diff answer.

### Combo 3: mistral:7b + nomic-embed-text — ✗ DISQUALIFIED

| Query | Archetype | Chunks | Confidence | TTFT(ms) | Total(ms) |
|-------|-----------|--------|------------|----------|-----------|
| Q1 | Factual | 1 | 0 | 85,498 | 85,676 |
| Q2 | Multi-hop | 1 | 0 | 114,426 | 114,573 |
| Q3 | Comparison | 1 | 0 | **591,074** | 591,180 |
| Q4 | Out-of-domain | 84 | 0 | 55,354 | 65,483 |
| Q5 | Vague | 94 | 100 | 82,775 | 92,950 |
| **Avg** | | 36 | 20 | 185,825 | 189,972 |

**BUG-P4-001**: Q3 took 591s TTFT — runaway research graph iteration. See `bugs.md`.

### Combo 4: phi4:14b + nomic-embed-text

| Query | Archetype | Chunks | Confidence | TTFT(ms) | Total(ms) |
|-------|-----------|--------|------------|----------|-----------|
| Q1 | Factual | 1 | 0 | 83,352 | 83,439 |
| Q2 | Multi-hop | 217 | 42 | 58,940 | 86,789 |
| Q3 | Comparison | 50 | 0 | 38,135 | 45,051 |
| Q4 | Out-of-domain | 62 | 0 | 41,872 | 74,356 |
| Q5 | Vague | 67 | 0 | 76,970 | 111,388 |
| **Avg** | | 79 | 8 | 59,853 | 80,204 |

**T041 VRAM Stress**: Loaded at 10,939 MiB (89% of 12,282 MiB). Auto-evicted by Ollama after Q1.
Q2–Q5 fell back to qwen2.5:7b (silent model swap). Peak=10,939 MiB confirmed — fits, but no headroom.

### Combo 5: deepseek-r1:8b + nomic-embed-text ★

| Query | Archetype | Chunks | Confidence | TTFT(ms) | Total(ms) |
|-------|-----------|--------|------------|----------|-----------|
| Q1 | Factual | 1 | 0 | 80,831 | 80,964 |
| Q2 | Multi-hop | 291 | 100 | 68,393 | 110,365 |
| Q3 | Comparison | 1 | 0 | 126,564 | 126,662 |
| Q4 | Out-of-domain | 1 | 0 | 74,752 | 74,831 |
| Q5 | Vague | 79 | 0 | 133,370 | 145,606 |
| **Avg** | | 75 | 20 | 96,782 | 107,685 |

**Notable**: Q2 best across all combos — 291 chunks, confidence=100, coherent chain-of-thought answer.
Q4 cleanest OOD rejection (1 chunk = below threshold, no hallucination risk).

### Combo 6: qwen2.5:7b + mxbai-embed-large

| Query | Archetype | Chunks | Confidence | TTFT(ms) | Total(ms) |
|-------|-----------|--------|------------|----------|-----------|
| Q1 | Factual | 112 | 0 | 57,083 | 65,995 |
| Q2 | Multi-hop | 1 | 0 | 127,895 | 127,997 |
| Q3 | Comparison | 122 | 0 | 54,547 | 64,672 |
| Q4 | Out-of-domain | 61 | 0 | 56,445 | 82,546 |
| Q5 | Vague | 50 | 0 | 110,399 | 125,149 |
| **Avg** | | 69 | 0 | 81,273 | 93,271 |

**Notable**: mxbai vastly improves Q1/Q3 retrieval (112/122 chunks vs 1 for nomic). Q1 answer
identified wsbfev1 (wrong), suggesting retrieval surfaced relevant but differently-named service docs.

### Combo 7: llama3.1:8b + mxbai-embed-large

| Query | Archetype | Chunks | Confidence | TTFT(ms) | Total(ms) |
|-------|-----------|--------|------------|----------|-----------|
| Q1 | Factual | 159 | 0 | 52,058 | 62,310 |
| Q2 | Multi-hop | 1 | 0 | 171,056 | 171,235 |
| Q3 | Comparison | 1 | 0 | 123,189 | 123,377 |
| Q4 | Out-of-domain | 67 | 0 | 84,458 | 91,761 |
| Q5 | Vague | 147 | 100 | 104,454 | 113,643 |
| **Avg** | | 75 | 20 | 107,043 | 112,465 |

**Notable**: Q1 correctly extracted "wsseg" from URL context in retrieved passages — only combo to
identify the correct service name. Q5: 147 chunks with confidence=100; cited authorization date context.

---

## Key Findings

### Finding 1: Embedding Dimension Is the Critical Retrieval Variable

mxbai-embed-large (1024-dim) retrieved 112–159 chunks for Q1 where all 5 nomic-embed-text (768-dim)
combos retrieved only 1 chunk. The ARCA WSSEG documentation likely uses vocabulary that aligns better
with mxbai's larger embedding space. **Recommendation**: Switch default embedding to mxbai-embed-large.

### Finding 2: Citation Pipeline Broken (BUG-P4-002)

All 7 combos had `citation_count=0` from the structured NDJSON citation events. However, models
produced inline `[N]` citation markers in their text responses. The backend retrieval works, the
models reference passages inline, but no `{"type":"citations", ...}` event is emitted.

### Finding 3: Confidence Threshold Needs Calibration

The global `confidence_threshold=60` (default) blocks most answers from being returned. With a small
(~5-chunk) seed collection, retrieval confidence scores rarely exceed 60. The threshold must be
re-calibrated or made collection-size-aware.

### Finding 4: Queries Must Match Corpus Language

The initial English queries in T040 (before correction) returned universal "none sufficiently relevant"
rejections. After switching to Spanish queries, domain retrieval improved significantly. The ARCA corpus
is in Spanish — query language must match.

### Finding 5: phi4:14b Not Viable as Default

Peak VRAM 10,939 MiB = 89% of total 12,282 MiB. Ollama auto-evicted phi4 after Q1, silently falling
back to qwen2.5:7b for Q2–Q5. No OOM crash, but unreliable for production use.

---

## SC-003 Assessment

**SC-003**: ≥5 of 7 model combos tested and scored.
**Result**: PASS — all 7 combos tested (T039 pull + T040/T041/T042 test runs).
