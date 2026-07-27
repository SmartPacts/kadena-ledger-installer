/**
 * Node transport for hardware testing only. Never shipped to the browser.
 *
 * Resolves @ledgerhq/hw-transport-node-hid from an external workspace rather than
 * adding a native dependency here — this package must stay browser-clean.
 */

import { createRequire } from "node:module";
import { homedir } from "node:os";
import { pathToFileURL } from "node:url";
import type { Transport } from "../src/transport.ts";
import { StatusError } from "../src/transport.ts";

const PACKAGE = "@ledgerhq/hw-transport-node-hid";

/**
 * Places to look for the native HID transport, in order. This package deliberately
 * does not depend on it — a native build has no business in something destined for a
 * browser bundle — so the harness borrows it from a workspace that already has it.
 * Override with HID_TRANSPORT_FROM=<path to a package.json>.
 */
function resolveCandidates(): string[] {
  const candidates = [];
  if (process.env.HID_TRANSPORT_FROM) candidates.push(process.env.HID_TRANSPORT_FROM);
  candidates.push(import.meta.url);
  candidates.push(pathToFileURL(`${homedir()}/enterprise/ledger-signer/packages/cli/package.json`).href);
  return candidates;
}

function loadTransportModule(): { module: any; require: NodeRequire } {
  const tried: string[] = [];
  for (const from of resolveCandidates()) {
    try {
      const require = createRequire(from);
      return { module: require(PACKAGE), require };
    } catch {
      tried.push(from);
    }
  }
  throw new Error(
    `could not find ${PACKAGE}.\nLooked in:\n  ${tried.join("\n  ")}\n` +
      `Point HID_TRANSPORT_FROM at a package.json whose dependencies include it.`,
  );
}

export async function openNodeTransport(): Promise<Transport> {
  const { module: mod, require } = loadTransportModule();
  const TransportNodeHid = mod.default ?? mod;
  try {
    const inner = createRequire(require.resolve(PACKAGE));
    inner("node-hid").setDriverType?.("hidraw");
  } catch {
    // hidraw selection is best-effort; libusb also works once udev rules are right.
  }

  const transport = await TransportNodeHid.create();
  transport.setExchangeTimeout(600_000); // on-device approval can take minutes

  return {
    async exchange(apdu: Uint8Array): Promise<Uint8Array> {
      const reply: Buffer = await transport.exchange(Buffer.from(apdu));
      const status = reply.readUInt16BE(reply.length - 2);
      if (status !== 0x9000) throw new StatusError(status);
      return new Uint8Array(reply.subarray(0, reply.length - 2));
    },
    async close() {
      await transport.close();
    },
  };
}
