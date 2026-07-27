/**
 * Cryptography for the Ledger manager secure channel.
 *
 * Ported from ledgerblue (Apache-2.0) — `hexLoader.py` and `deployed.py` — narrowed to
 * the single case this project needs: a Nano S Plus (target id 0x33100004) loading one
 * known application. Everything the general tool supports and we do not — custom CAs,
 * SCP v3/AES-SIV, alternate curves, signed certificate chains — is deliberately absent.
 *
 * Uses Web Crypto for AES and SHA-256 so the same source runs unmodified in a browser
 * and in Node (Node exposes `crypto.subtle` globally).
 */

import { secp256k1 } from "@noble/curves/secp256k1.js";
import { sha256 } from "@noble/hashes/sha2.js";

/** secp256k1 group order — a derived scalar must be below it to be a valid key. */
const SECP256K1_ORDER =
  0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141n;

export function concat(...parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((n, p) => n + p.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

export function hex(bytes: Uint8Array): string {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function fromHex(text: string): Uint8Array {
  const clean = text.replace(/\s+/g, "");
  const out = new Uint8Array(clean.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(clean.substr(i * 2, 2), 16);
  return out;
}

export function u32be(value: number): Uint8Array {
  const out = new Uint8Array(4);
  new DataView(out.buffer).setUint32(0, value, false);
  return out;
}

export function randomBytes(length: number): Uint8Array {
  const out = new Uint8Array(length);
  crypto.getRandomValues(out);
  return out;
}

// ---------------------------------------------------------------------------------
// secp256k1
// ---------------------------------------------------------------------------------

export function publicKeyUncompressed(privateKey: Uint8Array): Uint8Array {
  return secp256k1.getPublicKey(privateKey, false); // 65 bytes, 0x04-prefixed
}

export function verifyEcdsaDer(
  publicKey: Uint8Array,
  message: Uint8Array,
  derSignature: Uint8Array,
): boolean {
  try {
    return secp256k1.verify(derSignature, sha256(message), publicKey, {
      format: "der",
      prehash: false,
    });
  } catch {
    return false;
  }
}

export function signEcdsaDer(privateKey: Uint8Array, message: Uint8Array): Uint8Array {
  // The device verifies a DER-encoded ECDSA signature over sha256(message), which is
  // what libsecp256k1's ecdsa_sign does by default.
  const digest = sha256(message);
  return secp256k1.sign(digest, privateKey, { prehash: false }).toBytes("der");
}

/**
 * ECDH exactly as libsecp256k1 does it by default: SHA-256 over the COMPRESSED
 * shared point. Returning the raw point here instead would produce a channel whose
 * keys disagree with the device in a way that only shows up as a MAC failure much
 * later, so it is called out rather than left implicit.
 */
export function ecdhSecret(
  privateKey: Uint8Array,
  peerPublicKey: Uint8Array,
): Uint8Array {
  const shared = secp256k1.getSharedSecret(privateKey, peerPublicKey, true); // compressed
  return sha256(shared);
}

/**
 * Derive one secure-channel key from the ECDH secret.
 *
 * d(i) = sha256( be32(keyIndex) || u8(retry) || ecdhSecret ), retrying until the
 * result is a valid scalar; then k(i) = sha256( uncompressed(d(i) * G) ).
 */
export function scpDeriveKey(ecdh: Uint8Array, keyIndex: number): Uint8Array {
  for (let retry = 0; retry < 256; retry++) {
    const candidate = sha256(concat(u32be(keyIndex), Uint8Array.of(retry), ecdh));
    if (BigInt("0x" + hex(candidate)) >= SECP256K1_ORDER) continue;
    return sha256(publicKeyUncompressed(candidate));
  }
  throw new Error("could not derive a valid secure-channel key");
}

// ---------------------------------------------------------------------------------
// AES-CBC
//
// Web Crypto's AES-CBC always applies PKCS#7 on encrypt and validates it on decrypt.
// This protocol does its own ISO 7816-4 padding (0x80 then zeros) and also needs raw,
// unpadded block operations for the MAC. So every call here works on whole blocks and
// strips or supplies the PKCS#7 block Web Crypto insists on.
// ---------------------------------------------------------------------------------

const ZERO_IV = new Uint8Array(16);

async function importAesKey(raw: Uint8Array): Promise<CryptoKey> {
  return crypto.subtle.importKey("raw", raw as BufferSource, "AES-CBC", false, [
    "encrypt",
    "decrypt",
  ]);
}

/** Raw AES-CBC encrypt of whole blocks, with no padding added. */
export async function aesCbcEncryptRaw(
  key: Uint8Array,
  iv: Uint8Array,
  data: Uint8Array,
): Promise<Uint8Array> {
  if (data.length % 16 !== 0) throw new Error("AES-CBC input must be whole blocks");
  const cryptoKey = await importAesKey(key);
  const out = new Uint8Array(
    await crypto.subtle.encrypt({ name: "AES-CBC", iv: iv as BufferSource }, cryptoKey, data as BufferSource),
  );
  // Web Crypto appended one PKCS#7 block we did not ask for; drop it.
  return out.subarray(0, out.length - 16);
}

/** Raw AES-CBC decrypt of whole blocks, with no padding validation. */
export async function aesCbcDecryptRaw(
  key: Uint8Array,
  iv: Uint8Array,
  data: Uint8Array,
): Promise<Uint8Array> {
  if (data.length % 16 !== 0) throw new Error("AES-CBC input must be whole blocks");
  const cryptoKey = await importAesKey(key);
  // Web Crypto will strip a PKCS#7 block, so encrypt a valid padding block under the
  // trailing ciphertext block and append it, making the decrypt succeed and return
  // exactly our plaintext.
  const tail = data.subarray(data.length - 16);
  const padBlock = new Uint8Array(16).fill(16);
  const paddingCiphertext = new Uint8Array(
    await crypto.subtle.encrypt(
      { name: "AES-CBC", iv: tail as BufferSource },
      cryptoKey,
      padBlock as BufferSource,
    ),
  ).subarray(0, 16);
  const out = new Uint8Array(
    await crypto.subtle.decrypt(
      { name: "AES-CBC", iv: iv as BufferSource },
      cryptoKey,
      concat(data, paddingCiphertext) as BufferSource,
    ),
  );
  return out;
}

export { ZERO_IV };
