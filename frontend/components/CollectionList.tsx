"use client";

import React from "react";
import { useCollections } from "@/hooks/useCollections";
import CollectionCard from "@/components/CollectionCard";
import CreateCollectionDialog from "@/components/CreateCollectionDialog";

// Loading skeleton card
function SkeletonCard() {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 animate-pulse flex flex-col gap-3">
      <div className="h-4 w-2/3 rounded bg-gray-200" />
      <div className="h-3 w-full rounded bg-gray-100" />
      <div className="h-3 w-1/2 rounded bg-gray-100" />
      <div className="h-3 w-1/3 rounded bg-gray-100 mt-2" />
    </div>
  );
}

export default function CollectionList() {
  const { collections, isLoading, isError, mutate } = useCollections();

  const handleCreated = () => {
    mutate();
  };

  const handleDelete = () => {
    mutate();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-gray-900">Collections</h1>
        <CreateCollectionDialog onCreated={handleCreated} />
      </div>

      {isError ? (
        <div
          className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          role="alert"
        >
          Failed to load collections. Please try again.
        </div>
      ) : isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[...Array(3)].map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : collections !== undefined && collections.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {collections.map((collection) => (
            <CollectionCard
              key={collection.id}
              collection={collection}
              onDelete={handleDelete}
            />
          ))}
        </div>
      ) : (
        // Empty state
        <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-gray-300 py-16 px-6 text-center">
          <p className="text-base font-medium text-gray-700 mb-1">
            No collections yet
          </p>
          <p className="text-sm text-gray-500 mb-5">
            Create your first collection to start uploading documents.
          </p>
          <CreateCollectionDialog onCreated={handleCreated} />
        </div>
      )}
    </div>
  );
}
