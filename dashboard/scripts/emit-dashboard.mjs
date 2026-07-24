#!/usr/bin/env node
// Reads the built single-file dashboard (dashboard/dist/index.html), asserts it's a
// real self-contained production build, and copies it to argybargy/dashboard.html —
// the artifact the Python server ships and loads at runtime.
//
// Run after `pnpm --dir dashboard run build`:
//   node dashboard/scripts/emit-dashboard.mjs

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const distPath = resolve(__dirname, "..", "dist", "index.html");
const outPath = resolve(__dirname, "..", "..", "argybargy", "dashboard.html");

const MIN_BYTES = 20_000;

function fail(message) {
  console.error(`emit-dashboard: FAILED — ${message}`);
  process.exit(1);
}

if (!existsSync(distPath)) {
  fail(
    `build artifact not found at ${distPath} — run \`pnpm --dir dashboard run build\` first`
  );
}

const html = readFileSync(distPath, "utf-8");
const byteSize = Buffer.byteLength(html, "utf-8");

if (byteSize <= MIN_BYTES) {
  fail(
    `build artifact is only ${byteSize} bytes (expected > ${MIN_BYTES}) — looks truncated or empty`
  );
}

// Same checks the build relies on to guarantee zero external references:
// no <link> tags, no url()-based @import, no http(s) src attributes, no hotlinked images.
const externalRefChecks = [
  { name: "<link ...> tag", regex: /<link\s/i },
  {
    name: "@import url(...) from a URL",
    regex: /@import\s+url\(\s*['"]?https?:/i,
  },
  {
    name: 'src="http..." with a live URL',
    regex: /\ssrc\s*=\s*["']https?:\/\//i,
  },
  { name: "hotlinked <img> src", regex: /<img[^>]+src\s*=\s*["']https?:\/\//i },
];

const externalRefs = externalRefChecks.filter(({ regex }) => regex.test(html));

if (externalRefs.length > 0) {
  const names = externalRefs.map((r) => r.name).join(", ");
  fail(
    `found external reference(s) in build output: ${names} — build is not self-contained`
  );
}

if (!html.includes('id="app"')) {
  fail('built HTML is missing id="app" mount point — unexpected build output');
}

// Guard against emitting a VITE_DEMO / fixture-seeded build as the shipped
// "prod" artifact. `ak_9f2ce41b7a6d` is the claude access-key code baked into
// state/fixture.ts's FIXTURE — it only ever ends up inlined in the bundle if
// the build seeded demo data, so its presence here means this dist output is
// a demo build, not a clean prod build.
const DEMO_MARKER = "ak_9f2ce41b7a6d";

if (html.includes(DEMO_MARKER)) {
  fail(
    "refusing to emit: this looks like a VITE_DEMO/fixture build (found the " +
      `fixture marker "${DEMO_MARKER}" in the bundle) — run \`vite build\` ` +
      "without VITE_DEMO (or use `pnpm --dir dashboard run artifact`) first"
  );
}

writeFileSync(outPath, html, "utf-8");

console.log(`emit-dashboard: wrote ${outPath}`);
console.log(
  `emit-dashboard: bytes=${byteSize} ext-refs=${externalRefs.length}`
);
