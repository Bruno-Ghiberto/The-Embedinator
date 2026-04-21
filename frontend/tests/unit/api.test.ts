import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import {
  streamChat,
  updateSettings,
  createCollection,
  ApiError,
} from "@/lib/api";
import type { StreamChatCallbacks, ChatRequest } from "@/lib/types";

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Create a mock Response with an NDJSON body (raw JSON lines, no "data:" prefix). */
function makeNdjsonResponse(events: object[]): Response {
  const body = events.map((e) => JSON.stringify(e)).join("\n") + "\n";
  return new Response(body, {
    status: 200,
    headers: { "Content-Type": "application/x-ndjson" },
  });
}

/** Wait for all pending microtasks + one macrotask so async callbacks flush. */
const flush = () =>
  new Promise<void>((resolve) => setTimeout(resolve, 50));

/** Build a full set of vi.fn() callbacks. */
function makeCallbacks() {
  const onSession = vi.fn();
  const onStatus = vi.fn();
  const onToken = vi.fn();
  const onClarification = vi.fn();
  const onCitation = vi.fn();
  const onMetaReasoning = vi.fn();
  const onConfidence = vi.fn();
  const onGroundedness = vi.fn();
  const onDone = vi.fn();
  const onError = vi.fn();

  const callbacks: StreamChatCallbacks = {
    onSession,
    onStatus,
    onToken,
    onClarification,
    onCitation,
    onMetaReasoning,
    onConfidence,
    onGroundedness,
    onDone,
    onError,
  };

  return {
    callbacks,
    onSession,
    onStatus,
    onToken,
    onClarification,
    onCitation,
    onMetaReasoning,
    onConfidence,
    onGroundedness,
    onDone,
    onError,
  };
}

const BASE_REQUEST: ChatRequest = {
  message: "test question",
  collection_ids: ["col-1"],
};

const MOCK_CITATION = {
  passage_id: "p1",
  document_id: "d1",
  document_name: "report.pdf",
  start_offset: 0,
  end_offset: 50,
  text: "Some relevant passage text",
  relevance_score: 0.95,
  source_removed: false,
};

// ─── streamChat — NDJSON event parsing ────────────────────────────────────────

describe("streamChat — NDJSON event parsing (all 10 types)", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test("session event: calls onSession with session_id", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      makeNdjsonResponse([
        { type: "session", session_id: "sess-abc-123" },
        { type: "done", latency_ms: 100, trace_id: "t1" },
      ]),
    );

    const { callbacks, onSession } = makeCallbacks();
    streamChat(BASE_REQUEST, callbacks);
    await flush();

    expect(onSession).toHaveBeenCalledWith("sess-abc-123");
  });

  test("status event: calls onStatus with node name", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      makeNdjsonResponse([
        { type: "status", node: "research_graph" },
        { type: "done", latency_ms: 100, trace_id: "t1" },
      ]),
    );

    const { callbacks, onStatus } = makeCallbacks();
    streamChat(BASE_REQUEST, callbacks);
    await flush();

    expect(onStatus).toHaveBeenCalledWith("research_graph");
  });

  test("chunk event: calls onToken with event.text (NOT event.content)", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      makeNdjsonResponse([
        { type: "chunk", text: "Hello world" },
        { type: "done", latency_ms: 100, trace_id: "t1" },
      ]),
    );

    const { callbacks, onToken } = makeCallbacks();
    streamChat(BASE_REQUEST, callbacks);
    await flush();

    // Verifies the field is "text", not "content"
    expect(onToken).toHaveBeenCalledTimes(1);
    expect(onToken).toHaveBeenCalledWith("Hello world");
  });

  test("clarification event: calls onClarification; onDone is NOT called (no done follows)", async () => {
    // Backend closes stream after clarification — no done event sent
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      makeNdjsonResponse([
        { type: "clarification", question: "What did you mean by that?" },
      ]),
    );

    const { callbacks, onClarification, onDone } = makeCallbacks();
    streamChat(BASE_REQUEST, callbacks);
    await flush();

    expect(onClarification).toHaveBeenCalledWith("What did you mean by that?");
    expect(onDone).not.toHaveBeenCalled();
  });

  test("citation event: calls onCitation; source_removed field preserved in Citation", async () => {
    const citationWithRemovedSource = {
      ...MOCK_CITATION,
      source_removed: true,
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      makeNdjsonResponse([
        { type: "citation", citations: [citationWithRemovedSource] },
        { type: "done", latency_ms: 100, trace_id: "t1" },
      ]),
    );

    const { callbacks, onCitation } = makeCallbacks();
    streamChat(BASE_REQUEST, callbacks);
    await flush();

    expect(onCitation).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ source_removed: true }),
      ]),
    );
  });

  test("meta_reasoning event: calls onMetaReasoning with strategies_attempted", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      makeNdjsonResponse([
        {
          type: "meta_reasoning",
          strategies_attempted: ["WIDEN_SEARCH", "CHANGE_COLLECTION"],
        },
        { type: "done", latency_ms: 100, trace_id: "t1" },
      ]),
    );

    const { callbacks, onMetaReasoning } = makeCallbacks();
    streamChat(BASE_REQUEST, callbacks);
    await flush();

    expect(onMetaReasoning).toHaveBeenCalledWith([
      "WIDEN_SEARCH",
      "CHANGE_COLLECTION",
    ]);
  });

  test("confidence event: calls onConfidence with INTEGER score 0-100", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      makeNdjsonResponse([
        { type: "confidence", score: 72 },
        { type: "done", latency_ms: 100, trace_id: "t1" },
      ]),
    );

    const { callbacks, onConfidence } = makeCallbacks();
    streamChat(BASE_REQUEST, callbacks);
    await flush();

    // Score is integer 0-100, not float 0.0-1.0
    expect(onConfidence).toHaveBeenCalledWith(72);
  });

  test("groundedness event: calls onGroundedness with all required fields", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      makeNdjsonResponse([
        {
          type: "groundedness",
          overall_grounded: true,
          supported: 4,
          unsupported: 1,
          contradicted: 0,
        },
        { type: "done", latency_ms: 100, trace_id: "t1" },
      ]),
    );

    const { callbacks, onGroundedness } = makeCallbacks();
    streamChat(BASE_REQUEST, callbacks);
    await flush();

    expect(onGroundedness).toHaveBeenCalledWith(
      expect.objectContaining({
        overall_grounded: true,
        supported: 4,
        unsupported: 1,
        contradicted: 0,
      }),
    );
  });

  test("done event: calls onDone with latency_ms and trace_id", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      makeNdjsonResponse([
        { type: "done", latency_ms: 350, trace_id: "trace-xyz-789" },
      ]),
    );

    const { callbacks, onDone } = makeCallbacks();
    streamChat(BASE_REQUEST, callbacks);
    await flush();

    expect(onDone).toHaveBeenCalledWith(350, "trace-xyz-789");
  });

  test("error event (NDJSON): calls onError with message, code, trace_id", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      makeNdjsonResponse([
        {
          type: "error",
          message: "Circuit breaker open",
          code: "CIRCUIT_OPEN",
          trace_id: "t-err-001",
        },
      ]),
    );

    const { callbacks, onError } = makeCallbacks();
    streamChat(BASE_REQUEST, callbacks);
    await flush();

    expect(onError).toHaveBeenCalledWith(
      "Circuit breaker open",
      "CIRCUIT_OPEN",
      "t-err-001",
    );
  });

  test("HTTP error response: onError called with body error.code and error.message", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: {
            code: "SERVICE_UNAVAILABLE",
            message: "Backend is temporarily unavailable",
          },
          trace_id: "t-503",
        }),
        { status: 503 },
      ),
    );

    const { callbacks, onError } = makeCallbacks();
    streamChat(BASE_REQUEST, callbacks);
    await flush();

    expect(onError).toHaveBeenCalledWith(
      "Backend is temporarily unavailable",
      "SERVICE_UNAVAILABLE",
      "t-503",
    );
  });

  test("multiple chunk events accumulate in onToken calls (no stale closure)", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      makeNdjsonResponse([
        { type: "chunk", text: "Hello" },
        { type: "chunk", text: " world" },
        { type: "chunk", text: "!" },
        { type: "done", latency_ms: 100, trace_id: "t1" },
      ]),
    );

    const { callbacks, onToken } = makeCallbacks();
    streamChat(BASE_REQUEST, callbacks);
    await flush();

    expect(onToken).toHaveBeenCalledTimes(3);
    expect(onToken).toHaveBeenNthCalledWith(1, "Hello");
    expect(onToken).toHaveBeenNthCalledWith(2, " world");
    expect(onToken).toHaveBeenNthCalledWith(3, "!");
  });
});

// ─── updateSettings — HTTP method ────────────────────────────────────────────

describe("updateSettings — sends PUT, not PATCH", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test("method is PUT", async () => {
    const mockSettings = {
      default_llm_model: "qwen2.5:7b",
      default_embed_model: "nomic-embed-text",
      confidence_threshold: 60,
      groundedness_check_enabled: false,
      citation_alignment_threshold: 0.7,
      parent_chunk_size: 2000,
      child_chunk_size: 500,
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response(JSON.stringify(mockSettings), { status: 200 }),
    );

    await updateSettings({ confidence_threshold: 75 });

    const [, opts] = (
      global.fetch as ReturnType<typeof vi.fn>
    ).mock.calls[0] as [string, RequestInit];

    expect(opts.method).toBe("PUT");
  });

  test("method is NOT PATCH", async () => {
    const mockSettings = {
      default_llm_model: "qwen2.5:7b",
      default_embed_model: "nomic-embed-text",
      confidence_threshold: 60,
      groundedness_check_enabled: false,
      citation_alignment_threshold: 0.7,
      parent_chunk_size: 2000,
      child_chunk_size: 500,
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response(JSON.stringify(mockSettings), { status: 200 }),
    );

    await updateSettings({ confidence_threshold: 75 });

    const [, opts] = (
      global.fetch as ReturnType<typeof vi.fn>
    ).mock.calls[0] as [string, RequestInit];

    expect(opts.method).not.toBe("PATCH");
  });
});

// ─── ApiError — error body parsing ───────────────────────────────────────────

describe("ApiError — parsed from { error: { code, message }, trace_id } body", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test("thrown ApiError carries status, code, message, traceId", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: {
            code: "COLLECTION_NAME_CONFLICT",
            message: "A collection with this name already exists.",
          },
          trace_id: "t-409-conflict",
        }),
        { status: 409 },
      ),
    );

    let caught: ApiError | null = null;
    try {
      await createCollection({ name: "duplicate-name" });
    } catch (err) {
      if (err instanceof ApiError) {
        caught = err;
      }
    }

    expect(caught).not.toBeNull();
    expect(caught?.status).toBe(409);
    expect(caught?.code).toBe("COLLECTION_NAME_CONFLICT");
    expect(caught?.message).toBe(
      "A collection with this name already exists.",
    );
    expect(caught?.traceId).toBe("t-409-conflict");
  });

  test("ApiError is instance of Error", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: { code: "NOT_FOUND", message: "Resource not found" },
          trace_id: "t-404",
        }),
        { status: 404 },
      ),
    );

    let caught: unknown = null;
    try {
      await createCollection({ name: "missing" });
    } catch (err) {
      caught = err;
    }

    expect(caught).toBeInstanceOf(ApiError);
    expect(caught).toBeInstanceOf(Error);
  });
});

// ─── source_removed preserved in Citation ────────────────────────────────────

describe("Citation.source_removed field preservation", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test("source_removed: true is preserved in onCitation callback", async () => {
    const citationSourceRemoved = { ...MOCK_CITATION, source_removed: true };
    const citationNotRemoved = { ...MOCK_CITATION, passage_id: "p2", source_removed: false };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      makeNdjsonResponse([
        {
          type: "citation",
          citations: [citationSourceRemoved, citationNotRemoved],
        },
        { type: "done", latency_ms: 100, trace_id: "t1" },
      ]),
    );

    const { callbacks, onCitation } = makeCallbacks();
    streamChat(BASE_REQUEST, callbacks);
    await flush();

    const passedCitations = onCitation.mock.calls[0][0];
    expect(passedCitations[0].source_removed).toBe(true);
    expect(passedCitations[1].source_removed).toBe(false);
  });
});
