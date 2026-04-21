"use client";

import React, { useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import type { ChatMessage, Citation } from "@/lib/types";
import { getConfidenceTier } from "@/lib/types";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { CitationHoverCard } from "./CitationHoverCard";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ChevronDown, AlertCircle, RefreshCw } from "lucide-react";

interface ChatMessageBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
  currentStage?: string;
  onCitationClick?: (citation: Citation) => void;
  onRetry?: () => void;
}

// T027 — Inline citation parsing: split text on [N] markers
function renderWithCitations(
  text: string,
  citations: Citation[],
  onCitationClick?: (citation: Citation) => void,
): React.ReactNode {
  if (!citations?.length) {
    return <MarkdownRenderer content={text} />;
  }

  // Split on [N] markers — even indices are text, odd indices are captured group (the number)
  const parts = text.split(/\[(\d+)\]/g);
  if (parts.length === 1) {
    // No [N] markers found — render as plain markdown
    return <MarkdownRenderer content={text} />;
  }

  // Rebuild: text segments as markdown, [N] as CitationHoverCard
  const elements: React.ReactNode[] = [];
  for (let i = 0; i < parts.length; i++) {
    if (i % 2 === 0) {
      // Text segment — render inline (no block-level markdown to avoid broken layout)
      if (parts[i]) {
        elements.push(
          <MarkdownRenderer key={`text-${i}`} content={parts[i]} />,
        );
      }
    } else {
      // Citation number
      const num = parseInt(parts[i], 10);
      const citation = citations[num - 1];
      if (citation) {
        elements.push(
          <CitationHoverCard
            key={`cite-${i}`}
            citationNumber={num}
            citation={citation}
            onClick={
              onCitationClick
                ? () => onCitationClick(citation)
                : undefined
            }
          />,
        );
      } else {
        // Citation number out of range — render as text
        elements.push(<span key={`cite-${i}`}>[{num}]</span>);
      }
    }
  }

  return <>{elements}</>;
}

// Confidence meter — inline bar with label
function ConfidenceMeter({ score }: { score: number }) {
  const tier = getConfidenceTier(score);
  const barColor =
    tier === "green"
      ? "bg-green-500"
      : tier === "yellow"
        ? "bg-yellow-500"
        : "bg-red-500";
  const label =
    tier === "green" ? "High" : tier === "yellow" ? "Medium" : "Low";

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <div className="w-16 h-1.5 rounded-full bg-muted overflow-hidden">
        <div
          className={cn("h-full rounded-full", barColor)}
          style={{ width: `${score}%` }}
        />
      </div>
      <span>
        {label} ({score}%)
      </span>
    </div>
  );
}

function ChatMessageBubbleInner({
  message,
  isStreaming = false,
  onCitationClick,
  onRetry,
}: ChatMessageBubbleProps) {
  const router = useRouter();
  const isUser = message.role === "user";
  const hasCitations =
    !isUser && message.citations && message.citations.length > 0;

  const handleCitationClick = useCallback(
    (citation: Citation) => {
      if (onCitationClick) {
        onCitationClick(citation);
      } else {
        // Default: navigate to document
        router.push(`/documents/${citation.document_id}`);
      }
    },
    [onCitationClick, router],
  );

  // Clarification card
  if (message.clarification) {
    return (
      <div
        className="flex justify-start"
        style={{
          contentVisibility: "auto",
          containIntrinsicSize: "0 80px",
        }}
      >
        <div className="max-w-full sm:max-w-[80%] rounded-2xl bg-muted px-4 py-3 border border-primary/30">
          <p className="text-sm font-medium text-foreground mb-1">
            Clarification needed
          </p>
          <p className="text-sm text-muted-foreground">
            {message.clarification}
          </p>
        </div>
      </div>
    );
  }

  // Error message — system bubble
  if (!isUser && message.isError) {
    return (
      <div
        className="flex items-start gap-3 my-2"
        style={{ contentVisibility: "auto", containIntrinsicSize: "0 80px" }}
      >
        <div className="w-6 h-6 rounded-full bg-destructive/10 flex items-center justify-center shrink-0 mt-1">
          <AlertCircle className="h-3 w-3 text-destructive" />
        </div>
        <div className="bg-destructive/10 border border-destructive/20 rounded-2xl px-4 py-3 max-w-[80%] sm:max-w-[80%]">
          <p className="text-sm text-destructive">
            {message.content || "Something went wrong. Please try again."}
          </p>
          {onRetry && (
            <Button
              variant="ghost"
              size="sm"
              className="mt-2 h-7 text-xs"
              onClick={onRetry}
            >
              <RefreshCw className="h-3 w-3 mr-1" />
              Retry
            </Button>
          )}
        </div>
      </div>
    );
  }

  // User message
  if (isUser) {
    return (
      <div
        className="flex justify-end"
        style={{
          contentVisibility: "auto",
          containIntrinsicSize: "0 80px",
        }}
      >
        <div className="max-w-full sm:max-w-[80%] rounded-2xl bg-primary text-primary-foreground px-4 py-2">
          <p className="whitespace-pre-wrap text-sm">{message.content}</p>
        </div>
      </div>
    );
  }

  // Assistant message
  return (
    <div
      className="flex justify-start"
      style={{ contentVisibility: "auto", containIntrinsicSize: "0 80px" }}
    >
      <div className="max-w-full sm:max-w-[80%] w-full rounded-2xl bg-muted px-4 py-3">
        {/* Message content with inline citations */}
        <div className="prose-sm text-sm text-foreground">
          {hasCitations
            ? renderWithCitations(
                message.content,
                message.citations!,
                handleCitationClick,
              )
            : <MarkdownRenderer
                content={message.content}
                isStreaming={isStreaming}
              />
          }
        </div>

        {/* Blinking cursor during streaming */}
        {isStreaming && (
          <span
            className="ml-0.5 inline-block h-4 w-0.5 align-middle bg-foreground animate-[blink_530ms_ease-in-out_infinite]"
            aria-hidden="true"
          />
        )}

        {/* Collapsible citations section */}
        {hasCitations && !isStreaming && (
          <div className="mt-3 border-t border-border pt-2">
            <Collapsible>
              <CollapsibleTrigger className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer">
                <ChevronDown className="h-3 w-3" />
                {message.citations!.length} source
                {message.citations!.length !== 1 ? "s" : ""}
              </CollapsibleTrigger>
              <CollapsibleContent>
                <div className="mt-2 flex flex-wrap gap-1">
                  {message.citations!.map((c, i) => (
                    <CitationHoverCard
                      key={c.passage_id}
                      citationNumber={i + 1}
                      citation={c}
                      onClick={() => handleCitationClick(c)}
                    />
                  ))}
                </div>
              </CollapsibleContent>
            </Collapsible>
          </div>
        )}

        {/* Confidence meter */}
        {message.confidence !== undefined && !isStreaming && (
          <div className="mt-2 border-t border-border pt-2">
            <ConfidenceMeter score={message.confidence} />
          </div>
        )}

        {/* Groundedness data */}
        {message.groundedness && !isStreaming && (
          <div className="mt-1 text-xs text-muted-foreground">
            <span>{message.groundedness.supported} supported</span>
            {message.groundedness.unsupported > 0 && (
              <span className="ml-2 text-warning">
                {message.groundedness.unsupported} unsupported
              </span>
            )}
            {message.groundedness.contradicted > 0 && (
              <span className="ml-2 text-destructive">
                {message.groundedness.contradicted} contradicted
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export const ChatMessageBubble = React.memo(
  ChatMessageBubbleInner,
  (prev, next) =>
    prev.message.content === next.message.content &&
    prev.message.citations === next.message.citations &&
    prev.isStreaming === next.isStreaming &&
    prev.message.confidence === next.message.confidence &&
    prev.message.groundedness === next.message.groundedness &&
    prev.message.isError === next.message.isError &&
    prev.onRetry === next.onRetry,
);
