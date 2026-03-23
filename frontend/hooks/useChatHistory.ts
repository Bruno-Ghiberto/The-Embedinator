"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import type { ChatMessage } from "@/lib/types";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface SessionConfig {
  collectionIds: string[];
  llmModel: string;
  embedModel: string | null;
}

export interface ChatSessionSummary {
  id: string;
  title: string;
  messageCount: number;
  updatedAt: string;
}

export interface ChatSessionData extends ChatSessionSummary {
  messages: ChatMessage[];
  config: SessionConfig;
  createdAt: string;
}

interface SessionStore {
  version: 1;
  sessions: Record<string, ChatSessionData>;
}

export interface UseChatHistoryReturn {
  sessions: ChatSessionSummary[];
  activeSession: ChatSessionData | null;
  isLoading: boolean;
  createSession: (config: SessionConfig) => string;
  loadSession: (id: string) => void;
  saveMessage: (sessionId: string, message: ChatMessage) => void;
  syncMessages: (sessionId: string, messages: ChatMessage[]) => void;
  deleteSession: (id: string) => void;
  renameSession: (id: string, title: string) => void;
  searchSessions: (query: string) => ChatSessionSummary[];
}

// ─── Constants ───────────────────────────────────────────────────────────────

const STORAGE_KEY = "embedinator-sessions:v1";
const LEGACY_KEY = "embedinator-chat-session";
const MAX_SESSIONS = 50;
const SYNC_EVENT = "embedinator-sessions-changed";
const EMPTY_STORE: SessionStore = { version: 1, sessions: {} };

// ─── Helpers ─────────────────────────────────────────────────────────────────

function readStore(): SessionStore {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw) as SessionStore;
  } catch {
    /* private browsing or corrupt data */
  }
  return { version: 1, sessions: {} };
}

function writeStore(store: SessionStore): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
    window.dispatchEvent(new CustomEvent(SYNC_EVENT));
  } catch {
    /* quota exceeded or private browsing */
  }
}

function evictOldest(
  sessions: Record<string, ChatSessionData>,
): Record<string, ChatSessionData> {
  const entries = Object.entries(sessions);
  if (entries.length <= MAX_SESSIONS) return sessions;
  const sorted = entries.sort((a, b) =>
    a[1].updatedAt.localeCompare(b[1].updatedAt),
  );
  const toRemove = sorted.slice(0, entries.length - MAX_SESSIONS);
  const result = { ...sessions };
  for (const [id] of toRemove) {
    delete result[id];
  }
  return result;
}

function toSummary(session: ChatSessionData): ChatSessionSummary {
  return {
    id: session.id,
    title: session.title,
    messageCount: session.messageCount,
    updatedAt: session.updatedAt,
  };
}

function deriveTitle(
  currentTitle: string,
  messages: ChatMessage[],
): string {
  if (currentTitle !== "New Chat") return currentTitle;
  const firstUserMsg = messages.find((m) => m.role === "user");
  if (!firstUserMsg) return currentTitle;
  return firstUserMsg.content.slice(0, 40) || "New Chat";
}

// ─── Hook ────────────────────────────────────────────────────────────────────

export function useChatHistory(): UseChatHistoryReturn {
  const [store, setStore] = useState<SessionStore>(EMPTY_STORE);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Read on mount — hydration safe (localStorage in useEffect only)
  useEffect(() => {
    let currentStore = readStore();

    // Migration from legacy single-session storage
    if (Object.keys(currentStore.sessions).length === 0) {
      try {
        const oldData = localStorage.getItem(LEGACY_KEY);
        if (oldData) {
          const parsed = JSON.parse(oldData);
          if (parsed?.messages?.length > 0) {
            const id = crypto.randomUUID();
            const now = new Date().toISOString();
            const firstUserMsg = (parsed.messages as ChatMessage[]).find(
              (m) => m.role === "user",
            );
            const title = firstUserMsg
              ? firstUserMsg.content.slice(0, 40)
              : "Migrated Chat";
            const session: ChatSessionData = {
              id,
              title,
              messageCount: parsed.messages.length,
              messages: parsed.messages,
              config: {
                collectionIds: [],
                llmModel: "qwen2.5:7b",
                embedModel: null,
              },
              createdAt: now,
              updatedAt: now,
            };
            currentStore = { version: 1, sessions: { [id]: session } };
            writeStore(currentStore);
            localStorage.removeItem(LEGACY_KEY);
          }
        }
      } catch {
        /* silent migration failure */
      }
    }

    setStore(currentStore);
    setIsLoading(false);
  }, []);

  // Cross-component and cross-tab sync
  useEffect(() => {
    const handleSync = () => {
      setStore(readStore());
    };
    const handleStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) handleSync();
    };
    window.addEventListener(SYNC_EVENT, handleSync);
    window.addEventListener("storage", handleStorage);
    return () => {
      window.removeEventListener(SYNC_EVENT, handleSync);
      window.removeEventListener("storage", handleStorage);
    };
  }, []);

  // Sorted sessions (most recent first)
  const sessions = useMemo<ChatSessionSummary[]>(
    () =>
      Object.values(store.sessions)
        .map(toSummary)
        .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)),
    [store],
  );

  const activeSession = useMemo<ChatSessionData | null>(
    () => (activeSessionId ? (store.sessions[activeSessionId] ?? null) : null),
    [store, activeSessionId],
  );

  // Always read latest from localStorage to avoid stale state across components
  const updateStore = useCallback(
    (updater: (prev: SessionStore) => SessionStore) => {
      const current = readStore();
      const next = updater(current);
      writeStore(next);
      setStore(next);
    },
    [],
  );

  const createSession = useCallback(
    (config: SessionConfig): string => {
      const id = crypto.randomUUID();
      const now = new Date().toISOString();
      const session: ChatSessionData = {
        id,
        title: "New Chat",
        messageCount: 0,
        messages: [],
        config,
        createdAt: now,
        updatedAt: now,
      };
      updateStore((prev) => ({
        ...prev,
        sessions: evictOldest({ ...prev.sessions, [id]: session }),
      }));
      setActiveSessionId(id);
      return id;
    },
    [updateStore],
  );

  const loadSession = useCallback((id: string) => {
    setActiveSessionId(id);
  }, []);

  const saveMessage = useCallback(
    (sessionId: string, message: ChatMessage) => {
      updateStore((prev) => {
        const session = prev.sessions[sessionId];
        if (!session) return prev;
        const updatedMessages = [...session.messages, message];
        return {
          ...prev,
          sessions: {
            ...prev.sessions,
            [sessionId]: {
              ...session,
              messages: updatedMessages,
              messageCount: updatedMessages.length,
              title: deriveTitle(session.title, updatedMessages),
              updatedAt: new Date().toISOString(),
            },
          },
        };
      });
    },
    [updateStore],
  );

  const syncMessages = useCallback(
    (sessionId: string, messages: ChatMessage[]) => {
      updateStore((prev) => {
        const session = prev.sessions[sessionId];
        if (!session) return prev;
        return {
          ...prev,
          sessions: {
            ...prev.sessions,
            [sessionId]: {
              ...session,
              messages,
              messageCount: messages.length,
              title: deriveTitle(session.title, messages),
              updatedAt: new Date().toISOString(),
            },
          },
        };
      });
    },
    [updateStore],
  );

  const deleteSession = useCallback(
    (id: string) => {
      updateStore((prev) => {
        const { [id]: _, ...rest } = prev.sessions;
        return { ...prev, sessions: rest };
      });
      setActiveSessionId((current) => (current === id ? null : current));
    },
    [updateStore],
  );

  const renameSession = useCallback(
    (id: string, title: string) => {
      updateStore((prev) => {
        const session = prev.sessions[id];
        if (!session) return prev;
        return {
          ...prev,
          sessions: {
            ...prev.sessions,
            [id]: { ...session, title, updatedAt: new Date().toISOString() },
          },
        };
      });
    },
    [updateStore],
  );

  const searchSessions = useCallback(
    (query: string): ChatSessionSummary[] => {
      const lower = query.toLowerCase();
      return Object.values(store.sessions)
        .filter((s) => s.title.toLowerCase().includes(lower))
        .map(toSummary)
        .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
    },
    [store],
  );

  return {
    sessions,
    activeSession,
    isLoading,
    createSession,
    loadSession,
    saveMessage,
    syncMessages,
    deleteSession,
    renameSession,
    searchSessions,
  };
}
