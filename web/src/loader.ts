/**
 * The write path: delete, create and stream an application onto the device.
 *
 * Ported from ledgerblue's `hexLoader.py` and the TLV branch of `loadApp.py`
 * (Apache-2.0), narrowed to the exact parameters the Kadena release is built and
 * tested with. Anything upstream supports and we do not — reverse loading, language
 * packs, clear-data blocks, install-parameter generation, `run` — is absent, because
 * an unused branch in code that writes firmware is a liability.
 *
 * The device computes and displays the application hash from what it actually
 * receives. That display, not anything here, is what proves the right app was loaded.
 */

import type { IntelHex } from "./hex.ts";
import type { ManagerSession } from "./session.ts";
import { concat } from "./crypto.ts";

/** Framing overheads that eat into each APDU, from hexLoader.py. */
const LOAD_SEGMENT_CHUNK_HEADER_LENGTH = 3;
const MIN_PADDING_LENGTH = 1;
const SCP_MAC_LENGTH = 0x0e;

/**
 * Largest payload per APDU. Over HID the device accepts 255, and this channel rounds
 * down to a 16-byte boundary (`apduMaxDataSize() & 0xF0`), giving 240 — the same value
 * `loadApp.py` passes as `max_length_per_apdu`.
 */
const MAX_APDU_PAYLOAD = 240;

export interface LoadParameters {
  /** Bytes of the image that are code (total, minus data and install params). */
  codeLength: number;
  apiLevel: number;
  dataLength: number;
  installParamsLength: number;
  flags: number;
  bootOffset: number;
}

/** Derive the create-app parameters the way `loadApp.py` does for our TLV case. */
export function deriveLoadParameters(
  hex: IntelHex,
  options: { apiLevel: number; dataSize: number; installParamsSize: number; flags: number },
): LoadParameters {
  let codeLength = hex.maxAddr() - hex.minAddr() - options.dataSize;
  // Install parameters are already inside the image; they are not appended here, so
  // their size is carved out of the code length rather than added to the file.
  codeLength -= options.installParamsSize;

  let bootAddr = hex.bootAddr;
  if (bootAddr > hex.minAddr()) bootAddr -= hex.minAddr();

  return {
    codeLength,
    apiLevel: options.apiLevel,
    dataLength: options.dataSize,
    installParamsLength: options.installParamsSize,
    flags: options.flags,
    bootOffset: bootAddr | 1,
  };
}

export function crc16(data: Uint8Array): number {
  // CRC-16/CCITT-FALSE: polynomial 0x1021, initial value 0xFFFF.
  let crc = 0xffff;
  for (const byte of data) {
    let index = (byte ^ (crc >> 8)) & 0xff;
    let entry = index << 8;
    for (let bit = 0; bit < 8; bit++) {
      entry = entry & 0x8000 ? ((entry << 1) ^ 0x1021) & 0xffff : (entry << 1) & 0xffff;
    }
    crc = (entry ^ (crc << 8)) & 0xffff;
  }
  return crc;
}

function u32(value: number): Uint8Array {
  const out = new Uint8Array(4);
  new DataView(out.buffer).setUint32(0, value >>> 0, false);
  return out;
}

function u16(value: number): Uint8Array {
  const out = new Uint8Array(2);
  new DataView(out.buffer).setUint16(0, value & 0xffff, false);
  return out;
}

export interface LoadProgress {
  /** Bytes streamed so far. */
  loaded: number;
  /** Total bytes to stream. */
  total: number;
}

export class AppLoader {
  private readonly session: ManagerSession;

  constructor(session: ManagerSession) {
    this.session = session;
  }

  /**
   * Remove an app by name. A device that does not have it may reject this; that is
   * not a failure of the install, so the caller decides what to do about it.
   */
  async deleteApp(appName: string): Promise<void> {
    const name = new TextEncoder().encode(appName);
    await this.session.exchange(
      0x00,
      0x00,
      0x00,
      concat(Uint8Array.of(0x0c, name.length), name),
    );
  }

  /** Reserve space and describe the application about to be streamed. */
  async createApp(params: LoadParameters): Promise<void> {
    const body = concat(
      Uint8Array.of(params.apiLevel),
      u32(params.codeLength),
      u32(params.dataLength),
      u32(params.installParamsLength),
      u32(params.flags),
      u32(params.bootOffset),
    );
    await this.session.exchange(0x00, 0x00, 0x00, concat(Uint8Array.of(0x0b), body));
  }

  /** Stream every area of the image, verifying each segment with a CRC. */
  async load(hex: IntelHex, onProgress?: (progress: LoadProgress) => void): Promise<void> {
    const initialAddress = hex.minAddr();
    const total = hex.areas.reduce((sum, area) => sum + area.data.length, 0);
    let loaded = 0;

    // Largest chunk that still leaves room for the header, padding and MAC, rounded
    // down to a whole number of cipher blocks.
    let chunkSize =
      MAX_APDU_PAYLOAD - LOAD_SEGMENT_CHUNK_HEADER_LENGTH - MIN_PADDING_LENGTH - SCP_MAC_LENGTH;
    chunkSize -= chunkSize % 16;

    for (const area of hex.areas) {
      await this.selectSegment(area.start - initialAddress);
      if (area.data.length === 0) continue;
      if (area.data.length > 0x10000) throw new Error("segment too large for the loader");

      const expectedCrc = crc16(area.data);
      for (let offset = 0; offset < area.data.length; offset += chunkSize) {
        const chunk = area.data.subarray(offset, Math.min(offset + chunkSize, area.data.length));
        await this.loadSegmentChunk(offset, chunk);
        loaded += chunk.length;
        onProgress?.({ loaded, total });
      }

      await this.flushSegment();
      await this.crcSegment(0, area.data.length, expectedCrc);
    }
  }

  private async selectSegment(baseAddress: number): Promise<void> {
    await this.session.exchange(0x00, 0x00, 0x00, concat(Uint8Array.of(0x05), u32(baseAddress)));
  }

  private async loadSegmentChunk(offset: number, chunk: Uint8Array): Promise<void> {
    await this.session.exchange(
      0x00,
      0x00,
      0x00,
      concat(Uint8Array.of(0x06), u16(offset), chunk),
    );
  }

  private async flushSegment(): Promise<void> {
    await this.session.exchange(0x00, 0x00, 0x00, Uint8Array.of(0x07));
  }

  private async crcSegment(offset: number, length: number, expected: number): Promise<void> {
    await this.session.exchange(
      0x00,
      0x00,
      0x00,
      concat(Uint8Array.of(0x08), u16(offset), u32(length), u16(expected)),
    );
  }
}
