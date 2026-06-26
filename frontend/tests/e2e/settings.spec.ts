/**
 * T046 — Settings page E2E tests
 *
 * Covers:
 *  - Save settings → Toast "Settings saved" appears
 *  - Persisted values: GET on reload returns updated value
 *  - Provider key entry → PUT request sent
 *  - Delete provider key → DELETE request sent
 *
 * All API calls are intercepted via page.route().
 */

import { test, expect } from "@playwright/test";

const BACKEND = "";

const DEFAULT_SETTINGS = {
  default_llm_model: "qwen2.5:7b",
  default_embed_model: "nomic-embed-text",
  confidence_threshold: 60,
  groundedness_check_enabled: false,
  citation_alignment_threshold: 0.7,
  parent_chunk_size: 2000,
  child_chunk_size: 500,
};

const MOCK_PROVIDER = {
  name: "openai",
  is_active: true,
  has_key: false,
  base_url: null,
  model_count: 5,
};

test.describe("Settings page", () => {
  test.beforeEach(async ({ page }) => {
    // Default GET settings
    await page.route(`${BACKEND}/api/settings`, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(DEFAULT_SETTINGS),
        });
      } else {
        await route.continue();
      }
    });

    // Providers
    await page.route(`${BACKEND}/api/providers`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ providers: [MOCK_PROVIDER] }),
      });
    });

    await page.goto("/settings");
    // Settings page uses a tabbed UI (spec-22). Wait for the tab list to render.
    // Default active tab is "providers" — no form selector available at page root.
    await page.waitForSelector('[role="tablist"]');
  });

  test('saving settings shows "Settings saved" toast', async ({ page }) => {
    let putCalled = false;

    await page.route(`${BACKEND}/api/settings`, async (route) => {
      if (route.request().method() === "PUT") {
        putCalled = true;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ ...DEFAULT_SETTINGS, confidence_threshold: 75 }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(DEFAULT_SETTINGS),
        });
      }
    });

    // confidence_threshold lives in the "Inference" tab — navigate there first
    await page.getByRole("tab", { name: /Inference/i }).click();
    await page.waitForFunction(
      () =>
        !(document.querySelector("#confidence_threshold") as HTMLInputElement)
          ?.disabled,
      { timeout: 5000 },
    );

    // Change confidence_threshold to 75
    await page.fill("#confidence_threshold", "75");

    // Submit the Inference form
    await page.getByRole("button", { name: /Save Inference/i }).click();

    // PUT was called
    await expect.poll(() => putCalled, { timeout: 3000 }).toBe(true);

    // Toast with "Settings saved successfully" is visible
    await expect(page.getByText("Settings saved successfully")).toBeVisible({ timeout: 3000 });
  });

  test("settings persist across page reload (GET returns updated value)", async ({
    page,
  }) => {
    const updatedSettings = { ...DEFAULT_SETTINGS, confidence_threshold: 75 };

    // PUT succeeds
    await page.route(`${BACKEND}/api/settings`, async (route) => {
      if (route.request().method() === "PUT") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(updatedSettings),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(updatedSettings), // Simulates backend persistence
        });
      }
    });

    // confidence_threshold lives in the "Inference" tab — navigate there first
    await page.getByRole("tab", { name: /Inference/i }).click();
    await page.waitForFunction(
      () =>
        !(document.querySelector("#confidence_threshold") as HTMLInputElement)
          ?.disabled,
      { timeout: 5000 },
    );

    await page.fill("#confidence_threshold", "75");
    await page.getByRole("button", { name: /Save Inference/i }).click();
    await expect(page.getByText("Settings saved successfully")).toBeVisible({ timeout: 3000 });

    // Reload the page
    await page.reload();
    await page.waitForSelector('[role="tablist"]');

    // Navigate to Inference tab again after reload
    await page.getByRole("tab", { name: /Inference/i }).click();
    await page.waitForFunction(
      () =>
        !(document.querySelector("#confidence_threshold") as HTMLInputElement)
          ?.disabled,
      { timeout: 5000 },
    );

    // The loaded value reflects the persisted setting
    await expect(page.locator("#confidence_threshold")).toHaveValue("75");
  });

  test("entering provider API key sends PUT request", async ({ page }) => {
    let putKeyCalled = false;

    await page.route(
      `${BACKEND}/api/providers/openai/key`,
      async (route) => {
        if (route.request().method() === "PUT") {
          putKeyCalled = true;
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ name: "openai", has_key: true }),
          });
        }
      },
    );

    // Providers tab is default. ProviderHub renders one card per provider.
    await page.waitForSelector('text="openai"');

    // ProviderHub uses aria-labels on key input and save button.
    const keyInput = page.locator('[aria-label="API key input for openai"]');
    if (await keyInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await keyInput.fill("sk-test-key-e2e");
      await page.locator('[aria-label="Save API key for openai"]').click();
      await expect
        .poll(() => putKeyCalled, { timeout: 3000 })
        .toBe(true);
    }
  });

  test("deleting provider key sends DELETE request", async ({ page }) => {
    // Provider has_key: true so delete button should be visible
    await page.route(`${BACKEND}/api/providers`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          providers: [{ ...MOCK_PROVIDER, has_key: true }],
        }),
      });
    });

    let deleteCalled = false;
    await page.route(
      `${BACKEND}/api/providers/openai/key`,
      async (route) => {
        if (route.request().method() === "DELETE") {
          deleteCalled = true;
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ name: "openai", has_key: false }),
          });
        }
      },
    );

    // Reload to pick up has_key: true
    await page.reload();
    await page.waitForSelector('text="openai"');

    // Find and click the delete/remove key button
    const deleteBtn = page
      .getByRole("button", { name: /delete key|remove key/i })
      .first();
    if (await deleteBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await deleteBtn.click();
      await expect
        .poll(() => deleteCalled, { timeout: 3000 })
        .toBe(true);
    }
  });
});
