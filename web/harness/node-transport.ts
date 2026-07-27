/**
 * Node transport for hardware testing only. Never shipped to the browser.
 *
 * Resolves @ledgerhq/hw-transport-node-hid from an external workspace rather than
 * adding a native dependency here — this package must stay browser-clean.
 */

import { createRequire } from "node:module";
import type { Transport } from "../src/transport.ts";
import { StatusError } from "../src/transport.ts";

/**
 * Where to resolve the native HID transport from. Set HID_TRANSPORT_FROM to a
 * package.json whose dependency tree contains @ledgerhq/hw-transport-node-hid;
 * otherwise normal resolution from this file is used.
 */
const RESOLVE_FROM = process.env.HID_TRANSPORT_FROM ?? import.meta.url;

export async function openNodeTransport(): Promise<Transport> {
  const require = createRequire(RESOLVE_FROM);
  const mod = require("@ledgerhq/hw-transport-node-hid");
  const TransportNodeHid = mod.default ?? mod;
  try {
    const inner = createRequire(require.resolve("@ledgerhq/hw-transport-node-hid"));
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
