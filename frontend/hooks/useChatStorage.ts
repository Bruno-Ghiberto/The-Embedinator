"use client";

import { useState, useCallback } from "react";
import type { ChatMessage } from "@/lib/types";

interface StoredChat {
  sessionId: string;
  messages: ChatMessage[];
  updatedAt: number;
}

const STORAGE_KEY = "embedinator-chat-session";

function readStorage(): StoredChat | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as StoredChat;
  } catch {
    return null;
  }
}

export function useChatStorage() {
  const [stored] = useState<StoredChat | null>(() => readStorage());

  const saveMessages = useCallback(
    (msgs: ChatMessage[], sessionId: string) => {
      if (typeof window === "undefined") return;
      const data: StoredChat = {
        sessionId,
        messages: msgs,
        updatedAt: Date.now(),
      };
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      } catch {
        // localStorage full or unavailable
      }
    },
    [],
  );

  const clearChat = useCallback(() => {
    if (typeof window === "undefined") return;
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return {
    storedMessages: stored?.messages ?? [],
    storedSessionId: stored?.sessionId ?? null,
    saveMessages,
    clearChat,
  };
}
