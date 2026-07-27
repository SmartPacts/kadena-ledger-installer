/**
 * Checks that must pass before anything is written to a device.
 *
 * Two of these came out of real use rather than reading the protocol:
 *
 *  - Manager commands only work from the dashboard. With an app open the device
 *    answers 0x6e00 ("CLA not supported"), which reads like a broken tool rather than
 *    "close the app". Users will hit this constantly, because opening the app to check
 *    it is the natural thing to do right after installing.
 *  - Firmware generation matters more than firmware freshness. An image built for an
 *    older API level is refused at install time, which is exactly how the previous
 *    Kadena release became uninstallable. Being on "the latest firmware" is not the
 *    same as being compatible.
 */

import type { Transport } from "./transport.ts";
import { StatusError } from "./transport.ts";

export interface DeviceInfo {
  targetId: number;
  osVersion: string;
  flags: Uint8Array;
  mcuVersion: string;
}

/** SW returned by an application when it is asked a dashboard question. */
const SW_CLA_NOT_SUPPORTED = 0x6e00;

/** Read the device's identity. Throws {@link NotOnDashboardError} if an app is open. */
export async function getDeviceInfo(transport: Transport): Promise<DeviceInfo> {
  let response: Uint8Array;
  try {
    response = await transport.exchange(Uint8Array.of(0xe0, 0x01, 0x00, 0x00, 0x00));
  } catch (error) {
    if (error instanceof StatusError && error.status === SW_CLA_NOT_SUPPORTED) {
      throw new NotOnDashboardError();
    }
    throw error;
  }

  let offset = 0;
  const targetId =
    response[0] * 0x1000000 + response[1] * 0x10000 + response[2] * 0x100 + response[3];
  offset = 4;

  const readLengthPrefixed = (): Uint8Array => {
    const length = response[offset];
    offset += 1;
    const value = response.subarray(offset, offset + length);
    offset += length;
    return value;
  };

  const decoder = new TextDecoder();
  const osVersion = decoder.decode(readLengthPrefixed());
  const flags = readLengthPrefixed();
  const mcuVersion = offset < response.length ? decoder.decode(readLengthPrefixed()) : "";

  return { targetId, osVersion, flags, mcuVersion };
}

export class NotOnDashboardError extends Error {
  constructor() {
    super("an app is open on the device — return to the dashboard first");
    this.name = "NotOnDashboardError";
  }
}

/**
 * Ask the open application to exit.
 *
 * The device re-enumerates on the USB bus afterwards, so the transport in hand becomes
 * unusable and the caller must open a new one. That is why this returns nothing useful
 * and is deliberately awkward: pretending the same transport survives would produce
 * confusing failures a few commands later.
 */
export async function quitApp(transport: Transport): Promise<void> {
  try {
    await transport.exchange(Uint8Array.of(0xb0, 0xa7, 0x00, 0x00, 0x00));
  } catch {
    // The device frequently drops the connection mid-command here; that is success.
  }
}
