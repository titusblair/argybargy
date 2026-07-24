import preact from "@preact/preset-vite";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

export default defineConfig({
  build: {
    assetsInlineLimit: 100_000_000,
    chunkSizeWarningLimit: 5000,
    cssCodeSplit: false,
  },
  plugins: [preact(), tailwindcss(), viteSingleFile()],
});
