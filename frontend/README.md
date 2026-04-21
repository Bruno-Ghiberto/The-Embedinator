# frontend/

Next.js 16 web interface for The Embedinator, built with React 19 and
Tailwind CSS 4.

## Pages

| Route             | File                        | Description                  |
|-------------------|-----------------------------|------------------------------|
| `/chat`           | `app/chat/page.tsx`         | Chat interface with NDJSON streaming |
| `/collections`    | `app/collections/page.tsx`  | Collection management        |
| `/documents/[id]` | `app/documents/[id]/page.tsx` | Document browser           |
| `/settings`       | `app/settings/page.tsx`     | Application settings         |
| `/observability`  | `app/observability/page.tsx` | Traces, metrics, health dashboard |

## Components (21)

**Chat:** `ChatPanel`, `ChatInput`, `ChatSidebar`, `CitationTooltip`,
`ConfidenceIndicator`, `ModelSelector`

**Collections & Documents:** `CollectionList`, `CollectionCard`,
`CreateCollectionDialog`, `DocumentList`, `DocumentUploader`

**Observability:** `TraceTable`, `LatencyChart`, `ConfidenceDistribution`,
`CollectionStats`, `HealthDashboard`, `StageTimingsChart`, `MetricsTrends`

**Settings:** `ProviderHub`, `Toast`

**Layout:** `Navigation`

## Hooks

Custom SWR-based hooks for data fetching:

| Hook               | Purpose                                    |
|--------------------|--------------------------------------------|
| `useStreamChat`    | NDJSON streaming chat with event parsing   |
| `useCollections`   | Collection CRUD operations                 |
| `useModels`        | LLM and embedding model listing            |
| `useTraces`        | Query trace fetching                       |
| `useMetrics`       | Time-series metrics for charts             |

## Library

| File          | Purpose                                         |
|---------------|-------------------------------------------------|
| `lib/api.ts`  | API client with fetch wrappers                  |
| `lib/types.ts`| Shared TypeScript type definitions               |

## Development

```bash
npm install
npm run dev          # Start dev server on http://localhost:3000
npm run build        # Production build
npm run test         # Run vitest unit tests
npm run test:e2e     # Run Playwright E2E tests
npm run lint         # ESLint check
```

The frontend expects the backend API at `http://localhost:8000` by default.
In Docker, this is overridden to `http://backend:8000` via
`NEXT_PUBLIC_API_URL`.

## Tech Stack

- **Next.js 16** with App Router
- **React 19** with server components
- **Tailwind CSS 4** for styling
- **SWR 2** for data fetching and caching
- **recharts 2** for charts (latency, confidence, metrics)
- **Radix UI** for accessible dialog, tooltip, and select components
- **React Hook Form** for form handling
- **react-dropzone 14** for file upload drag-and-drop
