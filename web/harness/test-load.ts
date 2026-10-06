/**
 * Milestone 2: a full application load onto real hardware, driven entirely by the
 * ported TypeScript. Same code the browser will run; only the transport differs.
 *
 *   node harness/test-load.ts <path to app.hex>
 *
 * WRITES TO THE DEVICE. It installs the pinned Kadena release, so the device will ask
 * for approval and then display the application hash — which must be checked, exactly
 * as with any other install.
 */

import { readFileSync } from "node:fs";
import { openNodeTransport } from "./node-transport.ts";
import { IntelHex } from "../src/hex.ts";
import { AppLoader, deriveLoadParameters } from "../src/loader.ts";
import { ManagerSession } from "../src/session.ts";
import { getDeviceInfo, NotOnDashboardError, quitApp } from "../src/preflight.ts";
import { hex as toHex } from "../src/crypto.ts";
import type { Transport } from "../src/transport.ts";

const TARGET_ID = 0x33100004;
const APP_NAME = "Kadena";
const EXPECTED_DEVICE_HASH =
  "5de2186976638313a881faabe09bbf462df9ef8c5fae9451fa22b1a99d0efed4";

const LOAD_OPTIONS = { apiLevel: 26, dataSize: 16896, installParamsSize: 62, flags: 0 };

const hexPath = process.argv[2];
if (!hexPath) throw new Error("usage: node harness/test-load.ts <app.hex>");

let transport: Transport = await openNodeTransport();

// --- preflight ---------------------------------------------------------------------
let info;
try {
  info = await getDeviceInfo(transport);
} catch (error) {
  if (!(error instanceof NotOnDashboardError)) throw error;
  console.log("  an app is open — asking it to quit, then reconnecting");
  await quitApp(transport);
  await transport.close?.();
  await new Promise((resolve) => setTimeout(resolve, 4000));
  transport = await openNodeTransport();
  info = await getDeviceInfo(transport);
}

console.log(`  device    target 0x${info.targetId.toString(16)}, OS ${info.osVersion}`);
if (info.targetId !== TARGET_ID) {
  throw new Error(`unsupported device 0x${info.targetId.toString(16)}`);
}

// --- image -------------------------------------------------------------------------
const image = new IntelHex(readFileSync(hexPath, "utf8"));
const params = deriveLoadParameters(image, LOAD_OPTIONS);
console.log(
  `  image     ${image.areas.length} area(s), code ${params.codeLength} B, ` +
    `data ${params.dataLength} B, params ${params.installParamsLength} B`,
);

// --- install -----------------------------------------------------------------------
try {
  console.log("\n  Approve the unknown manager on the device...\n");
  const session = await ManagerSession.open(transport, TARGET_ID);
  console.log(`  manager key shown on device: ${toHex(session.managerPublicKey).slice(0, 32)}...`);

  const loader = new AppLoader(session);

  let lastPercent = -1;
  await loader.installApp(APP_NAME, image, params, {
    onDeleted: (existed) =>
      console.log(existed ? "  removed the existing app" : "  no existing app to remove"),
    onProgress: ({ loaded, total }) => {
      const percent = Math.floor((loaded / total) * 100);
      if (percent !== lastPercent && percent % 10 === 0) {
        console.log(`    ${percent}%  (${loaded}/${total} bytes)`);
        lastPercent = percent;
      }
    },
    // Fires immediately BEFORE the device is asked to finalise, so the expected value
    // is on screen while the device shows its own and waits. Printing it afterwards
    // would mean approving first and checking second, which is not a check at all.
    onFinalising: () => {
      const blocks = EXPECTED_DEVICE_HASH.match(/.{1,8}/g)!;
      console.log("\n  Streaming done. The device is about to show the application");
      console.log("  hash and ask you to approve. It must read:\n");
      console.log(`    ${blocks.slice(0, 4).join(" ")}`);
      console.log(`    ${blocks.slice(4).join(" ")}`);
      console.log("\n  Compare it on the device BEFORE approving. Reject if it differs.");
    },
  });

  console.log("\n  INSTALL COMPLETE");
} finally {
  await transport.close?.();
}
