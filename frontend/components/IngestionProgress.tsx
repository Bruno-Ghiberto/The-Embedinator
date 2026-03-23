'use client';

import React, { useEffect, useRef } from 'react';
import useSWR from 'swr';
import { getIngestionJob } from '@/lib/api';
import { TERMINAL_JOB_STATES } from '@/lib/types';
import type { IngestionJob } from '@/lib/types';
import { cn } from '@/lib/utils';
import { Progress, ProgressLabel, ProgressValue } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface IngestionProgressProps {
  collectionId: string;
  jobId: string;
  onComplete: () => void;
  onRetry: () => void;
}

// ─── Status config ────────────────────────────────────────────────────────────

const STATUS_LABELS: Record<string, string> = {
  pending:   'Pending\u2026',
  started:   'Starting\u2026',
  streaming: 'Processing\u2026',
  embedding: 'Embedding\u2026',
  completed: 'Complete!',
  failed:    'Failed',
  paused:    'Paused',
};

const STATUS_STYLE: Record<string, string> = {
  completed: 'bg-success/10 border-success/20 text-success',
  failed:    'bg-destructive/10 border-destructive/20 text-destructive',
};

const DEFAULT_STYLE = 'bg-primary/10 border-primary/20 text-primary';

// ─── IngestionProgress ────────────────────────────────────────────────────────

export default function IngestionProgress({
  collectionId,
  jobId,
  onComplete,
  onRetry,
}: IngestionProgressProps) {
  // Derive terminal state directly from data — rerender-derived-state-no-effect
  const { data: job } = useSWR<IngestionJob>(
    [`/api/collections/${collectionId}/ingest/${jobId}`, collectionId, jobId],
    () => getIngestionJob(collectionId, jobId),
    {
      refreshInterval: (latestData) =>
        latestData && TERMINAL_JOB_STATES.includes(latestData.status) ? 0 : 2000,
      revalidateOnFocus: false,
    },
  );

  const isTerminal = job ? TERMINAL_JOB_STATES.includes(job.status) : false;
  const label = job ? (STATUS_LABELS[job.status] ?? job.status) : 'Pending\u2026';
  const statusStyle = job ? (STATUS_STYLE[job.status] ?? DEFAULT_STYLE) : DEFAULT_STYLE;

  // Progress percentage — null when chunks_total is unknown (indeterminate)
  const pct =
    job && job.chunks_total !== null && job.chunks_total > 0
      ? Math.round((job.chunks_processed / job.chunks_total) * 100)
      : null;

  // Fire onComplete + toast exactly once on completion
  const completeFiredRef = useRef(false);
  useEffect(() => {
    if (job?.status === 'completed' && !completeFiredRef.current) {
      completeFiredRef.current = true;
      onComplete();
      toast.success('Document ingested successfully!');
    }
  }, [job?.status, onComplete]);

  return (
    <div className={cn('mt-3 p-3 rounded-lg text-sm border', statusStyle)}>
      {/* Status label + spinner */}
      <div className="flex items-center gap-2">
        {!isTerminal && (
          <span
            className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin"
            aria-hidden="true"
          />
        )}
        <span className="font-medium">{label}</span>
      </div>

      {/* Progress bar — visible only while processing */}
      {!isTerminal && job && (
        <div className="mt-2">
          <Progress value={pct ?? 0} aria-label="Ingestion progress">
            <ProgressLabel className="text-xs text-muted-foreground">
              {job.chunks_processed} / {job.chunks_total !== null ? job.chunks_total : '?'} chunks
            </ProgressLabel>
            {pct !== null && (
              <ProgressValue className="text-xs font-medium text-primary">
                {() => `${pct}%`}
              </ProgressValue>
            )}
          </Progress>
        </div>
      )}

      {/* Failure state — inline error + retry */}
      {job?.status === 'failed' && (
        <div className="mt-2">
          <p className="text-xs text-destructive">
            {job.error_message ?? 'Ingestion failed'}
          </p>
          <Button variant="outline" size="sm" onClick={onRetry} className="mt-1">
            Try again
          </Button>
        </div>
      )}
    </div>
  );
}
