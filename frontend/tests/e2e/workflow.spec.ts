import { test, expect } from "@playwright/test";

/**
 * SC-003: End-to-end cross-page workflow test.
 * Journey: Create collection → upload document → wait for completed → chat with that collection.
 */
test("SC-003 end-to-end workflow: create collection → upload → chat", async ({ page }) => {
  const collectionName = `e2e-workflow-${Date.now()}`;

  // Step 1: Create a new collection
  await page.goto("/collections");
  await page.getByRole("button", { name: /new collection/i }).click();

  const nameInput = page.getByLabel(/name/i);
  await nameInput.fill(collectionName);
  await page.getByRole("button", { name: /create/i }).click();

  // Collection card should appear in the grid
  await expect(page.getByText(collectionName)).toBeVisible({ timeout: 10000 });

  // Step 2: Navigate to the collection's documents page
  await page.getByText(collectionName).click();
  await expect(page).toHaveURL(/\/documents\//);

  // Step 3: Upload a valid file (small text file)
  const fileContent = Buffer.from("# Test document\nThis is a test for the e2e workflow.");
  await page.getByTestId("dropzone").evaluate((el) => {
    el.dispatchEvent(new Event("dragenter"));
  });

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles({
    name: "test-workflow.md",
    mimeType: "text/markdown",
    buffer: fileContent,
  });

  // Step 4: Wait for "completed" status badge
  await expect(page.getByText(/completed/i)).toBeVisible({ timeout: 60000 });

  // Step 5: Navigate to chat page
  await page.goto("/chat");
  await expect(page).toHaveURL(/\/chat/);

  // Step 6: Select the collection
  const collectionCheckbox = page.getByLabel(collectionName);
  await collectionCheckbox.check();

  // Step 7: Submit a query
  const textarea = page.getByRole("textbox");
  await textarea.fill("What is this document about?");
  await page.getByRole("button", { name: /send/i }).click();

  // Step 8: Verify streamed response appears
  await expect(page.locator(".assistant-message, [data-role='assistant']")).toBeVisible({
    timeout: 30000,
  });
});
