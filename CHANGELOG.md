# Changelog

## 1.0.4

Installs Kadena app **v1.3.3** (static-analysis fixes, no functional change from v1.3.2).

- New pins from the `SHA256SUMS.txt` published with app v1.3.3: the release script, the firmware
  image, and the Full hash the device shows
  (`5de2186976638313a881faabe09bbf462df9ef8c5fae9451fa22b1a99d0efed4`).
- Install parameters are unchanged.
- App v1.3.3 was installed on a real Nano S Plus with the release script this installer verifies
  and runs, and its Full hash was confirmed on the device character for character.

## 1.0.3

Installs Kadena app **v1.3.2** (security release) instead of v1.3.1.

- New pins from the `SHA256SUMS.txt` published with app v1.3.2: the release script, the firmware
  image, and the Full hash the device shows
  (`0f6f62ceb5f9b841fbd1b2253a9d14c221000d8da2aeb733c4d70ee30888ccc6`).
- Install parameters are unchanged.
- App v1.3.2 was installed on a real Nano S Plus with the release script this installer verifies
  and runs, and its Full hash was confirmed on the device character for character. This installer
  version was checked by its tests and a dry run against the published release.

## 1.0.2

Installs Kadena app **v1.3.1** (the security patch release) instead of v1.3.0.

- New pins, taken from the `SHA256SUMS.txt` published with app v1.3.1: the release script,
  the firmware image, and the Full hash the device shows
  (`726078b6269fdb4ef9a70e28c66d7a00ef9f94a0f4a5c7adac11f95fc3cd814a`).
- Install parameters are unchanged from v1.3.0.
- App v1.3.1 was installed and its Full hash confirmed character-for-character on real
  Nano S Plus devices with the release script this installer verifies and runs. This
  installer version itself was checked by its tests and a dry run against the published
  release, not by a fresh hardware run.

## 1.0.1

Documentation correctness only — no change to what is installed or verified.

- **Stop telling people the Full hash is "the fifth screen".** That order was never
  verified and observation on real hardware suggested it was wrong, which would have sent
  someone to the wrong screen for the one check that matters. The guidance now names the
  screens and says to read the labels; firmware is free to reorder them.
- Say plainly that the "Code identifier" screen is a different value, and that the manager
  public key differs on every run and is not a warning sign.


## 1.0.0

First release. Installs Kadena app **v1.3.0** onto a Ledger Nano S Plus.

**Linux only.** macOS and Windows wrappers are in the repository and lint-clean, but no one
has run them against real hardware, so they are not published. `build_release.py --all`
builds them for testing.

Proven end-to-end on a real Nano S Plus (OS 1.6.1): install, on-device hash confirmed
character-for-character, app reports 1.3.0, derivation deterministic, reinstall-over-existing
idempotent, and the unanswered-prompt path correctly records the install as unverified.

- One-file Python installer with no dependencies of its own; creates a private
  virtualenv and installs `ledgerblue==0.1.58` there, leaving the system Python alone.
- One command on Linux; double-clickable macOS and Windows wrappers written but unreleased.
- Verification chain: pinned SHA-256 on the release script, pinned SHA-256 on the
  firmware image extracted from it, version check, and install parameters read out of
  the verified file rather than restated.
- Device identification before install; Nano X, Stax, Flex, first-generation Nano S and
  unrecognised devices are refused with an explanation of what the user can do instead.
- Explicit device-hash confirmation after install, with instructions to remove the app
  if it does not match.
- `--dry-run` verifies the download without touching any device.
- Linux USB permission rules via `--install-udev-rules`, covering **both** the `hidraw`
  and `usb` subsystems — a hidraw-only rule fails with a bare "open failed" when Python's
  hidapi is built against the libusb backend.
- Walks the user through the device screen sequence and names the "Full hash" screen
  explicitly, distinguishing it from the code identifier, and notes that the manager public
  key differs on every run.

Pins for this release:

| | |
|---|---|
| Kadena app | v1.3.0 |
| `installer_nanos_plus.sh` | `93dd62d28c465edecf228ac02570845926b59c31eb47f33660457ada79bd6e0e` |
| `app.hex` | `636c396aa334aa835d4a99379fd30bcdcae0403ee6a21f63e91a64d5b2b80daa` |
| Device hash (nanos2) | `068f376be6115e1769952fabb61020ae5070867c9b2299c259f6947c5b5ce1db` |
| ledgerblue | 0.1.58 |
