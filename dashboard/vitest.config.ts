import preact from "@preact/preset-vite";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [preact()],
  test: {
    environment: "jsdom",
    exclude: ["tests/**", "node_modules/**"],
    globals: true,
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
  },
});
