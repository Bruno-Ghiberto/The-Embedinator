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
import { StatusBanner } from "@/components/StatusBanner";

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
function renderProvider(children: React.ReactNode = <StateProbe />) {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <BackendStatusProvider>{children}</BackendStatusProvider>
    </SWRConfig>,
  );
}

/** Same isolated provider, but wrapping the real banner the user actually sees. */
function renderWithBanner() {
  return renderProvider(<StatusBanner />);
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

/**
 * BUG-124 — the UI stays locked on "Connecting to backend..." for minutes after the
 * backend is healthy again.
 *
 * `refreshInterval` only governs while SWR holds no latched error. A DOWN backend is
 * an error (the Next proxy answers 5xx, or `fetch` rejects outright), and SWR then
 * suspends the refresh loop and re-probes on its default exponential backoff instead.
 * `retryCount` starts at 1, so with the 0.5 pin below the delays are 5s x 2^n and the
 * retries land at +10s, +30s, +70s, +150s, +310s after the first failure. After a ~190s
 * outage the next scheduled probe is therefore ~120s after recovery, so the recovered
 * backend goes unnoticed for that long — exactly the 197s lockout measured in the
 * browser on 2026-09-02.
 *
 * `Math.random` is pinned to 0.5 so SWR's jitter (`~~((Math.random() + 0.5) * ...)`)
 * resolves to x1.0 and those retry instants are deterministic. That is harness
 * determinism, not an assertion about the mechanism: every assertion below is the
 * user-visible symptom.
 */
describe("BackendStatusProvider — BUG-124 post-recovery lockout", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(Math, "random").mockReturnValue(0.5);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  test("a backend that comes back after a long outage is seen within one poll interval (live page)", async () => {
    // Fails today: SWR suspends refreshInterval while `error` is latched and re-probes on an
    // exponential backoff (next retry ~120 s after recovery here). Passes once the provider
    // supplies an onErrorRetry that re-probes every POLL_INTERVAL_MS.
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, HEALTHY));
    vi.stubGlobal("fetch", fetchMock);
    renderProvider();
    await advance(0);
    expect(state()).toBe("ready");

    // Backend container dies; the Next proxy answers 502 until it is back.
    fetchMock.mockResolvedValue(jsonResponse(502, { error: "Failed to proxy" }));
    await advance(5000);
    expect(state()).toBe("unreachable");
    for (let elapsed = 0; elapsed < 190_000; elapsed += 5000) await advance(5000);
    expect(state()).toBe("unreachable");

    // Backend healthy again: the UI must follow within ONE configured interval.
    fetchMock.mockResolvedValue(jsonResponse(200, HEALTHY));
    await advance(5000);
    expect(state()).toBe("ready");
  });

  test("a page loaded while the backend was down recovers within one poll interval (cold load)", async () => {
    // Same mechanism as above, from a cold start with a rejected fetch (connection refused).
    // Fails today: the very first probe latches the error, so the provider never enters the
    // refreshInterval loop at all and only the backoff schedule ever re-probes.
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);
    renderProvider();
    await advance(0);
    expect(state()).toBe("unreachable");
    for (let elapsed = 0; elapsed < 190_000; elapsed += 5000) await advance(5000);
    expect(state()).toBe("unreachable");

    fetchMock.mockResolvedValue(jsonResponse(200, HEALTHY));
    await advance(5000);
    expect(state()).toBe("ready");
  });

  test("the status banner reports the recovered backend within one poll interval", async () => {
    // The user-visible symptom: banner stuck on "Connecting to backend..." after recovery.
    // Fails today for the same reason as the first test; passes once a POLL_INTERVAL_MS
    // error-retry cadence replaces SWR's default exponential backoff.
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, HEALTHY));
    vi.stubGlobal("fetch", fetchMock);
    renderWithBanner(); // provider + real <StatusBanner />
    await advance(0);

    fetchMock.mockResolvedValue(jsonResponse(502, { error: "Failed to proxy" }));
    await advance(5000);
    expect(screen.getByRole("status")).toHaveTextContent("Connecting to backend...");
    for (let elapsed = 0; elapsed < 190_000; elapsed += 5000) await advance(5000);

    fetchMock.mockResolvedValue(jsonResponse(200, HEALTHY));
    await advance(5000);
    expect(screen.getByRole("status")).toHaveTextContent("Backend connected");
  });

  test("a backend that recovers after a run of hung probes is seen within one interval plus the probe timeout", async () => {
    // The contract's third error flavour: not a 5xx and not a rejected fetch, but a probe
    // that never answers and is killed by the provider's own PROBE_TIMEOUT_MS. The bound is
    // POLL_INTERVAL_MS + PROBE_TIMEOUT_MS (8000 ms), not POLL_INTERVAL_MS: SWR schedules the
    // next probe from the COMPLETION of the previous one, and a hung probe completes only
    // when it is aborted at 3 s. Fails on the unmodified tree (default exponential backoff);
    // passes with the POLL_INTERVAL_MS error-retry cadence.
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, HEALTHY));
    vi.stubGlobal("fetch", fetchMock);
    renderProvider();
    await advance(0);
    expect(state()).toBe("ready");

    // /api/health stops answering entirely; only the caller's abort ends the request.
    fetchMock.mockImplementation(
      (_url: string, init?: { signal?: AbortSignal }) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        }),
    );
    for (let elapsed = 0; elapsed < 190_000; elapsed += 5000) await advance(5000);
    expect(state()).toBe("unreachable");

    fetchMock.mockResolvedValue(jsonResponse(200, HEALTHY));
    await advance(8000);
    expect(state()).toBe("ready");
  });

  test("a downed backend is re-probed at the healthy cadence", async () => {
    // The three tests above each assert a single instant, so a retry cadence of 6 s, 8 s or
    // 500 ms would satisfy them. The contract is "one cadence in every state", and the probe
    // count over a fixed window is its observable form. Across the (60 s, 120 s] slice of the
    // outage a 5 s cadence makes 12 probes; a 6 s mutant makes 10, an 8 s mutant 7-8, a
    // 500 ms mutant 120, and the unmodified tree (exponential backoff) makes 1.
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, HEALTHY));
    vi.stubGlobal("fetch", fetchMock);
    renderProvider();
    await advance(0);
    expect(state()).toBe("ready");

    fetchMock.mockResolvedValue(jsonResponse(502, { error: "Failed to proxy" }));
    for (let elapsed = 0; elapsed < 60_000; elapsed += 5000) await advance(5000);
    expect(state()).toBe("unreachable");
    const callsAt60s = fetchMock.mock.calls.length;

    for (let elapsed = 60_000; elapsed < 120_000; elapsed += 5000) await advance(5000);
    const probesInWindow = fetchMock.mock.calls.length - callsAt60s;

    expect(probesInWindow).toBeGreaterThanOrEqual(11);
    expect(probesInWindow).toBeLessThanOrEqual(13);
  });
});
