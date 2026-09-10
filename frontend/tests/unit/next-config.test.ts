/**
 * Task 2.2 — static regression for the proxy limits that close BUG-054 and
 * BUG-040, plus the hard constraint that ties the client idle watchdog to them.
 *
 * next.config.ts is imported directly: its only import is a type, so no Next
 * runtime loads under vitest. Both keys live under `experimental`.
 */
import { describe, test, expect } from "vitest";
import nextConfig from "@/next.config";
import { STREAM_IDLE_TIMEOUT_MS } from "@/hooks/useStreamChat";

// Cold first LLM call measured at 31.1 s (qwen2.5:7b, engram #4435).
const COLD_FIRST_CALL_MS = 31_100;

describe("next.config — proxy limits (BUG-054 / BUG-040, task 2.2)", () => {
  test("experimental.proxyTimeout is a finite number of at least 300_000 ms (BUG-054, task 2.2)", () => {
    const t = nextConfig.experimental?.proxyTimeout;
    expect(typeof t).toBe("number");
    expect(Number.isFinite(t)).toBe(true);
    expect(t).toBeGreaterThanOrEqual(300_000);
  });

  test("experimental.proxyClientMaxBodySize is exactly 104_857_600 bytes (BUG-040, task 2.2)", () => {
    expect(nextConfig.experimental?.proxyClientMaxBodySize).toBe(104_857_600);
  });

  test("STREAM_IDLE_TIMEOUT_MS clears the measured cold-load gap and sits strictly inside the proxy window (hard constraint)", () => {
    expect(STREAM_IDLE_TIMEOUT_MS).toBeGreaterThanOrEqual(2 * COLD_FIRST_CALL_MS);
    expect(STREAM_IDLE_TIMEOUT_MS).toBeLessThan(nextConfig.experimental!.proxyTimeout!);
  });
});
