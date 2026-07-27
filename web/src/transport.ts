/**
 * The only thing the loader needs from the outside world.
 *
 * `exchange` sends one APDU and returns the response WITHOUT its status word,
 * throwing if the status is anything other than 0x9000. That matches what
 * ledgerblue's dongle does, so the ported logic reads the same as the original.
 *
 * Implementations: WebHID/WebUSB in the browser, node-hid for hardware testing.
 */
export interface Transport {
  exchange(apdu: Uint8Array): Promise<Uint8Array>;
  close?(): Promise<void>;
}

export class StatusError extends Error {
  readonly status: number;

  constructor(status: number) {
    super(`device returned status 0x${status.toString(16).padStart(4, "0")}`);
    this.name = "StatusError";
    this.status = status;
  }
}
