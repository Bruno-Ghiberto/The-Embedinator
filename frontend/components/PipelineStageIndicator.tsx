"use client";

import React from "react";
import { Loader2 } from "lucide-react";
import { getStageLabel } from "@/lib/stage-labels";

interface PipelineStageIndicatorProps {
  stage: string | null;
  isVisible: boolean;
}

function PipelineStageIndicatorInner({
  stage,
  isVisible,
}: PipelineStageIndicatorProps) {
  if (!isVisible || !stage) return null;

  return (
    <div className="flex items-center gap-1.5 text-sm text-muted-foreground px-4 py-1">
      <Loader2 className="h-3 w-3 animate-spin" />
      <span
        className="transition-opacity duration-200"
        key={stage}
      >
        {getStageLabel(stage)}
      </span>
    </div>
  );
}

export const PipelineStageIndicator = React.memo(
  PipelineStageIndicatorInner,
);
