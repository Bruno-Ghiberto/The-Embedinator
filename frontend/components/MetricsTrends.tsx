"use client";

import { useEffect, useState } from "react";
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
import { cn } from "@/lib/utils";

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

function resolveCssVar(varName: string): string {
  if (typeof window === "undefined") return "#7c3aed";
  return getComputedStyle(document.documentElement).getPropertyValue(varName).trim() || "#7c3aed";
}

// ─── MetricsTrends ────────────────────────────────────────────────────────────
// Imported via next/dynamic with { ssr: false } in observability/page.tsx

export function MetricsTrends({ defaultWindow = "24h" }: MetricsTrendsProps) {
  const [window, setWindow] = useState<MetricsWindow>(defaultWindow);
  const { data, error, isLoading } = useMetrics(window);

  const [chartColors, setChartColors] = useState({
    accent: "#7c3aed",
    warning: "#d97706",
    success: "#059669",
    axis: "#6b52b5",
    grid: "#d1c4f5",
  });

  useEffect(() => {
    setChartColors({
      accent: resolveCssVar("--primary"),
      warning: resolveCssVar("--warning"),
      success: resolveCssVar("--success"),
      axis: resolveCssVar("--muted-foreground"),
      grid: resolveCssVar("--border"),
    });
  }, []);

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
        <h2 className="text-lg font-semibold text-foreground">Metrics Trends</h2>

        {/* Window selector */}
        <div className="flex gap-1 rounded-lg border border-border bg-card p-1">
          {WINDOW_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setWindow(opt.value)}
              className={cn(
                "rounded-md px-3 py-1 text-sm font-medium transition-colors",
                window === opt.value
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
              aria-pressed={window === opt.value}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="flex h-[250px] items-center justify-center rounded-lg bg-card text-sm text-muted-foreground">
            Loading metrics...
          </div>
          <div className="flex h-[250px] items-center justify-center rounded-lg bg-card text-sm text-muted-foreground">
            Loading metrics...
          </div>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-4">
          <p className="text-sm text-destructive">
            Failed to load metrics data. The backend metrics endpoint may not be
            available yet.
          </p>
        </div>
      ) : chartData.length === 0 ? (
        <div className="rounded-lg border border-border bg-card p-8 text-center">
          <p className="text-sm text-muted-foreground">
            No metrics available for the selected window.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Average & P95 latency trend */}
          <div className="rounded-lg border border-border bg-background p-4 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-foreground">
              Latency Trend
            </h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart
                data={chartData}
                margin={{ top: 4, right: 16, left: 0, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                <XAxis dataKey="time" tick={{ fontSize: 11, fill: chartColors.axis }} />
                <YAxis
                  tick={{ fontSize: 11, fill: chartColors.axis }}
                  tickFormatter={(v: number) => `${v} ms`}
                />
                <Tooltip
                  formatter={(v: number) => [`${v} ms`]}
                  contentStyle={{
                    backgroundColor: "var(--card)",
                    borderColor: "var(--border)",
                    color: "var(--foreground)",
                    borderRadius: "0.5rem",
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line
                  type="monotone"
                  dataKey="avg_latency_ms"
                  name="Avg latency"
                  stroke={chartColors.accent}
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="p95_latency_ms"
                  name="P95 latency"
                  stroke={chartColors.warning}
                  strokeWidth={2}
                  dot={false}
                  strokeDasharray="4 2"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Average confidence trend */}
          <div className="rounded-lg border border-border bg-background p-4 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-foreground">
              Confidence Trend
            </h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart
                data={chartData}
                margin={{ top: 4, right: 16, left: 0, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                <XAxis dataKey="time" tick={{ fontSize: 11, fill: chartColors.axis }} />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fontSize: 11, fill: chartColors.axis }}
                  tickFormatter={(v: number) => `${v}`}
                />
                <Tooltip
                  formatter={(v: number) => [`${v}`, "Avg confidence"]}
                  contentStyle={{
                    backgroundColor: "var(--card)",
                    borderColor: "var(--border)",
                    color: "var(--foreground)",
                    borderRadius: "0.5rem",
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="avg_confidence"
                  name="Avg confidence"
                  stroke={chartColors.success}
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
