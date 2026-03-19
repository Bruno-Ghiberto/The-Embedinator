"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useState, useCallback } from "react";
import { useStreamChat } from "@/hooks/useStreamChat";
import ChatPanel from "@/components/ChatPanel";
import ChatInput from "@/components/ChatInput";
import ChatSidebar from "@/components/ChatSidebar";

const DEFAULT_LLM = "qwen2.5:7b";

export default function ChatPage() {
  const searchParams = useSearchParams();
  const router = useRouter();

  // Lazy init from URL params
  const [selectedCollections, setSelectedCollections] = useState<string[]>(
    () => searchParams.get("collections")?.split(",").filter(Boolean) ?? [],
  );
  const [llmModel, setLlmModel] = useState<string>(
    () => searchParams.get("llm") ?? DEFAULT_LLM,
  );
  const [embedModel, setEmbedModel] = useState<string | null>(
    () => searchParams.get("embed") ?? null,
  );

  const { messages, isStreaming, sendMessage } = useStreamChat();

  // Sync state to URL params
  const updateUrlParams = useCallback(
    (collections: string[], llm: string, embed: string | null) => {
      const params = new URLSearchParams();
      if (collections.length > 0) {
        params.set("collections", collections.join(","));
      }
      if (llm !== DEFAULT_LLM) {
        params.set("llm", llm);
      }
      if (embed) {
        params.set("embed", embed);
      }
      const qs = params.toString();
      router.replace(qs ? `?${qs}` : "/chat", { scroll: false });
    },
    [router],
  );

  const handleCollectionsChange = useCallback(
    (ids: string[]) => {
      setSelectedCollections(ids);
      updateUrlParams(ids, llmModel, embedModel);
    },
    [llmModel, embedModel, updateUrlParams],
  );

  const handleLLMModelChange = useCallback(
    (model: string) => {
      setLlmModel(model);
      updateUrlParams(selectedCollections, model, embedModel);
    },
    [selectedCollections, embedModel, updateUrlParams],
  );

  const handleEmbedModelChange = useCallback(
    (model: string | null) => {
      setEmbedModel(model);
      updateUrlParams(selectedCollections, llmModel, model);
    },
    [selectedCollections, llmModel, updateUrlParams],
  );

  const handleSubmit = useCallback(
    (message: string) => {
      sendMessage({
        message,
        collection_ids: selectedCollections,
        llm_model: llmModel,
        embed_model: embedModel,
      });
    },
    [selectedCollections, llmModel, embedModel, sendMessage],
  );

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      <ChatSidebar
        selectedCollections={selectedCollections}
        onCollectionsChange={handleCollectionsChange}
        llmModel={llmModel}
        onLLMModelChange={handleLLMModelChange}
        embedModel={embedModel}
        onEmbedModelChange={handleEmbedModelChange}
      />
      <div className="flex flex-1 flex-col">
        <ChatPanel messages={messages} isStreaming={isStreaming} />
        <ChatInput
          isStreaming={isStreaming}
          selectedCollections={selectedCollections}
          onSubmit={handleSubmit}
        />
      </div>
    </div>
  );
}
