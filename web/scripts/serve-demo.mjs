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

const server = createServer(async (request, response) => {
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
});

function ready() {
  // Read the port actually bound. Reporting the one we asked for was wrong after a
  // fallback: it announced a port nothing was listening on.
  const { port } = server.address();
  console.log(`\n  Demo installer: http://localhost:${port}/\n`);
  console.log("  Open it in Chrome, Edge or Brave.");
  console.log("  The Ledger must be attached to THIS machine's USB — if it is currently");
  console.log("  forwarded into WSL, detach it first so the browser's OS can see it.\n");
}

/**
 * Try a few ports rather than dying on a stack trace. A leftover server from an earlier
 * run is the normal cause, and "address already in use" plus a Node backtrace is a poor
 * way to say "something is already serving this".
 */
function listen(port, attemptsLeft) {
  server.once("error", (error) => {
    if (error.code !== "EADDRINUSE") throw error;
    if (attemptsLeft === 0) {
      console.error(`\n  Ports ${PORT}-${port} are all in use.`);
      console.error("  Another copy of this server is probably still running:");
      console.error("    pkill -f serve-demo\n");
      process.exit(1);
    }
    console.log(`  port ${port} is busy, trying ${port + 1}`);
    listen(port + 1, attemptsLeft - 1);
  });
  server.listen(port);
}

server.on("listening", ready);
listen(PORT, 5);
