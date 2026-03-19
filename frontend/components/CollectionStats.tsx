"use client";

import React from "react";
import useSWR from "swr";
import { getStats } from "@/lib/api";
import { useCollections } from "@/hooks/useCollections";
import type { Collection, SystemStats } from "@/lib/types";

// ─── CollectionRow ────────────────────────────────────────────────────────────

interface CollectionRowProps {
  collection: Collection;
}

const CollectionRow = React.memo(function CollectionRow({
  collection,
}: CollectionRowProps) {
  return (
    <tr className="border-b border-gray-100 hover:bg-gray-50">
      <td className="px-4 py-3 text-sm font-medium text-gray-900">
        {collection.name}
      </td>
      <td className="px-4 py-3 text-sm text-gray-600">
        {collection.description ?? <span className="text-gray-400">—</span>}
      </td>
      <td className="px-4 py-3 text-right text-sm text-gray-700">
        {collection.document_count}
      </td>
    </tr>
  );
});

// ─── CollectionStats ──────────────────────────────────────────────────────────

export function CollectionStats() {
  // Parallel SWR fetches — independent keys
  const { collections, isLoading: collectionsLoading, isError: collectionsError } =
    useCollections();

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
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          Collection Statistics
        </h2>
        <div className="h-40 animate-pulse rounded-lg bg-gray-100" />
      </section>
    );
  }

  if (hasError) {
    return (
      <section>
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          Collection Statistics
        </h2>
        <p className="text-sm text-red-600">Failed to load collection statistics.</p>
      </section>
    );
  }

  return (
    <section>
      <h2 className="mb-4 text-lg font-semibold text-gray-900">
        Collection Statistics
      </h2>

      {/* Aggregate summary from getStats() */}
      {stats ? (
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded-lg bg-indigo-50 p-4 text-center">
            <p className="text-2xl font-bold text-indigo-700">
              {stats.total_collections}
            </p>
            <p className="mt-1 text-xs text-indigo-600">Collections</p>
          </div>
          <div className="rounded-lg bg-blue-50 p-4 text-center">
            <p className="text-2xl font-bold text-blue-700">
              {stats.total_documents}
            </p>
            <p className="mt-1 text-xs text-blue-600">Documents</p>
          </div>
          <div className="rounded-lg bg-purple-50 p-4 text-center">
            <p className="text-2xl font-bold text-purple-700">
              {stats.total_chunks}
            </p>
            <p className="mt-1 text-xs text-purple-600">Total Chunks</p>
          </div>
          <div className="rounded-lg bg-green-50 p-4 text-center">
            <p className="text-2xl font-bold text-green-700">
              {stats.total_queries}
            </p>
            <p className="mt-1 text-xs text-green-600">Total Queries</p>
          </div>
        </div>
      ) : null}

      {/* Per-collection breakdown — document_count per collection */}
      {collections && collections.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-left">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600">
                  Collection
                </th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600">
                  Description
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-600">
                  Documents
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {collections.map((col) => (
                <CollectionRow key={col.id} collection={col} />
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-gray-500">No collections found.</p>
      )}
    </section>
  );
}
