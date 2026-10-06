/**
 * Build the demo installer into demo/dist.
 *
 * Bundles the page, copies the markup, and fetches the firmware image of EVERY pinned
 * release — the page picks one only after it has read the device's OS version — each
 * saved under its own name (app-v1.3.3.hex, ...) and refused unless its SHA-256 matches
 * that release's pin. The pins are read from src/releases.ts, the same table the page
 * uses, so the build cannot verify against one value while the page expects another.
 *
 * The images are downloaded rather than committed: a 170 KB binary in git that must
 * match a published checksum is a second copy to keep honest, and the check belongs at
 * the point of use anyway. A correct image already in demo/dist is reused, so a release
 * not yet published can be built by placing its app.hex there under its release name.
 *
 * Imports TypeScript directly, so it needs a Node that runs .ts files natively, as the
 * harness does.
 *
 *   node scripts/build-demo.mjs
 */

import { build } from "esbuild";
import { createHash } from "node:crypto";
import { mkdir, copyFile, writeFile, readFile } from "node:fs/promises";
import { RELEASES } from "../src/releases.ts";

const ROOT = new URL("..", import.meta.url);
const DIST = new URL("demo/dist/", ROOT);

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

for (const release of RELEASES) {
  const target = new URL(release.appHexFile, DIST);
  let bytes = await readFile(target).catch(() => null);
  if (!bytes || sha256(bytes) !== release.appHexSha256) {
    console.log(`  downloading app.hex from ${release.appReleaseTag}...`);
    const response = await fetch(release.appHexAssetUrl);
    if (!response.ok) {
      throw new Error(
        `could not download ${release.appReleaseTag} app.hex (${response.status})`,
      );
    }
    bytes = Buffer.from(await response.arrayBuffer());
  }

  const digest = sha256(bytes);
  if (digest !== release.appHexSha256) {
    throw new Error(
      `${release.appHexFile} checksum mismatch\n  expected ${release.appHexSha256}\n  actually ${digest}`,
    );
  }
  await writeFile(target, bytes);
  console.log(
    `  ${release.appHexFile} verified (${digest}) for Ledger OS ${release.osSeries}.x`,
  );
}
console.log("\n  Built. Serve it with: npm run serve:demo\n");
