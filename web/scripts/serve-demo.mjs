/**
 * Serves demo/dist on localhost for testing.
 *
 * localhost counts as a secure context, which is what the browser requires before it
 * will hand a page a USB device. Any other origin needs HTTPS.
 *
 *   npm run build:demo && npm run serve:demo
 */

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";

const ROOT = new URL("../demo/dist/", import.meta.url).pathname;
const PORT = Number(process.env.PORT ?? 8974);

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".hex": "text/plain; charset=utf-8",
};

createServer(async (request, response) => {
  const path = decodeURIComponent(new URL(request.url ?? "/", "http://x").pathname);
  const relative = normalize(path === "/" ? "index.html" : path.replace(/^\/+/, ""));
  if (relative.startsWith("..")) {
    response.writeHead(403).end("forbidden");
    return;
  }
  try {
    const body = await readFile(join(ROOT, relative));
    response.writeHead(200, {
      "content-type": TYPES[extname(relative)] ?? "application/octet-stream",
      "cache-control": "no-store",
    });
    response.end(body);
  } catch {
    response.writeHead(404).end("not found");
  }
}).listen(PORT, () => {
  console.log(`\n  Demo installer: http://localhost:${PORT}/\n`);
  console.log("  Open it in Chrome, Edge or Brave.");
  console.log("  The Ledger must be attached to THIS machine's USB — if it is currently");
  console.log("  forwarded into WSL, detach it first so the browser's OS can see it.\n");
});
