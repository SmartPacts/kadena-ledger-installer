/**
 * The Ledger manager secure channel (the variant a Nano S Plus negotiates).
 *
 * Ported from ledgerblue's `hexLoader.py` (Apache-2.0), `scpVersion == 3` branch —
 * which despite the name is AES-CBC with a CBC-MAC, not the separate AES-SIV mode
 * that file's `scpv3` flag selects. `loadApp.py` never sets that flag, so this is
 * the path a real install takes.
 *
 * Every payload is encrypted with a chained IV and authenticated with a 14-byte tag
 * taken from a second CBC chain. Both chains advance on every message in both
 * directions, so the two sides fall permanently out of step if a single message is
 * dropped, reordered or replayed.
 */

import {
  aesCbcDecryptRaw,
  aesCbcEncryptRaw,
  concat,
  ecdhSecret,
  scpDeriveKey,
  ZERO_IV,
} from "./crypto.ts";

/** ledgerblue's SCP_MAC_LENGTH. */
const MAC_LENGTH = 0x0e;
const PADDING_BYTE = 0x80;

export class SecureChannel {
  private encKey: Uint8Array;
  private macKey: Uint8Array;
  private encIv: Uint8Array = ZERO_IV;
  private macIv: Uint8Array = ZERO_IV;

  private constructor(encKey: Uint8Array, macKey: Uint8Array) {
    this.encKey = encKey;
    this.macKey = macKey;
  }

  /**
   * Build the channel from the ECDH secret agreed during the handshake.
   * Key 0 encrypts, key 1 authenticates; both are truncated to 16 bytes.
   */
  static fromEcdh(ephemeralPrivate: Uint8Array, devicePublic: Uint8Array): SecureChannel {
    const secret = ecdhSecret(ephemeralPrivate, devicePublic);
    return new SecureChannel(
      scpDeriveKey(secret, 0).subarray(0, 16),
      scpDeriveKey(secret, 1).subarray(0, 16),
    );
  }

  /** Encrypt then authenticate an outbound payload. */
  async wrap(data: Uint8Array): Promise<Uint8Array> {
    if (data.length === 0) return data;

    // ISO 7816-4 padding: a 0x80 marker then zeros to the block boundary.
    const padded = new Uint8Array(Math.ceil((data.length + 1) / 16) * 16);
    padded.set(data);
    padded[data.length] = PADDING_BYTE;

    const ciphertext = await aesCbcEncryptRaw(this.encKey, this.encIv, padded);
    this.encIv = ciphertext.slice(-16);

    const mac = await aesCbcEncryptRaw(this.macKey, this.macIv, ciphertext);
    this.macIv = mac.slice(-16);

    return concat(ciphertext, this.macIv.subarray(16 - MAC_LENGTH));
  }

  /** Verify then decrypt an inbound payload. */
  async unwrap(data: Uint8Array): Promise<Uint8Array> {
    // A bare status word carries no protected payload.
    if (data.length === 0 || data.length === 2) return data;
    if (data.length <= MAC_LENGTH) throw new Error("secure channel: response too short");

    const body = data.subarray(0, data.length - MAC_LENGTH);
    const receivedMac = data.subarray(data.length - MAC_LENGTH);

    const mac = await aesCbcEncryptRaw(this.macKey, this.macIv, body);
    this.macIv = mac.slice(-16);
    const expectedMac = this.macIv.subarray(16 - MAC_LENGTH);
    if (!timingSafeEqual(expectedMac, receivedMac)) {
      throw new Error("secure channel: invalid MAC on device response");
    }

    // The IV for the NEXT message is this message's final ciphertext block, but this
    // message is still decrypted under the previous IV — hence the ordering here.
    const previousIv = this.encIv;
    this.encIv = body.slice(-16);
    const plaintext = await aesCbcDecryptRaw(this.encKey, previousIv, body);

    let end = plaintext.length - 1;
    while (end >= 0 && plaintext[end] !== PADDING_BYTE) end--;
    if (end < 0) throw new Error("secure channel: invalid padding on device response");
    return plaintext.subarray(0, end);
  }
}

function timingSafeEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}
