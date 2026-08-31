import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useStreamChat, STREAM_IDLE_TIMEOUT_MS } from "@/hooks/useStreamChat";
import { streamChat } from "@/lib/api";
import type { StreamChatCallbacks } from "@/lib/types";

// ─── Mock @/lib/api ───────────────────────────────────────────────────────────
// Capture the callbacks passed to streamChat so we can invoke them manually.

let capturedCallbacks: StreamChatCallbacks | null = null;
const mockAbortController = { abort: vi.fn() };

vi.mock("@/lib/api", () => ({
  streamChat: vi.fn((request: unknown, callbacks: StreamChatCallbacks) => {
    capturedCallbacks = callbacks;
    return mockAbortController;
  }),
}));

// ─── Helpers ──────────────────────────────────────────────────────────────────

const BASE_REQUEST = {
  message: "hello",
  collection_ids: ["col-1"],
};

function setup() {
  capturedCallbacks = null;
  const hook = renderHook(() => useStreamChat());
  return hook;
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("useStreamChat — isStreaming state management", () => {
  afterEach(() => {
    capturedCallbacks = null;
    mockAbortController.abort.mockClear();
  });

  test("isStreaming starts as false", () => {
    const { result } = setup();
    expect(result.current.isStreaming).toBe(false);
  });

  test("isStreaming becomes true after sendMessage", () => {
    const { result } = setup();

    act(() => {
      result.current.sendMessage(BASE_REQUEST);
    });

    expect(result.current.isStreaming).toBe(true);
  });

  test("isStreaming released on done event", () => {
    const { result } = setup();

    act(() => {
      result.current.sendMessage(BASE_REQUEST);
    });

    expect(result.current.isStreaming).toBe(true);

    act(() => {
      capturedCallbacks!.onDone(300, "trace-done-123");
    });

    expect(result.current.isStreaming).toBe(false);
  });

  test("isStreaming released on error event", () => {
    const { result } = setup();

    act(() => {
      result.current.sendMessage(BASE_REQUEST);
    });

    expect(result.current.isStreaming).toBe(true);

    act(() => {
      capturedCallbacks!.onError("Something went wrong", "SERVICE_ERROR");
    });

    expect(result.current.isStreaming).toBe(false);
  });

  test("isStreaming released on clarification event (no done follows)", () => {
    const { result } = setup();

    act(() => {
      result.current.sendMessage(BASE_REQUEST);
    });

    expect(result.current.isStreaming).toBe(true);

    // Clarification ends the stream without a done event
    act(() => {
      capturedCallbacks!.onClarification?.("Can you clarify your question?");
    });

    expect(result.current.isStreaming).toBe(false);
  });
});

describe("useStreamChat — message array management", () => {
  test("sendMessage appends user + assistant messages to array", () => {
    const { result } = setup();

    expect(result.current.messages).toHaveLength(0);

    act(() => {
      result.current.sendMessage(BASE_REQUEST);
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0].role).toBe("user");
    expect(result.current.messages[0].content).toBe("hello");
    expect(result.current.messages[1].role).toBe("assistant");
    expect(result.current.messages[1].content).toBe("");
    expect(result.current.messages[1].isStreaming).toBe(true);
  });

  test("onToken accumulates text in assistant message", () => {
    const { result } = setup();

    act(() => {
      result.current.sendMessage(BASE_REQUEST);
    });

    act(() => {
      capturedCallbacks!.onToken("Hello");
    });

    act(() => {
      capturedCallbacks!.onToken(" World");
    });

    const assistantMsg = result.current.messages.find(
      (m) => m.role === "assistant",
    );
    expect(assistantMsg?.content).toBe("Hello World");
  });

  test("functional setState prevents stale closure on rapid simultaneous chunks", () => {
    const { result } = setup();

    act(() => {
      result.current.sendMessage(BASE_REQUEST);
    });

    // Dispatch multiple tokens in the same act() to test for stale closure issues
    act(() => {
      capturedCallbacks!.onToken("A");
      capturedCallbacks!.onToken("B");
      capturedCallbacks!.onToken("C");
    });

    const assistantMsg = result.current.messages.find(
      (m) => m.role === "assistant",
    );
    // All tokens must be accumulated — functional setState ensures no closure stale reads
    expect(assistantMsg?.content).toBe("ABC");
  });

  test("onDone marks assistant message as not streaming and sets traceId", () => {
    const { result } = setup();

    act(() => {
      result.current.sendMessage(BASE_REQUEST);
    });

    act(() => {
      capturedCallbacks!.onDone(500, "trace-final-456");
    });

    const assistantMsg = result.current.messages.find(
      (m) => m.role === "assistant",
    );
    expect(assistantMsg?.isStreaming).toBe(false);
    expect(assistantMsg?.traceId).toBe("trace-final-456");
  });

  test("onClarification sets clarification field on assistant message and releases isStreaming", () => {
    const { result } = setup();

    act(() => {
      result.current.sendMessage(BASE_REQUEST);
    });

    act(() => {
      capturedCallbacks!.onClarification?.("Please be more specific.");
    });

    const assistantMsg = result.current.messages.find(
      (m) => m.role === "assistant",
    );
    expect(assistantMsg?.clarification).toBe("Please be more specific.");
    expect(assistantMsg?.isStreaming).toBe(false);
    expect(result.current.isStreaming).toBe(false);
  });

  test("second sendMessage appends another user+assistant pair", () => {
    const { result } = setup();

    act(() => {
      result.current.sendMessage({ ...BASE_REQUEST, message: "first" });
    });

    act(() => {
      capturedCallbacks!.onDone(100, "t1");
    });

    act(() => {
      result.current.sendMessage({ ...BASE_REQUEST, message: "second" });
    });

    expect(result.current.messages).toHaveLength(4);
    expect(result.current.messages[0].content).toBe("first");
    expect(result.current.messages[2].content).toBe("second");
  });
});

describe("useStreamChat — abort / cleanup", () => {
  test("abort() sets isStreaming to false", () => {
    const { result } = setup();

    act(() => {
      result.current.sendMessage(BASE_REQUEST);
    });

    expect(result.current.isStreaming).toBe(true);

    act(() => {
      result.current.abort();
    });

    expect(result.current.isStreaming).toBe(false);
  });

  test("abort() calls AbortController.abort", () => {
    const { result } = setup();

    act(() => {
      result.current.sendMessage(BASE_REQUEST);
    });

    act(() => {
      result.current.abort();
    });

    expect(mockAbortController.abort).toHaveBeenCalled();
  });
});

describe("useStreamChat — idle watchdog (BUG-074 Branch T / BUG-123)", () => {
  const T = STREAM_IDLE_TIMEOUT_MS;

  /** Advance the fake clock inside act so the hook's state updates flush. */
  function advance(ms: number) {
    act(() => {
      vi.advanceTimersByTime(ms);
    });
  }

  beforeEach(() => {
    vi.useFakeTimers();
    // Auto-cleanup unmounts after afterEach ran, so the previous test's
    // unmount abort leaks into the shared spy. Count from zero.
    mockAbortController.abort.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    capturedCallbacks = null;
    mockAbortController.abort.mockClear();
  });

  test("idle watchdog: STREAM_IDLE_TIMEOUT_MS of silence aborts the controller, marks the bubble STREAM_STALLED and releases isStreaming", () => {
    const { result } = setup();

    act(() => {
      result.current.sendMessage(BASE_REQUEST);
    });

    // One millisecond short of the deadline nothing has happened yet.
    advance(T - 1);
    expect(mockAbortController.abort).not.toHaveBeenCalled();
    expect(result.current.isStreaming).toBe(true);

    advance(1);
    expect(mockAbortController.abort).toHaveBeenCalledTimes(1);
    expect(result.current.isStreaming).toBe(false);

    const assistantMsg = result.current.messages[1];
    expect(assistantMsg.isError).toBe(true);
    expect(assistantMsg.isStreaming).toBe(false);
    expect(assistantMsg.errorCode).toBe("STREAM_STALLED");
    expect(assistantMsg.content).toMatch(/stall/i);
  });

  // Every frame that proves the backend is alive must push the deadline back.
  // onStatus is load-bearing: it is the per-node frame emitted while the model
  // warms up, and the hook used to wire it as a no-op.
  const PROGRESS_FRAMES: Array<[string, (cb: StreamChatCallbacks) => void]> = [
    ["onSession", (cb) => cb.onSession?.("s")],
    ["onStatus", (cb) => cb.onStatus?.("retrieve")],
    ["onToken", (cb) => cb.onToken("x")],
    ["onCitation", (cb) => cb.onCitation([])],
    ["onMetaReasoning", (cb) => cb.onMetaReasoning?.([])],
    ["onConfidence", (cb) => cb.onConfidence(80)],
    [
      "onGroundedness",
      (cb) =>
        cb.onGroundedness?.({
          overall_grounded: true,
          supported: 1,
          unsupported: 0,
          contradicted: 0,
        }),
    ],
  ];

  test.each(PROGRESS_FRAMES)(
    "idle watchdog: every progress frame resets the timer (%s)",
    (_frame, fire) => {
      const { result } = setup();

      act(() => {
        result.current.sendMessage(BASE_REQUEST);
      });

      advance(T - 1);
      act(() => {
        fire(capturedCallbacks!);
      });

      // The original deadline passes without a stall...
      advance(T - 1);
      expect(result.current.isStreaming).toBe(true);
      expect(result.current.messages[1].isError).toBeFalsy();
      expect(mockAbortController.abort).not.toHaveBeenCalled();

      // ...and the reset deadline still fires.
      advance(1);
      expect(mockAbortController.abort).toHaveBeenCalledTimes(1);
      expect(result.current.messages[1].errorCode).toBe("STREAM_STALLED");
    },
  );

  // Terminal frames end the turn themselves; a stale timer must not fire
  // afterwards and rewrite a real outcome as a stall.
  const TERMINAL_FRAMES: Array<
    [string, (cb: StreamChatCallbacks) => void, string | undefined]
  > = [
    ["onDone", (cb) => cb.onDone(1, "t"), undefined],
    ["onError", (cb) => cb.onError("boom", "SERVICE_ERROR"), "SERVICE_ERROR"],
    ["onClarification", (cb) => cb.onClarification?.("which?"), undefined],
  ];

  test.each(TERMINAL_FRAMES)(
    "idle watchdog: a terminal frame disarms the timer and is never overwritten by STREAM_STALLED (%s)",
    (_frame, fire, expectedCode) => {
      const { result } = setup();

      act(() => {
        result.current.sendMessage(BASE_REQUEST);
      });
      act(() => {
        fire(capturedCallbacks!);
      });

      advance(2 * T);
      expect(mockAbortController.abort).not.toHaveBeenCalled();
      expect(result.current.isStreaming).toBe(false);

      const assistantMsg = result.current.messages[1];
      expect(assistantMsg.errorCode).toBe(expectedCode);
      expect(Boolean(assistantMsg.isError)).toBe(expectedCode !== undefined);
    },
  );

  test("idle watchdog: abort() disarms the timer (no phantom stall after a user Stop)", () => {
    const { result } = setup();

    act(() => {
      result.current.sendMessage(BASE_REQUEST);
    });
    act(() => {
      result.current.abort();
    });

    advance(2 * T);
    // abort() nulls controllerRef, so the count alone cannot see a stale timer;
    // the bubble staying unmarked is what proves the timer was disarmed.
    expect(mockAbortController.abort).toHaveBeenCalledTimes(1);
    expect(result.current.messages[1].isError).toBeFalsy();
    expect(result.current.isStreaming).toBe(false);
  });

  test("idle watchdog: unmount disarms the timer (no second abort from a stale timer)", () => {
    const { result, unmount } = setup();

    act(() => {
      result.current.sendMessage(BASE_REQUEST);
    });
    unmount();

    advance(2 * T);
    // Only the unmount cleanup reached the controller; a live timer would abort again.
    expect(mockAbortController.abort).toHaveBeenCalledTimes(1);
  });
});

// Retry on an older error bubble (page.tsx handleRetry is not gated on
// isStreaming) starts a second stream while one is live. The watchdog follows
// the newest stream; the superseded one keeps writing into its own bubble but
// must neither arm nor disarm the shared timer.
describe("useStreamChat — idle watchdog with overlapping streams", () => {
  const T = STREAM_IDLE_TIMEOUT_MS;

  type Stream = {
    callbacks: StreamChatCallbacks;
    controller: { abort: ReturnType<typeof vi.fn> };
  };
  const streams: Stream[] = [];
  const sharedStreamChat = vi.mocked(streamChat).getMockImplementation();

  function advance(ms: number) {
    act(() => {
      vi.advanceTimersByTime(ms);
    });
  }

  /** Start two streams back to back and return them oldest first. */
  function setupOverlap() {
    const { result } = setup();
    act(() => {
      result.current.sendMessage({ ...BASE_REQUEST, message: "first" });
    });
    act(() => {
      result.current.sendMessage({ ...BASE_REQUEST, message: "second" });
    });
    const [older, newer] = streams;
    return { result, older, newer };
  }

  beforeEach(() => {
    vi.useFakeTimers();
    streams.length = 0;
    // One controller per call so the two streams can be told apart.
    vi.mocked(streamChat).mockImplementation((_request, callbacks) => {
      const controller = { abort: vi.fn() };
      streams.push({ callbacks, controller });
      return controller as unknown as AbortController;
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.mocked(streamChat).mockImplementation(sharedStreamChat!);
  });

  test("idle watchdog: an older stream's terminal frame does not disarm the newer stream's watchdog", () => {
    const { result, older, newer } = setupOverlap();

    act(() => {
      newer.callbacks.onSession?.("s");
    });
    act(() => {
      older.callbacks.onDone(1, "trace-older");
    });

    // The older bubble closed normally...
    expect(result.current.messages[1].isStreaming).toBe(false);
    expect(result.current.messages[1].isError).toBeFalsy();

    // ...and the newer stream still expires on its own deadline.
    advance(T);
    expect(newer.controller.abort).toHaveBeenCalledTimes(1);
    expect(older.controller.abort).not.toHaveBeenCalled();
    expect(result.current.messages[3].errorCode).toBe("STREAM_STALLED");
    expect(result.current.messages[3].isStreaming).toBe(false);
  });

  test("idle watchdog: an older stream's progress frame neither re-arms nor hijacks the newer stream's watchdog", () => {
    const { result, older, newer } = setupOverlap();

    advance(T - 1);
    act(() => {
      older.callbacks.onToken("x");
    });

    // The newer deadline is unchanged and its expiry aborts the newer stream.
    advance(1);
    expect(newer.controller.abort).toHaveBeenCalledTimes(1);
    expect(older.controller.abort).not.toHaveBeenCalled();
    expect(result.current.messages[3].errorCode).toBe("STREAM_STALLED");
    expect(result.current.messages[1].content).toBe("x");
    expect(result.current.messages[1].isError).toBeFalsy();

    // Nothing is left armed for the older closure to fire later.
    advance(2 * T);
    expect(vi.getTimerCount()).toBe(0);
    expect(older.controller.abort).not.toHaveBeenCalled();
    expect(result.current.messages[1].isError).toBeFalsy();
  });
});
