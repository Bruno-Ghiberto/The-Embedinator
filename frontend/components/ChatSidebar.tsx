"use client";

import React from "react";
import { useCollections } from "@/hooks/useCollections";
import { useModels } from "@/hooks/useModels";
import { LLMModelSelector, EmbedModelSelector } from "./ModelSelector";

interface ChatSidebarProps {
  selectedCollections: string[];
  onCollectionsChange: (ids: string[]) => void;
  llmModel: string;
  onLLMModelChange: (model: string) => void;
  embedModel: string | null;
  onEmbedModelChange: (model: string | null) => void;
}

function ChatSidebarInner({
  selectedCollections,
  onCollectionsChange,
  llmModel,
  onLLMModelChange,
  embedModel,
  onEmbedModelChange,
}: ChatSidebarProps) {
  const { collections, isLoading: collectionsLoading } = useCollections();
  const { llmModels, embedModels, isLoading: modelsLoading } = useModels();

  const handleCollectionToggle = (id: string) => {
    const next = selectedCollections.includes(id)
      ? selectedCollections.filter((c) => c !== id)
      : [...selectedCollections, id];
    onCollectionsChange(next);
  };

  return (
    <aside className="flex w-64 flex-col gap-6 border-r border-neutral-200 bg-neutral-50 p-4 dark:border-neutral-800 dark:bg-neutral-900/50">
      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
          Collections
        </h3>
        {collectionsLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-6 animate-pulse rounded bg-neutral-200 dark:bg-neutral-700"
              />
            ))}
          </div>
        ) : collections && collections.length > 0 ? (
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {collections.map((col) => (
              <label
                key={col.id}
                className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm cursor-pointer hover:bg-neutral-100 dark:hover:bg-neutral-800"
              >
                <input
                  type="checkbox"
                  checked={selectedCollections.includes(col.id)}
                  onChange={() => handleCollectionToggle(col.id)}
                  className="h-4 w-4 rounded border-neutral-300 text-blue-600 focus:ring-blue-500 dark:border-neutral-600"
                />
                <span className="truncate text-neutral-700 dark:text-neutral-300">
                  {col.name}
                </span>
                <span className="ml-auto text-xs text-neutral-400">
                  {col.document_count}
                </span>
              </label>
            ))}
          </div>
        ) : (
          <p className="text-sm text-neutral-500 dark:text-neutral-400">
            No collections available
          </p>
        )}
      </section>

      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
          LLM Model
        </h3>
        {modelsLoading ? (
          <div className="h-10 animate-pulse rounded bg-neutral-200 dark:bg-neutral-700" />
        ) : (
          <LLMModelSelector
            models={llmModels ?? []}
            selectedModel={llmModel}
            onSelect={onLLMModelChange}
          />
        )}
      </section>

      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
          Embedding Model
        </h3>
        {modelsLoading ? (
          <div className="h-10 animate-pulse rounded bg-neutral-200 dark:bg-neutral-700" />
        ) : (
          <EmbedModelSelector
            models={embedModels ?? []}
            selectedModel={embedModel ?? ""}
            onSelect={(m) => onEmbedModelChange(m || null)}
          />
        )}
      </section>
    </aside>
  );
}

const ChatSidebar = React.memo(ChatSidebarInner);
export default ChatSidebar;
