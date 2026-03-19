"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ResponsiveContainer,
} from "recharts";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface StageTimingsChartProps {
  timings: Record<string, { duration_ms: number; failed?: boolean }>;
}

interface StageDataPoint {
  stage: string;
  duration_ms: number;
  failed: boolean;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function buildChartData(
  timings: Record<string, { duration_ms: number; failed?: boolean }>,
): StageDataPoint[] {
  return Object.entries(timings).map(([stage, timing]) => ({
    stage,
    duration_ms: timing.duration_ms,
    failed: timing.failed ?? false,
  }));
}

const FILL_SUCCESS = "#3b82f6";
const FILL_FAILED = "#ef4444";

// ─── StageTimingsChart ────────────────────────────────────────────────────────
// Imported via next/dynamic with { ssr: false } in TraceTable.tsx

export function StageTimingsChart({ timings }: StageTimingsChartProps) {
  const data = buildChartData(timings);

  return (
    <div>
      <ResponsiveContainer width="100%" height={Math.max(120, data.length * 36)}>
        <BarChart
          layout="vertical"
          data={data}
          margin={{ top: 4, right: 24, left: 8, bottom: 4 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis
            type="number"
            dataKey="duration_ms"
            tick={{ fontSize: 11 }}
            tickFormatter={(v: number) => `${v} ms`}
            label={{
              value: "Duration (ms)",
              position: "insideBottomRight",
              offset: -4,
              fontSize: 11,
              fill: "#6b7280",
            }}
          />
          <YAxis
            type="category"
            dataKey="stage"
            width={120}
            tick={{ fontSize: 11 }}
          />
          <Tooltip
            formatter={(value: number) => [`${value} ms`, "Duration"]}
            labelFormatter={(label: string) => `Stage: ${label}`}
          />
          <Bar dataKey="duration_ms" name="Duration" radius={[0, 3, 3, 0]}>
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.failed ? FILL_FAILED : FILL_SUCCESS}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
