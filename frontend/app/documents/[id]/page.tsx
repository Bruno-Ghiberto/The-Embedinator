'use client';

import { useCallback, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import useSWR from 'swr';
import { getDocuments, deleteDocument } from '@/lib/api';
import { useCollections } from '@/hooks/useCollections';
import DocumentList from '@/components/DocumentList';
import DocumentUploader from '@/components/DocumentUploader';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import {
  Breadcrumb,
  BreadcrumbList,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb';
import { MessageSquare } from 'lucide-react';

// ─── Documents Page ───────────────────────────────────────────────────────────

export default function DocumentsPage() {
  const params = useParams();
  const collectionId = params?.id;

  // Validate collection ID
  if (!collectionId || typeof collectionId !== 'string' || collectionId.trim() === '') {
    return (
      <main className="max-w-6xl mx-auto px-[var(--space-page)] py-10">
        <p className="text-destructive text-sm">Invalid or missing collection ID.</p>
      </main>
    );
  }

  return <DocumentsContent collectionId={collectionId} />;
}

// ─── DocumentsContent ─────────────────────────────────────────────────────────
// Separated so collectionId is known to be a valid string before SWR runs.

interface DocumentsContentProps {
  collectionId: string;
}

function DocumentsContent({ collectionId }: DocumentsContentProps) {
  const router = useRouter();
  const { collections } = useCollections();
  const collection = collections?.find((c) => c.id === collectionId);
  const collectionName = collection?.name ?? collectionId;

  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);

  const { data: documents, isLoading, error, mutate } = useSWR(
    ['documents', collectionId],
    () => getDocuments(collectionId),
    { revalidateOnFocus: false },
  );

  const handleDelete = useCallback(
    async (docId: string) => {
      setDeleteError(null);
      try {
        await deleteDocument(docId);
        if (selectedDocId === docId) setSelectedDocId(null);
        await mutate();
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Failed to delete document.';
        setDeleteError(message);
      }
    },
    [mutate, selectedDocId],
  );

  const handleUploadComplete = useCallback(async () => {
    await mutate();
  }, [mutate]);

  const selectedDoc = documents?.find((d) => d.id === selectedDocId) ?? null;

  return (
    <main className="max-w-6xl mx-auto px-[var(--space-page)] py-10">
      <header className="mb-6">
        <Breadcrumb className="mb-3">
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink render={<Link href="/collections" />}>
                Collections
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage>{collectionName}</BreadcrumbPage>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage>Documents</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>

        <div className="flex items-center justify-between gap-4">
          <h1 className="text-2xl font-bold text-foreground">{collectionName}</h1>
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push(`/chat?collections=${collectionId}`)}
          >
            <MessageSquare className="h-4 w-4 mr-2" />
            Chat with this collection
          </Button>
        </div>
      </header>

      {deleteError !== null ? (
        <div
          role="alert"
          className="mb-4 px-4 py-3 bg-destructive/10 border border-destructive/20 rounded-lg text-sm text-destructive"
        >
          {deleteError}
        </div>
      ) : null}

      {/* Two-column on desktop (>= 768px), stacked on mobile */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-[var(--space-card-gap)]">
        {/* Left column: file list + uploader */}
        <div className="min-w-0">
          {isLoading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-10 w-full rounded-md" />
              ))}
            </div>
          ) : error !== undefined && error !== null ? (
            <div
              role="alert"
              className="py-6 px-4 bg-destructive/10 border border-destructive/20 rounded-lg text-sm text-destructive"
            >
              Failed to load documents. Please try again.
            </div>
          ) : (
            <DocumentList documents={documents ?? []} onDelete={handleDelete} />
          )}

          <DocumentUploader
            collectionId={collectionId}
            onUploadComplete={handleUploadComplete}
          />
        </div>

        {/* Right column: chunk preview */}
        <div className="min-w-0">
          <div className="rounded-lg border border-border bg-card p-4">
            <h2 className="text-sm font-semibold text-foreground mb-3">
              Chunk Preview
            </h2>
            {selectedDoc ? (
              <ScrollArea className="h-[400px] md:h-[500px]">
                <div className="pr-4 space-y-3">
                  <p className="text-sm text-muted-foreground">
                    Showing chunks for <span className="font-medium text-foreground">{selectedDoc.filename}</span>
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {selectedDoc.chunk_count !== null
                      ? `${selectedDoc.chunk_count} chunks indexed`
                      : 'Chunk count unavailable'}
                  </p>
                </div>
              </ScrollArea>
            ) : (
              <div className="py-12 text-center">
                <p className="text-sm text-muted-foreground">
                  Select a document to preview its chunks.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
