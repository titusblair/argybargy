import preact from "@preact/preset-vite";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [preact()],
  test: {
    environment: "jsdom",
    exclude: ["tests/**/*.spec.ts", "node_modules/**"],
    globals: true,
    include: ["src/**/*.{test,spec}.{ts,tsx}", "tests/**/*.test.ts"],
    setupFiles: ["./vitest.setup.ts"],
  },
});
