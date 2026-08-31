/**
 * BUG-074 Branch T / BUG-123 — the idle watchdog against the REAL @/lib/api.
 *
 * hooks.test.ts mocks streamChat, so it cannot show what api.ts does once the
 * watchdog aborts the controller. Here the real streamChat runs against a
 * stubbed fetch whose 200 response body never emits and errors with an
 * AbortError when the request signal aborts — the shape undici produces. The
 * only terminal error must be the hook's STREAM_STALLED: api.ts's AbortError
 * filters stay silent, so the code is never overwritten by STREAM_ERROR or
 * NETWORK_ERROR.
 */
import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useStreamChat, STREAM_IDLE_TIMEOUT_MS } from "@/hooks/useStreamChat";

/** fetch stub: a 200 NDJSON response whose body stays silent until the signal aborts. */
function makeSilentStreamFetch() {
  return vi.fn((_url: string, init: RequestInit) => {
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        (init.signal as AbortSignal).addEventListener("abort", () => {
          controller.error(new DOMException("aborted", "AbortError"));
        });
      },
    });
    return Promise.resolve(
      new Response(stream, {
        status: 200,
        headers: { "Content-Type": "application/x-ndjson" },
      }),
    );
  });
}

describe("useStreamChat — idle watchdog with the real api.ts", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  test("idle watchdog with the real api.ts: expiry yields exactly one terminal error (STREAM_STALLED) and api.ts's AbortError catch stays silent", async () => {
    const fetchMock = makeSilentStreamFetch();
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useStreamChat());

    act(() => {
      result.current.sendMessage({ message: "hello", collection_ids: ["col-1"] });
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(STREAM_IDLE_TIMEOUT_MS);
    });
    // Let the rejected reader.read() settle through api.ts's catch blocks.
    await act(async () => {});

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect((fetchMock.mock.calls[0][1].signal as AbortSignal).aborted).toBe(true);
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[1].errorCode).toBe("STREAM_STALLED");
    expect(result.current.messages[1].content).toMatch(/stall/i);
    expect(result.current.isStreaming).toBe(false);
  });
});
