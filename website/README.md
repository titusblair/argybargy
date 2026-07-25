# website/ — what to upload to argybargy.dev

**Upload `index.html` from this folder. That's the whole site — one file, nothing else.**

The dashboard screenshot is embedded inside the HTML (base64 WebP), so there are no
images to upload alongside it and nothing can 404. The page makes **zero external
requests** — no CDNs, no fonts, no analytics.

## Uploading it (Hostinger)

hPanel → **File Manager** → open `public_html` → upload `index.html`, replacing the
existing one. Or paste the contents over the old file in the editor.

Copy it from any of these — all identical:

- this folder: `website/index.html`
- raw link: <https://raw.githubusercontent.com/titusblair/argybargy/main/index.html>
- terminal: `curl -L -o index.html https://raw.githubusercontent.com/titusblair/argybargy/main/index.html`

## Why there are two copies in the repo

`/index.html` (repo root) is what **GitHub Pages** serves — Pages only builds from the
repo root or `/docs`, so the file has to live there.

`website/index.html` is the same file in an obvious place to grab for a manual upload.

They are kept byte-identical by `tests/test_website_folder.py`, which fails the build if
they ever drift. **Edit the root `index.html`, then re-copy:**

```bash
cp index.html website/index.html
```

## Once DNS points at GitHub Pages

This folder stops mattering — pushing to `main` deploys the site automatically, and the
screenshot can be un-inlined (referenced from `docs/screenshots/` on the same origin),
which drops the page from ~94 KB to ~26 KB.
