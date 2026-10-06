/**
 * Milestone 2: a full application load onto real hardware, driven entirely by the
 * ported TypeScript. Same code the browser will run; only the transport differs.
 *
 *   node harness/test-load.ts <path to app.hex>
 *
 * WRITES TO THE DEVICE. It reads the device's OS version, chooses the pinned release
 * built for it exactly as the page does, and refuses the file unless it is that
 * release's image. The device will ask for approval and then display the application
 * hash — which must be checked, exactly as with any other install.
 */

import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { openNodeTransport } from "./node-transport.ts";
import { IntelHex } from "../src/hex.ts";
import { AppLoader, deriveLoadParameters } from "../src/loader.ts";
import { ManagerSession } from "../src/session.ts";
import { getDeviceInfo, NotOnDashboardError, quitApp } from "../src/preflight.ts";
import { hex as toHex } from "../src/crypto.ts";
import type { Transport } from "../src/transport.ts";
import { DEVICE, releaseForOsVersion } from "../src/releases.ts";

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
if (info.targetId !== DEVICE.targetId) {
  throw new Error(`unsupported device 0x${info.targetId.toString(16)}`);
}
const release = releaseForOsVersion(info.osVersion);
console.log(`  release   ${release.appReleaseTag} (built for Ledger OS ${release.osSeries}.x)`);

// --- image -------------------------------------------------------------------------
const bytes = readFileSync(hexPath);
const digest = createHash("sha256").update(bytes).digest("hex");
if (digest !== release.appHexSha256) {
  throw new Error(
    `${hexPath} is not the ${release.appReleaseTag} image this device needs\n` +
      `  expected ${release.appHexSha256}\n  actually ${digest}`,
  );
}
const image = new IntelHex(bytes.toString("utf8"));
const params = deriveLoadParameters(image, release.loadOptions);
console.log(
  `  image     ${image.areas.length} area(s), code ${params.codeLength} B, ` +
    `data ${params.dataLength} B, params ${params.installParamsLength} B`,
);

// --- install -----------------------------------------------------------------------
try {
  console.log("\n  Approve the unknown manager on the device...\n");
  const session = await ManagerSession.open(transport, DEVICE.targetId);
  console.log(`  manager key shown on device: ${toHex(session.managerPublicKey).slice(0, 32)}...`);

  const loader = new AppLoader(session);

  let lastPercent = -1;
  await loader.installApp(DEVICE.appName, image, params, {
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
      const blocks = release.deviceHash.match(/.{1,8}/g)!;
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
