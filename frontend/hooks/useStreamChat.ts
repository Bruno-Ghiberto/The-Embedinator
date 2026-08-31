"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { streamChat } from "@/lib/api";
import type { ChatMessage, ChatRequest, Citation, GroundednessData } from "@/lib/types";

// BUG-074 Branch T / BUG-123: client-side idle watchdog. Measured basis (#4435):
// a cold first LLM call took 31.1 s and the longest warm gap between frames was
// 14.8 s (qwen2.5:7b). Must stay strictly below experimental.proxyTimeout in
// next.config.ts (600 000 ms) so the client, not the proxy, ends a stalled
// stream. Exported only so next-config.test.ts can pin that invariant.
export const STREAM_IDLE_TIMEOUT_MS = 120_000;

export function useStreamChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // The watchdog follows the newest stream: Retry on an older error bubble can
  // start one while another is live. A superseded stream keeps writing into its
  // own bubble but must neither arm nor disarm the shared timer.
  const watchedStreamIdRef = useRef<string | null>(null);

  const clearIdleTimer = useCallback(() => {
    if (idleTimerRef.current !== null) {
      clearTimeout(idleTimerRef.current);
      idleTimerRef.current = null;
    }
  }, []);

  const sendMessage = useCallback(
    (request: ChatRequest) => {
      // A previous stream may still be pending; from here on it is unwatched.
      clearIdleTimer();

      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: request.message,
        isStreaming: false,
      };
      const assistantId = crypto.randomUUID();
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        isStreaming: true,
      };
      watchedStreamIdRef.current = assistantId;
      const ownsWatchdog = () => watchedStreamIdRef.current === assistantId;

      const failStream = (message: string, code: string, traceId?: string) => {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantId
              ? {
                  ...msg,
                  content: msg.content || message,
                  isStreaming: false,
                  isError: true,
                  errorCode: code,
                  traceId,
                }
              : msg,
          ),
        );
        setIsStreaming(false);
      };

      const onIdleExpiry = () => {
        idleTimerRef.current = null;
        // Only the watched stream can arm, so controllerRef holds this stream's
        // controller. Abort before marking the bubble: api.ts swallows the
        // AbortError, so no callback can touch this message afterwards.
        controllerRef.current?.abort();
        controllerRef.current = null;
        failStream(
          `The response stalled: no data for ${STREAM_IDLE_TIMEOUT_MS / 1000}s.`,
          "STREAM_STALLED",
        );
      };

      const armIdleTimer = () => {
        if (!ownsWatchdog()) return;
        clearIdleTimer();
        idleTimerRef.current = setTimeout(onIdleExpiry, STREAM_IDLE_TIMEOUT_MS);
      };

      const disarmIdleTimer = () => {
        if (ownsWatchdog()) clearIdleTimer();
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsStreaming(true);
      // Armed before the request leaves: the BUG-123 hang sits before the first byte.
      armIdleTimer();

      const requestWithSession: ChatRequest = {
        ...request,
        session_id: sessionIdRef.current,
      };

      const controller = streamChat(requestWithSession, {
        onSession: (sessionId) => {
          armIdleTimer();
          sessionIdRef.current = sessionId;
        },
        onStatus: () => {
          armIdleTimer();
        },
        onToken: (text) => {
          armIdleTimer();
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? { ...msg, content: msg.content + text }
                : msg,
            ),
          );
        },
        onClarification: (question) => {
          disarmIdleTimer();
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? { ...msg, clarification: question, isStreaming: false }
                : msg,
            ),
          );
          setIsStreaming(false);
        },
        onCitation: (citations: Citation[]) => {
          armIdleTimer();
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId ? { ...msg, citations } : msg,
            ),
          );
        },
        onMetaReasoning: () => {
          armIdleTimer();
        },
        onConfidence: (score: number) => {
          armIdleTimer();
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId ? { ...msg, confidence: score } : msg,
            ),
          );
        },
        onGroundedness: (data: GroundednessData) => {
          armIdleTimer();
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId ? { ...msg, groundedness: data } : msg,
            ),
          );
        },
        onDone: (_latencyMs: number, traceId: string) => {
          disarmIdleTimer();
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? { ...msg, isStreaming: false, traceId }
                : msg,
            ),
          );
          setIsStreaming(false);
        },
        onError: (message: string, code: string, traceId?: string) => {
          disarmIdleTimer();
          failStream(message, code, traceId);
        },
      });

      controllerRef.current = controller;
    },
    [clearIdleTimer],
  );

  const abort = useCallback(() => {
    clearIdleTimer();
    controllerRef.current?.abort();
    controllerRef.current = null;
    setIsStreaming(false);
  }, [clearIdleTimer]);

  useEffect(() => {
    return () => {
      clearIdleTimer();
      controllerRef.current?.abort();
    };
  }, [clearIdleTimer]);

  return { messages, isStreaming, sendMessage, abort, setMessages };
}
