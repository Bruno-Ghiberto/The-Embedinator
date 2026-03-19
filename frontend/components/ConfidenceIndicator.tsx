"use client";

import React from "react";
import * as Tooltip from "@radix-ui/react-tooltip";
import { getConfidenceTier } from "@/lib/types";
import type { ConfidenceTier } from "@/lib/types";

interface ConfidenceIndicatorProps {
  score: number; // integer 0-100
}

const TIER_COLORS: Record<ConfidenceTier, string> = {
  green: "bg-green-500",
  yellow: "bg-yellow-500",
  red: "bg-red-500",
};

const TIER_LABELS: Record<ConfidenceTier, string> = {
  green: "High confidence",
  yellow: "Medium confidence",
  red: "Low confidence",
};

function ConfidenceIndicatorInner({ score }: ConfidenceIndicatorProps) {
  const tier = getConfidenceTier(score);

  return (
    <Tooltip.Provider delayDuration={200}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <span
            className="inline-flex items-center gap-1.5 cursor-default"
            aria-label={`${TIER_LABELS[tier]}: ${score}%`}
          >
            <span
              className={`inline-block h-2.5 w-2.5 rounded-full ${TIER_COLORS[tier]}`}
              aria-hidden="true"
            />
          </span>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            className="rounded-md bg-neutral-900 px-3 py-1.5 text-sm text-white shadow-md dark:bg-neutral-100 dark:text-neutral-900"
            sideOffset={5}
          >
            <span className="font-medium">{score}</span>
            <span className="text-neutral-400 dark:text-neutral-500">
              /100
            </span>
            {" "}
            <span className="text-neutral-300 dark:text-neutral-600">
              {TIER_LABELS[tier]}
            </span>
            <Tooltip.Arrow className="fill-neutral-900 dark:fill-neutral-100" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
}

const ConfidenceIndicator = React.memo(ConfidenceIndicatorInner);
export default ConfidenceIndicator;
