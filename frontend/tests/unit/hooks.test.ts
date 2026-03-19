import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useStreamChat } from "@/hooks/useStreamChat";
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
