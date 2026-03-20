"use client";

import React, { memo, useState } from "react";
import Link from "next/link";
import { MoreVertical, Eye, Trash2 } from "lucide-react";
import { deleteCollection } from "@/lib/api";
import type { Collection } from "@/lib/types";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardAction,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@/components/ui/tooltip";

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
    <>
      <Card className="transition-shadow hover:shadow-md">
        <CardHeader>
          <CardTitle className="truncate">{collection.name}</CardTitle>
          <CardAction>
            <DropdownMenu>
              <Tooltip>
                <TooltipTrigger
                  render={
                    <DropdownMenuTrigger
                      render={<Button variant="ghost" size="icon-sm" />}
                    />
                  }
                >
                  <MoreVertical className="size-4" />
                  <span className="sr-only">
                    Actions for {collection.name}
                  </span>
                </TooltipTrigger>
                <TooltipContent>Actions</TooltipContent>
              </Tooltip>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  render={<Link href={`/documents/${collection.id}`} />}
                >
                  <Eye className="size-4" />
                  View Documents
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  variant="destructive"
                  onClick={() => setDialogOpen(true)}
                >
                  <Trash2 className="size-4" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </CardAction>
          {collection.description !== null && (
            <CardDescription className="line-clamp-2">
              {collection.description}
            </CardDescription>
          )}
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            <Badge variant="secondary">
              {collection.document_count} docs
            </Badge>
            <Badge variant="outline" className="max-w-[160px] truncate">
              {collection.embedding_model}
            </Badge>
            <Badge variant="outline">{collection.chunk_profile}</Badge>
          </div>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete collection?</DialogTitle>
            <DialogDescription>
              This will permanently remove{" "}
              <strong>{collection.name}</strong> and all its documents. This
              action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          {deleteError !== null && (
            <p className="text-sm text-destructive" role="alert">
              {deleteError}
            </p>
          )}
          <DialogFooter>
            <DialogClose
              render={<Button variant="outline" />}
              disabled={deleting}
            >
              Cancel
            </DialogClose>
            <Button
              variant="destructive"
              onClick={handleConfirmDelete}
              disabled={deleting}
            >
              {deleting ? "Deleting…" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
});

export default CollectionCard;
