"use client";

import React, { createContext, useContext, useMemo, useState, useEffect } from "react";
import useSWR from "swr";
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

async function fetchHealth(url: string): Promise<BackendHealthResponse> {
  const res = await fetch(url);
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
}

export function BackendStatusProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  // Track current status to drive adaptive polling intervals
  const [refreshInterval, setRefreshInterval] = useState<number>(5000);

  const { data, error } = useSWR<BackendHealthResponse>(
    "/api/health",
    fetchHealth,
    { refreshInterval, revalidateOnFocus: false },
  );

  const state = useMemo((): BackendStatus => {
    if (error || !data) return "unreachable";
    if (data.status === "healthy") return "ready";
    return "degraded";
  }, [data, error]);

  // Update polling interval based on derived status
  useEffect(() => {
    if (state === "unreachable") setRefreshInterval(5000);
    else if (state === "degraded") setRefreshInterval(10000);
    else setRefreshInterval(30000);
  }, [state]);

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
