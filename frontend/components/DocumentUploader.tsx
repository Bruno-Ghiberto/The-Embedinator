'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { FileText, FileType } from 'lucide-react';
import { ingestFile } from '@/lib/api';
import { UPLOAD_CONSTRAINTS } from '@/lib/types';
import { cn } from '@/lib/utils';
import IngestionProgress from '@/components/IngestionProgress';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface DocumentUploaderProps {
  collectionId: string;
  onUploadComplete: () => void;
}

interface QueuedFile {
  file: File;
  status: 'waiting' | 'uploading' | 'ingesting' | 'done' | 'error';
  jobId?: string;
  error?: string;
}

// ─── Helpers (module-level — rerender-no-inline-components) ───────────────────

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface FileIconProps {
  filename: string;
}

const FileIcon = React.memo(function FileIcon({ filename }: FileIconProps) {
  const ext = filename.split('.').pop()?.toLowerCase();
  if (ext === 'pdf') return <FileType className="h-4 w-4 shrink-0 text-red-500" />;
  return <FileText className="h-4 w-4 shrink-0 text-blue-500" />;
});

// ─── DocumentUploader ─────────────────────────────────────────────────────────

export default function DocumentUploader({
  collectionId,
  onUploadComplete,
}: DocumentUploaderProps) {
  const [queue, setQueue] = useState<QueuedFile[]>([]);
  const [fileError, setFileError] = useState<string | null>(null);

  // Derived — is any file currently uploading?
  const isUploading = queue.some((f) => f.status === 'uploading');
  // Derived — is any file still in-progress (uploading or ingesting)?
  const hasActiveWork = queue.some(
    (f) => f.status === 'uploading' || f.status === 'ingesting' || f.status === 'waiting',
  );

  // ─── Sequential upload effect ────────────────────────────────────────────
  useEffect(() => {
    if (isUploading) return;
    const nextIdx = queue.findIndex((f) => f.status === 'waiting');
    if (nextIdx === -1) return;

    // Mark as uploading
    setQueue((prev) =>
      prev.map((f, i) => (i === nextIdx ? { ...f, status: 'uploading' as const } : f)),
    );

    const item = queue[nextIdx];

    ingestFile(collectionId, item.file)
      .then((job) => {
        setQueue((prev) =>
          prev.map((f, i) =>
            i === nextIdx
              ? { ...f, status: 'ingesting' as const, jobId: job.job_id }
              : f,
          ),
        );
      })
      .catch((err: unknown) => {
        const message =
          err instanceof Error ? err.message : 'Upload failed. Please try again.';
        setQueue((prev) =>
          prev.map((f, i) =>
            i === nextIdx ? { ...f, status: 'error' as const, error: message } : f,
          ),
        );
      });
  }, [queue, collectionId, isUploading]);

  // ─── Queue callbacks ────────────────────────────────────────────────────
  const markDone = useCallback((idx: number) => {
    setQueue((prev) =>
      prev.map((f, i) => (i === idx ? { ...f, status: 'done' as const } : f)),
    );
  }, []);

  const retryUpload = useCallback((idx: number) => {
    setQueue((prev) =>
      prev.map((f, i) =>
        i === idx ? { ...f, status: 'waiting' as const, jobId: undefined, error: undefined } : f,
      ),
    );
  }, []);

  // ─── Drop handler ──────────────────────────────────────────────────────
  const handleDrop = useCallback(
    (acceptedFiles: File[]) => {
      setFileError(null);

      const validFiles: QueuedFile[] = [];
      const errors: string[] = [];

      for (const file of acceptedFiles) {
        // Client-side size guard
        if (file.size > UPLOAD_CONSTRAINTS.maxSizeBytes) {
          errors.push(`${file.name} exceeds the 50 MB limit.`);
          continue;
        }

        // Extension allowlist guard
        const ext = file.name.split('.').pop()?.toLowerCase();
        if (!ext || !(UPLOAD_CONSTRAINTS.allowedExtensions as readonly string[]).includes(ext)) {
          errors.push(`${file.name}: unsupported file type.`);
          continue;
        }

        validFiles.push({ file, status: 'waiting' });
      }

      if (errors.length > 0) {
        setFileError(errors.join(' '));
      }

      if (validFiles.length > 0) {
        setQueue((prev) => [...prev, ...validFiles]);
      }
    },
    [],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: handleDrop,
    accept: UPLOAD_CONSTRAINTS.accept,
    multiple: true,
    disabled: false,
  });

  return (
    <div className="mt-6">
      <h3 className="text-sm font-semibold text-foreground mb-2">Upload Documents</h3>

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={cn(
          'border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors',
          isDragActive
            ? 'border-primary bg-primary/5'
            : 'border-border bg-background hover:border-primary hover:bg-primary/5',
        )}
        aria-label="File upload drop zone"
      >
        <input {...getInputProps()} />
        {isDragActive ? (
          <p className="text-sm text-primary font-medium">Drop files here{'\u2026'}</p>
        ) : (
          <div>
            <p className="text-sm text-muted-foreground">
              Drag and drop files here, or{' '}
              <span className="text-primary font-medium">browse</span>
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              PDF, Markdown, TXT, RST — max 50 MB
            </p>
          </div>
        )}
      </div>

      {/* Client-side validation error */}
      {fileError !== null && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {fileError}
        </p>
      )}

      {/* File queue */}
      {queue.length > 0 && (
        <div className="mt-4 space-y-3">
          {queue.map((item, i) => (
            <div key={`${item.file.name}-${item.file.lastModified}-${i}`} className="rounded-lg border border-border p-3">
              {/* File info row */}
              <div className="flex items-center gap-3">
                <FileIcon filename={item.file.name} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{item.file.name}</p>
                  <p className="text-xs text-muted-foreground">{formatBytes(item.file.size)}</p>
                </div>
                {item.status === 'done' && (
                  <span className="text-xs text-success font-medium">Done</span>
                )}
              </div>

              {/* Uploading spinner */}
              {item.status === 'uploading' && (
                <p className="mt-2 text-sm text-muted-foreground flex items-center gap-2">
                  <span
                    className="inline-block w-3 h-3 border-2 border-primary border-t-transparent rounded-full animate-spin"
                    aria-hidden="true"
                  />
                  Uploading{'\u2026'}
                </p>
              )}

              {/* Upload error */}
              {item.status === 'error' && (
                <div className="mt-2">
                  <p className="text-xs text-destructive">{item.error}</p>
                  <button
                    type="button"
                    onClick={() => retryUpload(i)}
                    className="mt-1 text-xs text-primary hover:underline"
                  >
                    Try again
                  </button>
                </div>
              )}

              {/* IngestionProgress — SWR-based polling */}
              {item.status === 'ingesting' && item.jobId && (
                <IngestionProgress
                  collectionId={collectionId}
                  jobId={item.jobId}
                  onComplete={() => {
                    markDone(i);
                    onUploadComplete();
                  }}
                  onRetry={() => retryUpload(i)}
                />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
