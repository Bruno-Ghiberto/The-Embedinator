"use client";

import { Suspense, lazy, useState } from "react";
import { HealthDashboard } from "@/components/HealthDashboard";
import { TraceTable } from "@/components/TraceTable";
import { CollectionStats } from "@/components/CollectionStats";
import { useTraces } from "@/hooks/useTraces";
import { Skeleton } from "@/components/ui/skeleton";

// Recharts components are lazy-loaded and gated behind a user toggle.
// KNOWN ISSUE: recharts SVG rendering + ResizeObserver breaks Next.js
// client-side navigation when React is recovering from hydration mismatch
// (caused by next-themes injecting dark class before React hydrates).
// Charts are opt-in to preserve reliable page navigation.
const LatencyChart = lazy(() =>
  import("@/components/LatencyChart").then((m) => ({
    default: m.LatencyChart,
  })),
);

const ConfidenceDistribution = lazy(() =>
  import("@/components/ConfidenceDistribution").then((m) => ({
    default: m.ConfidenceDistribution,
  })),
);

const MetricsTrends = lazy(() =>
  import("@/components/MetricsTrends").then((m) => ({
    default: m.MetricsTrends,
  })),
);

const PAGE_LIMIT = 20;

export default function ObservabilityClient() {
  const [showCharts, setShowCharts] = useState(false);
  const [offset, setOffset] = useState(0);
  const [sessionFilter, setSessionFilter] = useState("");

  const sessionFilterParam = sessionFilter.trim() || undefined;
  const {
    traces,
    total,
    limit,
    isLoading: tracesLoading,
    isError: tracesError,
  } = useTraces({
    limit: PAGE_LIMIT,
    offset,
    session_id: sessionFilterParam,
  });

  const handleSessionFilterChange = (value: string) => {
    setSessionFilter(value);
    setOffset(0);
  };

  const handlePageChange = (newOffset: number) => {
    setOffset(newOffset);
  };

  return (
    <main className="mx-auto max-w-7xl space-y-10 px-4 py-8 sm:px-6 lg:px-8">
      <h1 className="text-2xl font-bold text-foreground">Observability</h1>

      <HealthDashboard />

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">
            Query Analytics
          </h2>
          {!showCharts && (
            <button
              onClick={() => setShowCharts(true)}
              className="rounded-md border border-border bg-background px-3 py-1.5 text-sm font-medium text-foreground shadow-sm hover:bg-accent"
            >
              Show Charts
            </button>
          )}
        </div>
        {showCharts ? (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-lg border border-border bg-background p-4 shadow-sm">
              {tracesLoading ? (
                <div className="flex h-[275px] items-center justify-center text-sm text-muted-foreground">
                  Loading traces...
                </div>
              ) : tracesError ? (
                <p className="text-sm text-destructive">
                  Failed to load trace data.
                </p>
              ) : (
                <Suspense
                  fallback={
                    <Skeleton className="h-[250px] w-full rounded-lg" />
                  }
                >
                  <LatencyChart traces={traces ?? []} />
                </Suspense>
              )}
            </div>
            <div className="rounded-lg border border-border bg-background p-4 shadow-sm">
              {tracesLoading ? (
                <div className="flex h-[275px] items-center justify-center text-sm text-muted-foreground">
                  Loading traces...
                </div>
              ) : tracesError ? (
                <p className="text-sm text-destructive">
                  Failed to load trace data.
                </p>
              ) : (
                <Suspense
                  fallback={
                    <Skeleton className="h-[250px] w-full rounded-lg" />
                  }
                >
                  <ConfidenceDistribution traces={traces ?? []} />
                </Suspense>
              )}
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            Charts are loaded on demand. Click &quot;Show Charts&quot; to view
            latency and confidence distributions.
          </p>
        )}
      </section>

      {showCharts ? (
        <Suspense
          fallback={<Skeleton className="h-[300px] w-full rounded-lg" />}
        >
          <MetricsTrends />
        </Suspense>
      ) : null}

      {tracesLoading ? (
        <section>
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            Query Traces
          </h2>
          <Skeleton className="h-40 w-full rounded-lg" />
        </section>
      ) : tracesError ? (
        <section>
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            Query Traces
          </h2>
          <p className="text-sm text-destructive">Failed to load traces.</p>
        </section>
      ) : (
        <TraceTable
          traces={traces ?? []}
          total={total}
          limit={limit}
          offset={offset}
          onPageChange={handlePageChange}
          sessionFilter={sessionFilter}
          onSessionFilterChange={handleSessionFilterChange}
        />
      )}

      <CollectionStats />
    </main>
  );
}
