import { test, expect } from "@playwright/test";

/**
 * SC-003: End-to-end cross-page workflow test.
 * Journey: Create collection → upload document → wait for completed → chat with that collection.
 */
test("SC-003 end-to-end workflow: create collection → upload → chat", async ({ page }) => {
  // Real-stack E2E: create collection + ingest + Ollama inference takes > 30 s.
  // Override Playwright's default 30 s test timeout to 2 minutes.
  test.setTimeout(120_000);

  const collectionName = `e2e-workflow-${Date.now()}`;

  // Step 1: Create a new collection
  await page.goto("/collections");
  await page.getByRole("button", { name: /new collection/i }).click();

  const nameInput = page.getByLabel(/name/i);
  await nameInput.fill(collectionName);
  await page.getByRole("button", { name: /create/i }).click();

  // Collection card should appear in the grid
  // exact: true avoids strict-mode violation with sr-only "Actions for {name}" span
  await expect(page.getByText(collectionName, { exact: true })).toBeVisible({ timeout: 10000 });

  // Step 2: Navigate to the collection's documents page via Actions dropdown
  // CollectionCard titles have no onClick — navigate through the dropdown menu
  await page.getByRole("button", { name: `Actions for ${collectionName}` }).click();
  await page.getByRole("menuitem", { name: /View Documents/i }).click();
  await expect(page).toHaveURL(/\/documents\//);

  // Step 3: Upload a valid file (small text file) via the hidden file input
  // react-dropzone does not need drag events — setInputFiles on the hidden
  // <input type="file"> is sufficient. No data-testid="dropzone" attribute exists.
  const fileContent = Buffer.from("# Test document\nThis is a test for the e2e workflow.");
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles({
    name: "test-workflow.md",
    mimeType: "text/markdown",
    buffer: fileContent,
  });

  // Step 4: Wait for stable "Done" badge (DocumentUploader final state).
  // IngestionProgress shows "Complete!" briefly then fires onComplete() which
  // transitions the file item to status='done' → renders the stable "Done" badge.
  await expect(page.getByText("Done")).toBeVisible({ timeout: 60000 });

  // Step 5: Navigate to chat page
  await page.goto("/chat");
  await expect(page).toHaveURL(/\/chat/);

  // Step 6: Select the collection
  // ChatConfigPanel is a Collapsible — closed by default. Open it first.
  await page.getByRole("button", { name: "Open config panel" }).click();
  // Base UI Checkbox renders both role="checkbox" span AND a hidden native input
  // — getByLabel matches both, causing strict mode violation. Use getByRole.
  await page.getByRole("checkbox", { name: collectionName }).check();

  // Step 7: Submit a query
  // Two textboxes exist on the page (search + message) — use placeholder to target message input
  const textarea = page.getByPlaceholder(/Ask a question/i);
  await textarea.fill("What is this document about?");
  await page.getByRole("button", { name: /send message/i }).click();

  // Step 8: Verify streamed response appears
  // Assistant messages render inside a div.prose-sm — no .assistant-message class exists
  await expect(page.locator(".prose-sm")).toBeVisible({
    timeout: 30000,
  });
});
