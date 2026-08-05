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
import type { ConfidenceBucketStat } from "@/lib/types";

export interface ConfidenceDistributionProps {
  /**
   * Tier counts from `/api/stats`, aggregated in SQL over every scored trace.
   * Deriving them here from the current 20-row page made the panel read
   * High-dominant while the population averaged Low (BUG-112).
   */
  buckets: ConfidenceBucketStat[];
}

function resolveCssVar(varName: string): string {
  if (typeof window === "undefined") return "#7c3aed";
  return getComputedStyle(document.documentElement).getPropertyValue(varName).trim() || "#7c3aed";
}

// Confidence is INTEGER 0-100 \u2014 green >= 70, yellow 40-69, red < 40. The tiers are
// keyed by name rather than by position so a reordered response cannot paint "Low"
// with the "High" colour.
const TIER_COLOR_VARS: Record<ConfidenceBucketStat["tier"], string> = {
  high: "--success",
  medium: "--warning",
  low: "--destructive",
};

export function colorVarForTier(tier: ConfidenceBucketStat["tier"]): string {
  return TIER_COLOR_VARS[tier];
}

// ─── ConfidenceDistribution (raw) ────────────────────────────────────────────
// Imported via next/dynamic with { ssr: false } in observability/page.tsx

export function ConfidenceDistribution({
  buckets,
}: ConfidenceDistributionProps) {
  const data = buckets;

  const [resolved, setResolved] = useState<Record<string, string>>({});

  useEffect(() => {
    const colors: Record<string, string> = {};
    for (const d of data) {
      colors[colorVarForTier(d.tier)] = resolveCssVar(colorVarForTier(d.tier));
    }
    colors["--muted-foreground"] = resolveCssVar("--muted-foreground");
    colors["--border"] = resolveCssVar("--border");
    setResolved(colors);
  }, [data]);

  const axisColor = resolved["--muted-foreground"] || "#6b52b5";
  const gridColor = resolved["--border"] || "#d1c4f5";

  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold text-foreground">
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
              backgroundColor: "var(--card)",
              borderColor: "var(--border)",
              color: "var(--foreground)",
              borderRadius: "0.5rem",
            }}
          />
          <Bar dataKey="count" name="Queries" radius={[3, 3, 0, 0]}>
            {data.map((entry) => (
              <Cell
                key={entry.tier}
                fill={resolved[colorVarForTier(entry.tier)] || "#7c3aed"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
