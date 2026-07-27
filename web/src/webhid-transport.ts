/**
 * WebHID transport.
 *
 * Ledger's USB framing splits each APDU across 64-byte HID reports: every report carries
 * a channel id, a tag, a sequence number, and — on the first report only — the total
 * length. Implemented here rather than pulled from `@ledgerhq/hw-transport-webhid` so
 * this package stays dependency-light and the bytes that reach a hardware wallet are
 * ones we can read in full.
 */

import type { Transport } from "./transport.ts";
import { StatusError } from "./transport.ts";

const PACKET_SIZE = 64;
const CHANNEL = 0x0101;
const TAG_APDU = 0x05;
const LEDGER_VENDOR_ID = 0x2c97;

/** Split an APDU into HID reports. */
function frame(apdu: Uint8Array): Uint8Array[] {
  const packets: Uint8Array[] = [];
  let offset = 0;
  let sequence = 0;

  while (offset < apdu.length || sequence === 0) {
    const packet = new Uint8Array(PACKET_SIZE);
    const view = new DataView(packet.buffer);
    view.setUint16(0, CHANNEL, false);
    packet[2] = TAG_APDU;
    view.setUint16(3, sequence, false);

    let cursor = 5;
    if (sequence === 0) {
      view.setUint16(cursor, apdu.length, false);
      cursor += 2;
    }
    const take = Math.min(PACKET_SIZE - cursor, apdu.length - offset);
    packet.set(apdu.subarray(offset, offset + take), cursor);
    offset += take;
    sequence += 1;
    packets.push(packet);
  }
  return packets;
}

/** Reassemble HID reports into one APDU response. */
class Reassembler {
  private expected: number | null = null;
  private chunks: number[] = [];
  private sequence = 0;

  /** Returns the complete response once every packet has arrived. */
  push(packet: Uint8Array): Uint8Array | null {
    const view = new DataView(packet.buffer, packet.byteOffset, packet.byteLength);
    if (view.getUint16(0, false) !== CHANNEL) return null;
    if (packet[2] !== TAG_APDU) return null;
    if (view.getUint16(3, false) !== this.sequence) {
      throw new Error("device response arrived out of order");
    }

    let cursor = 5;
    if (this.sequence === 0) {
      this.expected = view.getUint16(cursor, false);
      cursor += 2;
    }
    this.sequence += 1;

    for (let i = cursor; i < packet.length && this.chunks.length < (this.expected ?? 0); i++) {
      this.chunks.push(packet[i]);
    }
    return this.chunks.length >= (this.expected ?? 0) ? Uint8Array.from(this.chunks) : null;
  }
}

export interface WebHidOptions {
  /** How long to wait for a reply. On-device approval can take minutes. */
  timeoutMs?: number;
}

/**
 * Prompt for a device and open it. Must be called from a user gesture — browsers
 * refuse `requestDevice` otherwise.
 */
export async function requestWebHidTransport(options: WebHidOptions = {}): Promise<Transport> {
  const hid = (navigator as unknown as { hid?: HID }).hid;
  if (!hid) {
    throw new Error(
      "This browser cannot talk to USB devices. Use Chrome, Edge or Brave on a desktop computer.",
    );
  }

  const devices = await hid.requestDevice({ filters: [{ vendorId: LEDGER_VENDOR_ID }] });
  const device = devices[0];
  if (!device) throw new Error("No device was selected.");
  if (!device.opened) await device.open();

  return openWebHidTransport(device, options);
}

export function openWebHidTransport(device: HIDDevice, options: WebHidOptions = {}): Transport {
  const timeoutMs = options.timeoutMs ?? 600_000;
  // One command at a time: the secure channel's IV chains advance per message, so
  // overlapping exchanges would desynchronise it irrecoverably.
  let queue: Promise<unknown> = Promise.resolve();

  const exchangeOnce = (apdu: Uint8Array): Promise<Uint8Array> =>
    new Promise((resolve, reject) => {
      const reassembler = new Reassembler();
      let timer: ReturnType<typeof setTimeout>;

      const onInput = (event: HIDInputReportEvent) => {
        try {
          const packet = new Uint8Array(event.data.buffer, event.data.byteOffset, event.data.byteLength);
          const complete = reassembler.push(packet);
          if (!complete) return;
          cleanup();

          const status = (complete[complete.length - 2] << 8) | complete[complete.length - 1];
          if (status !== 0x9000) reject(new StatusError(status));
          else resolve(complete.subarray(0, complete.length - 2));
        } catch (error) {
          cleanup();
          reject(error);
        }
      };

      const cleanup = () => {
        clearTimeout(timer);
        device.removeEventListener("inputreport", onInput);
      };

      timer = setTimeout(() => {
        cleanup();
        reject(new Error("The device did not respond. It may have locked, or be waiting for you."));
      }, timeoutMs);

      device.addEventListener("inputreport", onInput);

      (async () => {
        for (const packet of frame(apdu)) await device.sendReport(0, packet);
      })().catch((error) => {
        cleanup();
        reject(error);
      });
    });

  return {
    exchange(apdu: Uint8Array): Promise<Uint8Array> {
      const result = queue.then(() => exchangeOnce(apdu));
      queue = result.catch(() => undefined);
      return result;
    },
    async close() {
      if (device.opened) await device.close();
    },
  };
}
