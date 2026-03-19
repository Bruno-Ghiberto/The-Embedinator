"use client";

import React, { useState, useCallback, useRef } from "react";

interface ChatInputProps {
  isStreaming: boolean;
  selectedCollections: string[];
  onSubmit: (message: string) => void;
}

function ChatInputInner({
  isStreaming,
  selectedCollections,
  onSubmit,
}: ChatInputProps) {
  const [message, setMessage] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const canSend =
    !isStreaming && message.trim().length > 0 && selectedCollections.length > 0;

  const handleSubmit = useCallback(() => {
    const trimmed = message.trim();
    if (!trimmed || isStreaming || selectedCollections.length === 0) return;
    onSubmit(trimmed);
    setMessage("");
    textareaRef.current?.focus();
  }, [message, isStreaming, selectedCollections.length, onSubmit]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  return (
    <div className="flex gap-2 border-t border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-950">
      <textarea
        ref={textareaRef}
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={
          selectedCollections.length === 0
            ? "Select at least one collection to start..."
            : "Ask a question... (Shift+Enter for newline)"
        }
        rows={2}
        className="flex-1 resize-none rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm placeholder:text-neutral-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100 dark:placeholder:text-neutral-500"
        disabled={isStreaming}
      />
      <button
        type="button"
        onClick={handleSubmit}
        disabled={!canSend}
        className="self-end rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-blue-500 dark:hover:bg-blue-600"
      >
        {isStreaming ? "Sending..." : "Send"}
      </button>
    </div>
  );
}

const ChatInput = React.memo(ChatInputInner);
export default ChatInput;
