"use client";

import React, { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import * as Select from "@radix-ui/react-select";
import { createCollection } from "@/lib/api";
import { ApiError } from "@/lib/api";
import { useModels } from "@/hooks/useModels";

// Slug validation: ^[a-z0-9][a-z0-9_-]*$, max 100 chars
const SLUG_RE = /^[a-z0-9][a-z0-9_-]*$/;

function validateSlug(name: string): string | null {
  if (!name) return "Name is required.";
  if (name.length > 100) return "Name must be 100 characters or fewer.";
  if (!SLUG_RE.test(name))
    return 'Name must start with a lowercase letter or digit and contain only lowercase letters, digits, hyphens, and underscores.';
  return null;
}

interface CreateCollectionDialogProps {
  onCreated: () => void;
}

export default function CreateCollectionDialog({
  onCreated,
}: CreateCollectionDialogProps) {
  const [open, setOpen] = useState(false);

  // Form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [embeddingModel, setEmbeddingModel] = useState("");

  // Validation & submission state
  const [nameError, setNameError] = useState<string | null>(null);
  const [conflictError, setConflictError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const { embedModels } = useModels();

  const resetForm = () => {
    setName("");
    setDescription("");
    setEmbeddingModel("");
    setNameError(null);
    setConflictError(null);
    setSubmitting(false);
  };

  const handleOpenChange = (next: boolean) => {
    if (!next) resetForm();
    setOpen(next);
  };

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setName(e.target.value);
    // Clear conflict error when the user edits the name
    setConflictError(null);
    // Live inline validation
    setNameError(validateSlug(e.target.value));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const slugError = validateSlug(name);
    if (slugError !== null) {
      setNameError(slugError);
      return;
    }

    setSubmitting(true);
    setConflictError(null);

    try {
      await createCollection({
        name,
        description: description.trim() || null,
        embedding_model: embeddingModel || null,
      });
      // Success: close dialog and notify parent
      setOpen(false);
      resetForm();
      onCreated();
    } catch (err: unknown) {
      if (err instanceof ApiError && err.code === "COLLECTION_NAME_CONFLICT") {
        // Keep dialog open, show conflict error inline
        setConflictError(err.message);
      } else {
        const message =
          err instanceof Error ? err.message : "Failed to create collection.";
        setConflictError(message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Trigger asChild>
        <button className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400">
          New Collection
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40 z-40" />
        <Dialog.Content
          className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg bg-white p-6 shadow-xl focus:outline-none"
          aria-describedby="create-dialog-desc"
        >
          <Dialog.Title className="text-base font-semibold text-gray-900 mb-1">
            Create Collection
          </Dialog.Title>
          <p id="create-dialog-desc" className="text-sm text-gray-500 mb-4">
            Collections group related documents for search and retrieval.
          </p>

          <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
            {/* Name */}
            <div>
              <label
                htmlFor="collection-name"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Name <span aria-hidden="true" className="text-red-500">*</span>
              </label>
              <input
                id="collection-name"
                type="text"
                value={name}
                onChange={handleNameChange}
                placeholder="my-collection"
                maxLength={100}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 aria-invalid:border-red-400"
                aria-invalid={nameError !== null ? "true" : undefined}
                aria-describedby={nameError !== null ? "name-error" : undefined}
                autoComplete="off"
                spellCheck={false}
              />
              {nameError !== null ? (
                <p
                  id="name-error"
                  className="mt-1 text-xs text-red-600"
                  role="alert"
                >
                  {nameError}
                </p>
              ) : (
                <p className="mt-1 text-xs text-gray-400">
                  Lowercase letters, digits, hyphens, underscores only.
                </p>
              )}
            </div>

            {/* Description */}
            <div>
              <label
                htmlFor="collection-description"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Description{" "}
                <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <input
                id="collection-description"
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief description of this collection"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
              />
            </div>

            {/* Embedding model */}
            <div>
              <label
                htmlFor="embedding-model-trigger"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Embedding model{" "}
                <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <Select.Root value={embeddingModel} onValueChange={setEmbeddingModel}>
                <Select.Trigger
                  id="embedding-model-trigger"
                  className="w-full flex items-center justify-between rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                  aria-label="Embedding model"
                >
                  <Select.Value placeholder="Default model" />
                  <Select.Icon className="text-gray-400 ml-2">▾</Select.Icon>
                </Select.Trigger>
                <Select.Portal>
                  <Select.Content
                    className="z-50 rounded-md border border-gray-200 bg-white shadow-md"
                    position="popper"
                    sideOffset={4}
                  >
                    <Select.Viewport className="p-1">
                      <Select.Item
                        value=""
                        className="relative flex cursor-pointer select-none items-center rounded px-3 py-2 text-sm text-gray-500 hover:bg-gray-50 focus:bg-gray-100 focus:outline-none data-[highlighted]:bg-gray-100"
                      >
                        <Select.ItemText>Default model</Select.ItemText>
                      </Select.Item>
                      {embedModels?.map((model) => (
                        <Select.Item
                          key={model.name}
                          value={model.name}
                          className="relative flex cursor-pointer select-none items-center rounded px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 focus:bg-gray-100 focus:outline-none data-[highlighted]:bg-gray-100"
                        >
                          <Select.ItemText>{model.name}</Select.ItemText>
                        </Select.Item>
                      ))}
                    </Select.Viewport>
                  </Select.Content>
                </Select.Portal>
              </Select.Root>
            </div>

            {/* Conflict / server error */}
            {conflictError !== null ? (
              <p className="text-sm text-red-600" role="alert">
                {conflictError}
              </p>
            ) : null}

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-1">
              <Dialog.Close asChild>
                <button
                  type="button"
                  className="rounded px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-400"
                  disabled={submitting}
                >
                  Cancel
                </button>
              </Dialog.Close>
              <button
                type="submit"
                disabled={submitting || nameError !== null}
                className="rounded px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
              >
                {submitting ? "Creating…" : "Create"}
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
