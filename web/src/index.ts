/**
 * Public API.
 *
 * One function does the whole install, because the steps are not independently useful
 * and a partial sequence has already caused a device to be left with no app at all.
 * Callers supply presentation; this supplies everything that touches the device.
 *
 * The release constants live here, not in the caller. A page that restated the expected
 * hash could drift from the image it actually serves, and the drift would be invisible
 * until someone compared against a device.
 */

import { IntelHex } from "./hex.ts";
import { AppLoader, deriveLoadParameters } from "./loader.ts";
import { ManagerSession } from "./session.ts";
import { getDeviceInfo, NotOnDashboardError, quitApp } from "./preflight.ts";
import { requestWebHidTransport } from "./webhid-transport.ts";
import { hex as toHex } from "./crypto.ts";
import type { Transport } from "./transport.ts";

export { NotOnDashboardError } from "./preflight.ts";
export { StatusError } from "./transport.ts";
export type { LoadProgress } from "./loader.ts";

/** Everything about the release this build installs. */
export const RELEASE = {
  appName: "Kadena",
  appVersion: "1.3.0",
  appReleaseTag: "v1.3.0",
  appReleaseUrl: "https://github.com/SmartPacts/app-kadena/releases/tag/v1.3.0",
  /** SHA-256 of app.hex, checked before the image is parsed. */
  appHexSha256: "636c396aa334aa835d4a99379fd30bcdcae0403ee6a21f63e91a64d5b2b80daa",
  /** What the device displays. The only thing that proves what is running. */
  deviceHash: "068f376be6115e1769952fabb61020ae5070867c9b2299c259f6947c5b5ce1db",
  targetId: 0x33100004,
  deviceName: "Ledger Nano S Plus",
  loadOptions: { apiLevel: 26, dataSize: 16896, installParamsSize: 62, flags: 0 },
} as const;

export interface InstallHooks {
  /** Device identified. */
  onDevice?: (info: { osVersion: string; targetId: number }) => void;
  /** The image was fetched and its checksum verified. */
  onImageVerified?: (sha256: string) => void;
  /** The device is about to ask the user to approve an unknown manager. */
  onApproveManager?: () => void;
  /** Handshake done; this key is what the device displayed. Differs every run. */
  onManagerKey?: (publicKeyHex: string) => void;
  onDeleted?: (existed: boolean) => void;
  onProgress?: (progress: { loaded: number; total: number }) => void;
  /**
   * Streaming finished; the device is ABOUT to display its hash and block for
   * approval. Show the expected value here — never after the install resolves, or
   * the user approves before they can compare.
   */
  onFinalising?: () => void;
}

/** Split a hash into 8-character blocks for display. Never render it as one long line. */
export function hashBlocks(digest: string = RELEASE.deviceHash): string[] {
  return digest.match(/.{1,8}/g) ?? [];
}

async function sha256Hex(bytes: Uint8Array): Promise<string> {
  return toHex(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes as BufferSource)));
}

export class ImageChecksumError extends Error {
  constructor(readonly expected: string, readonly actual: string) {
    super(
      `The application image does not match its published checksum.\n` +
        `expected ${expected}\nactually ${actual}\n` +
        `Nothing has been sent to the device.`,
    );
    this.name = "ImageChecksumError";
  }
}

export class UnsupportedDeviceError extends Error {
  constructor(readonly targetId: number) {
    super(
      `This is not a ${RELEASE.deviceName}. The Kadena app can only be installed this ` +
        `way on a ${RELEASE.deviceName}; every other Ledger needs it from Ledger Live.`,
    );
    this.name = "UnsupportedDeviceError";
  }
}

/**
 * Prompt for a device and install the pinned release onto it.
 *
 * Throws {@link NotOnDashboardError} if an app is open — the device re-enumerates when
 * it closes, so the caller must ask the user to start again rather than silently
 * reconnecting behind their back.
 */
export async function installKadenaApp(
  appHexUrl: string,
  hooks: InstallHooks = {},
): Promise<void> {
  let transport: Transport | null = null;
  try {
    transport = await requestWebHidTransport();

    let info;
    try {
      info = await getDeviceInfo(transport);
    } catch (error) {
      if (error instanceof NotOnDashboardError) {
        await quitApp(transport);
        await transport.close?.();
        transport = null;
      }
      throw error;
    }
    if (info.targetId !== RELEASE.targetId) throw new UnsupportedDeviceError(info.targetId);
    hooks.onDevice?.({ osVersion: info.osVersion, targetId: info.targetId });

    const response = await fetch(appHexUrl);
    if (!response.ok) {
      throw new Error(`Could not download the application image (${response.status}).`);
    }
    const bytes = new Uint8Array(await response.arrayBuffer());
    const digest = await sha256Hex(bytes);
    if (digest !== RELEASE.appHexSha256) {
      throw new ImageChecksumError(RELEASE.appHexSha256, digest);
    }
    hooks.onImageVerified?.(digest);

    const image = new IntelHex(new TextDecoder().decode(bytes));
    const params = deriveLoadParameters(image, RELEASE.loadOptions);

    hooks.onApproveManager?.();
    const session = await ManagerSession.open(transport, RELEASE.targetId);
    hooks.onManagerKey?.(toHex(session.managerPublicKey));

    await new AppLoader(session).installApp(RELEASE.appName, image, params, {
      onDeleted: hooks.onDeleted,
      onProgress: hooks.onProgress,
      onFinalising: hooks.onFinalising,
    });
  } finally {
    await transport?.close?.();
  }
}
