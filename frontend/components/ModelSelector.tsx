"use client";

import React from "react";
import type { ModelInfo } from "@/lib/types";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";

interface ModelSelectorProps {
  models: ModelInfo[];
  selectedModel: string;
  onSelect: (model: string) => void;
  placeholder?: string;
}

function ModelSelectorBase({
  models,
  selectedModel,
  onSelect,
  placeholder = "Select model...",
}: ModelSelectorProps) {
  return (
    <Select value={selectedModel} onValueChange={(val) => { if (val) onSelect(val); }}>
      <SelectTrigger className="w-full" aria-label={placeholder}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {models.map((model) => (
          <SelectItem key={model.name} value={model.name}>
            <span className="font-medium">{model.name}</span>
            <span className="ml-2 text-xs text-muted-foreground">
              {model.provider}
            </span>
          </SelectItem>
        ))}
        {models.length === 0 && (
          <div className="px-3 py-2 text-sm text-muted-foreground">
            No models available
          </div>
        )}
      </SelectContent>
    </Select>
  );
}

function LLMModelSelectorInner(
  props: Omit<ModelSelectorProps, "placeholder">,
) {
  return <ModelSelectorBase {...props} placeholder="Select LLM model..." />;
}

function EmbedModelSelectorInner(
  props: Omit<ModelSelectorProps, "placeholder">,
) {
  return (
    <ModelSelectorBase {...props} placeholder="Select embedding model..." />
  );
}

export const LLMModelSelector = React.memo(LLMModelSelectorInner);
export const EmbedModelSelector = React.memo(EmbedModelSelectorInner);
