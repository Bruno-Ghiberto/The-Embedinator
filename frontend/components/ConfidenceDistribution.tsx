"use client";

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
  fill: string;
}

// Confidence is INTEGER 0-100
// green >= 70, yellow 40-69, red < 40
function buildConfidenceData(traces: QueryTrace[]): TierBucket[] {
  const withScore = traces.filter((t) => t.confidence_score !== null);

  return [
    {
      label: "High (≥70)",
      count: withScore.filter((t) => (t.confidence_score as number) >= 70).length,
      fill: "#22c55e",
    },
    {
      label: "Medium (40-69)",
      count: withScore.filter((t) => {
        const s = t.confidence_score as number;
        return s >= 40 && s < 70;
      }).length,
      fill: "#eab308",
    },
    {
      label: "Low (<40)",
      count: withScore.filter((t) => (t.confidence_score as number) < 40).length,
      fill: "#ef4444",
    },
  ];
}

// ─── ConfidenceDistribution (raw) ────────────────────────────────────────────
// Imported via next/dynamic with { ssr: false } in observability/page.tsx

export function ConfidenceDistribution({ traces }: ConfidenceDistributionProps) {
  const data = buildConfidenceData(traces);

  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold text-gray-700">
        Confidence Distribution
      </h3>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
          <Tooltip
            formatter={(value: number) => [value, "Queries"]}
            labelFormatter={(label: string) => `Tier: ${label}`}
          />
          <Bar dataKey="count" name="Queries" radius={[3, 3, 0, 0]}>
            {data.map((entry) => (
              <Cell key={entry.label} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
