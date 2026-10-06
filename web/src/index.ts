/**
 * Public API.
 *
 * One function does the whole install, because the steps are not independently useful
 * and a partial sequence has already caused a device to be left with no app at all.
 * Callers supply presentation; this supplies everything that touches the device.
 *
 * The release constants live in releases.ts, not in the caller, and the release is
 * chosen here from the OS version the device reports. A page that restated the expected
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
import { DEVICE, releaseForOsVersion, type Release } from "./releases.ts";

export {
  DEVICE,
  RELEASES,
  INSTALLER_RELEASES_URL,
  releaseForOsVersion,
  UnsupportedOsError,
} from "./releases.ts";
export type { Release, LoadOptions } from "./releases.ts";
export { NotOnDashboardError } from "./preflight.ts";
export { StatusError } from "./transport.ts";
export type { LoadProgress } from "./loader.ts";

export interface InstallHooks {
  /**
   * Device identified and the release for its OS chosen. Show the release's version and
   * device hash from here on: before this point it is not known which one applies.
   */
  onDevice?: (info: { osVersion: string; targetId: number; release: Release }) => void;
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
export function hashBlocks(digest: string): string[] {
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
      `This is not a ${DEVICE.deviceName}. The Kadena app can only be installed this ` +
        `way on a ${DEVICE.deviceName}; every other Ledger needs it from Ledger Live.`,
    );
    this.name = "UnsupportedDeviceError";
  }
}

/**
 * Prompt for a device, choose the release built for its OS version, and install it.
 *
 * `appHexUrl` maps the chosen release to where its image is served (for example
 * `(r) => "/ledger/" + r.appHexFile`). The image is refused unless its SHA-256 is that
 * release's pin. Throws {@link UnsupportedOsError} for an OS version with no release.
 *
 * Throws {@link NotOnDashboardError} if an app is open — the device re-enumerates when
 * it closes, so the caller must ask the user to start again rather than silently
 * reconnecting behind their back.
 */
export async function installKadenaApp(
  appHexUrl: (release: Release) => string,
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
    if (info.targetId !== DEVICE.targetId) throw new UnsupportedDeviceError(info.targetId);
    const release = releaseForOsVersion(info.osVersion);
    hooks.onDevice?.({ osVersion: info.osVersion, targetId: info.targetId, release });

    const response = await fetch(appHexUrl(release));
    if (!response.ok) {
      throw new Error(`Could not download the application image (${response.status}).`);
    }
    const bytes = new Uint8Array(await response.arrayBuffer());
    const digest = await sha256Hex(bytes);
    if (digest !== release.appHexSha256) {
      throw new ImageChecksumError(release.appHexSha256, digest);
    }
    hooks.onImageVerified?.(digest);

    const image = new IntelHex(new TextDecoder().decode(bytes));
    const params = deriveLoadParameters(image, release.loadOptions);

    hooks.onApproveManager?.();
    const session = await ManagerSession.open(transport, DEVICE.targetId);
    hooks.onManagerKey?.(toHex(session.managerPublicKey));

    await new AppLoader(session).installApp(DEVICE.appName, image, params, {
      onDeleted: hooks.onDeleted,
      onProgress: hooks.onProgress,
      onFinalising: hooks.onFinalising,
    });
  } finally {
    await transport?.close?.();
  }
}
