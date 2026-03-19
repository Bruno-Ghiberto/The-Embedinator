"use client";

import React from "react";
import * as Tooltip from "@radix-ui/react-tooltip";
import type { Citation } from "@/lib/types";

interface CitationTooltipProps {
  citation: Citation;
  index: number; // display as [N]
}

function CitationTooltipInner({ citation, index }: CitationTooltipProps) {
  return (
    <Tooltip.Provider delayDuration={200}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <button
            type="button"
            className="inline-flex items-center justify-center rounded px-1 text-xs font-semibold text-blue-600 hover:text-blue-800 hover:bg-blue-50 dark:text-blue-400 dark:hover:text-blue-300 dark:hover:bg-blue-900/30"
            aria-label={`Citation ${index}: ${citation.document_name}`}
          >
            [{index}]
          </button>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            className="z-50 max-w-sm rounded-lg border border-neutral-200 bg-white p-3 shadow-lg dark:border-neutral-700 dark:bg-neutral-900"
            sideOffset={5}
          >
            {citation.source_removed ? (
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/40 dark:text-red-400">
                  Source removed
                </span>
                <span className="text-sm text-neutral-500 dark:text-neutral-400">
                  {citation.document_name}
                </span>
              </div>
            ) : (
              <div className="space-y-1.5">
                <p className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
                  {citation.document_name}
                </p>
                <p className="text-sm text-neutral-800 dark:text-neutral-200 line-clamp-4">
                  {citation.text}
                </p>
              </div>
            )}
            <Tooltip.Arrow className="fill-white dark:fill-neutral-900" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
}

const CitationTooltip = React.memo(CitationTooltipInner);
export default CitationTooltip;
