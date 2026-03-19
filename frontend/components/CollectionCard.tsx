"use client";

import React, { memo, useState } from "react";
import Link from "next/link";
import * as Dialog from "@radix-ui/react-dialog";
import { deleteCollection } from "@/lib/api";
import type { Collection } from "@/lib/types";

interface CollectionCardProps {
  collection: Collection;
  onDelete: (id: string) => void;
}

const CollectionCard = memo(function CollectionCard({
  collection,
  onDelete,
}: CollectionCardProps) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleConfirmDelete = async () => {
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteCollection(collection.id);
      setDialogOpen(false);
      onDelete(collection.id);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to delete collection";
      setDeleteError(message);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm flex flex-col gap-3 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-base font-semibold text-gray-900 truncate">
          {collection.name}
        </h3>
        <Dialog.Root open={dialogOpen} onOpenChange={setDialogOpen}>
          <Dialog.Trigger asChild>
            <button
              className="shrink-0 text-sm text-red-500 hover:text-red-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400 rounded"
              aria-label={`Delete collection ${collection.name}`}
            >
              Delete
            </button>
          </Dialog.Trigger>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 bg-black/40 z-40" />
            <Dialog.Content
              className="fixed left-1/2 top-1/2 z-50 w-full max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-lg bg-white p-6 shadow-xl focus:outline-none"
              aria-describedby="delete-dialog-desc"
            >
              <Dialog.Title className="text-base font-semibold text-gray-900 mb-2">
                Delete collection?
              </Dialog.Title>
              <p id="delete-dialog-desc" className="text-sm text-gray-600 mb-4">
                This will permanently remove{" "}
                <strong>{collection.name}</strong> and all its documents. This
                action cannot be undone.
              </p>
              {deleteError !== null ? (
                <p className="text-sm text-red-600 mb-3" role="alert">
                  {deleteError}
                </p>
              ) : null}
              <div className="flex justify-end gap-3">
                <Dialog.Close asChild>
                  <button
                    className="rounded px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-400"
                    disabled={deleting}
                  >
                    Cancel
                  </button>
                </Dialog.Close>
                <button
                  onClick={handleConfirmDelete}
                  disabled={deleting}
                  className="rounded px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                >
                  {deleting ? "Deleting…" : "Delete"}
                </button>
              </div>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
      </div>

      {collection.description !== null ? (
        <p className="text-sm text-gray-500 line-clamp-2">
          {collection.description}
        </p>
      ) : null}

      <dl className="text-xs text-gray-500 grid grid-cols-2 gap-1">
        <dt className="font-medium text-gray-700">Documents</dt>
        <dd>{collection.document_count}</dd>
        <dt className="font-medium text-gray-700">Embedding model</dt>
        <dd className="truncate">{collection.embedding_model}</dd>
        <dt className="font-medium text-gray-700">Chunk profile</dt>
        <dd>{collection.chunk_profile}</dd>
      </dl>

      <Link
        href={`/documents/${collection.id}`}
        className="mt-1 inline-block text-sm font-medium text-blue-600 hover:text-blue-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 rounded"
      >
        View Documents →
      </Link>
    </div>
  );
});

export default CollectionCard;
