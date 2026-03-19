"use client";

import { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useMetrics } from "@/hooks/useMetrics";

// ─── Types ────────────────────────────────────────────────────────────────────

export type MetricsWindow = "1h" | "24h" | "7d";

export interface MetricsTrendsProps {
  defaultWindow?: MetricsWindow;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const WINDOW_OPTIONS: { label: string; value: MetricsWindow }[] = [
  { label: "Last 1 h", value: "1h" },
  { label: "Last 24 h", value: "24h" },
  { label: "Last 7 d", value: "7d" },
];

function formatTimestamp(ts: string): string {
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// ─── MetricsTrends ────────────────────────────────────────────────────────────
// Imported via next/dynamic with { ssr: false } in observability/page.tsx

export function MetricsTrends({ defaultWindow = "24h" }: MetricsTrendsProps) {
  const [window, setWindow] = useState<MetricsWindow>(defaultWindow);
  const { data, error, isLoading } = useMetrics(window);

  const chartData =
    data?.buckets.map((b) => ({
      time: formatTimestamp(b.timestamp),
      avg_latency_ms: b.avg_latency_ms,
      p95_latency_ms: b.p95_latency_ms,
      avg_confidence: b.avg_confidence,
    })) ?? [];

  return (
    <section>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Metrics Trends</h2>

        {/* Window selector */}
        <div className="flex gap-1 rounded-lg border border-gray-200 bg-gray-50 p-1">
          {WINDOW_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setWindow(opt.value)}
              className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
                window === opt.value
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
              aria-pressed={window === opt.value}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="flex h-[250px] items-center justify-center rounded-lg bg-gray-50 text-sm text-gray-400">
            Loading metrics…
          </div>
          <div className="flex h-[250px] items-center justify-center rounded-lg bg-gray-50 text-sm text-gray-400">
            Loading metrics…
          </div>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-100 bg-red-50 p-4">
          <p className="text-sm text-red-600">
            Failed to load metrics data. The backend metrics endpoint may not be
            available yet.
          </p>
        </div>
      ) : chartData.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-8 text-center">
          <p className="text-sm text-gray-400">
            No metrics available for the selected window.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Average & P95 latency trend */}
          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-gray-700">
              Latency Trend
            </h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart
                data={chartData}
                margin={{ top: 4, right: 16, left: 0, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" tick={{ fontSize: 11 }} />
                <YAxis
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v: number) => `${v} ms`}
                />
                <Tooltip formatter={(v: number) => [`${v} ms`]} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line
                  type="monotone"
                  dataKey="avg_latency_ms"
                  name="Avg latency"
                  stroke="#6366f1"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="p95_latency_ms"
                  name="P95 latency"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  dot={false}
                  strokeDasharray="4 2"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Average confidence trend */}
          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-gray-700">
              Confidence Trend
            </h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart
                data={chartData}
                margin={{ top: 4, right: 16, left: 0, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" tick={{ fontSize: 11 }} />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v: number) => `${v}`}
                />
                <Tooltip
                  formatter={(v: number) => [`${v}`, "Avg confidence"]}
                />
                <Line
                  type="monotone"
                  dataKey="avg_confidence"
                  name="Avg confidence"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </section>
  );
}
