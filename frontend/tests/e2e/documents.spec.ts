/**
 * T045 — Documents page E2E tests
 *
 * Covers:
 *  - File > 50 MB: size error shown, NO ingest API request made
 *  - .exe file: extension error shown, NO ingest API request made
 *  - Valid PDF upload → progress shown → "Completed" badge
 *
 * react-dropzone validates MIME type; our custom guard in DocumentUploader
 * validates both size AND extension. Tests pass files via the hidden
 * <input type="file"> that react-dropzone exposes.
 */

import { test, expect } from "@playwright/test";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";

const BACKEND = "";
const COLLECTION_ID = "col-e2e-docs";

test.describe("Documents page — file upload validation and progress", () => {
  test.beforeEach(async ({ page }) => {
    // Mock documents list
    await page.route(
      `${BACKEND}/api/documents?collection_id=${COLLECTION_ID}`,
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ documents: [] }),
        });
      },
    );

    await page.goto(`/documents/${COLLECTION_ID}`);
    // Wait for the upload drop zone to render
    await page.waitForSelector('[aria-label="File upload drop zone"]');
  });

  test(">50 MB file shows size error without calling the ingest API", async ({
    page,
  }) => {
    let ingestCalled = false;
    await page.route(
      `${BACKEND}/api/collections/${COLLECTION_ID}/ingest`,
      async (route) => {
        ingestCalled = true;
        await route.continue();
      },
    );

    // 50 MB + 1 byte exceeds UPLOAD_CONSTRAINTS.maxSizeBytes (50 * 1024 * 1024).
    // Playwright's setInputFiles rejects in-memory buffers > 50 MB, so write
    // the oversized file to disk and pass the path instead.
    const tmpPath = path.join(os.tmpdir(), `large-e2e-${Date.now()}.pdf`);
    fs.writeFileSync(tmpPath, Buffer.alloc(50 * 1024 * 1024 + 1));
    try {
      await page.locator('input[type="file"]').setInputFiles(tmpPath);
    } finally {
      fs.unlinkSync(tmpPath);
    }

    // Error message contains "50 MB"
    await expect(page.locator('p[role="alert"]')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('p[role="alert"]')).toContainText("50 MB");

    // No network call was made to the ingest endpoint
    expect(ingestCalled).toBe(false);
  });

  test(".exe file shows extension error without calling the ingest API", async ({
    page,
  }) => {
    let ingestCalled = false;
    await page.route(
      `${BACKEND}/api/collections/${COLLECTION_ID}/ingest`,
      async (route) => {
        ingestCalled = true;
        await route.continue();
      },
    );

    // MIME is pdf (so react-dropzone accept filter passes),
    // but extension is .exe (our custom guard catches it)
    await page.locator('input[type="file"]').setInputFiles({
      name: "malicious.exe",
      mimeType: "application/pdf",
      buffer: Buffer.from("fake executable content"),
    });

    // Extension error
    await expect(page.locator('p[role="alert"]')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('p[role="alert"]')).toContainText("unsupported file type");

    // No network call
    expect(ingestCalled).toBe(false);
  });

  test("valid PDF upload → progress spinner → Completed badge", async ({
    page,
  }) => {
    const jobId = "job-e2e-1";

    // Ingest POST → returns started job
    await page.route(
      `${BACKEND}/api/collections/${COLLECTION_ID}/ingest`,
      async (route) => {
        if (route.request().method() === "POST") {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              job_id: jobId,
              document_id: "doc-e2e-1",
              status: "started",
              chunks_processed: 0,
              chunks_total: null,
              error_message: null,
              started_at: new Date().toISOString(),
              completed_at: null,
            }),
          });
        }
      },
    );

    // Job poll GET → immediately returns completed
    await page.route(
      `${BACKEND}/api/collections/${COLLECTION_ID}/ingest/${jobId}`,
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            job_id: jobId,
            document_id: "doc-e2e-1",
            status: "completed",
            chunks_processed: 10,
            chunks_total: 10,
            error_message: null,
            started_at: new Date().toISOString(),
            completed_at: new Date().toISOString(),
          }),
        });
      },
    );

    // Upload valid PDF
    await page.locator('input[type="file"]').setInputFiles({
      name: "document.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 fake pdf content"),
    });

    // "Uploading…" spinner text appears first
    await expect(page.getByText("Uploading…")).toBeVisible({ timeout: 3000 });

    // IngestionProgress shows "Complete!" briefly, then fires onComplete().
    // DocumentUploader transitions status → 'done' and renders the stable
    // "Done" badge. Check the stable end-state to avoid a timing race.
    await expect(page.getByText("Done")).toBeVisible({ timeout: 10000 });
  });
});
