/**
 * T043 — Chat page E2E tests
 *
 * Covers:
 *  - Query submission and streaming token rendering
 *  - Send button disabled during stream, re-enabled on completion
 *  - Confidence indicator rendered after done event
 *  - Citation [1] marker rendered after citation + done events
 *
 * All backend API calls are intercepted via page.route().
 * The NDJSON stream is sent as a single fulfilled response body.
 */

import { test, expect } from "@playwright/test";

const BACKEND = "http://localhost:8000";

const MOCK_COLLECTION = {
  id: "col-e2e-chat",
  name: "E2E Collection",
  description: null,
  embedding_model: "nomic-embed-text",
  chunk_profile: "default",
  document_count: 3,
  created_at: "2024-01-01T00:00:00Z",
};

/** Build a raw NDJSON body from an array of event objects (no "data:" prefix). */
function ndjson(events: object[]): string {
  return events.map((e) => JSON.stringify(e)).join("\n") + "\n";
}

test.describe("Chat page — streaming workflow", () => {
  test.beforeEach(async ({ page }) => {
    // Mock sidebar data
    await page.route(`${BACKEND}/api/collections`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ collections: [MOCK_COLLECTION] }),
      });
    });
    await page.route(`${BACKEND}/api/models/llm`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ models: [] }),
      });
    });
    await page.route(`${BACKEND}/api/models/embed`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ models: [] }),
      });
    });

    await page.goto("/chat");
    // Wait for sidebar collection to load
    await page.waitForSelector('label:has-text("E2E Collection")');
  });

  test("submit query: tokens stream and Send button disabled then re-enabled", async ({
    page,
  }) => {
    await page.route(`${BACKEND}/api/chat`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/x-ndjson",
        body: ndjson([
          { type: "session", session_id: "sess-e2e" },
          { type: "chunk", text: "Hello " },
          { type: "chunk", text: "world!" },
          { type: "done", latency_ms: 200, trace_id: "tr-e2e-1" },
        ]),
      });
    });

    // Select the collection via checkbox
    await page.getByLabel("E2E Collection").check();

    // Type a message
    await page
      .getByPlaceholder(/Ask a question/)
      .fill("What is the capital of France?");

    // Send is enabled before submitting
    await expect(page.getByRole("button", { name: "Send" })).toBeEnabled();

    // Submit
    await page.getByRole("button", { name: "Send" }).click();

    // During stream: button shows "Sending..." and is disabled
    await expect(
      page.getByRole("button", { name: "Sending..." }),
    ).toBeDisabled();

    // After stream completes: button reverts to "Send" and is enabled
    await expect(page.getByRole("button", { name: "Send" })).toBeEnabled({
      timeout: 5000,
    });

    // Streamed content is visible in the chat panel
    await expect(page.getByText("Hello world!")).toBeVisible();
  });

  test("confidence indicator rendered after done event (integer score 0-100)", async ({
    page,
  }) => {
    await page.route(`${BACKEND}/api/chat`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/x-ndjson",
        body: ndjson([
          { type: "chunk", text: "Paris is the capital." },
          { type: "confidence", score: 82 }, // integer, not float 0.82
          { type: "done", latency_ms: 300, trace_id: "tr-e2e-2" },
        ]),
      });
    });

    await page.getByLabel("E2E Collection").check();
    await page
      .getByPlaceholder(/Ask a question/)
      .fill("Capital of France?");
    await page.getByRole("button", { name: "Send" }).click();

    // Wait for stream to finish
    await expect(page.getByRole("button", { name: "Send" })).toBeEnabled({
      timeout: 5000,
    });

    // ConfidenceIndicator: aria-label = "High confidence: 82%" (score 82 ≥ 70 → green)
    await expect(
      page.locator('[aria-label="High confidence: 82%"]'),
    ).toBeVisible();
  });

  test("citation [1] marker is visible after citation + done events", async ({
    page,
  }) => {
    const citation = {
      passage_id: "p-e2e-1",
      document_id: "d-e2e-1",
      document_name: "test-doc.pdf",
      start_offset: 0,
      end_offset: 100,
      text: "Paris is the capital of France.",
      relevance_score: 0.95,
      source_removed: false,
    };

    await page.route(`${BACKEND}/api/chat`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/x-ndjson",
        body: ndjson([
          { type: "chunk", text: "Answer text." },
          { type: "citation", citations: [citation] },
          { type: "done", latency_ms: 200, trace_id: "tr-e2e-3" },
        ]),
      });
    });

    await page.getByLabel("E2E Collection").check();
    await page
      .getByPlaceholder(/Ask a question/)
      .fill("Capital of France?");
    await page.getByRole("button", { name: "Send" }).click();

    // Wait for stream to finish
    await expect(page.getByRole("button", { name: "Send" })).toBeEnabled({
      timeout: 5000,
    });

    // CitationHoverCard renders a trigger with aria-label "Citation 1: test-doc.pdf"
    await expect(
      page.getByRole("button", { name: /Citation 1/i }),
    ).toBeVisible();
  });

  test("clarification event: isStreaming released without a done event", async ({
    page,
  }) => {
    // Backend sends clarification then closes stream — no done event follows
    await page.route(`${BACKEND}/api/chat`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/x-ndjson",
        body: ndjson([
          { type: "clarification", question: "Can you be more specific?" },
        ]),
      });
    });

    await page.getByLabel("E2E Collection").check();
    await page
      .getByPlaceholder(/Ask a question/)
      .fill("vague question");
    await page.getByRole("button", { name: "Send" }).click();

    // Send button re-enables even though no "done" event was sent
    await expect(page.getByRole("button", { name: "Send" })).toBeEnabled({
      timeout: 5000,
    });
  });
});
