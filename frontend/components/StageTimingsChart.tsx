"use client";

import { useEffect, useState } from "react";
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

/**
 * A stage entry is either a graph-node record or a bare number. The research
 * accumulators (`research_orchestrator_ms`, `research_tools_ms` and their `_calls`
 * counters) are written straight into `stage_timings` as numbers, as siblings of the
 * `{duration_ms}` records — see research_nodes.py:139-140.
 */
export type StageTiming = number | { duration_ms: number; failed?: boolean };

export interface StageTimingsChartProps {
  timings: Record<string, StageTiming>;
}

interface StageDataPoint {
  stage: string;
  duration_ms: number;
  failed: boolean;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

// `*_calls` entries count invocations, not milliseconds. They were previously drawn
// as empty rows; plotting them at face value on a millisecond axis would replace one
// misreport with another, so they are excluded from a duration chart entirely.
const COUNTER_KEY = /_calls$/;

function toDataPoint(stage: string, timing: StageTiming): StageDataPoint | null {
  if (typeof timing === "number") {
    return Number.isFinite(timing)
      ? { stage, duration_ms: timing, failed: false }
      : null;
  }
  if (timing && typeof timing.duration_ms === "number" && Number.isFinite(timing.duration_ms)) {
    return { stage, duration_ms: timing.duration_ms, failed: timing.failed ?? false };
  }
  // Unreadable entry: omit it. An empty bar reads as "this stage took no time",
  // which is a stronger and falser claim than not charting it at all.
  return null;
}

export function buildChartData(
  timings: Record<string, StageTiming>,
): StageDataPoint[] {
  return Object.entries(timings)
    .filter(([stage]) => !COUNTER_KEY.test(stage))
    .map(([stage, timing]) => toDataPoint(stage, timing))
    .filter((point): point is StageDataPoint => point !== null);
}

// Stage color map — uses CSS variable values for theme compatibility.
// Keys are lowercase stage names; fallback to accent color.
const STAGE_COLOR_MAP: Record<string, string> = {
  retrieval: "var(--primary)",
  rerank: "var(--success)",
  compress: "var(--warning)",
  "meta-reasoning": "var(--chart-2)",
  inference: "var(--chart-4)",
};

const FILL_FAILED = "var(--destructive)";

function getStageColor(stage: string, failed: boolean): string {
  if (failed) return FILL_FAILED;
  return STAGE_COLOR_MAP[stage.toLowerCase()] ?? "var(--primary)";
}

// Resolve CSS variable to actual color value for recharts fill
function resolveCssVar(cssVar: string): string {
  if (typeof window === "undefined") return "#7c3aed";
  if (!cssVar.startsWith("var(")) return cssVar;
  const varName = cssVar.slice(4, -1).trim();
  return getComputedStyle(document.documentElement).getPropertyValue(varName).trim() || "#7c3aed";
}

// ─── StageTimingsChart ────────────────────────────────────────────────────────
// Imported via next/dynamic with { ssr: false } in TraceTable.tsx

export function StageTimingsChart({ timings }: StageTimingsChartProps) {
  const data = buildChartData(timings);

  // Resolve CSS vars to actual colors for recharts (which needs real color values)
  const [resolvedColors, setResolvedColors] = useState<Record<string, string>>({});

  useEffect(() => {
    const colors: Record<string, string> = {};
    for (const entry of data) {
      const cssVar = getStageColor(entry.stage, entry.failed);
      colors[`${entry.stage}-${entry.failed}`] = resolveCssVar(cssVar);
    }
    // Also resolve the axis label color
    colors["__axis"] = resolveCssVar("var(--muted-foreground)");
    colors["__grid"] = resolveCssVar("var(--border)");
    setResolvedColors(colors);
  }, [data]);

  const axisColor = resolvedColors["__axis"] || "#6b52b5";
  const gridColor = resolvedColors["__grid"] || "#d1c4f5";

  return (
    <div>
      <ResponsiveContainer width="100%" height={Math.max(120, data.length * 36)}>
        <BarChart
          layout="vertical"
          data={data}
          margin={{ top: 4, right: 24, left: 8, bottom: 4 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke={gridColor} />
          <XAxis
            type="number"
            dataKey="duration_ms"
            tick={{ fontSize: 11, fill: axisColor }}
            tickFormatter={(v: number) => `${v} ms`}
            label={{
              value: "Duration (ms)",
              position: "insideBottomRight",
              offset: -4,
              fontSize: 11,
              fill: axisColor,
            }}
          />
          <YAxis
            type="category"
            dataKey="stage"
            width={120}
            tick={{ fontSize: 11, fill: axisColor }}
          />
          <Tooltip
            formatter={(value: number) => [`${value} ms`, "Duration"]}
            labelFormatter={(label: string) => `Stage: ${label}`}
            contentStyle={{
              backgroundColor: "var(--card)",
              borderColor: "var(--border)",
              color: "var(--foreground)",
              borderRadius: "0.5rem",
            }}
          />
          <Bar dataKey="duration_ms" name="Duration" radius={[0, 3, 3, 0]}>
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={resolvedColors[`${entry.stage}-${entry.failed}`] || "#7c3aed"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
