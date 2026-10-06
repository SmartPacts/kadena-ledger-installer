/**
 * Offline check of the Intel HEX parser, CRC and parameter derivation against the
 * values ledgerblue computes for the same file. No device involved.
 *
 *   node harness/test-hex.ts <path to app.hex> <expected json>
 *
 * The file must be the image of one of the pinned releases; its SHA-256 says which, and
 * that release's load options are the ones derived with. Any other file is refused.
 */
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { IntelHex } from "../src/hex.ts";
import { deriveLoadParameters } from "../src/loader.ts";
import { RELEASES } from "../src/releases.ts";

const path = process.argv[2];
const expected = JSON.parse(process.argv[3]);

const bytes = readFileSync(path);
const digest = createHash("sha256").update(bytes).digest("hex");
const release = RELEASES.find((r) => r.appHexSha256 === digest);
if (!release) {
  throw new Error(`${path} (sha256 ${digest}) is not the image of any pinned release`);
}
console.log(`  release   ${release.appReleaseTag} (Ledger OS ${release.osSeries}.x, API ${release.loadOptions.apiLevel})`);

const hex = new IntelHex(bytes.toString("utf8"));
const params = deriveLoadParameters(hex, release.loadOptions);

const actual = {
  minAddr: hex.minAddr(),
  maxAddr: hex.maxAddr(),
  bootAddr: hex.bootAddr,
  areas: hex.areas.length,
  areaStart: hex.areas[0].start,
  areaLength: hex.areas[0].data.length,
  codeLength: params.codeLength,
  bootOffset: params.bootOffset,
  apiLevel: params.apiLevel,
};

let failures = 0;
for (const [key, want] of Object.entries(expected)) {
  const got = (actual as Record<string, number>)[key];
  const ok = got === want;
  if (!ok) failures++;
  console.log(`  ${ok ? "OK  " : "FAIL"} ${key.padEnd(12)} got ${got}${ok ? "" : `, expected ${want}`}`);
}
if (Object.keys(expected).length === 0) failures++; // checking nothing is not a pass
console.log(`\n  RESULT: ${failures === 0 ? "PASS — matches ledgerblue" : `${failures} MISMATCH(ES)`}`);
process.exitCode = failures === 0 ? 0 : 1;
