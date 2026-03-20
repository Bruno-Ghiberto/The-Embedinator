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
    <tr className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface)]">
      <td className="px-4 py-3 text-sm font-medium text-[var(--color-text-primary)]">
        {collection.name}
      </td>
      <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
        {collection.description ?? (
          <span className="text-[var(--color-text-muted)]">—</span>
        )}
      </td>
      <td className="px-4 py-3 text-right text-sm text-[var(--color-text-primary)]">
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
        <h2 className="mb-4 text-lg font-semibold text-[var(--color-text-primary)]">
          Collection Statistics
        </h2>
        <Skeleton className="h-40 w-full" />
      </section>
    );
  }

  if (hasError) {
    return (
      <section>
        <h2 className="mb-4 text-lg font-semibold text-[var(--color-text-primary)]">
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
      <h2 className="mb-4 text-lg font-semibold text-[var(--color-text-primary)]">
        Collection Statistics
      </h2>

      {/* Aggregate summary from getStats() */}
      {stats ? (
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded-lg bg-[var(--color-surface)] p-4 text-center">
            <p className="text-2xl font-bold text-chart-1">
              {stats.total_collections}
            </p>
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">
              Collections
            </p>
          </div>
          <div className="rounded-lg bg-[var(--color-surface)] p-4 text-center">
            <p className="text-2xl font-bold text-chart-2">
              {stats.total_documents}
            </p>
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">
              Documents
            </p>
          </div>
          <div className="rounded-lg bg-[var(--color-surface)] p-4 text-center">
            <p className="text-2xl font-bold text-chart-3">
              {stats.total_chunks}
            </p>
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">
              Total Chunks
            </p>
          </div>
          <div className="rounded-lg bg-[var(--color-surface)] p-4 text-center">
            <p className="text-2xl font-bold text-chart-4">
              {stats.total_queries}
            </p>
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">
              Total Queries
            </p>
          </div>
        </div>
      ) : null}

      {/* Per-collection breakdown — document_count per collection */}
      {collections && collections.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-[var(--color-border)]">
          <table className="min-w-full divide-y divide-[var(--color-border)] text-left">
            <thead className="bg-[var(--color-surface)]">
              <tr>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
                  Collection
                </th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
                  Description
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
                  Documents
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)] bg-[var(--color-background)]">
              {collections.map((col) => (
                <CollectionRow key={col.id} collection={col} />
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-[var(--color-text-muted)]">
          No collections found.
        </p>
      )}
    </section>
  );
}
