/**
 * BUG-102 — the stage-timings chart drops bare-number stages.
 *
 * The backend writes two shapes into `stage_timings` side by side:
 *   - `{duration_ms, failed?}` objects for graph nodes, and
 *   - bare numbers for the research accumulators, written directly at
 *     research_nodes.py:139-140/200-201/232-233/320-321 as `research_orchestrator_ms`,
 *     `research_orchestrator_calls`, `research_tools_ms`, `research_tools_calls`.
 *
 * `buildChartData` read `.duration_ms` off every value, so a bare number yielded
 * `undefined`. The 18.1s orchestrator (69% of a 26.1s turn) rendered as an empty bar
 * while the 1.9s intent_classification looked dominant. The chart did not merely omit
 * the bottleneck — it named the wrong one.
 *
 * The `_calls` keys are counters, not durations. Plotting a call count on a
 * millisecond axis would swap one misreport for another, so they are excluded rather
 * than coerced.
 */
import { describe, test, expect } from "vitest";
import { buildChartData } from "@/components/StageTimingsChart";

/** The shape actually observed in P6-S1, trimmed to the relevant keys. */
const REAL_TIMINGS = {
  intent_classification: { duration_ms: 1900 },
  research_orchestrator_ms: 18108.8,
  research_orchestrator_calls: 3,
  research_tools_ms: 4200,
  research_tools_calls: 6,
  compress: { duration_ms: 1904.2 },
};

function byStage(data: ReturnType<typeof buildChartData>, stage: string) {
  return data.find((d) => d.stage === stage);
}

describe("buildChartData — BUG-102", () => {
  test("plots a bare numeric stage at its real duration", () => {
    const data = buildChartData(REAL_TIMINGS);

    expect(byStage(data, "research_orchestrator_ms")?.duration_ms).toBe(18108.8);
  });

  test("the dominant stage is the one that actually dominated", () => {
    const data = buildChartData(REAL_TIMINGS);
    const largest = data.reduce((a, b) => (b.duration_ms > a.duration_ms ? b : a));

    // Pre-fix this was intent_classification at 1900ms, because the 18.1s
    // orchestrator resolved to undefined and sorted as nothing.
    expect(largest.stage).toBe("research_orchestrator_ms");
  });

  test("call counters are not plotted as durations", () => {
    const data = buildChartData(REAL_TIMINGS);

    expect(byStage(data, "research_orchestrator_calls")).toBeUndefined();
    expect(byStage(data, "research_tools_calls")).toBeUndefined();
  });

  test("no row is emitted with an undefined duration", () => {
    const data = buildChartData(REAL_TIMINGS);

    for (const point of data) {
      expect(typeof point.duration_ms).toBe("number");
      expect(Number.isFinite(point.duration_ms)).toBe(true);
    }
  });

  test("object-shaped stages keep working", () => {
    const data = buildChartData(REAL_TIMINGS);

    expect(byStage(data, "intent_classification")?.duration_ms).toBe(1900);
    expect(byStage(data, "compress")?.duration_ms).toBe(1904.2);
  });

  test("the failed flag survives on object-shaped stages", () => {
    const data = buildChartData({
      retrieval: { duration_ms: 120, failed: true },
      rerank: { duration_ms: 80 },
    });

    expect(byStage(data, "retrieval")?.failed).toBe(true);
    expect(byStage(data, "rerank")?.failed).toBe(false);
  });

  test("bare numeric stages are not marked failed", () => {
    const data = buildChartData({ research_tools_ms: 4200 });

    expect(byStage(data, "research_tools_ms")?.failed).toBe(false);
  });

  test("malformed entries are dropped rather than rendered as empty bars", () => {
    const data = buildChartData({
      good: { duration_ms: 10 },
      missing_duration: {} as { duration_ms: number },
      not_a_number: "nope" as unknown as number,
    });

    expect(data).toHaveLength(1);
    expect(data[0].stage).toBe("good");
  });

  test("an empty timings map produces no rows", () => {
    expect(buildChartData({})).toEqual([]);
  });
});
