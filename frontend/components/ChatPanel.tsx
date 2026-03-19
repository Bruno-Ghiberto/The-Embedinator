"use client";

import React, { useEffect, useRef } from "react";
import type { ChatMessage } from "@/lib/types";
import CitationTooltip from "./CitationTooltip";
import ConfidenceIndicator from "./ConfidenceIndicator";

interface ChatPanelProps {
  messages: ChatMessage[];
  isStreaming: boolean;
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`max-w-[80%] rounded-lg px-4 py-3 ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-neutral-100 text-neutral-900 dark:bg-neutral-800 dark:text-neutral-100"
        }`}
      >
        {message.clarification ? (
          <div className="space-y-2">
            <p className="text-sm italic">{message.clarification}</p>
          </div>
        ) : (
          <p className="whitespace-pre-wrap text-sm">{message.content}</p>
        )}

        {message.role === "assistant" &&
          message.citations &&
          message.citations.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-1 border-t border-neutral-200 pt-2 dark:border-neutral-700">
              {message.citations.map((citation, idx) => (
                <CitationTooltip
                  key={citation.passage_id}
                  citation={citation}
                  index={idx + 1}
                />
              ))}
            </div>
          ) : null}

        {message.role === "assistant" &&
          !message.isStreaming &&
          message.confidence !== undefined ? (
            <div className="mt-2 flex items-center gap-1 border-t border-neutral-200 pt-2 dark:border-neutral-700">
              <ConfidenceIndicator score={message.confidence} />
              <span className="text-xs text-neutral-500 dark:text-neutral-400">
                Confidence
              </span>
            </div>
          ) : null}

        {message.isStreaming ? (
          <span className="mt-1 inline-block h-4 w-1 animate-pulse bg-neutral-400 dark:bg-neutral-500" />
        ) : null}
      </div>
    </div>
  );
}

const MemoizedMessageBubble = React.memo(MessageBubble);

function ChatPanelInner({ messages, isStreaming }: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);

  // Passive scroll listener to track if user has scrolled up
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      shouldAutoScrollRef.current =
        scrollHeight - scrollTop - clientHeight < 100;
    };

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => container.removeEventListener("scroll", handleScroll);
  }, []);

  // Auto-scroll to bottom on new message or streaming content
  useEffect(() => {
    if (shouldAutoScrollRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto p-4"
    >
      {messages.length === 0 ? (
        <div className="flex h-full items-center justify-center">
          <p className="text-neutral-400 dark:text-neutral-500">
            Select a collection and ask a question to get started.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {messages.map((msg) => (
            <MemoizedMessageBubble key={msg.id} message={msg} />
          ))}
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}

const ChatPanel = React.memo(ChatPanelInner);
export default ChatPanel;
