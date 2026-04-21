"use client";

import React from "react";
import useSWR from "swr";
import { getStats } from "@/lib/api";
import { useCollections } from "@/hooks/useCollections";
import type { Collection, SystemStats } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

// ─── CollectionRow ────────────────────────────────────────────────────────────

interface CollectionRowProps {
  collection: Collection;
}

const CollectionRow = React.memo(function CollectionRow({
  collection,
}: CollectionRowProps) {
  return (
    <tr className="border-b border-border hover:bg-card">
      <td className="px-4 py-3 text-sm font-medium text-foreground">
        {collection.name}
      </td>
      <td className="px-4 py-3 text-sm text-muted-foreground">
        {collection.description ?? (
          <span className="text-muted-foreground">—</span>
        )}
      </td>
      <td className="px-4 py-3 text-right text-sm text-foreground">
        {collection.document_count}
      </td>
    </tr>
  );
});

// ─── CollectionStats ──────────────────────────────────────────────────────────

export function CollectionStats() {
  // Parallel SWR fetches — independent keys
  const {
    collections,
    isLoading: collectionsLoading,
    isError: collectionsError,
  } = useCollections();

  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
  } = useSWR<SystemStats>("/api/stats", getStats, {
    revalidateOnFocus: false,
  });

  const isLoading = collectionsLoading || statsLoading;
  const hasError = collectionsError || statsError;

  if (isLoading) {
    return (
      <section>
        <h2 className="mb-4 text-lg font-semibold text-foreground">
          Collection Statistics
        </h2>
        <Skeleton className="h-40 w-full" />
      </section>
    );
  }

  if (hasError) {
    return (
      <section>
        <h2 className="mb-4 text-lg font-semibold text-foreground">
          Collection Statistics
        </h2>
        <p className="text-sm text-destructive">
          Failed to load collection statistics.
        </p>
      </section>
    );
  }

  return (
    <section>
      <h2 className="mb-4 text-lg font-semibold text-foreground">
        Collection Statistics
      </h2>

      {/* Aggregate summary from getStats() */}
      {stats ? (
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded-lg bg-card p-4 text-center">
            <p className="text-2xl font-bold text-chart-1">
              {stats.total_collections}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Collections
            </p>
          </div>
          <div className="rounded-lg bg-card p-4 text-center">
            <p className="text-2xl font-bold text-chart-2">
              {stats.total_documents}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Documents
            </p>
          </div>
          <div className="rounded-lg bg-card p-4 text-center">
            <p className="text-2xl font-bold text-chart-3">
              {stats.total_chunks}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Total Chunks
            </p>
          </div>
          <div className="rounded-lg bg-card p-4 text-center">
            <p className="text-2xl font-bold text-chart-4">
              {stats.total_queries}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Total Queries
            </p>
          </div>
        </div>
      ) : null}

      {/* Per-collection breakdown — document_count per collection */}
      {collections && collections.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="min-w-full divide-y divide-border text-left">
            <thead className="bg-card">
              <tr>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Collection
                </th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Description
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Documents
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-background">
              {collections.map((col) => (
                <CollectionRow key={col.id} collection={col} />
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          No collections found.
        </p>
      )}
    </section>
  );
}
