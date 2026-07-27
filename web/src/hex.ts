/**
 * Intel HEX parsing — a port of ledgerblue's `hexParser.py` (Apache-2.0).
 *
 * Only the record types Ledger's build output actually uses are handled: data (0x00),
 * end-of-file (0x01), extended linear address (0x04) and start linear address (0x05).
 * Records 0x02 and 0x03 are rejected rather than ignored, matching upstream — silently
 * skipping an address record would place code at the wrong offset.
 */

/**
 * Load addresses sit above 2^31, where JavaScript's bitwise operators would wrap to
 * negative. Every address here is built with arithmetic instead of shifts, keeping it
 * an exact non-negative number.
 */
const ZONE_MULTIPLIER = 0x10000;

export interface HexArea {
  start: number;
  data: Uint8Array;
}

export class IntelHex {
  readonly areas: HexArea[];
  readonly bootAddr: number;

  constructor(text: string) {
    const areas: HexArea[] = [];
    let bootAddr = 0;

    let startZone: number | null = null;
    let startFirst: number | null = null;
    let current: number | null = null;
    let zoneData: number[] = [];

    const flush = () => {
      if (zoneData.length !== 0) {
        areas.push({
          start: (startZone ?? 0) * ZONE_MULTIPLIER + (startFirst ?? 0),
          data: Uint8Array.from(zoneData),
        });
        zoneData = [];
        startZone = null;
        startFirst = null;
        current = null;
      }
    };

    const lines = text.split(/\r?\n/);
    for (let n = 0; n < lines.length; n++) {
      const line = lines[n];
      if (line.length === 0) continue;
      if (line[0] !== ":") throw new Error(`invalid Intel HEX data at line ${n + 1}`);

      const raw = line.slice(1);
      const bytes = new Uint8Array(raw.length / 2);
      for (let i = 0; i < bytes.length; i++) bytes[i] = parseInt(raw.substr(i * 2, 2), 16);

      const count = bytes[0];
      const address = (bytes[1] << 8) + bytes[2];
      const recordType = bytes[3];

      if (recordType === 0x00) {
        if (startZone === null) {
          throw new Error(`data record before any address record at line ${n + 1}`);
        }
        if (startFirst === null) {
          startFirst = address;
          current = address;
        }
        if (address !== current) {
          // A gap: close the run and start a new area at this address.
          areas.push({
            start: startZone * ZONE_MULTIPLIER + startFirst,
            data: Uint8Array.from(zoneData),
          });
          zoneData = [];
          startFirst = address;
          current = address;
        }
        for (let i = 0; i < count; i++) zoneData.push(bytes[4 + i]);
        current += count;
      } else if (recordType === 0x01) {
        flush();
      } else if (recordType === 0x02 || recordType === 0x03) {
        throw new Error(`unsupported Intel HEX record type 0x0${recordType}`);
      } else if (recordType === 0x04) {
        flush();
        startZone = (bytes[4] << 8) + bytes[5];
      } else if (recordType === 0x05) {
        bootAddr =
          (bytes[4] & 0xff) * 0x1000000 +
          (bytes[5] & 0xff) * 0x10000 +
          (bytes[6] & 0xff) * 0x100 +
          (bytes[7] & 0xff);
      }
    }
    flush();

    // Upstream keeps areas sorted by start address; load order must match.
    areas.sort((a, b) => a.start - b.start);

    this.areas = areas;
    this.bootAddr = bootAddr;
  }

  minAddr(): number {
    return this.areas.reduce((min, a) => Math.min(min, a.start), Number.MAX_SAFE_INTEGER);
  }

  maxAddr(): number {
    return this.areas.reduce((max, a) => Math.max(max, a.start + a.data.length), 0);
  }
}
