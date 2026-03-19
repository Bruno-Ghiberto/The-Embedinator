# Agent A6: Observability Page Engineer

**Agent Type**: `performance-engineer`
**Model**: Sonnet
**Wave**: 4 (serial)
**Tasks**: T032-T037

## Mission

Build the observability dashboard with health service cards, recharts latency histogram and confidence distribution, a paginated trace table with expandable detail rows, and per-collection statistics. All chart components use dynamic imports with `ssr: false`.

## Authoritative Sources

Read these files FIRST before writing any code:

- `specs/009-next-frontend/contracts/api-client.ts` -- HealthStatus, HealthService (services array), SystemStats, QueryTrace, QueryTraceDetail, getHealth, getStats, getTraces, getTraceDetail
- `specs/009-next-frontend/data-model.md` -- HealthStatus structure, confidence tiers, QueryTrace fields
- `specs/009-next-frontend/tasks.md` -- Task list with exact descriptions for T032-T037
- `Docs/PROMPTS/spec-09-frontend/09-implement.md` -- Component props, SWR patterns

## Tasks

1. **T032** [P] [US5] Create `frontend/components/HealthDashboard.tsx` -- 3 service cards from `getHealth()`; service names `sqlite`/`qdrant`/`ollama`; green `ok` / red `error` status badge; `latency_ms` value; `error_message` shown on error state
2. **T033** [P] [US5] Create `frontend/components/LatencyChart.tsx` -- `recharts` `BarChart` showing query latency distribution (buckets from trace data); loaded via `next/dynamic` with `{ ssr: false }`; loading placeholder
3. **T034** [P] [US5] Create `frontend/components/ConfidenceDistribution.tsx` -- `recharts` `BarChart` with 3 bars (green >= 70, yellow 40-69, red < 40) computed from trace `confidence_score` values; loaded via `next/dynamic` with `{ ssr: false }`
4. **T035** [P] [US5] Create `frontend/components/TraceTable.tsx` -- paginated via `useTraces`; previous/next controls; `session_id` filter input; expand row fetches `getTraceDetail(id)` on demand; expanded row shows `sub_questions`, `reasoning_steps`, `strategy_switches`, `meta_reasoning_triggered` flag
5. **T036** [P] [US5] Create `frontend/components/CollectionStats.tsx` -- per-collection `document_count` from `useCollections`; aggregate `total_chunks` and `total_documents` from `getStats()`; parallel `useSWR` keys
6. **T037** [US5] Create `frontend/app/observability/page.tsx` -- `'use client'`; composes `HealthDashboard`, `LatencyChart`, `ConfidenceDistribution`, `TraceTable`, `CollectionStats`; parallel SWR fetches for health and stats; incremental loading states (each section renders independently)

## Key Constraints

- **HealthStatus structure**: `{ status: "healthy" | "degraded", services: HealthService[] }` where `HealthService` has `{ name, status, latency_ms, error_message }`. This is NOT a flat object with `qdrant`/`ollama`/`sqlite` as top-level keys. Iterate over `services` array.
- **Confidence is INTEGER 0-100**: When computing distribution tiers: green >= 70, yellow 40-69, red < 40. NOT float thresholds.
- **Dynamic imports for recharts**: Both `LatencyChart` and `ConfidenceDistribution` must be loaded via `next/dynamic` with `{ ssr: false }` to avoid SSR issues with recharts.
- **Trace pagination**: `getTraces()` accepts `{ limit, offset }` params (NOT `page`). Calculate offset from page number: `offset = page * limit`.
- **Expandable trace detail**: Fetch `getTraceDetail(traceId)` on demand when a row is expanded. Do not pre-fetch all details.
- **QueryTraceDetail fields**: `sub_questions`, `chunks_retrieved`, `reasoning_steps`, `strategy_switches` -- all are arrays. `reasoning_steps` and `strategy_switches` are `Record<string, unknown>[]`.
- **No per-collection chunk count**: Only `document_count` exists per collection. Aggregate `total_chunks` comes from `getStats()`.
- **Parallel SWR fetches**: Health and stats use separate SWR keys and fetch independently.

## Testing Protocol

- NEVER run tests inside Claude Code
- TypeScript compile: `cd frontend && npx tsc --noEmit`
- Visual verification: `/observability` renders health cards with status/latency; charts render; trace table paginates; expanded rows show detail

## Done Criteria

- `/observability` page renders all 5 sections without errors
- Health cards show 3 services from `services[]` array with status badges and latency
- Charts render via dynamic import (no SSR errors)
- Confidence distribution uses integer 0-100 tiers
- Trace table paginates with offset-based navigation
- Expanding a row fetches and displays trace detail
- Collection stats show per-collection doc counts and aggregate stats
- `npx tsc --noEmit` exits 0
