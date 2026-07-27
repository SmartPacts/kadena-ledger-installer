/**
 * An authenticated manager session: the handshake plus every subsequent command
 * wrapped by the secure channel.
 *
 * Once `open` returns, the device has shown the user the manager public key and they
 * have approved it. From that point the channel is stateful and order-dependent in
 * both directions, so a session must not be shared or used concurrently.
 */

import { establishSecureChannel } from "./handshake.ts";
import { SecureChannel } from "./secure-channel.ts";
import type { Transport } from "./transport.ts";
import { concat } from "./crypto.ts";

export interface MemoryInfo {
  systemSize: number;
  applicationsSize: number;
  freeSize: number;
  usedAppSlots: number;
  totalAppSlots: number;
}

export class ManagerSession {
  readonly transport: Transport;
  readonly channel: SecureChannel;
  /** The key the device displayed during approval, for reporting back to the user. */
  readonly managerPublicKey: Uint8Array;
  readonly cla: number;

  private constructor(
    transport: Transport,
    channel: SecureChannel,
    managerPublicKey: Uint8Array,
    cla: number,
  ) {
    this.transport = transport;
    this.channel = channel;
    this.managerPublicKey = managerPublicKey;
    this.cla = cla;
  }

  static async open(transport: Transport, targetId: number, cla = 0xe0): Promise<ManagerSession> {
    const { ephemeralPrivate, devicePublic, managerPublic } = await establishSecureChannel(
      transport,
      targetId,
    );
    const channel = SecureChannel.fromEcdh(ephemeralPrivate, devicePublic);
    return new ManagerSession(transport, channel, managerPublic, cla);
  }

  /** Send one command inside the secure channel. */
  async exchange(
    ins: number,
    p1: number,
    p2: number,
    data: Uint8Array,
  ): Promise<Uint8Array> {
    const wrapped = await this.channel.wrap(data);
    const response = await this.transport.exchange(
      concat(Uint8Array.of(this.cla, ins, p1, p2, wrapped.length), wrapped),
    );
    return this.channel.unwrap(response);
  }

  /**
   * Read the device's memory layout. Read-only, so it is a safe way to confirm the
   * channel is actually working before anything is written.
   */
  async getMemoryInfo(): Promise<MemoryInfo> {
    const r = await this.exchange(0x00, 0x00, 0x00, Uint8Array.of(0x11));
    const view = new DataView(r.buffer, r.byteOffset, r.byteLength);
    return {
      systemSize: view.getUint32(0, false),
      applicationsSize: view.getUint32(4, false),
      freeSize: view.getUint32(8, false),
      usedAppSlots: view.getUint32(12, false),
      totalAppSlots: view.getUint32(16, false),
    };
  }
}
