"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { HealthDashboard } from "@/components/HealthDashboard";
import { TraceTable } from "@/components/TraceTable";
import { CollectionStats } from "@/components/CollectionStats";
import { useTraces } from "@/hooks/useTraces";
import type { LatencyChartProps } from "@/components/LatencyChart";
import type { ConfidenceDistributionProps } from "@/components/ConfidenceDistribution";
import type { MetricsTrendsProps } from "@/components/MetricsTrends";

// ─── Dynamic imports for recharts (no SSR) ────────────────────────────────────

const LatencyChart = dynamic<LatencyChartProps>(
  () => import("@/components/LatencyChart").then((m) => m.LatencyChart),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-[250px] items-center justify-center rounded-lg bg-gray-50 text-sm text-gray-400">
        Loading chart…
      </div>
    ),
  },
);

const ConfidenceDistribution = dynamic<ConfidenceDistributionProps>(
  () =>
    import("@/components/ConfidenceDistribution").then(
      (m) => m.ConfidenceDistribution,
    ),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-[250px] items-center justify-center rounded-lg bg-gray-50 text-sm text-gray-400">
        Loading chart…
      </div>
    ),
  },
);

const MetricsTrends = dynamic<MetricsTrendsProps>(
  () =>
    import("@/components/MetricsTrends").then((m) => m.MetricsTrends),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-[250px] items-center justify-center rounded-lg bg-gray-50 text-sm text-gray-400">
        Loading metrics…
      </div>
    ),
  },
);

// ─── Page ─────────────────────────────────────────────────────────────────────

const PAGE_LIMIT = 20;

export default function ObservabilityPage() {
  const [offset, setOffset] = useState(0);
  const [sessionFilter, setSessionFilter] = useState("");

  // Build trace query params — use primitive values to avoid stale closure issues
  const sessionFilterParam = sessionFilter.trim() || undefined;
  const { traces, total, limit, isLoading: tracesLoading, isError: tracesError } =
    useTraces({
      limit: PAGE_LIMIT,
      offset,
      session_id: sessionFilterParam,
    });

  const handleSessionFilterChange = (value: string) => {
    setSessionFilter(value);
    setOffset(0); // Reset to first page on filter change
  };

  const handlePageChange = (newOffset: number) => {
    setOffset(newOffset);
  };

  return (
    <main className="mx-auto max-w-7xl space-y-10 px-4 py-8 sm:px-6 lg:px-8">
      <h1 className="text-2xl font-bold text-gray-900">Observability</h1>

      {/* ── Section 1: Health Dashboard — fetches its own data independently ── */}
      <HealthDashboard />

      {/* ── Section 2 & 3: Charts — loaded via dynamic import (ssr: false) ── */}
      <section>
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          Query Analytics
        </h2>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            {tracesLoading ? (
              <div className="flex h-[275px] items-center justify-center text-sm text-gray-400">
                Loading traces…
              </div>
            ) : tracesError ? (
              <p className="text-sm text-red-600">Failed to load trace data.</p>
            ) : (
              <LatencyChart traces={traces ?? []} />
            )}
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            {tracesLoading ? (
              <div className="flex h-[275px] items-center justify-center text-sm text-gray-400">
                Loading traces…
              </div>
            ) : tracesError ? (
              <p className="text-sm text-red-600">Failed to load trace data.</p>
            ) : (
              <ConfidenceDistribution traces={traces ?? []} />
            )}
          </div>
        </div>
      </section>

      {/* ── Section 3b: Metrics Trends — loaded via dynamic import (ssr: false) ── */}
      <MetricsTrends />

      {/* ── Section 4: Trace Table ── */}
      {tracesLoading ? (
        <section>
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Query Traces</h2>
          <div className="h-40 animate-pulse rounded-lg bg-gray-100" />
        </section>
      ) : tracesError ? (
        <section>
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Query Traces</h2>
          <p className="text-sm text-red-600">Failed to load traces.</p>
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

      {/* ── Section 5: Collection Stats — fetches its own data independently ── */}
      <CollectionStats />
    </main>
  );
}
