"use client";

import useSWR from "swr";
import { getTraces } from "@/lib/api";
import type { QueryTrace } from "@/lib/types";

interface UseTracesParams {
  session_id?: string;
  collection_id?: string;
  min_confidence?: number;
  max_confidence?: number;
  limit?: number;
  offset?: number;
}

export function useTraces(params?: UseTracesParams) {
  const key = params
    ? `/api/traces?${JSON.stringify(params)}`
    : "/api/traces";

  const { data, error, mutate } = useSWR<{
    traces: QueryTrace[];
    total: number;
    limit: number;
    offset: number;
  }>(key, () => getTraces(params));

  return {
    traces: data?.traces,
    total: data?.total ?? 0,
    limit: data?.limit ?? 20,
    offset: data?.offset ?? 0,
    isLoading: !error && !data,
    isError: error,
    mutate,
  };
}
