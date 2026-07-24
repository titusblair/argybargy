import preact from "@preact/preset-vite";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [preact()],
  test: {
    environment: "jsdom",
    environmentOptions: {
      // jsdom disables window.localStorage for opaque origins (the
      // default "about:blank"-ish URL). Theme persistence tests need a
      // real origin so Storage is available.
      jsdom: { url: "http://localhost/" },
    },
    exclude: ["tests/**/*.spec.ts", "node_modules/**"],
    globals: true,
    include: ["src/**/*.{test,spec}.{ts,tsx}", "tests/**/*.test.ts"],
  },
});
