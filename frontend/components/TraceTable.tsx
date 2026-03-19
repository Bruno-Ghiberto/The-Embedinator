"use client";

import React, { useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { getTraceDetail } from "@/lib/api";
import type { QueryTrace, QueryTraceDetail } from "@/lib/types";
import type { StageTimingsChartProps } from "@/components/StageTimingsChart";

// ─── Dynamic import for recharts (no SSR) ─────────────────────────────────────

const StageTimingsChart = dynamic<StageTimingsChartProps>(
  () =>
    import("@/components/StageTimingsChart").then((m) => m.StageTimingsChart),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-16 items-center justify-center text-sm text-gray-400">
        Loading chart…
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

// ─── ExpandedRow ─────────────────────────────────────────────────────────────

interface ExpandedRowProps {
  traceId: string;
  meta_reasoning_triggered: boolean;
}

const ExpandedRow = React.memo(function ExpandedRow({
  traceId,
  meta_reasoning_triggered,
}: ExpandedRowProps) {
  const [detail, setDetail] = useState<QueryTraceDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch on mount — only called once per expansion
  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    getTraceDetail(traceId)
      .then((d) => {
        if (!cancelled) {
          setDetail(d);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message || "Failed to load trace detail");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // traceId is a primitive string — safe as dependency
  }, [traceId]);

  if (loading) {
    return (
      <td colSpan={6} className="bg-gray-50 px-6 py-4">
        <p className="text-sm text-gray-500">Loading trace detail…</p>
      </td>
    );
  }

  if (error) {
    return (
      <td colSpan={6} className="bg-gray-50 px-6 py-4">
        <p className="text-sm text-red-600">{error}</p>
      </td>
    );
  }

  if (!detail) {
    return null;
  }

  return (
    <td colSpan={6} className="bg-gray-50 px-6 py-4">
      <div className="space-y-3 text-sm">
        {/* Meta-reasoning flag */}
        <div className="flex items-center gap-2">
          <span className="font-medium text-gray-700">Meta-Reasoning:</span>
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              meta_reasoning_triggered
                ? "bg-purple-100 text-purple-800"
                : "bg-gray-100 text-gray-600"
            }`}
          >
            {meta_reasoning_triggered ? "Triggered" : "Not triggered"}
          </span>
        </div>

        {/* Sub-questions */}
        {detail.sub_questions.length > 0 ? (
          <div>
            <p className="mb-1 font-medium text-gray-700">
              Sub-questions ({detail.sub_questions.length}):
            </p>
            <ul className="list-inside list-disc space-y-0.5 text-gray-600">
              {detail.sub_questions.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {/* Reasoning steps */}
        {detail.reasoning_steps.length > 0 ? (
          <div>
            <p className="mb-1 font-medium text-gray-700">
              Reasoning Steps ({detail.reasoning_steps.length}):
            </p>
            <ol className="list-inside list-decimal space-y-0.5 text-gray-600">
              {detail.reasoning_steps.map((step, i) => (
                <li key={i}>
                  <code className="text-xs">{JSON.stringify(step)}</code>
                </li>
              ))}
            </ol>
          </div>
        ) : null}

        {/* Strategy switches */}
        {detail.strategy_switches.length > 0 ? (
          <div>
            <p className="mb-1 font-medium text-gray-700">
              Strategy Switches ({detail.strategy_switches.length}):
            </p>
            <ul className="list-inside list-disc space-y-0.5 text-gray-600">
              {detail.strategy_switches.map((sw, i) => (
                <li key={i}>
                  <code className="text-xs">{JSON.stringify(sw)}</code>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {/* Stage Timings chart — only when timings data is present */}
        {detail.stage_timings && Object.keys(detail.stage_timings).length > 0 && (
          <div className="mt-4">
            <h3 className="text-sm font-medium mb-2">Stage Timings</h3>
            <StageTimingsChart timings={detail.stage_timings} />
          </div>
        )}

        {detail.sub_questions.length === 0 &&
        detail.reasoning_steps.length === 0 &&
        detail.strategy_switches.length === 0 &&
        !(detail.stage_timings && Object.keys(detail.stage_timings).length > 0) ? (
          <p className="text-gray-500">No additional detail available.</p>
        ) : null}
      </div>
    </td>
  );
});

// ─── TraceRow ────────────────────────────────────────────────────────────────

interface TraceRowProps {
  trace: QueryTrace;
  isExpanded: boolean;
  onToggle: (id: string) => void;
}

const TraceRow = React.memo(function TraceRow({
  trace,
  isExpanded,
  onToggle,
}: TraceRowProps) {
  const confidenceColor =
    trace.confidence_score === null
      ? "text-gray-400"
      : trace.confidence_score >= 70
        ? "text-green-700"
        : trace.confidence_score >= 40
          ? "text-yellow-700"
          : "text-red-700";

  return (
    <>
      <tr
        className="cursor-pointer border-b border-gray-100 hover:bg-gray-50"
        onClick={() => onToggle(trace.id)}
      >
        <td className="px-4 py-3 text-xs text-gray-500">
          {isExpanded ? "▼" : "▶"}
        </td>
        <td
          className="max-w-[200px] truncate px-4 py-3 text-sm text-gray-900"
          title={trace.query}
        >
          {trace.query}
        </td>
        <td className="px-4 py-3 text-xs text-gray-500">
          {trace.session_id.slice(0, 8)}…
        </td>
        <td className={`px-4 py-3 text-sm font-medium ${confidenceColor}`}>
          {trace.confidence_score !== null ? `${trace.confidence_score}` : "—"}
        </td>
        <td className="px-4 py-3 text-sm text-gray-600">{trace.latency_ms} ms</td>
        <td className="px-4 py-3 text-xs text-gray-400">
          {new Date(trace.created_at).toLocaleString()}
        </td>
      </tr>
      {isExpanded ? (
        <tr className="border-b border-gray-100">
          <ExpandedRow
            traceId={trace.id}
            meta_reasoning_triggered={trace.meta_reasoning_triggered}
          />
        </tr>
      ) : null}
    </>
  );
});

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
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const handleToggle = useCallback((id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  }, []);

  const currentPage = Math.floor(offset / limit);
  const totalPages = Math.ceil(total / limit);
  const hasPrev = offset > 0;
  const hasNext = offset + limit < total;

  return (
    <section>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-lg font-semibold text-gray-900">
          Query Traces{" "}
          <span className="text-sm font-normal text-gray-500">({total} total)</span>
        </h2>

        {/* Session filter */}
        <input
          type="text"
          value={sessionFilter ?? ""}
          onChange={(e) => onSessionFilterChange(e.target.value)}
          placeholder="Filter by session ID…"
          className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 sm:w-64"
        />
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200 text-left">
          <thead className="bg-gray-50">
            <tr>
              <th className="w-8 px-4 py-3" />
              <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600">
                Query
              </th>
              <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600">
                Session
              </th>
              <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600">
                Confidence
              </th>
              <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600">
                Latency
              </th>
              <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600">
                Time
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {traces.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-4 py-8 text-center text-sm text-gray-400"
                >
                  No traces found.
                </td>
              </tr>
            ) : (
              traces.map((trace) => (
                <TraceRow
                  key={trace.id}
                  trace={trace}
                  isExpanded={expandedId === trace.id}
                  onToggle={handleToggle}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 ? (
        <div className="mt-4 flex items-center justify-between text-sm text-gray-600">
          <span>
            Page {currentPage + 1} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              disabled={!hasPrev}
              onClick={() => onPageChange(offset - limit)}
              className="rounded-md border border-gray-300 px-3 py-1.5 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Previous
            </button>
            <button
              disabled={!hasNext}
              onClick={() => onPageChange(offset + limit)}
              className="rounded-md border border-gray-300 px-3 py-1.5 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
