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
  Cell,
} from "recharts";
import type { QueryTrace } from "@/lib/types";

export interface ConfidenceDistributionProps {
  traces: QueryTrace[];
}

interface TierBucket {
  label: string;
  count: number;
  colorVar: string;
}

function resolveCssVar(varName: string): string {
  if (typeof window === "undefined") return "#7c3aed";
  return getComputedStyle(document.documentElement).getPropertyValue(varName).trim() || "#7c3aed";
}

// Confidence is INTEGER 0-100
// green >= 70, yellow 40-69, red < 40
function buildConfidenceData(traces: QueryTrace[]): TierBucket[] {
  const withScore = traces.filter((t) => t.confidence_score !== null);

  return [
    {
      label: "High (\u226570)",
      count: withScore.filter((t) => (t.confidence_score as number) >= 70).length,
      colorVar: "--color-success",
    },
    {
      label: "Medium (40-69)",
      count: withScore.filter((t) => {
        const s = t.confidence_score as number;
        return s >= 40 && s < 70;
      }).length,
      colorVar: "--color-warning",
    },
    {
      label: "Low (<40)",
      count: withScore.filter((t) => (t.confidence_score as number) < 40).length,
      colorVar: "--color-destructive",
    },
  ];
}

// ─── ConfidenceDistribution (raw) ────────────────────────────────────────────
// Imported via next/dynamic with { ssr: false } in observability/page.tsx

export function ConfidenceDistribution({ traces }: ConfidenceDistributionProps) {
  const data = buildConfidenceData(traces);

  const [resolved, setResolved] = useState<Record<string, string>>({});

  useEffect(() => {
    const colors: Record<string, string> = {};
    for (const d of data) {
      colors[d.colorVar] = resolveCssVar(d.colorVar);
    }
    colors["--color-text-muted"] = resolveCssVar("--color-text-muted");
    colors["--color-border"] = resolveCssVar("--color-border");
    setResolved(colors);
  }, [data]);

  const axisColor = resolved["--color-text-muted"] || "#6b52b5";
  const gridColor = resolved["--color-border"] || "#d1c4f5";

  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold text-[var(--color-text-primary)]">
        Confidence Distribution
      </h3>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
          <XAxis dataKey="label" tick={{ fontSize: 12, fill: axisColor }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: axisColor }} />
          <Tooltip
            formatter={(value: number) => [value, "Queries"]}
            labelFormatter={(label: string) => `Tier: ${label}`}
            contentStyle={{
              backgroundColor: "var(--color-surface)",
              borderColor: "var(--color-border)",
              color: "var(--color-text-primary)",
              borderRadius: "0.5rem",
            }}
          />
          <Bar dataKey="count" name="Queries" radius={[3, 3, 0, 0]}>
            {data.map((entry) => (
              <Cell key={entry.label} fill={resolved[entry.colorVar] || "#7c3aed"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
