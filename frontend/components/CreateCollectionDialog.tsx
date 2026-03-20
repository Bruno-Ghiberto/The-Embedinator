"use client";

import React, { useState } from "react";
import { createCollection, ApiError } from "@/lib/api";
import { useModels } from "@/hooks/useModels";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";

// Slug validation: ^[a-z0-9][a-z0-9_-]*$, max 100 chars
const SLUG_RE = /^[a-z0-9][a-z0-9_-]*$/;
const DEFAULT_MODEL = "__default__";

function validateSlug(name: string): string | null {
  if (!name) return "Name is required.";
  if (name.length > 100) return "Name must be 100 characters or fewer.";
  if (!SLUG_RE.test(name))
    return "Name must start with a lowercase letter or digit and contain only lowercase letters, digits, hyphens, and underscores.";
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
  const [embeddingModel, setEmbeddingModel] = useState(DEFAULT_MODEL);

  // Validation & submission state
  const [nameError, setNameError] = useState<string | null>(null);
  const [conflictError, setConflictError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const { embedModels } = useModels();

  const resetForm = () => {
    setName("");
    setDescription("");
    setEmbeddingModel(DEFAULT_MODEL);
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
        embedding_model:
          embeddingModel === DEFAULT_MODEL ? null : embeddingModel,
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
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={<Button />}>New Collection</DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Collection</DialogTitle>
          <DialogDescription>
            Collections group related documents for search and retrieval.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
          {/* Name */}
          <div>
            <label
              htmlFor="collection-name"
              className="block text-sm font-medium text-[var(--color-text-primary)] mb-1"
            >
              Name{" "}
              <span aria-hidden="true" className="text-destructive">
                *
              </span>
            </label>
            <Input
              id="collection-name"
              type="text"
              value={name}
              onChange={handleNameChange}
              placeholder="my-collection"
              maxLength={100}
              aria-invalid={nameError !== null ? "true" : undefined}
              aria-describedby={nameError !== null ? "name-error" : undefined}
              autoComplete="off"
              spellCheck={false}
            />
            {nameError !== null ? (
              <p
                id="name-error"
                className="mt-1 text-xs text-destructive"
                role="alert"
              >
                {nameError}
              </p>
            ) : (
              <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                Lowercase letters, digits, hyphens, underscores only.
              </p>
            )}
          </div>

          {/* Description */}
          <div>
            <label
              htmlFor="collection-description"
              className="block text-sm font-medium text-[var(--color-text-primary)] mb-1"
            >
              Description{" "}
              <span className="text-[var(--color-text-muted)] font-normal">
                (optional)
              </span>
            </label>
            <Input
              id="collection-description"
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of this collection"
            />
          </div>

          {/* Embedding model */}
          <div>
            <label
              htmlFor="embedding-model-trigger"
              className="block text-sm font-medium text-[var(--color-text-primary)] mb-1"
            >
              Embedding model{" "}
              <span className="text-[var(--color-text-muted)] font-normal">
                (optional)
              </span>
            </label>
            <Select
              value={embeddingModel}
              onValueChange={(val) => setEmbeddingModel(val ?? DEFAULT_MODEL)}
            >
              <SelectTrigger
                id="embedding-model-trigger"
                className="w-full"
                aria-label="Embedding model"
              >
                <SelectValue placeholder="Default model" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={DEFAULT_MODEL}>Default model</SelectItem>
                {embedModels?.map((model) => (
                  <SelectItem key={model.name} value={model.name}>
                    {model.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Conflict / server error */}
          {conflictError !== null && (
            <p className="text-sm text-destructive" role="alert">
              {conflictError}
            </p>
          )}

          {/* Actions */}
          <DialogFooter>
            <DialogClose
              render={<Button variant="outline" type="button" />}
              disabled={submitting}
            >
              Cancel
            </DialogClose>
            <Button type="submit" disabled={submitting || nameError !== null}>
              {submitting ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
