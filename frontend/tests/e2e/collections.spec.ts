/**
 * T044 — Collections page E2E tests
 *
 * Covers:
 *  - Create collection with valid name → dialog closes
 *  - Invalid name ("-foo") → validation error shown inline
 *  - Duplicate name conflict (409) → dialog stays open, error shown
 *  - Delete collection with confirmation → DELETE request sent
 *
 * All API calls are intercepted via page.route().
 */

import { test, expect } from "@playwright/test";

const BACKEND = "http://localhost:8000";

const EXISTING_COLLECTION = {
  id: "col-e2e-existing",
  name: "existing-col",
  description: null,
  embedding_model: "nomic-embed-text",
  chunk_profile: "default",
  document_count: 0,
  created_at: "2024-01-01T00:00:00Z",
};

test.describe("Collections page", () => {
  test.beforeEach(async ({ page }) => {
    // Default GET handler — returns one existing collection
    await page.route(`${BACKEND}/api/collections`, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ collections: [EXISTING_COLLECTION] }),
        });
      } else {
        // Pass POST/DELETE through to individual test handlers
        await route.continue();
      }
    });

    // Embed models for the CreateCollectionDialog Select dropdown
    await page.route(`${BACKEND}/api/models/embed`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ models: [] }),
      });
    });

    await page.goto("/collections");
    await page.waitForSelector('text="existing-col"');
  });

  test("create collection with valid name → dialog closes", async ({
    page,
  }) => {
    // Override to handle POST
    await page.route(`${BACKEND}/api/collections`, async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "col-new",
            name: "my-collection",
            description: null,
            embedding_model: "nomic-embed-text",
            chunk_profile: "default",
            document_count: 0,
            created_at: "2024-01-01T00:00:00Z",
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ collections: [EXISTING_COLLECTION] }),
        });
      }
    });

    // Open dialog from the header button
    await page.getByRole("button", { name: /New Collection/i }).first().click();

    // Type a valid slug
    await page.getByPlaceholder("my-collection").fill("my-collection");

    // No validation error
    await expect(page.getByRole("alert")).not.toBeVisible();

    // Submit
    await page.getByRole("button", { name: /^Create$/i }).click();

    // Dialog should close after success
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 3000 });
  });

  test('invalid name "-foo" shows inline validation error', async ({
    page,
  }) => {
    await page
      .getByRole("button", { name: /New Collection/i })
      .first()
      .click();

    await page.getByPlaceholder("my-collection").fill("-foo");

    // Slug starts with '-' → role=alert error
    await expect(page.getByRole("alert")).toBeVisible();

    // Submit button is disabled
    await expect(
      page.getByRole("button", { name: /^Create$/i }),
    ).toBeDisabled();
  });

  test("duplicate name conflict (409) keeps dialog open with error", async ({
    page,
  }) => {
    await page.route(`${BACKEND}/api/collections`, async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 409,
          contentType: "application/json",
          body: JSON.stringify({
            error: {
              code: "COLLECTION_NAME_CONFLICT",
              message: "A collection with this name already exists.",
            },
            trace_id: "t-409",
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ collections: [EXISTING_COLLECTION] }),
        });
      }
    });

    await page
      .getByRole("button", { name: /New Collection/i })
      .first()
      .click();

    await page.getByPlaceholder("my-collection").fill("existing-col");
    await page.getByRole("button", { name: /^Create$/i }).click();

    // Dialog STAYS open — conflict error appears
    await expect(page.getByRole("alert")).toBeVisible({ timeout: 3000 });
    await expect(page.getByRole("alert")).toContainText(
      "already exists",
    );
    await expect(page.getByRole("dialog")).toBeVisible();
  });

  test("delete collection with confirmation sends DELETE request", async ({
    page,
  }) => {
    let deleteCalled = false;

    await page.route(
      `${BACKEND}/api/collections/${EXISTING_COLLECTION.id}`,
      async (route) => {
        deleteCalled = true;
        await route.fulfill({ status: 204, body: "" });
      },
    );

    // Click the Delete button on the collection card
    await page
      .getByRole("button", {
        name: /Delete collection existing-col/i,
      })
      .click();

    // Confirmation dialog is visible
    await expect(page.getByText("Delete collection?")).toBeVisible();

    // Confirm — the button with text "Delete" (NOT "Delete collection existing-col")
    await page.getByRole("button", { name: "Delete" }).click();

    // DELETE API was called
    await expect
      .poll(() => deleteCalled, { timeout: 3000 })
      .toBe(true);
  });
});
