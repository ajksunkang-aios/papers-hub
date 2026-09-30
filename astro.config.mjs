// @ts-check
import { defineConfig } from 'astro/config';

// Papers Hub — Astro config.
//
// The site is statically deployed to GitHub Pages from `dist/`. The Python
// build pipeline (crawl_*, build_*) writes JSON data into src/data/, which the
// pages fetch at runtime exactly as before. Astro here is purely a static-site
// generator that lets us share HTML partials (sidebar/header/footer) as
// components and hash-bust assets automatically — no SSR, no runtime framework.
export default defineConfig({
  // GitHub Pages serves the project at the repo root, so no base path.
  site: 'https://ajksunkang-aios.github.io',
  build: {
    // Emit each route as a flat .html file (e.g. /area-picks.html), NOT
    // /area-picks/index.html. The existing pages use relative asset paths
    // (area-picks.js, data/hub.json) that resolve against the page's own
    // directory; directory format would move them into a subfolder and break
    // those relative paths. File format keeps URLs identical to the old site.
    format: 'file',
  },
  // Keep the public/ dir for favicons etc. Data JSON produced by Python lives
  // under src/data/ and is imported/copied by the pages.
  publicDir: './public',
});
