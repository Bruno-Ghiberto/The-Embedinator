'use client';

import { useCallback, useState } from 'react';
import { useParams } from 'next/navigation';
import useSWR from 'swr';
import { getDocuments, deleteDocument } from '@/lib/api';
import DocumentList from '@/components/DocumentList';
import DocumentUploader from '@/components/DocumentUploader';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';

// ─── Documents Page ───────────────────────────────────────────────────────────

export default function DocumentsPage() {
  const params = useParams();
  const collectionId = params?.id;

  // Validate collection ID
  if (!collectionId || typeof collectionId !== 'string' || collectionId.trim() === '') {
    return (
      <main className="max-w-6xl mx-auto px-[var(--space-page)] py-10">
        <p className="text-[var(--color-destructive)] text-sm">Invalid or missing collection ID.</p>
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
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Documents</h1>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">
          Collection: <span className="font-mono text-[var(--color-text-primary)]">{collectionId}</span>
        </p>
      </header>

      {deleteError !== null ? (
        <div
          role="alert"
          className="mb-4 px-4 py-3 bg-[var(--color-destructive)]/10 border border-[var(--color-destructive)]/20 rounded-lg text-sm text-[var(--color-destructive)]"
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
              className="py-6 px-4 bg-[var(--color-destructive)]/10 border border-[var(--color-destructive)]/20 rounded-lg text-sm text-[var(--color-destructive)]"
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
          <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
            <h2 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">
              Chunk Preview
            </h2>
            {selectedDoc ? (
              <ScrollArea className="h-[400px] md:h-[500px]">
                <div className="pr-4 space-y-3">
                  <p className="text-sm text-[var(--color-text-muted)]">
                    Showing chunks for <span className="font-medium text-[var(--color-text-primary)]">{selectedDoc.filename}</span>
                  </p>
                  <p className="text-xs text-[var(--color-text-muted)]">
                    {selectedDoc.chunk_count !== null
                      ? `${selectedDoc.chunk_count} chunks indexed`
                      : 'Chunk count unavailable'}
                  </p>
                </div>
              </ScrollArea>
            ) : (
              <div className="py-12 text-center">
                <p className="text-sm text-[var(--color-text-muted)]">
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
