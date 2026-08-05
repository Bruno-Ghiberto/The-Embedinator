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
import type { LatencyBucketStat } from "@/lib/types";

export interface LatencyChartProps {
  /**
   * Bucket counts from `/api/stats`, aggregated in SQL over every matching trace.
   * These used to be derived here from the current 20-row trace page, which made
   * the histogram describe one page rather than the query population (BUG-112).
   * The boundaries now live with their labels in the backend so the two cannot
   * drift apart.
   */
  buckets: LatencyBucketStat[];
}

function resolveCssVar(varName: string): string {
  if (typeof window === "undefined") return "#7c3aed";
  return getComputedStyle(document.documentElement).getPropertyValue(varName).trim() || "#7c3aed";
}

// ─── LatencyChart (raw) ───────────────────────────────────────────────────────
// Imported via next/dynamic with { ssr: false } in observability/page.tsx

export function LatencyChart({ buckets }: LatencyChartProps) {
  const data = buckets;

  const [colors, setColors] = useState({ bar: "#7c3aed", axis: "#6b52b5", grid: "#d1c4f5" });

  useEffect(() => {
    setColors({
      bar: resolveCssVar("--primary"),
      axis: resolveCssVar("--muted-foreground"),
      grid: resolveCssVar("--border"),
    });
  }, []);

  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold text-foreground">
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
              backgroundColor: "var(--card)",
              borderColor: "var(--border)",
              color: "var(--foreground)",
              borderRadius: "0.5rem",
            }}
          />
          <Bar dataKey="count" name="Queries" fill={colors.bar} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
