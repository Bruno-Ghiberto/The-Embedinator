import { test, expect } from "@playwright/test";

const PAGES = [
  { path: "/chat", name: "Chat" },
  { path: "/collections", name: "Collections" },
  { path: "/settings", name: "Settings" },
  { path: "/observability", name: "Observability" },
];

const VIEWPORTS = [
  { width: 768, height: 1024, label: "tablet (768px)" },
  { width: 1024, height: 768, label: "desktop (1024px)" },
];

for (const viewport of VIEWPORTS) {
  test.describe(`Responsive layout at ${viewport.label}`, () => {
    test.beforeEach(async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
    });

    test(`Navigation bar is visible at ${viewport.label}`, async ({ page }) => {
      await page.goto("/chat");
      const nav = page.locator("nav");
      await expect(nav).toBeVisible();
    });

    for (const { path, name } of PAGES) {
      test(`${name} page renders without horizontal overflow at ${viewport.label}`, async ({ page }) => {
        await page.goto(path);
        // Verify no horizontal scrollbar (scrollWidth === clientWidth)
        const hasHorizontalOverflow = await page.evaluate(() => {
          return document.documentElement.scrollWidth > document.documentElement.clientWidth;
        });
        expect(hasHorizontalOverflow).toBe(false);
      });
    }
  });
}
