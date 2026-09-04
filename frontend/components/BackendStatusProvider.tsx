"use client";

import React, { createContext, useContext, useMemo } from "react";
import useSWR, { type SWRConfiguration } from "swr";
import type {
  BackendStatus,
  BackendHealthResponse,
  BackendHealthServiceStatus,
} from "@/lib/types";

interface BackendStatusContextValue {
  state: BackendStatus;
  services: BackendHealthServiceStatus[];
}

const BackendStatusContext = createContext<BackendStatusContextValue>({
  state: "unreachable",
  services: [],
});

// BUG-034: one cadence for every state. The previous adaptive schedule polled every
// 30s while healthy, so a healthy -> degraded transition stayed invisible for up to
// 30 seconds and the banner kept claiming "Backend connected" through a stream of
// 503s. Detection latency while healthy is the whole bug, and a healthy backend is
// exactly the state you are in when degradation starts.
const POLL_INTERVAL_MS = 5000;

// BUG-035: /api/health probes SQLite, Qdrant and Ollama and has been observed hanging
// ~18s. An un-aborted hang never settles, so SWR holds the last healthy payload with
// no error and the UI shows a stale green for the whole hang. Bounding the request
// converts that silence into an honest "unreachable".
const PROBE_TIMEOUT_MS = 3000;

// BUG-124: while `error` is latched SWR suspends `refreshInterval` polling and hands the
// schedule to `onErrorRetry`, whose default is exponential backoff with jitter
// (5 s x 2^n, n <= 8). A backend that was down for ~3 min is then re-probed only every
// 2-8 min, so the banner and composer stay locked long after /api/health is healthy
// again (measured: 197 s on 2026-09-02). A health poller has one cadence in every state.
const retryAtPollInterval: NonNullable<SWRConfiguration["onErrorRetry"]> = (
  _err,
  _key,
  _config,
  revalidate,
  opts,
) => {
  setTimeout(() => revalidate(opts), POLL_INTERVAL_MS);
};

async function fetchHealth(url: string): Promise<BackendHealthResponse> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (res.status === 503) {
      // Backend reachable but degraded — parse body if available
      try {
        return await res.json();
      } catch {
        return { status: "degraded", services: [] };
      }
    }
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    return res.json();
  } finally {
    clearTimeout(timer);
  }
}

export function BackendStatusProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const { data, error } = useSWR<BackendHealthResponse>(
    "/api/health",
    fetchHealth,
    {
      refreshInterval: POLL_INTERVAL_MS,
      revalidateOnFocus: false,
      onErrorRetry: retryAtPollInterval,
    },
  );

  const state = useMemo((): BackendStatus => {
    if (error || !data) return "unreachable";
    if (data.status === "healthy") return "ready";
    return "degraded";
  }, [data, error]);

  const value = useMemo(
    () => ({ state, services: data?.services ?? [] }),
    [state, data],
  );

  return (
    <BackendStatusContext.Provider value={value}>
      {children}
    </BackendStatusContext.Provider>
  );
}

export function useBackendStatus(): BackendStatusContextValue {
  return useContext(BackendStatusContext);
}
