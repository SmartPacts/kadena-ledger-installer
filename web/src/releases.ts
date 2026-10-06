/**
 * The pinned app releases, and the rule that picks one for a device.
 *
 * Which release fits is decided by the device's OS, not by us: Ledger's OS refuses an
 * app built for a different API level. OS 1.6.x refuses apps built for API 27 and OS
 * 1.7.x refuses apps built for API 26, so there is one release per supported OS series
 * and the version the device reports chooses between them. Any other OS version is
 * refused — a wrong guess is an install the device rejects at the last step.
 *
 * This is the single copy of these values for the loader, the demo page, its build and
 * the harness. A caller that restated a hash could drift from the image it serves, and
 * the drift would be invisible until someone compared against a device.
 *
 * Kept free of runtime dependencies and of TypeScript-only syntax that cannot be erased
 * (no parameter properties, no enums), so Node scripts can import it directly.
 */

export interface LoadOptions {
  apiLevel: number;
  dataSize: number;
  installParamsSize: number;
  flags: number;
}

export interface Release {
  /** Nano S Plus OS major.minor this release is built for, e.g. "1.7". */
  osSeries: string;
  appVersion: string;
  appReleaseTag: string;
  appReleaseUrl: string;
  /** URL of the release's app.hex asset. */
  appHexAssetUrl: string;
  /** The name the image is served under, distinct per release. */
  appHexFile: string;
  /** SHA-256 of app.hex, checked before the image is parsed. */
  appHexSha256: string;
  /** What the device displays as "Full hash". The only thing that proves what is running. */
  deviceHash: string;
  /** The values in the release's own LOAD_PARAMS. */
  loadOptions: LoadOptions;
}

export const DEVICE = {
  appName: "Kadena",
  targetId: 0x33100004,
  deviceName: "Ledger Nano S Plus",
} as const;

export const INSTALLER_RELEASES_URL =
  "https://github.com/SmartPacts/kadena-ledger-installer/releases";

const APP_REPO_URL = "https://github.com/SmartPacts/app-kadena";

function release(
  osSeries: string,
  appVersion: string,
  apiLevel: number,
  appHexSha256: string,
  deviceHash: string,
): Release {
  const tag = `v${appVersion}`;
  return {
    osSeries,
    appVersion,
    appReleaseTag: tag,
    appReleaseUrl: `${APP_REPO_URL}/releases/tag/${tag}`,
    appHexAssetUrl: `${APP_REPO_URL}/releases/download/${tag}/app.hex`,
    appHexFile: `app-${tag}.hex`,
    appHexSha256,
    deviceHash,
    loadOptions: { apiLevel, dataSize: 16896, installParamsSize: 62, flags: 0 },
  };
}

export const RELEASES: readonly Release[] = Object.freeze([
  release(
    "1.6",
    "1.3.3",
    26,
    "63e492e9c8cb16776f1b22e1a17d7356e57b54cd32e97e501a488ab158766236",
    "5de2186976638313a881faabe09bbf462df9ef8c5fae9451fa22b1a99d0efed4",
  ),
  release(
    "1.7",
    "1.3.4",
    27,
    "d18f6bc0e7c9e56d6124d14866decf6c572b438f47033e3377240acb7eb2cffd",
    "03b75bacb5f651c27c27adcc4be525c4bc9f554797a39555ee7dbdc2f69d9d85",
  ),
]);

function supportedList(): string {
  return RELEASES.map((r) => `Ledger OS ${r.osSeries}.x (Kadena app ${r.appVersion})`).join(
    " and ",
  );
}

export class UnsupportedOsError extends Error {
  readonly osVersion: string;
  constructor(osVersion: string, message: string) {
    super(message);
    this.name = "UnsupportedOsError";
    this.osVersion = osVersion;
  }
}

/** The release built for this OS version. Throws {@link UnsupportedOsError} otherwise. */
export function releaseForOsVersion(osVersion: string): Release {
  const match = /^([0-9]+)\.([0-9]+)\.([0-9]+)$/.exec(osVersion);
  if (!match) {
    throw new UnsupportedOsError(
      osVersion,
      `Your Ledger reported its OS version as "${osVersion}", which this installer cannot ` +
        `read, so it cannot tell which Kadena app release fits it. It supports the ` +
        `${DEVICE.deviceName} on ${supportedList()}, and will not guess. Please check for ` +
        `a newer version of this installer: ${INSTALLER_RELEASES_URL}`,
    );
  }

  const series = `${Number(match[1])}.${Number(match[2])}`;
  const found = RELEASES.find((r) => r.osSeries === series);
  if (found) return found;

  const [major, minor] = [Number(match[1]), Number(match[2])];
  const oldest = RELEASES[0].osSeries.split(".").map(Number);
  const older = major < oldest[0] || (major === oldest[0] && minor < oldest[1]);
  throw new UnsupportedOsError(
    osVersion,
    `Your Ledger runs OS version ${osVersion}, and this installer has no Kadena app release ` +
      `for it. It supports the ${DEVICE.deviceName} on ${supportedList()}, and will not ` +
      `guess: the device refuses an app built for a different OS version. ` +
      (older
        ? `Update your Ledger's OS in Ledger Live (open "My Ledger"), then try again.`
        : `Please check for a newer version of this installer: ${INSTALLER_RELEASES_URL}`),
  );
}
