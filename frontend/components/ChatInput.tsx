"use client";

import React, { useState, useCallback, useRef } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { useBackendStatus } from "@/components/BackendStatusProvider";

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
  const { state: backendState } = useBackendStatus();

  const backendReady = backendState === "ready";

  const canSend =
    backendReady &&
    !isStreaming &&
    message.trim().length > 0 &&
    selectedCollections.length > 0;

  const handleSubmit = useCallback(() => {
    const trimmed = message.trim();
    if (!trimmed || isStreaming || selectedCollections.length === 0 || !backendReady) return;
    onSubmit(trimmed);
    setMessage("");
    textareaRef.current?.focus();
  }, [message, isStreaming, selectedCollections.length, backendReady, onSubmit]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  function getPlaceholder(): string {
    if (backendState === "unreachable") return "Waiting for backend to start...";
    if (backendState === "degraded") {
      // Placeholder will be refined by StatusBanner which shows the specific service
      return "AI models are still loading...";
    }
    if (selectedCollections.length === 0) return "Select at least one collection to start...";
    return "Ask a question... (Shift+Enter for newline)";
  }

  return (
    <div className="flex gap-2 border-t border-[var(--color-border)] bg-[var(--color-background)] p-4">
      <Textarea
        ref={textareaRef}
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={getPlaceholder()}
        rows={2}
        className="flex-1 resize-none"
        disabled={isStreaming || !backendReady}
      />
      <Button
        onClick={handleSubmit}
        disabled={!canSend}
        className="self-end"
      >
        {isStreaming ? "Sending..." : "Send"}
      </Button>
    </div>
  );
}

const ChatInput = React.memo(ChatInputInner);
export default ChatInput;
