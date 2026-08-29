"use client";

import useSWR from "swr";
import { getStats } from "@/lib/api";
import type { SystemStats } from "@/lib/types";

interface UseStatsParams {
  session_id?: string;
}

/**
 * System statistics, including the latency and confidence distributions that the
 * Observability charts render. The distributions are aggregated server-side over
 * every matching trace, so they describe the population rather than the current
 * page (BUG-112).
 *
 * `session_id` is part of the cache key: without it, switching the trace table's
 * session filter would keep serving the previous session's distribution.
 */
export function useStats(params?: UseStatsParams) {
  const key = params?.session_id
    ? `/api/stats?session_id=${params.session_id}`
    : "/api/stats";

  const { data, error, mutate } = useSWR<SystemStats>(key, () =>
    getStats(params),
  );

  return {
    stats: data,
    isLoading: !error && !data,
    isError: error,
    mutate,
  };
}
