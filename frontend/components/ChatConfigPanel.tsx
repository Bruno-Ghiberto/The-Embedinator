"use client";

import type { Collection, ModelInfo } from "@/lib/types";
import {
  Collapsible,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import { Checkbox } from "@/components/ui/checkbox";
import { LLMModelSelector, EmbedModelSelector } from "@/components/ModelSelector";

interface ChatConfigPanelProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  collections: Collection[];
  selectedCollectionIds: string[];
  onCollectionChange: (ids: string[]) => void;
  llmModels: ModelInfo[];
  embedModels: ModelInfo[];
  selectedLlmModel: string;
  selectedEmbedModel: string;
  onLlmModelChange: (model: string) => void;
  onEmbedModelChange: (model: string) => void;
}

export function ChatConfigPanel({
  isOpen,
  onOpenChange,
  collections,
  selectedCollectionIds,
  onCollectionChange,
  llmModels,
  embedModels,
  selectedLlmModel,
  selectedEmbedModel,
  onLlmModelChange,
  onEmbedModelChange,
}: ChatConfigPanelProps) {
  const handleCollectionToggle = (id: string) => {
    const next = selectedCollectionIds.includes(id)
      ? selectedCollectionIds.filter((c) => c !== id)
      : [...selectedCollectionIds, id];
    onCollectionChange(next);
  };

  return (
    <Collapsible open={isOpen} onOpenChange={onOpenChange}>
      <CollapsibleContent>
        <div className="border-b bg-muted/30 px-4 py-3 space-y-4">
          <div>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Collections
            </h4>
            {collections.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {collections.map((col) => (
                  <label
                    key={col.id}
                    className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted"
                  >
                    <Checkbox
                      checked={selectedCollectionIds.includes(col.id)}
                      onCheckedChange={() => handleCollectionToggle(col.id)}
                    />
                    <span className="truncate">{col.name}</span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {col.document_count}
                    </span>
                  </label>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No collections available
              </p>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                LLM Model
              </h4>
              <LLMModelSelector
                models={llmModels}
                selectedModel={selectedLlmModel}
                onSelect={onLlmModelChange}
              />
            </div>
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Embedding Model
              </h4>
              <EmbedModelSelector
                models={embedModels}
                selectedModel={selectedEmbedModel}
                onSelect={onEmbedModelChange}
              />
            </div>
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
