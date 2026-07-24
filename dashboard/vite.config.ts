import { defineConfig } from "vite";
import preact from "@preact/preset-vite";
import tailwindcss from "@tailwindcss/vite";
import { viteSingleFile } from "vite-plugin-singlefile";

export default defineConfig({
  plugins: [preact(), tailwindcss(), viteSingleFile()],
  build: { cssCodeSplit: false, assetsInlineLimit: 100000000, chunkSizeWarningLimit: 5000 },
});
