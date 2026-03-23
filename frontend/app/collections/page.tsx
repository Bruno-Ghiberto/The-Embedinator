"use client";

import React, { Component } from "react";
import { FolderPlus } from "lucide-react";
import CollectionList from "@/components/CollectionList";
import CreateCollectionDialog from "@/components/CreateCollectionDialog";
import { useCollections } from "@/hooks/useCollections";

// ─── Error Boundary ───────────────────────────────────────────────────────────

interface ErrorBoundaryState {
  hasError: boolean;
  message: string;
}

class CollectionErrorBoundary extends Component<
  { children: React.ReactNode },
  ErrorBoundaryState
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(err: unknown): ErrorBoundaryState {
    const message =
      err instanceof Error ? err.message : "An unexpected error occurred.";
    return { hasError: true, message };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          className="rounded-md border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive"
          role="alert"
        >
          {this.state.message}
        </div>
      );
    }
    return this.props.children;
  }
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function CollectionsPage() {
  const { collections, isLoading, mutate } = useCollections();

  const showEmptyState =
    !isLoading && collections !== undefined && collections.length === 0;

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <CollectionErrorBoundary>
        {showEmptyState ? (
          <div>
            <div className="mb-6 flex items-center justify-between">
              <h1 className="text-xl font-semibold text-foreground">
                Collections
              </h1>
            </div>
            <div className="flex items-center justify-center min-h-[400px]">
              <div className="text-center space-y-4">
                <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-muted">
                  <FolderPlus className="h-10 w-10 text-muted-foreground" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold">
                    No collections yet
                  </h2>
                  <p className="mx-auto mt-2 max-w-sm text-muted-foreground">
                    Collections are named groups of documents. Create your first
                    collection to start building your knowledge base.
                  </p>
                </div>
                <CreateCollectionDialog onCreated={() => mutate()} />
              </div>
            </div>
          </div>
        ) : (
          <CollectionList />
        )}
      </CollectionErrorBoundary>
    </main>
  );
}
