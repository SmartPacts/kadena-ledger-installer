/**
 * Milestone 1: prove the ported handshake and secure channel work against a real device.
 *
 * Read-only. Opens an authenticated manager session and asks the device for its memory
 * layout. If the MAC verifies and the numbers are sane, the ECDH, the key derivation,
 * the CBC chaining and the MAC are all correct — which is the entire risky part of the
 * port. Nothing is written to the device.
 *
 *   node harness/test-channel.ts
 *
 * The device must be unlocked, on the dashboard, with Ledger Live closed. It will ask
 * you to approve an unknown manager.
 */

import { openNodeTransport } from "./node-transport.ts";
import { ManagerSession } from "../src/session.ts";
import { hex } from "../src/crypto.ts";
import { DEVICE } from "../src/releases.ts";

function kb(bytes: number): string {
  return `${(bytes / 1024).toFixed(1)} KB`;
}

const transport = await openNodeTransport();
try {
  console.log("Opening a manager session — approve the unknown manager on the device.\n");
  const session = await ManagerSession.open(transport, DEVICE.targetId);
  console.log("  handshake OK");
  console.log(`  manager public key shown on device: ${hex(session.managerPublicKey)}`);

  const info = await session.getMemoryInfo();
  console.log("\n  secure-channel command succeeded (MAC verified, payload decrypted):");
  console.log(`    system      ${kb(info.systemSize)}`);
  console.log(`    apps        ${kb(info.applicationsSize)}`);
  console.log(`    free        ${kb(info.freeSize)}`);
  console.log(`    app slots   ${info.usedAppSlots} used of ${info.totalAppSlots}`);

  const sane =
    info.totalAppSlots > 0 &&
    info.usedAppSlots <= info.totalAppSlots &&
    info.freeSize <= info.systemSize + info.applicationsSize + info.freeSize;
  console.log(`\n  RESULT: ${sane ? "PASS — channel is correct" : "FAIL — implausible values"}`);
  process.exitCode = sane ? 0 : 1;
} finally {
  await transport.close?.();
}
