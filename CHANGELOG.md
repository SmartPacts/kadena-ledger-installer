# Changelog

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
