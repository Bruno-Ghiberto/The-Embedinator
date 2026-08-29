/**
 * BUG-034 — silent health-lie window.
 *
 * The banner is not the defect. `fetchHealth` already handles a 503 correctly, and
 * StatusBanner re-renders immediately on provider state changes. The lie comes from
 * the polling cadence: while healthy the provider polled every 30s, so a healthy →
 * degraded transition stayed invisible for up to a full 30 seconds.
 *
 * The second half is BUG-035's 18s health-endpoint hang. That bug was deferred on the
 * explicit assumption that BUG-034 would "treat any non-200 or timeout as degraded";
 * without a request timeout here, a hung probe leaves SWR holding stale healthy data
 * with no error, and the banner stays green for the entire hang. So the timeout is
 * load-bearing for that deferral, not an extra.
 */
import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import React from "react";
import { render, screen, act } from "@testing-library/react";
import { SWRConfig } from "swr";
import {
  BackendStatusProvider,
  useBackendStatus,
} from "@/components/BackendStatusProvider";

const HEALTHY = { status: "healthy", services: [] };
const DEGRADED = {
  status: "degraded",
  services: [{ name: "qdrant", status: "error", error_message: "Unreachable" }],
};

/** Minimal Response stand-in — the provider only reads ok/status/json. */
function jsonResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

function StateProbe() {
  const { state } = useBackendStatus();
  return <span data-testid="state">{state}</span>;
}

/**
 * Each render gets its own SWR cache. Without an isolated provider the module-level
 * cache leaks the "/api/health" entry between tests and a later test starts with a
 * primed healthy value instead of a cold fetch.
 */
function renderProvider() {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <BackendStatusProvider>
        <StateProbe />
      </BackendStatusProvider>
    </SWRConfig>,
  );
}

/** Advance fake timers AND flush the promise chain SWR resolves on. */
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

function state() {
  return screen.getByTestId("state").textContent;
}

describe("BackendStatusProvider — BUG-034 detection latency", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  test("a healthy backend settles on ready", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, HEALTHY)));

    renderProvider();
    await advance(0);

    expect(state()).toBe("ready");
  });

  test("degradation surfaces within a single polling cycle (<=5s)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, HEALTHY));
    vi.stubGlobal("fetch", fetchMock);

    renderProvider();
    await advance(0);
    expect(state()).toBe("ready");

    // qdrant goes down: /api/health starts answering 503 "degraded".
    fetchMock.mockResolvedValue(jsonResponse(503, DEGRADED));
    await advance(5000);

    // Pre-fix the healthy cadence was 30_000ms, so nothing was re-fetched here at
    // all and the provider was still reporting a stale "ready".
    expect(state()).toBe("degraded");
  });

  test("the healthy poll actually re-requests within 5s", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, HEALTHY));
    vi.stubGlobal("fetch", fetchMock);

    renderProvider();
    await advance(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await advance(5000);

    expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  test("a hung probe degrades instead of holding a stale green", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, HEALTHY));
    vi.stubGlobal("fetch", fetchMock);

    renderProvider();
    await advance(0);
    expect(state()).toBe("ready");

    // BUG-035: the endpoint hangs. Settles only if the caller aborts it.
    fetchMock.mockImplementation(
      (_url: string, init?: { signal?: AbortSignal }) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        }),
    );

    await advance(5000); // fire the next poll
    await advance(5000); // give any request timeout room to elapse

    // Without an AbortController the request never settles, SWR keeps the last
    // healthy payload with no error, and this stays "ready" — the silent lie.
    expect(state()).toBe("unreachable");
  });

  test("a non-503 error response is not reported as ready (BUG-038)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, HEALTHY));
    vi.stubGlobal("fetch", fetchMock);

    renderProvider();
    await advance(0);
    expect(state()).toBe("ready");

    fetchMock.mockResolvedValue(jsonResponse(500, { detail: "boom" }));
    await advance(5000);

    expect(state()).toBe("unreachable");
  });

  test("recovery is detected within one cycle too", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(503, DEGRADED));
    vi.stubGlobal("fetch", fetchMock);

    renderProvider();
    await advance(0);
    expect(state()).toBe("degraded");

    fetchMock.mockResolvedValue(jsonResponse(200, HEALTHY));
    await advance(5000);

    expect(state()).toBe("ready");
  });
});
