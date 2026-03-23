'use client';

import React from 'react';
import type { Document, DocumentStatus } from '@/lib/types';
import { cn } from '@/lib/utils';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';

// ─── Status Badge ─────────────────────────────────────────────────────────────
// Defined outside DocumentList to satisfy rerender-no-inline-components rule.

const STATUS_CONFIG: Record<
  DocumentStatus,
  { variant: 'outline' | 'default' | 'secondary' | 'destructive'; label: string; className?: string; showSpinner?: boolean }
> = {
  pending: {
    variant: 'outline',
    label: 'Pending',
  },
  ingesting: {
    variant: 'default',
    label: 'Ingesting',
    showSpinner: true,
  },
  completed: {
    variant: 'secondary',
    label: 'Completed',
    className: 'bg-success/10 text-success border-success/20',
  },
  failed: {
    variant: 'destructive',
    label: 'Failed',
  },
  duplicate: {
    variant: 'outline',
    label: 'Duplicate',
    className: 'text-muted-foreground',
  },
};

interface StatusBadgeProps {
  status: DocumentStatus;
}

const StatusBadge = React.memo(function StatusBadge({ status }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending;
  return (
    <Badge variant={config.variant} className={cn('gap-1.5', config.className)}>
      {config.showSpinner ? (
        <span
          className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin"
          aria-hidden="true"
        />
      ) : null}
      {config.label}
    </Badge>
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
    <TableRow>
      <TableCell className="font-medium max-w-xs truncate">
        {doc.filename}
      </TableCell>
      <TableCell>
        <StatusBadge status={doc.status} />
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {doc.chunk_count !== null ? doc.chunk_count.toLocaleString() : '\u2014'}
      </TableCell>
      <TableCell className="text-muted-foreground">
        {new Date(doc.created_at).toLocaleDateString()}
      </TableCell>
      <TableCell className="text-right">
        <button
          onClick={handleDelete}
          className="text-sm text-destructive hover:text-destructive/80 font-medium transition-colors"
          aria-label={`Delete ${doc.filename}`}
        >
          Delete
        </button>
      </TableCell>
    </TableRow>
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
      <div className="text-center py-12 text-muted-foreground">
        <p className="text-sm">No documents yet. Upload a file to get started.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="text-xs uppercase tracking-wider">
              Filename
            </TableHead>
            <TableHead className="text-xs uppercase tracking-wider">
              Status
            </TableHead>
            <TableHead className="text-xs uppercase tracking-wider text-right">
              Chunks
            </TableHead>
            <TableHead className="text-xs uppercase tracking-wider">
              Uploaded
            </TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.map((doc) => (
            <DocumentRow key={doc.id} document={doc} onDelete={onDelete} />
          ))}
        </TableBody>
      </Table>
    </div>
  );
});

export default DocumentList;
