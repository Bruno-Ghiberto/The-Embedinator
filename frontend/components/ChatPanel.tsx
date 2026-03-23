"use client";

import React, { useEffect, useRef } from "react";
import Link from "next/link";
import type { ChatMessage, Citation } from "@/lib/types";
import { useCollections } from "@/hooks/useCollections";
import { ChatMessageBubble } from "./ChatMessageBubble";
import { PipelineStageIndicator } from "./PipelineStageIndicator";
import { ScrollToBottom } from "./ScrollToBottom";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { FolderPlus, Upload, HelpCircle } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";

interface ChatPanelProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  currentStage?: string;
  onSubmit?: (message: string) => void;
  onCitationClick?: (citation: Citation) => void;
  onRetry?: () => void;
}

const STARTER_QUESTIONS = [
  "What documents are in this collection?",
  "Summarize the key findings",
  "What are the main topics covered?",
  "Compare the different perspectives",
];

function ChatPanelInner({
  messages,
  isStreaming,
  currentStage,
  onSubmit,
  onCitationClick,
  onRetry,
}: ChatPanelProps) {
  const messagesContainerRef = useRef<HTMLDivElement>(null);
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

  // Empty state: onboarding card (no collections) or starter questions
  if (messages.length === 0) {
    const hasNoCollections =
      !collectionsLoading &&
      collections !== undefined &&
      collections.length === 0;

    if (hasNoCollections) {
      return (
        <div className="flex flex-1 items-center justify-center p-6">
          <Card className="w-full max-w-md border-border">
            <CardContent className="space-y-5 pt-6">
              <div className="space-y-1 text-center">
                <h2 className="text-lg font-semibold text-foreground">
                  Welcome to The Embedinator
                </h2>
                <p className="text-sm text-muted-foreground">
                  Get started in three steps
                </p>
              </div>

              <div className="space-y-3">
                <div className="flex items-start gap-3">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-card">
                    <FolderPlus className="size-4 text-primary" />
                  </div>
                  <div className="space-y-0.5">
                    <p className="text-sm font-medium text-foreground">
                      Create a collection
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Organize your documents into searchable collections
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-card">
                    <Upload className="size-4 text-primary" />
                  </div>
                  <div className="space-y-0.5">
                    <p className="text-sm font-medium text-foreground">
                      Upload documents
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Supported formats: PDF, Markdown (.md), plain text (.txt),
                      reStructuredText (.rst)
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-card">
                    <HelpCircle className="size-4 text-primary" />
                  </div>
                  <div className="space-y-0.5">
                    <p className="text-sm font-medium text-foreground">
                      Ask questions
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Get AI-powered answers grounded in your documents, with
                      citations
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
            <h2 className="text-lg font-semibold text-foreground">
              What would you like to explore?
            </h2>
            <p className="text-sm text-muted-foreground">
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
    <div className="relative flex-1 min-h-0">
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto min-h-0 h-full px-4 py-4 space-y-4"
      >
        {messages.map((message, index) => (
          <ChatMessageBubble
            key={message.id}
            message={message}
            isStreaming={isStreaming && index === messages.length - 1}
            currentStage={
              isStreaming && index === messages.length - 1
                ? currentStage
                : undefined
            }
            onCitationClick={onCitationClick}
            onRetry={message.isError ? onRetry : undefined}
          />
        ))}

        {/* Shimmer placeholder when streaming but no assistant content yet */}
        {isStreaming &&
          messages.length > 0 &&
          messages[messages.length - 1]?.role === "assistant" &&
          !messages[messages.length - 1]?.content && (
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 rounded-full bg-muted animate-pulse" />
              <Skeleton className="h-16 w-3/4 rounded-2xl animate-pulse" />
            </div>
          )}

        {isStreaming && (
          <PipelineStageIndicator
            stage={currentStage ?? null}
            isVisible={!!currentStage}
          />
        )}

        <div ref={bottomRef} />
      </div>

      <ScrollToBottom
        scrollContainerRef={messagesContainerRef}
        isStreaming={isStreaming}
      />
    </div>
  );
}

const ChatPanel = React.memo(ChatPanelInner);
export default ChatPanel;
