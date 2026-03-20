"use client";

import React from "react";
import type { Citation } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
  PopoverHeader,
  PopoverTitle,
  PopoverDescription,
} from "@/components/ui/popover";

interface CitationTooltipProps {
  citation: Citation;
  index: number;
}

function CitationTooltipInner({ citation, index }: CitationTooltipProps) {
  return (
    <Popover>
      <PopoverTrigger
        className="inline-flex items-center justify-center rounded-full border border-[var(--color-border)] px-2 py-0.5 text-xs font-semibold text-[var(--color-accent)] transition-colors hover:bg-[var(--color-surface)] cursor-pointer"
        aria-label={`Citation ${index}: ${citation.document_name}`}
      >
        [{index}]
      </PopoverTrigger>
      <PopoverContent className="w-80">
        {citation.source_removed ? (
          <div className="flex items-center gap-2">
            <Badge variant="destructive">Source removed</Badge>
            <span className="text-sm text-[var(--color-text-muted)]">
              {citation.document_name}
            </span>
          </div>
        ) : (
          <>
            <PopoverHeader>
              <PopoverTitle>{citation.document_name}</PopoverTitle>
              <PopoverDescription>
                Relevance: {(citation.relevance_score * 100).toFixed(0)}%
              </PopoverDescription>
            </PopoverHeader>
            <p className="text-sm text-[var(--color-text-primary)] line-clamp-4">
              {citation.text}
            </p>
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}

const CitationTooltip = React.memo(CitationTooltipInner);
export default CitationTooltip;
