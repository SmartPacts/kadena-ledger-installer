/**
 * Build the demo installer into demo/dist.
 *
 * Bundles the page, copies the markup, and fetches the firmware image from the pinned
 * app release — refusing it unless its SHA-256 matches. The image is downloaded rather
 * than committed: a 155 KB binary in git that must match a published checksum is a
 * second copy to keep honest, and the check belongs at the point of use anyway.
 *
 *   node scripts/build-demo.mjs
 */

import { build } from "esbuild";
import { createHash } from "node:crypto";
import { mkdir, copyFile, writeFile, readFile } from "node:fs/promises";

const ROOT = new URL("..", import.meta.url);
const DIST = new URL("demo/dist/", ROOT);

const APP_RELEASE_TAG = "v1.3.3";
const APP_HEX_URL = `https://github.com/SmartPacts/app-kadena/releases/download/${APP_RELEASE_TAG}/app.hex`;
const APP_HEX_SHA256 = "63e492e9c8cb16776f1b22e1a17d7356e57b54cd32e97e501a488ab158766236";

const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");

await mkdir(DIST, { recursive: true });

await build({
  entryPoints: [new URL("demo/app.ts", ROOT).pathname],
  outfile: new URL("bundle.js", DIST).pathname,
  bundle: true,
  format: "esm",
  target: "es2022",
  logLevel: "warning",
});
console.log("  bundled demo/dist/bundle.js");

await copyFile(new URL("demo/index.html", ROOT).pathname, new URL("index.html", DIST).pathname);
console.log("  copied index.html");

const target = new URL("app.hex", DIST);
let bytes = await readFile(target).catch(() => null);
if (!bytes || sha256(bytes) !== APP_HEX_SHA256) {
  console.log(`  downloading app.hex from ${APP_RELEASE_TAG}...`);
  const response = await fetch(APP_HEX_URL);
  if (!response.ok) throw new Error(`could not download app.hex (${response.status})`);
  bytes = Buffer.from(await response.arrayBuffer());
}

const digest = sha256(bytes);
if (digest !== APP_HEX_SHA256) {
  throw new Error(`app.hex checksum mismatch\n  expected ${APP_HEX_SHA256}\n  actually ${digest}`);
}
await writeFile(target, bytes);
console.log(`  app.hex verified (${digest.slice(0, 16)}...)`);
console.log("\n  Built. Serve it with: npm run serve:demo\n");
