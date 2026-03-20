"use client";

import React from "react";
import { useCollections } from "@/hooks/useCollections";
import { useModels } from "@/hooks/useModels";
import { LLMModelSelector, EmbedModelSelector } from "./ModelSelector";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";

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
    <aside className="flex w-64 flex-col gap-6 border-r border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
          Collections
        </h3>
        {collectionsLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-6 w-full" />
            ))}
          </div>
        ) : collections && collections.length > 0 ? (
          <ScrollArea className="max-h-48">
            <div className="space-y-1">
              {collections.map((col) => (
                <label
                  key={col.id}
                  className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-[var(--color-background)]"
                >
                  <input
                    type="checkbox"
                    checked={selectedCollections.includes(col.id)}
                    onChange={() => handleCollectionToggle(col.id)}
                    className="h-4 w-4 rounded border-[var(--color-border)] text-[var(--color-accent)] focus:ring-[var(--color-accent)]"
                  />
                  <span className="truncate text-[var(--color-text-primary)]">
                    {col.name}
                  </span>
                  <span className="ml-auto text-xs text-[var(--color-text-muted)]">
                    {col.document_count}
                  </span>
                </label>
              ))}
            </div>
          </ScrollArea>
        ) : (
          <p className="text-sm text-[var(--color-text-muted)]">
            No collections available
          </p>
        )}
      </section>

      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
          LLM Model
        </h3>
        {modelsLoading ? (
          <Skeleton className="h-8 w-full" />
        ) : (
          <LLMModelSelector
            models={llmModels ?? []}
            selectedModel={llmModel}
            onSelect={onLLMModelChange}
          />
        )}
      </section>

      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
          Embedding Model
        </h3>
        {modelsLoading ? (
          <Skeleton className="h-8 w-full" />
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
