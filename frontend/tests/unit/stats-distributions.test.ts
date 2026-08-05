/**
 * BUG-112 — "Query Analytics" described one page of 20, not the population.
 *
 * Both distribution charts were a client-side re-slice of the current `useTraces`
 * page (`ObservabilityClient.tsx` PAGE_LIMIT=20), so the panel read High-dominant
 * (8/8/4) while `avg_confidence` across all 1008 traces was 31.1 — Low. Paging the
 * table silently changed the "analytics".
 *
 * The counts now come from `/api/stats`, aggregated in SQL over every row. That
 * moves one risk to the client: the trace table has a session filter, and stats
 * fetched without it would replace "this page" with "every session" — a different
 * lie. So `session_id` has to reach the request, and it has to be part of the SWR
 * cache key, or switching filters serves the previous session's distribution.
 */
import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { SWRConfig } from "swr";
import { createElement, type ReactNode } from "react";
import { getStats } from "@/lib/api";
import { useStats } from "@/hooks/useStats";
import { colorVarForTier } from "@/components/ConfidenceDistribution";

const STATS_BODY = {
  total_collections: 2,
  total_documents: 4,
  total_chunks: 300,
  total_queries: 1008,
  avg_confidence: 31.1,
  avg_latency_ms: 1500,
  meta_reasoning_rate: 0.15,
  latency_buckets: [
    { label: "0-100ms", count: 12 },
    { label: "100-500ms", count: 40 },
    { label: "500ms-1s", count: 100 },
    { label: "1-2s", count: 300 },
    { label: "2s+", count: 556 },
  ],
  confidence_buckets: [
    { tier: "high", label: "High (≥70)", count: 20 },
    { tier: "medium", label: "Medium (40-69)", count: 40 },
    { tier: "low", label: "Low (<40)", count: 948 },
  ],
};

function mockStatsResponse() {
  (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
    new Response(JSON.stringify(STATS_BODY), { status: 200 }),
  );
}

function requestedUrls(): string[] {
  return (global.fetch as ReturnType<typeof vi.fn>).mock.calls.map(
    (c) => c[0] as string,
  );
}

function wrapper({ children }: { children: ReactNode }) {
  return createElement(
    SWRConfig,
    { value: { provider: () => new Map(), dedupingInterval: 0 } },
    children,
  );
}

describe("getStats — session filter reaches the request", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    mockStatsResponse();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test("without a filter it aggregates every session", async () => {
    await getStats();

    expect(requestedUrls()[0]).toMatch(/\/api\/stats$/);
  });

  test("a session filter is forwarded as a query parameter", async () => {
    await getStats({ session_id: "sess-42" });

    expect(requestedUrls()[0]).toMatch(/\/api\/stats\?session_id=sess-42$/);
  });

  test("an absent filter does not leak an undefined parameter", async () => {
    await getStats({});

    expect(requestedUrls()[0]).not.toContain("session_id");
  });
});

describe("ConfidenceDistribution — tiers keep their semantic colour", () => {
  // The tier ordering now comes from the backend. If the colour lookup drifted to
  // positional indexing, a reordered response would paint "Low" green — the same
  // class of lie BUG-112 was filed for.
  test("each tier maps to its own colour variable", () => {
    expect(colorVarForTier("high")).toBe("--success");
    expect(colorVarForTier("medium")).toBe("--warning");
    expect(colorVarForTier("low")).toBe("--destructive");
  });
});

describe("useStats — the session filter is part of the cache key", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    mockStatsResponse();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test("exposes the distributions from /api/stats", async () => {
    const { result } = renderHook(() => useStats(), { wrapper });

    await waitFor(() => expect(result.current.stats).toBeDefined());
    expect(result.current.stats?.confidence_buckets[2]).toEqual({
      tier: "low",
      label: "Low (<40)",
      count: 948,
    });
  });

  test("changing the session filter refetches instead of serving the old one", async () => {
    const { result, rerender } = renderHook(
      ({ sessionId }: { sessionId?: string }) =>
        useStats({ session_id: sessionId }),
      { wrapper, initialProps: { sessionId: "sess-a" } },
    );

    await waitFor(() => expect(result.current.stats).toBeDefined());
    rerender({ sessionId: "sess-b" });
    await waitFor(() => expect(requestedUrls().length).toBe(2));

    expect(requestedUrls()[0]).toMatch(/session_id=sess-a$/);
    expect(requestedUrls()[1]).toMatch(/session_id=sess-b$/);
  });
});
