"use client";

import React from "react";
import * as Select from "@radix-ui/react-select";
import type { ModelInfo } from "@/lib/types";

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
    <Select.Root value={selectedModel} onValueChange={onSelect}>
      <Select.Trigger
        className="inline-flex w-full items-center justify-between rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100"
        aria-label={placeholder}
      >
        <Select.Value placeholder={placeholder} />
        <Select.Icon className="ml-2 text-neutral-500">
          <ChevronDownIcon />
        </Select.Icon>
      </Select.Trigger>
      <Select.Portal>
        <Select.Content
          className="z-50 overflow-hidden rounded-lg border border-neutral-200 bg-white shadow-lg dark:border-neutral-700 dark:bg-neutral-900"
          position="popper"
          sideOffset={4}
        >
          <Select.Viewport className="p-1">
            {models.map((model) => (
              <Select.Item
                key={model.name}
                value={model.name}
                className="relative flex cursor-pointer items-center rounded-md px-3 py-2 text-sm text-neutral-900 outline-none hover:bg-neutral-100 focus:bg-neutral-100 data-[highlighted]:bg-neutral-100 dark:text-neutral-100 dark:hover:bg-neutral-800 dark:focus:bg-neutral-800 dark:data-[highlighted]:bg-neutral-800"
              >
                <Select.ItemText>
                  <span className="font-medium">{model.name}</span>
                  <span className="ml-2 text-xs text-neutral-500 dark:text-neutral-400">
                    {model.provider}
                  </span>
                </Select.ItemText>
              </Select.Item>
            ))}
            {models.length === 0 ? (
              <div className="px-3 py-2 text-sm text-neutral-500">
                No models available
              </div>
            ) : null}
          </Select.Viewport>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
}

function ChevronDownIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        d="M3 4.5L6 7.5L9 4.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
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
