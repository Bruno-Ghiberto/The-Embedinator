'use client';

import { useCallback, useState } from 'react';
import { useParams } from 'next/navigation';
import useSWR from 'swr';
import { getDocuments, deleteDocument } from '@/lib/api';
import DocumentList from '@/components/DocumentList';
import DocumentUploader from '@/components/DocumentUploader';

// ─── Documents Page ───────────────────────────────────────────────────────────

export default function DocumentsPage() {
  const params = useParams();
  const collectionId = params?.id;

  // Validate collection ID
  if (!collectionId || typeof collectionId !== 'string' || collectionId.trim() === '') {
    return (
      <main className="max-w-4xl mx-auto px-4 py-10">
        <p className="text-red-600 text-sm">Invalid or missing collection ID.</p>
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
        await mutate();
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Failed to delete document.';
        setDeleteError(message);
      }
    },
    [mutate],
  );

  const handleUploadComplete = useCallback(async () => {
    await mutate();
  }, [mutate]);

  return (
    <main className="max-w-4xl mx-auto px-4 py-10">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Documents</h1>
        <p className="text-sm text-gray-500 mt-1">
          Collection: <span className="font-mono text-gray-700">{collectionId}</span>
        </p>
      </header>

      {deleteError !== null ? (
        <div
          role="alert"
          className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700"
        >
          {deleteError}
        </div>
      ) : null}

      {isLoading ? (
        <div className="py-12 text-center text-sm text-gray-500">Loading documents…</div>
      ) : error !== undefined && error !== null ? (
        <div
          role="alert"
          className="py-6 px-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700"
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
    </main>
  );
}
