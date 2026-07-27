# Changelog

## 1.0.0 — unreleased

First release. Installs Kadena app **v1.3.0** onto a Ledger Nano S Plus.

- One-file Python installer with no dependencies of its own; creates a private
  virtualenv and installs `ledgerblue==0.1.58` there, leaving the system Python alone.
- Double-clickable wrappers for macOS and Windows, one command on Linux.
- Verification chain: pinned SHA-256 on the release script, pinned SHA-256 on the
  firmware image extracted from it, version check, and install parameters read out of
  the verified file rather than restated.
- Device identification before install; Nano X, Stax, Flex, first-generation Nano S and
  unrecognised devices are refused with an explanation of what the user can do instead.
- Explicit device-hash confirmation after install, with instructions to remove the app
  if it does not match.
- `--dry-run` verifies the download without touching any device.
- Linux USB permission rules via `--install-udev-rules`.

Pins for this release:

| | |
|---|---|
| Kadena app | v1.3.0 |
| `installer_nanos_plus.sh` | `93dd62d28c465edecf228ac02570845926b59c31eb47f33660457ada79bd6e0e` |
| `app.hex` | `636c396aa334aa835d4a99379fd30bcdcae0403ee6a21f63e91a64d5b2b80daa` |
| Device hash (nanos2) | `068f376be6115e1769952fabb61020ae5070867c9b2299c259f6947c5b5ce1db` |
| ledgerblue | 0.1.58 |
