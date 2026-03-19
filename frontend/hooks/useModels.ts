"use client";

import useSWR from "swr";
import { getLLMModels, getEmbedModels } from "@/lib/api";
import type { ModelInfo } from "@/lib/types";

export function useModels() {
  const {
    data: llmModels,
    error: llmError,
  } = useSWR<ModelInfo[]>("/api/models/llm", getLLMModels, {
    revalidateOnFocus: false,
  });

  const {
    data: embedModels,
    error: embedError,
  } = useSWR<ModelInfo[]>("/api/models/embed", getEmbedModels, {
    revalidateOnFocus: false,
  });

  return {
    llmModels,
    embedModels,
    isLoading: (!llmError && !llmModels) || (!embedError && !embedModels),
    isError: llmError || embedError,
  };
}
