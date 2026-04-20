import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  plugins: [react() as any],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    exclude: ["**/node_modules/**", "**/e2e/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      // TODO: raise to 70% once test suite expands — see spec-27 tech-debt
      thresholds: {
        lines: 15,
        branches: 85,
        functions: 67,
        statements: 15,
        autoUpdate: false,  // gate, not ratchet — never auto-raise/lower
      },
      include: ["lib/**", "hooks/**", "components/**"],
      exclude: ["**/*.config.ts", "**/*.d.ts", "node_modules/**"],
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
