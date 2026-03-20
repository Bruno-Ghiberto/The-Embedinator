"use client";

import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { QueryTrace } from "@/lib/types";

export interface LatencyChartProps {
  traces: QueryTrace[];
}

interface LatencyBucket {
  label: string;
  min: number;
  max: number;
}

const LATENCY_BUCKETS: LatencyBucket[] = [
  { label: "0-100ms", min: 0, max: 100 },
  { label: "100-500ms", min: 100, max: 500 },
  { label: "500ms-1s", min: 500, max: 1000 },
  { label: "1-2s", min: 1000, max: 2000 },
  { label: "2s+", min: 2000, max: Infinity },
];

function buildLatencyData(traces: QueryTrace[]) {
  return LATENCY_BUCKETS.map((bucket) => ({
    label: bucket.label,
    count: traces.filter(
      (t) => t.latency_ms >= bucket.min && t.latency_ms < bucket.max,
    ).length,
  }));
}

function resolveCssVar(varName: string): string {
  if (typeof window === "undefined") return "#7c3aed";
  return getComputedStyle(document.documentElement).getPropertyValue(varName).trim() || "#7c3aed";
}

// ─── LatencyChart (raw) ───────────────────────────────────────────────────────
// Imported via next/dynamic with { ssr: false } in observability/page.tsx

export function LatencyChart({ traces }: LatencyChartProps) {
  const data = buildLatencyData(traces);

  const [colors, setColors] = useState({ bar: "#7c3aed", axis: "#6b52b5", grid: "#d1c4f5" });

  useEffect(() => {
    setColors({
      bar: resolveCssVar("--color-accent"),
      axis: resolveCssVar("--color-text-muted"),
      grid: resolveCssVar("--color-border"),
    });
  }, []);

  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold text-[var(--color-text-primary)]">
        Latency Distribution
      </h3>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
          <XAxis dataKey="label" tick={{ fontSize: 12, fill: colors.axis }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: colors.axis }} />
          <Tooltip
            formatter={(value: number) => [value, "Queries"]}
            labelFormatter={(label: string) => `Bucket: ${label}`}
            contentStyle={{
              backgroundColor: "var(--color-surface)",
              borderColor: "var(--color-border)",
              color: "var(--color-text-primary)",
              borderRadius: "0.5rem",
            }}
          />
          <Bar dataKey="count" name="Queries" fill={colors.bar} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
