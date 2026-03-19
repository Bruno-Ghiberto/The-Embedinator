"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { streamChat } from "@/lib/api";
import type { ChatMessage, ChatRequest, Citation, GroundednessData } from "@/lib/types";

export function useStreamChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  const sendMessage = useCallback(
    (request: ChatRequest) => {
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

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsStreaming(true);

      const requestWithSession: ChatRequest = {
        ...request,
        session_id: sessionIdRef.current,
      };

      const controller = streamChat(requestWithSession, {
        onSession: (sessionId) => {
          sessionIdRef.current = sessionId;
        },
        onStatus: () => {},
        onToken: (text) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? { ...msg, content: msg.content + text }
                : msg,
            ),
          );
        },
        onClarification: (question) => {
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
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId ? { ...msg, citations } : msg,
            ),
          );
        },
        onMetaReasoning: () => {},
        onConfidence: (score: number) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId ? { ...msg, confidence: score } : msg,
            ),
          );
        },
        onGroundedness: (data: GroundednessData) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId ? { ...msg, groundedness: data } : msg,
            ),
          );
        },
        onDone: (_latencyMs: number, traceId: string) => {
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
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? {
                    ...msg,
                    content: msg.content || `Error: ${message} (${code})`,
                    isStreaming: false,
                    traceId,
                  }
                : msg,
            ),
          );
          setIsStreaming(false);
        },
      });

      controllerRef.current = controller;
    },
    [],
  );

  const abort = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    setIsStreaming(false);
  }, []);

  useEffect(() => {
    return () => {
      controllerRef.current?.abort();
    };
  }, []);

  return { messages, isStreaming, sendMessage, abort, setMessages };
}
