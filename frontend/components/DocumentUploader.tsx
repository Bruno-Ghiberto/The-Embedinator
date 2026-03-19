'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { ingestFile, getIngestionJob } from '@/lib/api';
import { UPLOAD_CONSTRAINTS, TERMINAL_JOB_STATES } from '@/lib/types';
import type { IngestionJob } from '@/lib/types';

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
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-gray-600">
          {chunksProcessed} / {chunksTotal !== null ? chunksTotal : '?'} chunks
        </span>
        {pct !== null ? (
          <span className="text-xs font-medium text-blue-700">{pct}%</span>
        ) : null}
      </div>
      <div className="w-full bg-gray-200 rounded-full h-1.5">
        <div
          className="bg-blue-500 h-1.5 rounded-full transition-all duration-300"
          style={{ width: pct !== null ? `${pct}%` : '0%' }}
        />
      </div>
    </div>
  );
});

// ─── JobStatus ────────────────────────────────────────────────────────────────

interface JobStatusProps {
  job: IngestionJob;
}

const JOB_STATUS_LABEL: Record<string, string> = {
  pending:   'Queued…',
  started:   'Starting…',
  streaming: 'Processing…',
  embedding: 'Embedding…',
  completed: 'Completed',
  failed:    'Failed',
  paused:    'Paused',
};

const JobStatus = React.memo(function JobStatus({ job }: JobStatusProps) {
  const label = JOB_STATUS_LABEL[job.status] ?? job.status;
  const isTerminal = TERMINAL_JOB_STATES.includes(job.status);

  return (
    <div
      className={`mt-4 p-3 rounded-lg text-sm ${
        job.status === 'completed'
          ? 'bg-green-50 border border-green-200 text-green-800'
          : job.status === 'failed'
          ? 'bg-red-50 border border-red-200 text-red-800'
          : 'bg-blue-50 border border-blue-200 text-blue-800'
      }`}
    >
      <div className="flex items-center gap-2">
        {!isTerminal ? (
          <span
            className="inline-block w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"
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
        <p className="mt-1 text-xs text-red-700">{job.error_message}</p>
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
      <h3 className="text-sm font-semibold text-gray-700 mb-2">Upload Document</h3>

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-blue-400 bg-blue-50'
            : isActive
            ? 'border-gray-200 bg-gray-50 cursor-not-allowed opacity-60'
            : 'border-gray-300 bg-white hover:border-blue-400 hover:bg-blue-50'
        }`}
        aria-label="File upload drop zone"
      >
        <input {...getInputProps()} />
        {isDragActive ? (
          <p className="text-sm text-blue-600 font-medium">Drop the file here…</p>
        ) : (
          <div>
            <p className="text-sm text-gray-600">
              Drag and drop a file here, or{' '}
              <span className="text-blue-600 font-medium">browse</span>
            </p>
            <p className="text-xs text-gray-400 mt-1">
              PDF, Markdown, TXT, RST — max 50 MB
            </p>
          </div>
        )}
      </div>

      {/* Client-side file error — shown without network request */}
      {state.fileError !== null ? (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {state.fileError}
        </p>
      ) : null}

      {/* Upload / API error */}
      {state.uploadError !== null ? (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {state.uploadError}
        </p>
      ) : null}

      {/* Uploading spinner */}
      {state.isUploading ? (
        <p className="mt-3 text-sm text-gray-500 flex items-center gap-2">
          <span
            className="inline-block w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"
            aria-hidden="true"
          />
          Uploading…
        </p>
      ) : null}

      {/* Job polling status */}
      {state.job !== null ? <JobStatus job={state.job} /> : null}
    </div>
  );
}
