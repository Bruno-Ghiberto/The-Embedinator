"use client";

import React, { useState, useMemo } from "react";
import { Search } from "lucide-react";
import { useCollections } from "@/hooks/useCollections";
import CollectionCard from "@/components/CollectionCard";
import CreateCollectionDialog from "@/components/CreateCollectionDialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";

function SkeletonCard() {
  return (
    <div className="flex flex-col gap-4 rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <div className="flex items-start justify-between">
        <Skeleton className="h-5 w-2/3" />
        <Skeleton className="size-5 rounded-full" />
      </div>
      <Skeleton className="h-4 w-full" />
      <div className="flex gap-2">
        <Skeleton className="h-5 w-16 rounded-full" />
        <Skeleton className="h-5 w-20 rounded-full" />
        <Skeleton className="h-5 w-24 rounded-full" />
      </div>
    </div>
  );
}

export default function CollectionList() {
  const { collections, isLoading, isError, mutate } = useCollections();
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    if (!collections) return [];
    if (!search.trim()) return collections;
    const q = search.toLowerCase();
    return collections.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        (c.description && c.description.toLowerCase().includes(q))
    );
  }, [collections, search]);

  const handleCreated = () => {
    mutate();
  };

  const handleDelete = () => {
    mutate();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-[var(--color-text-primary)]">
          Collections
        </h1>
        <CreateCollectionDialog onCreated={handleCreated} />
      </div>

      {!isLoading && !isError && collections && collections.length > 0 && (
        <div className="relative mb-6">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-[var(--color-text-muted)]" />
          <Input
            type="search"
            placeholder="Search collections…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8"
          />
        </div>
      )}

      {isError ? (
        <div
          className="rounded-md border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive"
          role="alert"
        >
          Failed to load collections. Please try again.
        </div>
      ) : isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-[var(--space-card-gap)]">
          {[...Array(3)].map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : filtered.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-[var(--space-card-gap)]">
          {filtered.map((collection) => (
            <CollectionCard
              key={collection.id}
              collection={collection}
              onDelete={handleDelete}
            />
          ))}
        </div>
      ) : search.trim() ? (
        <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-[var(--color-border)] py-16 px-6 text-center">
          <p className="text-base font-medium text-[var(--color-text-primary)] mb-1">
            No matching collections
          </p>
          <p className="text-sm text-[var(--color-text-muted)]">
            Try a different search term.
          </p>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-[var(--color-border)] py-16 px-6 text-center">
          <p className="text-base font-medium text-[var(--color-text-primary)] mb-1">
            No collections yet
          </p>
          <p className="text-sm text-[var(--color-text-muted)] mb-5">
            Create your first collection to start uploading documents.
          </p>
          <CreateCollectionDialog onCreated={handleCreated} />
        </div>
      )}
    </div>
  );
}
