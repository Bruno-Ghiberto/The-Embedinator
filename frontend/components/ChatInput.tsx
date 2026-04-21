"use client";

import React, { useState, useCallback, useRef } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { useBackendStatus } from "@/components/BackendStatusProvider";
import { ArrowUp, Square } from "lucide-react";

interface ChatInputProps {
  isStreaming: boolean;
  selectedCollections: string[];
  onSubmit: (message: string) => void;
  onStop?: () => void;
}

function ChatInputInner({
  isStreaming,
  selectedCollections,
  onSubmit,
  onStop,
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
    if (
      !trimmed ||
      isStreaming ||
      selectedCollections.length === 0 ||
      !backendReady
    )
      return;
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
    if (backendState === "unreachable")
      return "Waiting for backend to start...";
    if (backendState === "degraded") {
      return "AI models are still loading...";
    }
    if (selectedCollections.length === 0)
      return "Select at least one collection to start...";
    return "Ask a question... (Shift+Enter for newline)";
  }

  return (
    <div className="flex items-end gap-2 border-t border-border bg-background p-4 shrink-0">
      <Textarea
        ref={textareaRef}
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={getPlaceholder()}
        className="flex-1 resize-none min-h-10 max-h-[120px]"
        disabled={!backendReady && !isStreaming}
      />
      {isStreaming ? (
        <Button
          variant="destructive"
          size="icon"
          className="min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0"
          onClick={onStop}
          aria-label="Stop generation"
        >
          <Square className="h-4 w-4 fill-current" />
        </Button>
      ) : (
        <Button
          size="icon"
          className="min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0"
          onClick={handleSubmit}
          disabled={!canSend}
          aria-label="Send message"
        >
          <ArrowUp className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}

const ChatInput = React.memo(ChatInputInner);
export default ChatInput;
