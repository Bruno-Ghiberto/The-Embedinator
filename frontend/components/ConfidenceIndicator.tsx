"use client";

import React from "react";
import { getConfidenceTier } from "@/lib/types";
import type { ConfidenceTier } from "@/lib/types";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
  PopoverHeader,
  PopoverTitle,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

interface ConfidenceIndicatorProps {
  score: number;
}

const TIER_STYLES: Record<ConfidenceTier, string> = {
  green: "bg-success text-white",
  yellow: "bg-warning text-white",
  red: "bg-destructive text-white",
};

const TIER_LABELS: Record<ConfidenceTier, string> = {
  green: "High confidence",
  yellow: "Medium confidence",
  red: "Low confidence",
};

function ConfidenceIndicatorInner({ score }: ConfidenceIndicatorProps) {
  const tier = getConfidenceTier(score);

  return (
    <Popover>
      <PopoverTrigger
        className={cn(
          "inline-flex h-5 items-center rounded-full px-2 py-0.5 text-xs font-medium cursor-pointer transition-opacity hover:opacity-80",
          TIER_STYLES[tier],
        )}
        aria-label={`${TIER_LABELS[tier]}: ${score}%`}
      >
        {score}%
      </PopoverTrigger>
      <PopoverContent className="w-56">
        <PopoverHeader>
          <PopoverTitle>{TIER_LABELS[tier]}</PopoverTitle>
        </PopoverHeader>
        <div className="space-y-1 text-sm text-muted-foreground">
          <div className="flex justify-between">
            <span>Score</span>
            <span className="font-medium text-foreground">{score}/100</span>
          </div>
          <div className="flex justify-between">
            <span>Tier</span>
            <span className="font-medium text-foreground capitalize">{tier}</span>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

const ConfidenceIndicator = React.memo(ConfidenceIndicatorInner);
export default ConfidenceIndicator;
