/**
 * BUG-074 Branch E + BUG-119 — the chat page has exactly one stream owner.
 *
 * These render the real `app/chat/page.tsx` with the real `useStreamChat` and
 * the real `lib/api.ts`; only `fetch`, `next/navigation` and the page's data
 * hooks/providers are stubbed. Nothing about the stream itself is mocked, so
 * the assertions are on what a user sees: the composer's Stop control, the red
 * error bubble's Retry affordance, and how many requests actually left.
 *
 * - BUG-074 Branch E: a stream body that closes with no terminal NDJSON frame
 *   must not leave the page stuck in its streaming state.
 * - BUG-119: while a stream is in flight, Retry on an earlier error bubble must
 *   not start a second one.
 */
import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { Collection } from "@/lib/types";

// ─── Mocks (minimal, in-file; hoisted above the imports by vitest) ────────────

vi.mock("next/navigation", () => {
  // Stable identities: the page keeps router/searchParams in useCallback and
  // useEffect dependency lists.
  const router = {
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    prefetch: vi.fn(),
  };
  const params = new URLSearchParams("collections=col-1");
  return {
    useRouter: () => router,
    usePathname: () => "/chat",
    useSearchParams: () => params,
  };
});

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => React.createElement("a", { href }, children),
}));

vi.mock("@/hooks/useCollections", () => {
  const collections: Collection[] = [
    {
      id: "col-1",
      name: "Docs",
      description: null,
      embedding_model: "nomic-embed-text",
      chunk_profile: "default",
      document_count: 3,
      created_at: "2026-01-01T00:00:00Z",
    },
  ];
  const mutate = vi.fn();
  return {
    useCollections: () => ({
      collections,
      isLoading: false,
      isError: undefined,
      mutate,
    }),
  };
});

vi.mock("@/hooks/useModels", () => {
  const none: never[] = [];
  return {
    useModels: () => ({
      llmModels: none,
      embedModels: none,
      isLoading: false,
      isError: undefined,
    }),
  };
});

vi.mock("@/hooks/useChatHistory", () => {
  const history = {
    sessions: [],
    activeSession: null,
    isLoading: false,
    createSession: vi.fn(() => "hist-1"),
    loadSession: vi.fn(),
    saveMessage: vi.fn(),
    syncMessages: vi.fn(),
    deleteSession: vi.fn(),
    renameSession: vi.fn(),
    searchSessions: vi.fn(() => []),
  };
  return { useChatHistory: () => history };
});

vi.mock("@/components/BackendStatusProvider", () => {
  // ChatInput refuses to submit unless the backend reads as "ready".
  const value = { state: "ready", services: [] };
  return {
    useBackendStatus: () => value,
    BackendStatusProvider: ({ children }: { children: React.ReactNode }) =>
      children,
  };
});

import ChatPage from "@/app/chat/page";

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** A real 200 NDJSON Response whose body ends naturally after these events. */
function ndjsonResponse(events: object[]): Response {
  const body = events.map((e) => JSON.stringify(e)).join("\n") + "\n";
  return new Response(body, {
    status: 200,
    headers: { "Content-Type": "application/x-ndjson" },
  });
}

/** A real 200 response whose body never closes until the request is aborted. */
function openStreamResponse(init: RequestInit): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      (init.signal as AbortSignal).addEventListener("abort", () => {
        controller.error(new DOMException("aborted", "AbortError"));
      });
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { "Content-Type": "application/x-ndjson" },
  });
}

/** Type into the composer and press its send button. */
function submit(text: string) {
  fireEvent.change(screen.getByRole("textbox"), { target: { value: text } });
  fireEvent.click(screen.getByLabelText("Send message"));
}

/** Let the detached fetch/reader promise chain settle (streamChat returns no promise). */
const settle = () => new Promise<void>((resolve) => setTimeout(resolve, 50));

describe("chat page — single stream owner (BUG-074 Branch E, BUG-119)", () => {
  beforeEach(() => {
    // jsdom implements neither; ChatPanel and ScrollToBottom call both.
    Element.prototype.scrollIntoView = vi.fn();
    Element.prototype.scrollTo = vi.fn();
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
        takeRecords() {
          return [];
        }
      },
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  // RED (BUG-074 Branch E). Fails on the unmodified tree: api.ts's reader
  // breaks on EOF without a terminal callback, so isStreaming never flips back
  // and the composer keeps showing Stop forever.
  // Would fail again if the reader stopped reporting an un-terminated stream,
  // or if the hook stopped clearing isStreaming on that report.
  test("a stream that closes without a terminal frame does not leave the page streaming", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        // One chunk, then the body closes: no done / error / clarification.
        ndjsonResponse([{ type: "chunk", text: "partial answer" }]),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<ChatPage />);
    submit("what is in this collection?");

    // The turn really started: the composer swapped Send for Stop.
    await screen.findByLabelText("Stop generation");

    // Symptom: the page must leave its streaming state and surface an error.
    await waitFor(
      () => {
        expect(screen.queryByLabelText("Stop generation")).toBeNull();
      },
      { timeout: 2000 },
    );
    expect(screen.getByLabelText("Send message")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /retry/i }),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  // RED (BUG-119). Failed before the fix: page.tsx passed onRetry unconditionally,
  // so a Retry button rendered on the earlier error bubble during the live stream
  // and clicking it sent a third request.
  // This test proves exactly one thing — the prop gate at the <ChatPanel> call
  // site (`onRetry={isStreaming ? undefined : handleRetry}`). Remove it and
  // ChatPanel.tsx:195 renders Retry again on the error bubble, the click below
  // fires, and fetch is called a third time. It does NOT prove anything about a
  // guard inside handleRetry: while streaming there is no button, so the handler
  // is never reached and its body is not exercised here.
  test("Retry cannot start a second stream while one is in flight", async () => {
    const fetchMock = vi.fn((_url: string, init: RequestInit) =>
      Promise.resolve(openStreamResponse(init)),
    );
    // First turn only: a server error frame, so the bubble becomes retryable.
    fetchMock.mockImplementationOnce(() =>
      Promise.resolve(
        ndjsonResponse([
          {
            type: "error",
            message: "Retrieval circuit is open",
            code: "CIRCUIT_OPEN",
            trace_id: "t-1",
          },
        ]),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<ChatPage />);

    // 1. First turn fails and settles into a retryable error bubble.
    submit("first question");
    await screen.findByText("Retrieval circuit is open");
    await waitFor(() => {
      expect(screen.getByLabelText("Send message")).toBeInTheDocument();
    });

    // 2. Second turn starts and stays open.
    submit("second question");
    await screen.findByLabelText("Stop generation");
    expect(fetchMock).toHaveBeenCalledTimes(2);

    // 3. Activate Retry on the EARLIER error bubble while that stream is live.
    //    Conditional on purpose: the assertion is that no second request leaves,
    //    not that a button is or is not rendered. With the prop gate in place
    //    there is nothing to click; remove the gate and there is, and the click
    //    below sends the third request that fails the count.
    const retry = screen.queryByRole("button", { name: /retry/i });
    if (retry) fireEvent.click(retry);
    await settle();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    // The earlier message is untouched and the live stream still owns the page.
    expect(screen.getByText("Retrieval circuit is open")).toBeInTheDocument();
    expect(screen.getByLabelText("Stop generation")).toBeInTheDocument();
  });
});
