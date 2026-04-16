# Contract: Model Comparison Scorecard

**Version**: 1.0 | **Spec**: 025-master-debug

## Purpose

The scorecard is the primary output of Phase 3 (Model Experimentation Matrix). It ranks all tested model combinations by overall quality score and provides a data-driven recommendation for the default configuration.

## Scorecard Table Format

```markdown
| Rank | LLM | Embedding | Overall | AQ | CA | RC | Lat | VRAM | SS | TTFT(ms) | Peak VRAM(MB) | Notes |
|------|-----|-----------|---------|----|----|----|----|------|----|----------|---------------|-------|
| 1    |     |           |         |    |    |    |    |      |    |          |               |       |
```

### Column Definitions

| Column | Full Name | Type | Description |
|--------|-----------|------|-------------|
| Rank | Rank | integer | Position by overall score (1 = best) |
| LLM | LLM Model | string | Model name (e.g., "qwen2.5:7b") |
| Embedding | Embedding Model | string | Embedding model name |
| Overall | Overall Score | float (2 decimals) | Weighted average (see formula below) |
| AQ | Answer Quality | float (1 decimal) | Mean across 5 queries (1-5 scale) |
| CA | Citation Accuracy | float (1 decimal) | Mean across 5 queries (1-5 scale) |
| RC | Response Coherence | float (1 decimal) | Mean across 5 queries (1-5 scale) |
| Lat | Latency Score | float (1 decimal) | Normalized: 5 = fastest, 1 = slowest |
| VRAM | VRAM Efficiency | float (1 decimal) | Normalized: 5 = lowest usage, 1 = highest |
| SS | Streaming Smoothness | float (1 decimal) | Mean across 5 queries (1-5 scale) |
| TTFT(ms) | Time to First Token | integer | Mean TTFT in milliseconds |
| Peak VRAM(MB) | Peak GPU Memory | integer | Peak observed VRAM during inference |
| Notes | Notes | string | Anomalies, OOM, re-ingestion time, etc. |

## Scoring Formula

```
Overall = (AQ * 0.30) + (CA * 0.25) + (RC * 0.15) + (Lat * 0.15) + (VRAM * 0.10) + (SS * 0.05)
```

### Weight Rationale

| Dimension | Weight | Rationale |
|-----------|--------|-----------|
| Answer Quality | 0.30 | Core value proposition of the RAG system |
| Citation Accuracy | 0.25 | Trust signal --- users need accurate source attribution |
| Response Coherence | 0.15 | Readability and structure matter for comprehension |
| Latency Score | 0.15 | User experience degrades with slow responses |
| VRAM Efficiency | 0.10 | 12GB constraint makes efficiency a differentiator |
| Streaming Smoothness | 0.05 | Minor UX factor --- bursty streaming is tolerable |

### Normalization for Derived Scores

**Latency Score** (derived from TTFT):
- Rank all combos by mean TTFT (ascending = better).
- Fastest combo gets 5.0, slowest gets 1.0. Linear interpolation for others.
- Formula: `5.0 - 4.0 * (combo_ttft - min_ttft) / (max_ttft - min_ttft)`

**VRAM Efficiency Score** (derived from peak VRAM):
- Rank all combos by peak VRAM (ascending = better).
- Lowest VRAM gets 5.0, highest gets 1.0. Linear interpolation.
- Formula: `5.0 - 4.0 * (combo_vram - min_vram) / (max_vram - min_vram)`

### Special Cases

- **VRAM_EXCEEDED combos**: Listed at the bottom with "VRAM EXCEEDED" in Notes. No overall score. All dimension columns show "---" except Peak VRAM (shows observed value).
- **SKIPPED combos**: Listed at the bottom with "SKIPPED" in Notes. All columns show "---".
- **Recommended combo**: Marked with a star or bold. Must include a tradeoff analysis paragraph.

## Per-Query Detail Table (appendix)

For each combo, a detail table records per-query scores:

```markdown
### Combo {N}: {LLM} + {Embedding}

| Query | Archetype | AQ | CA | RC | SS | IF | TTFT(ms) | Latency(ms) | Confidence |
|-------|-----------|----|----|----|----|----|---------  |-------------|------------|
| Q1    | Factual   |    |    |    |    |    |           |             |            |
| Q2    | Multi-hop |    |    |    |    |    |           |             |            |
| Q3    | Compare   |    |    |    |    |    |           |             |            |
| Q4    | OOD       |    |    |    |    |    |           |             |            |
| Q5    | Vague     |    |    |    |    |    |           |             |            |
| **Avg** |         |    |    |    |    |    |           |             |            |
```

(IF = Instruction Following, scored 1-5 but not included in the overall formula --- reported for informational purposes.)

## Recommendation Section

After the scorecard table, include:

```markdown
### Recommended Default Configuration

**Model**: {LLM} + {Embedding}
**Overall Score**: {score}

**Why this combination**:
[2-3 sentences explaining the tradeoff analysis --- quality vs latency vs VRAM]

**Runner-up**: {LLM} + {Embedding} (score: {N})
[1 sentence on why the runner-up is a valid alternative]
```

## Engram Persistence

Scorecard data persisted to `spec-25/p3-model-matrix` with per-combo raw scores and the final ranked table.
