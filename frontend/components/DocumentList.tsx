'use client';

import React from 'react';
import type { Document, DocumentStatus } from '@/lib/types';
import { deleteDocument } from '@/lib/api';

// ─── Status Badge ─────────────────────────────────────────────────────────────
// Defined outside DocumentList to satisfy rerender-no-inline-components rule.

const STATUS_STYLES: Record<DocumentStatus, { bg: string; text: string; label: string }> = {
  pending:    { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'Pending' },
  ingesting:  { bg: 'bg-blue-100',   text: 'text-blue-800',   label: 'Ingesting' },
  completed:  { bg: 'bg-green-100',  text: 'text-green-800',  label: 'Completed' },
  failed:     { bg: 'bg-red-100',    text: 'text-red-800',    label: 'Failed' },
  duplicate:  { bg: 'bg-gray-100',   text: 'text-gray-600',   label: 'Duplicate' },
};

interface StatusBadgeProps {
  status: DocumentStatus;
}

const StatusBadge = React.memo(function StatusBadge({ status }: StatusBadgeProps) {
  const { bg, text, label } = STATUS_STYLES[status] ?? STATUS_STYLES.pending;
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${bg} ${text}`}
    >
      {label}
    </span>
  );
});

// ─── DocumentRow ──────────────────────────────────────────────────────────────

interface DocumentRowProps {
  document: Document;
  onDelete: (id: string) => void;
}

const DocumentRow = React.memo(function DocumentRow({ document: doc, onDelete }: DocumentRowProps) {
  const handleDelete = () => onDelete(doc.id);

  return (
    <tr className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
      <td className="py-3 px-4 text-sm text-gray-900 font-medium max-w-xs truncate">
        {doc.filename}
      </td>
      <td className="py-3 px-4">
        <StatusBadge status={doc.status} />
      </td>
      <td className="py-3 px-4 text-sm text-gray-500 text-right">
        {doc.chunk_count !== null ? doc.chunk_count.toLocaleString() : '—'}
      </td>
      <td className="py-3 px-4 text-sm text-gray-500">
        {new Date(doc.created_at).toLocaleDateString()}
      </td>
      <td className="py-3 px-4 text-right">
        <button
          onClick={handleDelete}
          className="text-sm text-red-600 hover:text-red-800 font-medium transition-colors"
          aria-label={`Delete ${doc.filename}`}
        >
          Delete
        </button>
      </td>
    </tr>
  );
});

// ─── DocumentList ─────────────────────────────────────────────────────────────

export interface DocumentListProps {
  documents: Document[];
  onDelete: (id: string) => void;
}

const DocumentList = React.memo(function DocumentList({ documents, onDelete }: DocumentListProps) {
  if (documents.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        <p className="text-sm">No documents yet. Upload a file to get started.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="w-full text-left">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            <th className="py-3 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Filename
            </th>
            <th className="py-3 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Status
            </th>
            <th className="py-3 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider text-right">
              Chunks
            </th>
            <th className="py-3 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Uploaded
            </th>
            <th className="py-3 px-4" />
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {documents.map((doc) => (
            <DocumentRow key={doc.id} document={doc} onDelete={onDelete} />
          ))}
        </tbody>
      </table>
    </div>
  );
});

export default DocumentList;
