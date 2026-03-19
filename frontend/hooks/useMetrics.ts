"use client";

import useSWR from "swr";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Types ────────────────────────────────────────────────────────────────────

interface MetricsBucket {
  timestamp: string;
  query_count: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  avg_confidence: number;
  meta_reasoning_count: number;
  error_count: number;
}

interface CircuitBreakerSnapshot {
  state: "closed" | "open" | "unknown";
  failure_count: number;
}

interface MetricsResponse {
  window: string;
  bucket_size: string;
  buckets: MetricsBucket[];
  circuit_breakers: Record<string, CircuitBreakerSnapshot>;
  active_ingestion_jobs: number;
}

// ─── Fetcher ──────────────────────────────────────────────────────────────────

async function fetchMetrics(url: string): Promise<MetricsResponse> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch metrics: ${res.statusText}`);
  }
  return res.json();
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useMetrics(window: "1h" | "24h" | "7d" = "24h") {
  const { data, error, isLoading } = useSWR<MetricsResponse>(
    `${API_BASE}/api/metrics?window=${window}`,
    fetchMetrics,
    { refreshInterval: 30_000 },
  );
  return { data, error, isLoading };
}
