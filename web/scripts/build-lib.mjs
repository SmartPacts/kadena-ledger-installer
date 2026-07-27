/**
 * Build the vendored loader bundle and print its checksum.
 *
 * The website serves this file verbatim from its own origin and records the checksum,
 * so the crypto is reviewed and versioned here rather than edited in a repository where
 * a push is a production deploy.
 *
 *   node scripts/build-lib.mjs [outfile]
 */

import { build } from "esbuild";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";

const ROOT = new URL("..", import.meta.url);
const outfile = process.argv[2] ?? new URL("dist/loader.js", ROOT).pathname;

await build({
  entryPoints: [new URL("src/index.ts", ROOT).pathname],
  outfile,
  bundle: true,
  format: "esm",
  target: "es2022",
  minify: true,
  legalComments: "inline",
  logLevel: "warning",
});

const bytes = await readFile(outfile);
const digest = createHash("sha256").update(bytes).digest("hex");
console.log(`  ${outfile}`);
console.log(`  ${(bytes.length / 1024).toFixed(1)} KB`);
console.log(`  sha256 ${digest}`);
