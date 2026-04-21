"use client";

import React from "react";
import type { Collection } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Settings2, Plus } from "lucide-react";

interface ChatToolbarProps {
  collections: Collection[];
  model: string;
  onNewChat: () => void;
  onToggleConfig: () => void;
  isConfigOpen: boolean;
}

export const ChatToolbar = React.memo(function ChatToolbar({
  collections,
  model,
  onNewChat,
  onToggleConfig,
  isConfigOpen,
}: ChatToolbarProps) {
  return (
    <div className="flex h-10 items-center gap-2 border-b px-4 bg-background">
      <div className="flex flex-1 items-center gap-2 overflow-hidden">
        {collections.length > 0 ? (
          collections.map((col) => (
            <Badge key={col.id} variant="secondary" className="truncate">
              {col.name}
            </Badge>
          ))
        ) : (
          <span className="text-sm text-muted-foreground">
            Select a collection
          </span>
        )}
      </div>

      <Badge variant="outline">{model}</Badge>

      <Button
        variant="ghost"
        size="icon"
        className="min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0"
        onClick={onToggleConfig}
        aria-label={isConfigOpen ? "Close config panel" : "Open config panel"}
        aria-expanded={isConfigOpen}
      >
        <Settings2 className="h-4 w-4" />
      </Button>

      <Button
        variant="ghost"
        size="icon"
        className="min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0"
        onClick={onNewChat}
        aria-label="New chat"
      >
        <Plus className="h-4 w-4" />
      </Button>
    </div>
  );
});
