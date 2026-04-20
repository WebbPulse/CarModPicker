// Post-build step: crawl the freshly built SPA in a headless Chrome, snapshot
// each public route's rendered HTML, and write it back into dist/ so S3 can
// serve fully-rendered HTML for those routes. Routes not listed here fall
// back to the SPA shell (index.html) via CloudFront's error response.
//
// Why this exists: AdSense/bot crawlers see dist/index.html as a mostly empty
// shell until JS runs. Static routes have no API dependencies, so we can
// render them once at build time with real content baked in.
//
// Run via `npm run build` (wired as a postbuild script).

import { createServer } from 'node:http';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, extname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DIST = resolve(__dirname, '..', 'dist');

// Only prerender routes that render correctly without backend data. The home
// page renders its hero + layout synchronously; its featured-builds/popular-
// parts sections will show loading or empty states in the snapshot, which is
// acceptable (head metadata + hero content are what matter for crawlers).
const ROUTES = [
  '/',
  '/about',
  '/privacy-policy',
  '/terms-of-service',
  '/contact-us',
  '/support',
  '/pricing',
];

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.map': 'application/json; charset=utf-8',
  '.xml': 'application/xml; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.webmanifest': 'application/manifest+json',
};

function serveDist(port) {
  return new Promise((resolvePromise) => {
    const server = createServer(async (req, res) => {
      const path = (req.url || '/').split('?')[0];
      const fileCandidate =
        path === '/' ? '/index.html' : path;
      const filePath = join(DIST, fileCandidate);

      try {
        const body = await readFile(filePath);
        res.setHeader('Content-Type', MIME[extname(filePath)] ?? 'application/octet-stream');
        res.end(body);
      } catch {
        // SPA fallback — same behavior as CloudFront 403/404 → /index.html.
        const body = await readFile(join(DIST, 'index.html'));
        res.setHeader('Content-Type', 'text/html; charset=utf-8');
        res.end(body);
      }
    });
    server.listen(port, '127.0.0.1', () => resolvePromise(server));
  });
}

async function snapshotRoute(page, baseUrl, route) {
  const url = baseUrl + route;
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30_000 });

  // Give effects a beat to run (useDocumentMeta sets title/description in an
  // effect; some routes fire API calls that will time out with no backend).
  // We don't wait for network idle because failing API calls can stall for
  // many seconds. 1.5s is plenty for the synchronous content we care about.
  await new Promise((r) => setTimeout(r, 1500));

  const html = await page.evaluate(() => '<!doctype html>\n' + document.documentElement.outerHTML);

  const outPath =
    route === '/'
      ? join(DIST, 'index.html')
      : join(DIST, route.replace(/^\//, ''), 'index.html');

  await mkdir(dirname(outPath), { recursive: true });
  await writeFile(outPath, html, 'utf8');
  return outPath;
}

async function main() {
  if (!existsSync(DIST)) {
    throw new Error(`dist/ does not exist at ${DIST} — run vite build first.`);
  }

  const port = 4173 + Math.floor(Math.random() * 1000);
  const baseUrl = `http://127.0.0.1:${port}`;
  const server = await serveDist(port);

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  const start = Date.now();
  try {
    const page = await browser.newPage();
    page.setDefaultTimeout(30_000);
    // Silence failed API calls so they don't pollute build logs.
    await page.setRequestInterception(true);
    page.on('request', (req) => {
      const reqUrl = req.url();
      if (reqUrl.startsWith(baseUrl) || reqUrl.startsWith('data:')) {
        req.continue();
      } else {
        // External (Google Fonts, analytics) and /api calls are aborted
        // quickly so snapshots don't wait on them.
        req.abort('failed');
      }
    });

    for (const route of ROUTES) {
      const out = await snapshotRoute(page, baseUrl, route);
      console.log(`  prerendered ${route.padEnd(22)} → ${out.replace(DIST, 'dist')}`);
    }
  } finally {
    await browser.close();
    await new Promise((r) => server.close(() => r()));
  }

  const elapsed = ((Date.now() - start) / 1000).toFixed(1);
  console.log(`\n✓ prerender complete (${ROUTES.length} routes in ${elapsed}s)`);
}

main().catch((err) => {
  console.error('prerender failed:', err);
  process.exit(1);
});
