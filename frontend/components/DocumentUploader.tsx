'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { ingestFile, getIngestionJob } from '@/lib/api';
import { UPLOAD_CONSTRAINTS, TERMINAL_JOB_STATES } from '@/lib/types';
import type { IngestionJob } from '@/lib/types';
import { cn } from '@/lib/utils';
import { Progress, ProgressLabel, ProgressValue } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface DocumentUploaderProps {
  collectionId: string;
  onUploadComplete: () => void;
}

interface UploadState {
  job: IngestionJob | null;
  isUploading: boolean;
  fileError: string | null;
  uploadError: string | null;
}

// ─── ProgressBar ──────────────────────────────────────────────────────────────
// Defined outside DocumentUploader — rerender-no-inline-components

interface ProgressBarProps {
  chunksProcessed: number;
  chunksTotal: number | null;
}

const ProgressBar = React.memo(function ProgressBar({
  chunksProcessed,
  chunksTotal,
}: ProgressBarProps) {
  const pct =
    chunksTotal !== null && chunksTotal > 0
      ? Math.round((chunksProcessed / chunksTotal) * 100)
      : null;

  return (
    <div className="mt-3">
      <Progress value={pct ?? 0} aria-label="Ingestion progress">
        <ProgressLabel className="text-xs text-[var(--color-text-muted)]">
          {chunksProcessed} / {chunksTotal !== null ? chunksTotal : '?'} chunks
        </ProgressLabel>
        {pct !== null ? (
          <ProgressValue className="text-xs font-medium text-[var(--color-accent)]">
            {() => `${pct}%`}
          </ProgressValue>
        ) : null}
      </Progress>
    </div>
  );
});

// ─── JobStatus ────────────────────────────────────────────────────────────────

interface JobStatusProps {
  job: IngestionJob;
}

const JOB_STATUS_LABEL: Record<string, string> = {
  pending:   'Queued\u2026',
  started:   'Starting\u2026',
  streaming: 'Processing\u2026',
  embedding: 'Embedding\u2026',
  completed: 'Completed',
  failed:    'Failed',
  paused:    'Paused',
};

const JOB_STATUS_STYLE: Record<string, string> = {
  completed: 'bg-[var(--color-success)]/10 border-[var(--color-success)]/20 text-[var(--color-success)]',
  failed:    'bg-[var(--color-destructive)]/10 border-[var(--color-destructive)]/20 text-[var(--color-destructive)]',
};

const JOB_STATUS_DEFAULT_STYLE = 'bg-[var(--color-accent)]/10 border-[var(--color-accent)]/20 text-[var(--color-accent)]';

const JobStatus = React.memo(function JobStatus({ job }: JobStatusProps) {
  const label = JOB_STATUS_LABEL[job.status] ?? job.status;
  const isTerminal = TERMINAL_JOB_STATES.includes(job.status);
  const statusStyle = JOB_STATUS_STYLE[job.status] ?? JOB_STATUS_DEFAULT_STYLE;

  return (
    <div className={cn('mt-4 p-3 rounded-lg text-sm border', statusStyle)}>
      <div className="flex items-center gap-2">
        {!isTerminal ? (
          <span
            className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin"
            aria-hidden="true"
          />
        ) : null}
        <span className="font-medium">{label}</span>
      </div>

      {!isTerminal ? (
        <ProgressBar
          chunksProcessed={job.chunks_processed}
          chunksTotal={job.chunks_total}
        />
      ) : null}

      {job.status === 'failed' && job.error_message ? (
        <p className="mt-1 text-xs text-[var(--color-destructive)]">{job.error_message}</p>
      ) : null}
    </div>
  );
});

// ─── DocumentUploader ─────────────────────────────────────────────────────────

export default function DocumentUploader({
  collectionId,
  onUploadComplete,
}: DocumentUploaderProps) {
  const [state, setState] = useState<UploadState>({
    job: null,
    isUploading: false,
    fileError: null,
    uploadError: null,
  });

  // Primitive jobId stored in a ref so the polling effect dep array stays stable.
  // rerender-dependencies: use primitive string, not object reference.
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Store collectionId in ref to avoid stale closures in polling callback
  const collectionIdRef = useRef(collectionId);
  useEffect(() => {
    collectionIdRef.current = collectionId;
  }, [collectionId]);

  // ─── Polling effect ──────────────────────────────────────────────────────
  // Dep array uses primitive `activeJobId` string — rerender-dependencies rule.
  useEffect(() => {
    if (activeJobId === null) return;

    const jobId = activeJobId; // capture primitive

    intervalRef.current = setInterval(async () => {
      try {
        const job = await getIngestionJob(collectionIdRef.current, jobId);

        // rerender-functional-setstate: use functional update for stable callbacks
        setState((prev) => ({ ...prev, job }));

        if (TERMINAL_JOB_STATES.includes(job.status)) {
          if (intervalRef.current !== null) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
          setActiveJobId(null);

          if (job.status === 'completed') {
            onUploadComplete();
          }
        }
      } catch {
        if (intervalRef.current !== null) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
        setActiveJobId(null);
        setState((prev) => ({
          ...prev,
          uploadError: 'Failed to poll ingestion status.',
        }));
      }
    }, 2000);

    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [activeJobId, onUploadComplete]);

  // ─── Drop handler ────────────────────────────────────────────────────────
  const handleDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;

      // Client-side size guard — NO network request on violation
      if (file.size > UPLOAD_CONSTRAINTS.maxSizeBytes) {
        setState((prev) => ({
          ...prev,
          fileError: `${file.name} exceeds the 50 MB limit. Choose a smaller file.`,
          uploadError: null,
        }));
        return;
      }

      // Extension allowlist guard — NO network request on violation
      const ext = file.name.split('.').pop()?.toLowerCase();
      if (!ext || !(UPLOAD_CONSTRAINTS.allowedExtensions as readonly string[]).includes(ext)) {
        setState((prev) => ({
          ...prev,
          fileError: `${file.name}: unsupported file type. Allowed: pdf, md, txt, rst`,
          uploadError: null,
        }));
        return;
      }

      // Valid file — proceed with upload
      setState((prev) => ({
        ...prev,
        fileError: null,
        uploadError: null,
        isUploading: true,
        job: null,
      }));

      try {
        const job = await ingestFile(collectionId, file);
        setState((prev) => ({ ...prev, isUploading: false, job }));
        setActiveJobId(job.job_id); // primitive string — starts polling
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : 'Upload failed. Please try again.';
        setState((prev) => ({
          ...prev,
          isUploading: false,
          uploadError: message,
        }));
      }
    },
    [collectionId],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: handleDrop,
    accept: UPLOAD_CONSTRAINTS.accept,
    multiple: false,
    disabled: state.isUploading || activeJobId !== null,
  });

  const isActive = state.isUploading || activeJobId !== null;

  return (
    <div className="mt-6">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-2">Upload Document</h3>

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={cn(
          'border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors',
          isDragActive
            ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/5'
            : isActive
            ? 'border-[var(--color-border)] bg-[var(--color-surface)] cursor-not-allowed opacity-60'
            : 'border-[var(--color-border)] bg-[var(--color-background)] hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)]/5'
        )}
        aria-label="File upload drop zone"
      >
        <input {...getInputProps()} />
        {isDragActive ? (
          <p className="text-sm text-[var(--color-accent)] font-medium">Drop the file here\u2026</p>
        ) : (
          <div>
            <p className="text-sm text-[var(--color-text-muted)]">
              Drag and drop a file here, or{' '}
              <span className="text-[var(--color-accent)] font-medium">browse</span>
            </p>
            <p className="text-xs text-[var(--color-text-muted)] mt-1">
              PDF, Markdown, TXT, RST — max 50 MB
            </p>
          </div>
        )}
      </div>

      {/* Client-side file error — shown without network request */}
      {state.fileError !== null ? (
        <p role="alert" className="mt-2 text-sm text-[var(--color-destructive)]">
          {state.fileError}
        </p>
      ) : null}

      {/* Upload / API error */}
      {state.uploadError !== null ? (
        <p role="alert" className="mt-2 text-sm text-[var(--color-destructive)]">
          {state.uploadError}
        </p>
      ) : null}

      {/* Uploading spinner */}
      {state.isUploading ? (
        <p className="mt-3 text-sm text-[var(--color-text-muted)] flex items-center gap-2">
          <span
            className="inline-block w-4 h-4 border-2 border-[var(--color-accent)] border-t-transparent rounded-full animate-spin"
            aria-hidden="true"
          />
          Uploading\u2026
        </p>
      ) : null}

      {/* Job polling status */}
      {state.job !== null ? <JobStatus job={state.job} /> : null}
    </div>
  );
}
