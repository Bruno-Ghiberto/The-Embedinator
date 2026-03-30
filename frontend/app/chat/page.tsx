"use client";

import { Suspense, useMemo } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useState, useCallback, useEffect, useRef } from "react";
import { useStreamChat } from "@/hooks/useStreamChat";
import { useChatHistory } from "@/hooks/useChatHistory";
import { useCollections } from "@/hooks/useCollections";
import { useModels } from "@/hooks/useModels";
import Link from "next/link";
import { Database, MessageSquare } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import ChatPanel from "@/components/ChatPanel";
import ChatInput from "@/components/ChatInput";
import { ChatToolbar } from "@/components/ChatToolbar";
import { ChatConfigPanel } from "@/components/ChatConfigPanel";

const DEFAULT_LLM = "qwen2.5:7b";

const SUGGESTED_PROMPTS = [
  "What are the main topics covered in this collection?",
  "Summarize the key findings or conclusions",
  "What are the most important concepts I should understand?",
  "Are there any specific recommendations or action items?",
];

export default function ChatPage() {
  return (
    <Suspense>
      <ChatPageContent />
    </Suspense>
  );
}

function ChatPageContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const sessionParam = searchParams.get("session");

  // Data hooks
  const { collections: allCollections } = useCollections();
  const { llmModels, embedModels } = useModels();
  const {
    activeSession,
    loadSession,
    createSession,
    syncMessages,
  } = useChatHistory();

  // Config panel open/close
  const [isConfigOpen, setIsConfigOpen] = useState(false);

  // Lazy init from URL params
  const [selectedCollectionIds, setSelectedCollectionIds] = useState<string[]>(
    () => searchParams.get("collections")?.split(",").filter(Boolean) ?? [],
  );
  const [llmModel, setLlmModel] = useState<string>(
    () => searchParams.get("llm") ?? DEFAULT_LLM,
  );
  const [embedModel, setEmbedModel] = useState<string | null>(
    () => searchParams.get("embed") ?? null,
  );

  const { messages, isStreaming, sendMessage, abort, setMessages } =
    useStreamChat();

  // Escape key: stop streaming
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && isStreaming) {
        abort();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isStreaming, abort]);

  // Track history session ID for multi-session persistence
  const historySessionIdRef = useRef<string | null>(sessionParam);

  // Guard to load from history only once per session param change
  const sessionLoadedRef = useRef<string | null>(null);

  // Load session from URL param
  useEffect(() => {
    if (sessionParam) {
      loadSession(sessionParam);
    }
  }, [sessionParam, loadSession]);

  // Populate messages from loaded history session
  useEffect(() => {
    if (
      activeSession &&
      sessionParam &&
      sessionLoadedRef.current !== activeSession.id &&
      !isStreaming
    ) {
      setMessages(activeSession.messages);
      sessionLoadedRef.current = activeSession.id;
      historySessionIdRef.current = activeSession.id;
      // Restore config from session
      if (activeSession.config.collectionIds.length > 0) {
        setSelectedCollectionIds(activeSession.config.collectionIds);
      }
      if (activeSession.config.llmModel) {
        setLlmModel(activeSession.config.llmModel);
      }
      if (activeSession.config.embedModel) {
        setEmbedModel(activeSession.config.embedModel);
      }
    }
  }, [activeSession, sessionParam, setMessages, isStreaming]);

  // Save to history when streaming completes (transition: streaming → done)
  const prevStreamingRef = useRef(false);
  useEffect(() => {
    const wasStreaming = prevStreamingRef.current;
    prevStreamingRef.current = isStreaming;

    if (
      wasStreaming &&
      !isStreaming &&
      historySessionIdRef.current &&
      messages.length > 0
    ) {
      syncMessages(historySessionIdRef.current, messages);
    }
  }, [isStreaming, messages, syncMessages]);

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
      // Preserve session param if present
      if (historySessionIdRef.current) {
        params.set("session", historySessionIdRef.current);
      }
      const qs = params.toString();
      router.replace(qs ? `?${qs}` : "/chat", { scroll: false });
    },
    [router],
  );

  const handleCollectionsChange = useCallback(
    (ids: string[]) => {
      setSelectedCollectionIds(ids);
      updateUrlParams(ids, llmModel, embedModel);
    },
    [llmModel, embedModel, updateUrlParams],
  );

  const handleLlmModelChange = useCallback(
    (model: string) => {
      setLlmModel(model);
      updateUrlParams(selectedCollectionIds, model, embedModel);
    },
    [selectedCollectionIds, embedModel, updateUrlParams],
  );

  const handleEmbedModelChange = useCallback(
    (model: string) => {
      setEmbedModel(model);
      updateUrlParams(selectedCollectionIds, llmModel, model);
    },
    [selectedCollectionIds, llmModel, updateUrlParams],
  );

  const handleSubmit = useCallback(
    (message: string) => {
      // Create history session on first message
      if (!historySessionIdRef.current) {
        historySessionIdRef.current = createSession({
          collectionIds: selectedCollectionIds,
          llmModel,
          embedModel,
        });
      }

      sendMessage({
        message,
        collection_ids: selectedCollectionIds,
        llm_model: llmModel,
        embed_model: embedModel,
      });
    },
    [selectedCollectionIds, llmModel, embedModel, sendMessage, createSession],
  );

  // Retry: remove the error message(s) and resend the last user message
  const handleRetry = useCallback(() => {
    const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUserMsg) return;
    // Remove error assistant messages from the end
    setMessages((prev) => {
      const trimmed = [...prev];
      while (trimmed.length > 0 && trimmed[trimmed.length - 1].isError) {
        trimmed.pop();
      }
      // Also remove the last user message — it will be re-added by sendMessage
      if (trimmed.length > 0 && trimmed[trimmed.length - 1].role === "user") {
        trimmed.pop();
      }
      return trimmed;
    });
    sendMessage({
      message: lastUserMsg.content,
      collection_ids: selectedCollectionIds,
      llm_model: llmModel,
      embed_model: embedModel,
    });
  }, [messages, setMessages, sendMessage, selectedCollectionIds, llmModel, embedModel],
  );

  const handleNewChat = useCallback(() => {
    setMessages([]);
    historySessionIdRef.current = null;
    sessionLoadedRef.current = null;
    router.push("/chat");
  }, [setMessages, router]);

  // Handle "New Chat" from sidebar button (?new=1 param)
  useEffect(() => {
    if (searchParams.get("new")) {
      handleNewChat();
      router.replace("/chat", { scroll: false });
    }
  }, [searchParams, handleNewChat, router]);

  // Derive selected Collection objects for the toolbar
  const selectedCollections = useMemo(
    () =>
      (allCollections ?? []).filter((c) =>
        selectedCollectionIds.includes(c.id),
      ),
    [allCollections, selectedCollectionIds],
  );

  return (
    <div className="flex flex-1 flex-col min-h-0">
      <ChatToolbar
        collections={selectedCollections}
        model={llmModel}
        onNewChat={handleNewChat}
        onToggleConfig={() => setIsConfigOpen((v) => !v)}
        isConfigOpen={isConfigOpen}
      />
      <ChatConfigPanel
        isOpen={isConfigOpen}
        onOpenChange={setIsConfigOpen}
        collections={allCollections ?? []}
        selectedCollectionIds={selectedCollectionIds}
        onCollectionChange={handleCollectionsChange}
        llmModels={llmModels ?? []}
        embedModels={embedModels ?? []}
        selectedLlmModel={llmModel}
        selectedEmbedModel={embedModel ?? ""}
        onLlmModelChange={handleLlmModelChange}
        onEmbedModelChange={handleEmbedModelChange}
      />
      {/* Empty state variants (ternary chain per Vercel rendering-conditional-render) */}
      {allCollections !== undefined && allCollections.length === 0 ? (
        // State 1: No collections — onboarding
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="text-center max-w-md space-y-4">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-muted">
              <Database className="h-8 w-8 text-muted-foreground" />
            </div>
            <h2 className="text-xl font-semibold">No collections yet</h2>
            <p className="text-muted-foreground">
              Create a collection and upload documents to start chatting with
              your knowledge base.
            </p>
            <div className="mx-auto flex w-fit flex-col gap-2 text-left">
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                  1
                </span>
                Create a collection
              </div>
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                  2
                </span>
                Upload documents
              </div>
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                  3
                </span>
                Ask questions
              </div>
            </div>
            <Link href="/collections" className={buttonVariants()}>
              Go to Collections
            </Link>
          </div>
        </div>
      ) : (allCollections ?? []).length > 0 &&
        selectedCollectionIds.length === 0 ? (
        // State 2: Collections exist, none selected
        <div className="flex-1 flex flex-col items-center justify-center px-4">
          <h2 className="text-lg font-semibold mb-4">
            Select a collection to start chatting
          </h2>
          <div className="grid w-full max-w-2xl grid-cols-1 gap-3 sm:grid-cols-2">
            {(allCollections ?? []).map((collection) => (
              <Card
                key={collection.id}
                className="cursor-pointer transition-colors hover:border-primary/50"
                onClick={() => handleCollectionsChange([collection.id])}
              >
                <CardContent className="p-4">
                  <h3 className="font-medium truncate">{collection.name}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {collection.document_count ?? 0} documents
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      ) : selectedCollectionIds.length > 0 && messages.length === 0 ? (
        // State 3: Collection selected, no messages — suggested prompts
        <div className="flex-1 flex flex-col items-center justify-center px-4">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <MessageSquare className="h-6 w-6 text-primary" />
          </div>
          <h2 className="text-lg font-semibold mb-2">
            What would you like to know?
          </h2>
          <p className="mb-6 text-sm text-muted-foreground">
            Try one of these suggested questions
          </p>
          <div className="grid w-full max-w-2xl grid-cols-1 gap-2 sm:grid-cols-2">
            {SUGGESTED_PROMPTS.map((prompt) => (
              <Card
                key={prompt}
                className="cursor-pointer transition-colors hover:border-primary/50"
                onClick={() => handleSubmit(prompt)}
              >
                <CardContent className="p-3">
                  <p className="text-sm">{prompt}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      ) : (
        // State 4: Has messages — normal chat
        <ChatPanel
          messages={messages}
          isStreaming={isStreaming}
          onSubmit={handleSubmit}
          onRetry={handleRetry}
        />
      )}
      {/* ChatInput: hidden when no collections exist */}
      {allCollections !== undefined && allCollections.length === 0 ? null : (
        <ChatInput
          isStreaming={isStreaming}
          selectedCollections={selectedCollectionIds}
          onSubmit={handleSubmit}
          onStop={abort}
        />
      )}
    </div>
  );
}
