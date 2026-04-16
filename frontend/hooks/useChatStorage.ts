"use client";

import { useCallback } from "react";

const STORAGE_KEY = "embedinator-sessions:v1";
const SYNC_EVENT = "embedinator-sessions-changed";

export interface UseChatStorageReturn {
  clearChat: () => void;
}

export function useChatStorage(): UseChatStorageReturn {
  const clearChat = useCallback(() => {
    try {
      localStorage.removeItem(STORAGE_KEY);
      window.dispatchEvent(new CustomEvent(SYNC_EVENT));
    } catch {
      /* private browsing or quota */
    }
  }, []);

  return { clearChat };
}
