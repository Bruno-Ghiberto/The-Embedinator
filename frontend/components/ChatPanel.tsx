"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import type { ChatMessage } from "@/lib/types";
import { useCollections } from "@/hooks/useCollections";
import CitationTooltip from "./CitationTooltip";
import ConfidenceIndicator from "./ConfidenceIndicator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Copy, Check, Sparkles, MessageCircleQuestion, FolderPlus, Upload, HelpCircle } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@/components/ui/tooltip";

interface ChatPanelProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  onSubmit?: (message: string) => void;
}

const STARTER_QUESTIONS = [
  "What documents are in this collection?",
  "Summarize the key findings",
  "What are the main topics covered?",
  "Compare the different perspectives",
];

// T023 — Copy-to-clipboard button for assistant messages
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [text]);

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={handleCopy}
            className="opacity-0 transition-opacity group-hover/msg:opacity-100"
            aria-label="Copy message"
          />
        }
      >
        {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
      </TooltipTrigger>
      <TooltipContent>{copied ? "Copied!" : "Copy message"}</TooltipContent>
    </Tooltip>
  );
}

// T017 — Redesigned message bubbles with token-based colors
function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  // T022 — Clarification card rendering
  if (message.clarification) {
    return (
      <div className="flex justify-start">
        <Card className="max-w-[80%] border-[var(--color-accent)]/30">
          <CardContent className="flex items-start gap-3">
            <MessageCircleQuestion className="mt-0.5 size-5 shrink-0 text-[var(--color-accent)]" />
            <div className="space-y-1">
              <p className="text-sm font-medium text-[var(--color-text-primary)]">
                Clarification needed
              </p>
              <p className="text-sm text-[var(--color-text-muted)]">
                {message.clarification}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "group/msg relative max-w-[80%] rounded-lg px-4 py-3",
          isUser
            ? "bg-[var(--color-accent)] text-white"
            : "bg-[var(--color-surface)] text-[var(--color-text-primary)]",
        )}
      >
        <p className="whitespace-pre-wrap text-sm">{message.content}</p>

        {/* T018 — Blinking caret cursor during streaming */}
        {message.isStreaming && (
          <span
            className="ml-0.5 inline-block h-4 w-0.5 align-middle bg-[var(--color-accent)] animate-[blink_530ms_ease-in-out_infinite]"
            aria-hidden="true"
          />
        )}

        {/* T018 — Stage status badge during streaming */}
        {message.isStreaming && (
          <div className="mt-2">
            <Badge variant="secondary" className="text-xs">
              <Sparkles className="size-3" />
              Generating
            </Badge>
          </div>
        )}

        {/* Citations (preserved from original) */}
        {message.role === "assistant" &&
          message.citations &&
          message.citations.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1 border-t border-[var(--color-border)] pt-2">
              {message.citations.map((citation, idx) => (
                <CitationTooltip
                  key={citation.passage_id}
                  citation={citation}
                  index={idx + 1}
                />
              ))}
            </div>
          )}

        {/* Confidence indicator (preserved from original) */}
        {message.role === "assistant" &&
          !message.isStreaming &&
          message.confidence !== undefined && (
            <div className="mt-2 flex items-center gap-2 border-t border-[var(--color-border)] pt-2">
              <ConfidenceIndicator score={message.confidence} />
              <span className="text-xs text-[var(--color-text-muted)]">
                Confidence
              </span>
            </div>
          )}

        {/* Groundedness data (preserved from original) */}
        {message.role === "assistant" &&
          !message.isStreaming &&
          message.groundedness && (
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-[var(--color-text-muted)]">
              <span>{message.groundedness.supported} supported</span>
              {message.groundedness.unsupported > 0 && (
                <span className="text-[var(--color-warning)]">
                  {message.groundedness.unsupported} unsupported
                </span>
              )}
              {message.groundedness.contradicted > 0 && (
                <span className="text-[var(--color-destructive)]">
                  {message.groundedness.contradicted} contradicted
                </span>
              )}
            </div>
          )}

        {/* T021 — Meta-reasoning indicator (renders when strategies_attempted data is available) */}
        {message.role === "assistant" &&
          !message.isStreaming &&
          "strategies_attempted" in message &&
          Array.isArray(
            (message as Record<string, unknown>).strategies_attempted,
          ) && (
            <div className="mt-1">
              <Badge variant="outline" className="text-xs">
                <Sparkles className="size-3" />
                Meta-Reasoning
              </Badge>
            </div>
          )}

        {/* T023 — Copy button for assistant messages */}
        {message.role === "assistant" &&
          !message.isStreaming &&
          message.content && (
            <div className="absolute -top-3 right-1">
              <CopyButton text={message.content} />
            </div>
          )}
      </div>
    </div>
  );
}

const MemoizedMessageBubble = React.memo(MessageBubble);

function ChatPanelInner({ messages, isStreaming, onSubmit }: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const { collections, isLoading: collectionsLoading } = useCollections();

  // Track if bottom is visible to decide auto-scroll behavior
  useEffect(() => {
    const el = bottomRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        shouldAutoScrollRef.current = entry.isIntersecting;
      },
      { threshold: 0.1 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (shouldAutoScrollRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  // T024 — Empty state: onboarding card (no collections) or starter questions
  if (messages.length === 0) {
    const hasNoCollections =
      !collectionsLoading && collections !== undefined && collections.length === 0;

    if (hasNoCollections) {
      // US7 — First-run onboarding card
      return (
        <div className="flex flex-1 items-center justify-center p-6">
          <Card className="w-full max-w-md border-[var(--color-border)]">
            <CardContent className="space-y-5 pt-6">
              <div className="space-y-1 text-center">
                <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">
                  Welcome to The Embedinator
                </h2>
                <p className="text-sm text-[var(--color-text-muted)]">
                  Get started in three steps
                </p>
              </div>

              <div className="space-y-3">
                <div className="flex items-start gap-3">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-[var(--color-surface)]">
                    <FolderPlus className="size-4 text-[var(--color-accent)]" />
                  </div>
                  <div className="space-y-0.5">
                    <p className="text-sm font-medium text-[var(--color-text-primary)]">
                      Create a collection
                    </p>
                    <p className="text-xs text-[var(--color-text-muted)]">
                      Organize your documents into searchable collections
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-[var(--color-surface)]">
                    <Upload className="size-4 text-[var(--color-accent)]" />
                  </div>
                  <div className="space-y-0.5">
                    <p className="text-sm font-medium text-[var(--color-text-primary)]">
                      Upload documents
                    </p>
                    <p className="text-xs text-[var(--color-text-muted)]">
                      Supported formats: PDF, Markdown (.md), plain text (.txt), reStructuredText (.rst)
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-[var(--color-surface)]">
                    <HelpCircle className="size-4 text-[var(--color-accent)]" />
                  </div>
                  <div className="space-y-0.5">
                    <p className="text-sm font-medium text-[var(--color-text-primary)]">
                      Ask questions
                    </p>
                    <p className="text-xs text-[var(--color-text-muted)]">
                      Get AI-powered answers grounded in your documents, with citations
                    </p>
                  </div>
                </div>
              </div>

              <Link
                href="/collections"
                className={cn(buttonVariants(), "w-full justify-center")}
              >
                Create your first collection
              </Link>
            </CardContent>
          </Card>
        </div>
      );
    }

    // Standard empty state with starter questions
    return (
      <div className="flex flex-1 items-center justify-center p-4">
        <div className="max-w-md space-y-6 text-center">
          <div className="space-y-2">
            <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">
              What would you like to explore?
            </h2>
            <p className="text-sm text-[var(--color-text-muted)]">
              Select a collection and ask a question to get started.
            </p>
          </div>
          {onSubmit && (
            <div className="flex flex-wrap justify-center gap-2">
              {STARTER_QUESTIONS.map((q) => (
                <Button
                  key={q}
                  variant="outline"
                  size="sm"
                  onClick={() => onSubmit(q)}
                  className="text-xs"
                >
                  {q}
                </Button>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <ScrollArea className="flex-1">
      <div className="space-y-4 p-4">
        {messages.map((msg) => (
          <MemoizedMessageBubble key={msg.id} message={msg} />
        ))}
      </div>
      <div ref={bottomRef} />
    </ScrollArea>
  );
}

const ChatPanel = React.memo(ChatPanelInner);
export default ChatPanel;
