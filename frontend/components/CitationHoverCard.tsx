"use client";

import React from "react";
import type { Citation } from "@/lib/types";
import {
  HoverCard,
  HoverCardTrigger,
  HoverCardContent,
} from "@/components/ui/hover-card";

interface CitationHoverCardProps {
  citationNumber: number;
  citation: Citation;
  collectionId?: string;
  onClick?: () => void;
}

function getRelevanceColor(score: number): string {
  if (score >= 0.7) return "bg-green-500";
  if (score >= 0.4) return "bg-yellow-500";
  return "bg-red-500";
}

function CitationHoverCardInner({
  citationNumber,
  citation,
  onClick,
}: CitationHoverCardProps) {
  if (citation.source_removed) {
    return (
      <span
        className="inline-flex items-center justify-center rounded-full bg-destructive/10 text-destructive text-xs font-medium px-1.5 py-0.5 mx-0.5 line-through cursor-default"
        title={`Source removed: ${citation.document_name}`}
      >
        [{citationNumber}]
      </span>
    );
  }

  return (
    <HoverCard>
      <HoverCardTrigger
        className="inline-flex items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-medium px-1.5 py-0.5 cursor-pointer mx-0.5 hover:bg-primary/20 transition-colors"
        onClick={onClick}
        aria-label={`Citation ${citationNumber}: ${citation.document_name}`}
      >
        [{citationNumber}]
      </HoverCardTrigger>
      <HoverCardContent className="w-80 p-3">
        <div className="space-y-2">
          <p className="font-semibold text-sm text-foreground truncate">
            {citation.document_name}
          </p>
          <p className="text-xs text-muted-foreground line-clamp-3">
            {citation.text}
          </p>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
              <div
                className={`h-full rounded-full ${getRelevanceColor(citation.relevance_score)}`}
                style={{
                  width: `${Math.round(citation.relevance_score * 100)}%`,
                }}
              />
            </div>
            <span className="text-xs text-muted-foreground tabular-nums">
              {Math.round(citation.relevance_score * 100)}%
            </span>
          </div>
        </div>
      </HoverCardContent>
    </HoverCard>
  );
}

export const CitationHoverCard = React.memo(CitationHoverCardInner);
