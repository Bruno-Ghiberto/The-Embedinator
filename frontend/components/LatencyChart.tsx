"use client";

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

// ─── LatencyChart (raw) ───────────────────────────────────────────────────────
// Imported via next/dynamic with { ssr: false } in observability/page.tsx

export function LatencyChart({ traces }: LatencyChartProps) {
  const data = buildLatencyData(traces);

  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold text-gray-700">
        Latency Distribution
      </h3>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
          <Tooltip
            formatter={(value: number) => [value, "Queries"]}
            labelFormatter={(label: string) => `Bucket: ${label}`}
          />
          <Bar dataKey="count" name="Queries" fill="#6366f1" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
