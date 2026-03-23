"use client";

import React, { useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { getTraceDetail } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { QueryTrace, QueryTraceDetail } from "@/lib/types";
import type { StageTimingsChartProps } from "@/components/StageTimingsChart";

// ─── Dynamic import for recharts (no SSR) ─────────────────────────────────────

const StageTimingsChart = dynamic<StageTimingsChartProps>(
  () =>
    import("@/components/StageTimingsChart").then((m) => m.StageTimingsChart),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-16 items-center justify-center text-sm text-muted-foreground">
        Loading chart...
      </div>
    ),
  },
);

// ─── Props ───────────────────────────────────────────────────────────────────

interface TraceTableProps {
  traces: QueryTrace[];
  total: number;
  limit: number;
  offset: number;
  onPageChange: (offset: number) => void;
  sessionFilter?: string;
  onSessionFilterChange: (sessionId: string) => void;
}

// ─── TraceDetailSheet ────────────────────────────────────────────────────────

interface TraceDetailSheetProps {
  trace: QueryTrace | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function TraceDetailSheet({ trace, open, onOpenChange }: TraceDetailSheetProps) {
  const [detail, setDetail] = useState<QueryTraceDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  React.useEffect(() => {
    if (!trace || !open) {
      setDetail(null);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    getTraceDetail(trace.id)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message || "Failed to load trace detail");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [trace?.id, open]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Trace Detail</SheetTitle>
          {trace && (
            <SheetDescription>
              Session: {trace.session_id.slice(0, 8)}... | {new Date(trace.created_at).toLocaleString()}
            </SheetDescription>
          )}
        </SheetHeader>

        {loading ? (
          <div className="px-4 py-6 text-sm text-muted-foreground">Loading trace detail...</div>
        ) : error ? (
          <div className="px-4 py-6 text-sm text-destructive">{error}</div>
        ) : trace && detail ? (
          <div className="space-y-5 px-4 pb-6">
            {/* Query text */}
            <div>
              <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Query</h4>
              <p className="text-sm text-foreground">{trace.query}</p>
            </div>

            {/* Response metadata */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Confidence</h4>
                <span className={cn(
                  "text-sm font-medium",
                  trace.confidence_score === null
                    ? "text-muted-foreground"
                    : trace.confidence_score >= 70
                      ? "text-success"
                      : trace.confidence_score >= 40
                        ? "text-warning"
                        : "text-destructive"
                )}>
                  {trace.confidence_score !== null ? trace.confidence_score : "\u2014"}
                </span>
              </div>
              <div>
                <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Latency</h4>
                <span className="text-sm text-foreground">{trace.latency_ms} ms</span>
              </div>
              <div>
                <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Model</h4>
                <span className="text-sm text-foreground">{trace.llm_model ?? "\u2014"}</span>
              </div>
              <div>
                <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Meta-Reasoning</h4>
                <span className={cn(
                  "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                  trace.meta_reasoning_triggered
                    ? "bg-primary/15 text-primary"
                    : "bg-card text-muted-foreground"
                )}>
                  {trace.meta_reasoning_triggered ? "Triggered" : "Not triggered"}
                </span>
              </div>
            </div>

            {/* Stage Timings */}
            {detail.stage_timings && Object.keys(detail.stage_timings).length > 0 && (
              <div>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Stage Timings</h4>
                <StageTimingsChart timings={detail.stage_timings} />
              </div>
            )}

            {/* Sub-questions */}
            {detail.sub_questions.length > 0 && (
              <div>
                <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Sub-questions ({detail.sub_questions.length})
                </h4>
                <ul className="list-inside list-disc space-y-0.5 text-sm text-foreground">
                  {detail.sub_questions.map((q, i) => (
                    <li key={i}>{q}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Reasoning steps */}
            {detail.reasoning_steps.length > 0 && (
              <div>
                <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Reasoning Steps ({detail.reasoning_steps.length})
                </h4>
                <ol className="list-inside list-decimal space-y-0.5 text-sm text-foreground">
                  {detail.reasoning_steps.map((step, i) => (
                    <li key={i}>
                      <code className="text-xs">{JSON.stringify(step)}</code>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {/* Strategy switches */}
            {detail.strategy_switches.length > 0 && (
              <div>
                <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Strategy Switches ({detail.strategy_switches.length})
                </h4>
                <ul className="list-inside list-disc space-y-0.5 text-sm text-foreground">
                  {detail.strategy_switches.map((sw, i) => (
                    <li key={i}>
                      <code className="text-xs">{JSON.stringify(sw)}</code>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Citations / chunks retrieved */}
            {detail.chunks_retrieved.length > 0 && (
              <div>
                <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Citations ({detail.chunks_retrieved.length})
                </h4>
                <ul className="list-inside list-disc space-y-0.5 text-sm text-foreground">
                  {detail.chunks_retrieved.map((chunk, i) => (
                    <li key={i}>
                      <code className="text-xs">{JSON.stringify(chunk)}</code>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {detail.sub_questions.length === 0 &&
            detail.reasoning_steps.length === 0 &&
            detail.strategy_switches.length === 0 &&
            detail.chunks_retrieved.length === 0 &&
            !(detail.stage_timings && Object.keys(detail.stage_timings).length > 0) ? (
              <p className="text-sm text-muted-foreground">No additional detail available.</p>
            ) : null}
          </div>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

// ─── TraceTable ───────────────────────────────────────────────────────────────

export function TraceTable({
  traces,
  total,
  limit,
  offset,
  onPageChange,
  sessionFilter,
  onSessionFilterChange,
}: TraceTableProps) {
  const [selectedTrace, setSelectedTrace] = useState<QueryTrace | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  const handleRowClick = useCallback((trace: QueryTrace) => {
    setSelectedTrace(trace);
    setSheetOpen(true);
  }, []);

  const currentPage = Math.floor(offset / limit);
  const totalPages = Math.ceil(total / limit);
  const hasPrev = offset > 0;
  const hasNext = offset + limit < total;

  return (
    <section>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-lg font-semibold text-foreground">
          Query Traces{" "}
          <span className="text-sm font-normal text-muted-foreground">({total} total)</span>
        </h2>

        {/* Session filter */}
        <Input
          type="text"
          value={sessionFilter ?? ""}
          onChange={(e) => onSessionFilterChange(e.target.value)}
          placeholder="Filter by session ID..."
          className="w-full sm:w-64"
        />
      </div>

      <div className="rounded-lg border border-border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-card hover:bg-card">
              <TableHead className="w-8 px-4 py-3" />
              <TableHead className="px-4 py-3 text-xs font-semibold uppercase tracking-wide">
                Query
              </TableHead>
              <TableHead className="px-4 py-3 text-xs font-semibold uppercase tracking-wide">
                Session
              </TableHead>
              <TableHead className="px-4 py-3 text-xs font-semibold uppercase tracking-wide">
                Confidence
              </TableHead>
              <TableHead className="px-4 py-3 text-xs font-semibold uppercase tracking-wide">
                Latency
              </TableHead>
              <TableHead className="px-4 py-3 text-xs font-semibold uppercase tracking-wide">
                Time
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {traces.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={6}
                  className="px-4 py-8 text-center text-sm text-muted-foreground"
                >
                  No traces found.
                </TableCell>
              </TableRow>
            ) : (
              traces.map((trace) => {
                const confidenceColor =
                  trace.confidence_score === null
                    ? "text-muted-foreground"
                    : trace.confidence_score >= 70
                      ? "text-success"
                      : trace.confidence_score >= 40
                        ? "text-warning"
                        : "text-destructive";

                return (
                  <TableRow
                    key={trace.id}
                    className="cursor-pointer"
                    onClick={() => handleRowClick(trace)}
                  >
                    <TableCell className="px-4 py-3 text-xs text-muted-foreground">
                      ▶
                    </TableCell>
                    <TableCell
                      className="max-w-[200px] truncate px-4 py-3 text-sm text-foreground"
                      title={trace.query}
                    >
                      {trace.query}
                    </TableCell>
                    <TableCell className="px-4 py-3 text-xs text-muted-foreground">
                      {trace.session_id.slice(0, 8)}...
                    </TableCell>
                    <TableCell className={cn("px-4 py-3 text-sm font-medium", confidenceColor)}>
                      {trace.confidence_score !== null ? `${trace.confidence_score}` : "\u2014"}
                    </TableCell>
                    <TableCell className="px-4 py-3 text-sm text-foreground">{trace.latency_ms} ms</TableCell>
                    <TableCell className="px-4 py-3 text-xs text-muted-foreground">
                      {new Date(trace.created_at).toLocaleString()}
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 ? (
        <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Page {currentPage + 1} of {totalPages}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={!hasPrev}
              onClick={() => onPageChange(offset - limit)}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!hasNext}
              onClick={() => onPageChange(offset + limit)}
            >
              Next
            </Button>
          </div>
        </div>
      ) : null}

      {/* Trace Detail Sheet */}
      <TraceDetailSheet
        trace={selectedTrace}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
      />
    </section>
  );
}
