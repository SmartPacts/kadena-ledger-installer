/**
 * Offline check of the Intel HEX parser, CRC and parameter derivation against the
 * values ledgerblue computes for the same file. No device involved.
 *
 *   node harness/test-hex.ts <path to app.hex> <expected json>
 */
import { readFileSync } from "node:fs";
import { IntelHex } from "../src/hex.ts";
import { deriveLoadParameters } from "../src/loader.ts";

const path = process.argv[2];
const expected = JSON.parse(process.argv[3]);

const hex = new IntelHex(readFileSync(path, "utf8"));
const params = deriveLoadParameters(hex, {
  apiLevel: 26,
  dataSize: 16896,
  installParamsSize: 62,
  flags: 0,
});

const actual = {
  minAddr: hex.minAddr(),
  maxAddr: hex.maxAddr(),
  bootAddr: hex.bootAddr,
  areas: hex.areas.length,
  areaStart: hex.areas[0].start,
  areaLength: hex.areas[0].data.length,
  codeLength: params.codeLength,
  bootOffset: params.bootOffset,
};

let failures = 0;
for (const [key, want] of Object.entries(expected)) {
  const got = (actual as Record<string, number>)[key];
  const ok = got === want;
  if (!ok) failures++;
  console.log(`  ${ok ? "OK  " : "FAIL"} ${key.padEnd(12)} got ${got}${ok ? "" : `, expected ${want}`}`);
}
console.log(`\n  RESULT: ${failures === 0 ? "PASS — matches ledgerblue" : `${failures} MISMATCH(ES)`}`);
process.exitCode = failures === 0 ? 0 : 1;
