/**
 * Manager mutual authentication — ledgerblue's `getDeployedSecretV2`, narrowed.
 *
 * We hold no Ledger-issued signing key, so we generate one per session, present it as
 * our own root and self-sign the chain. The device accepts it and warns the human
 * ("Allow unknown manager?", showing that key). That is precisely why installing an
 * unreviewed app needs physical approval — and why the manager public key the user
 * sees is different on every run.
 *
 * Honest limit: because our root is not Ledger's, this does NOT attest that the peer
 * is a genuine Ledger. The signature check below only proves the chain is internally
 * consistent — the device's ephemeral key really was signed by the device certificate
 * it just presented. Upstream behaves the same way when loading from a user key. The
 * assurance that the right application landed on the device comes from the hash shown
 * on its screen, not from this handshake.
 *
 * Ported from ledgerblue (Apache-2.0), stripped of the signed-certificate-chain and
 * custom-CA paths this project does not use.
 */

import type { Transport } from "./transport.ts";
import {
  concat,
  publicKeyUncompressed,
  randomBytes,
  signEcdsaDer,
  u32be,
  verifyEcdsaDer,
} from "./crypto.ts";

export interface HandshakeResult {
  /** Our per-session ephemeral private key — one half of the channel's ECDH. */
  ephemeralPrivate: Uint8Array;
  /** The device's ephemeral public key — the other half. */
  devicePublic: Uint8Array;
  /** The key the device displayed as "manager public key". */
  managerPublic: Uint8Array;
}

const CLA = 0xe0;

function certificate(publicKey: Uint8Array, signature: Uint8Array): Uint8Array {
  return concat(
    Uint8Array.of(publicKey.length),
    publicKey,
    Uint8Array.of(signature.length),
    signature,
  );
}

/** Split [len][header][len][publicKey][len][signature]. */
function parseCertificate(cert: Uint8Array): {
  header: Uint8Array;
  publicKey: Uint8Array;
  signature: Uint8Array;
} {
  let offset = 1;
  const header = cert.subarray(offset, offset + cert[offset - 1]);
  offset += cert[offset - 1] + 1;
  const publicKey = cert.subarray(offset, offset + cert[offset - 1]);
  offset += cert[offset - 1] + 1;
  const signature = cert.subarray(offset, offset + cert[offset - 1]);
  return { header, publicKey, signature };
}

export async function establishSecureChannel(
  transport: Transport,
  targetId: number,
): Promise<HandshakeResult> {
  if ((targetId & 0xf) < 2) {
    throw new Error(`target 0x${targetId.toString(16)} does not support this channel`);
  }

  // 1. Identify the target we believe we are talking to.
  await transport.exchange(concat(Uint8Array.of(CLA, 0x04, 0x00, 0x00, 4), u32be(targetId)));

  // 2. Open the exchange with our nonce; the device answers with its own.
  const hostNonce = randomBytes(8);
  const authInfo = await transport.exchange(
    concat(Uint8Array.of(CLA, 0x50, 0x00, 0x00, hostNonce.length), hostNonce),
  );
  const deviceNonce = authInfo.subarray(4, 12);

  // 3. Present our self-signed root. This is the key the device shows the user.
  const managerPrivate = randomBytes(32);
  const managerPublic = publicKeyUncompressed(managerPrivate);
  const rootCert = certificate(
    managerPublic,
    signEcdsaDer(managerPrivate, concat(Uint8Array.of(0x01), managerPublic)),
  );
  await transport.exchange(
    concat(Uint8Array.of(CLA, 0x51, 0x00, 0x00, rootCert.length), rootCert),
  );

  // 4. Present an ephemeral key signed by that root and bound to BOTH nonces, so the
  //    certificate cannot be replayed into another session. Note P1 = 0x80 here.
  const ephemeralPrivate = randomBytes(32);
  const ephemeralPublic = publicKeyUncompressed(ephemeralPrivate);
  const ephemeralCert = certificate(
    ephemeralPublic,
    signEcdsaDer(
      managerPrivate,
      concat(Uint8Array.of(0x11), hostNonce, deviceNonce, ephemeralPublic),
    ),
  );
  await transport.exchange(
    concat(Uint8Array.of(CLA, 0x51, 0x80, 0x00, ephemeralCert.length), ephemeralCert),
  );

  // 5. Read the device's two certificates: the device certificate, then its ephemeral
  //    key. Each is fetched with its own APDU (P1 0x00 then 0x80).
  let signerPublic = managerPublic; // what each certificate should be signed by
  let devicePublic: Uint8Array | null = null;

  for (const [index, p1] of [[0, 0x00], [1, 0x80]] as const) {
    const raw = await transport.exchange(Uint8Array.of(CLA, 0x52, p1, 0x00, 0x00));
    if (raw.length === 0) break;
    const { header, publicKey, signature } = parseCertificate(raw);

    const signedData =
      index === 0
        ? concat(Uint8Array.of(0x02), header, publicKey)
        : concat(Uint8Array.of(0x12), deviceNonce, hostNonce, publicKey);

    const valid = verifyEcdsaDer(signerPublic, signedData, signature);
    if (!valid && index !== 0) {
      // Index 0 cannot verify against our own root — upstream tolerates that, and so
      // do we. A bad ephemeral certificate is a genuine failure.
      throw new Error("device certificate chain is broken");
    }

    signerPublic = publicKey;
    devicePublic = publicKey;
  }

  if (!devicePublic || devicePublic.length === 0) {
    throw new Error("device did not return an ephemeral public key");
  }

  // 6. Commit. Every payload after this point is wrapped by the secure channel.
  await transport.exchange(Uint8Array.of(CLA, 0x53, 0x00, 0x00, 0x00));

  return { ephemeralPrivate, devicePublic, managerPublic };
}
