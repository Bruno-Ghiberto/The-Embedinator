"use client";

import useSWR from "swr";
import { getCollections } from "@/lib/api";
import type { Collection } from "@/lib/types";

export function useCollections() {
  const { data, error, mutate } = useSWR<Collection[]>(
    "/api/collections",
    getCollections,
    { revalidateOnFocus: false },
  );

  return {
    collections: data,
    isLoading: !error && !data,
    isError: error,
    mutate,
  };
}
