# How to know you installed the real thing

There is exactly one check that matters, and it takes ten seconds.

## The check

While the app installs, your Ledger displays a long line of letters and numbers on its
own screen. For Kadena app **v1.3.0** it must read:

```
068f376be6115e1769952fabb61020ae5070867c9b2299c259f6947c5b5ce1db
```

Compare it against the screen. If it matches, the correct app is on your device. If it
differs anywhere at all, reject the installation on the device and
[report it](https://github.com/SmartPacts/kadena-ledger-installer/issues).

## Why this one check is enough

Everything else in the chain runs on your computer, and a computer can be compromised.
The installer could be replaced. The download could be swapped in transit. The checksums
it prints could be faked by a program that is lying to you.

The device screen is different. That hash is calculated by the Ledger itself, from the
bytes it actually received, and shown on hardware your computer does not control. A
compromised computer can send the wrong app — but it cannot make the Ledger display the
right hash for the wrong app. Finding two different apps with the same SHA-256 is not
something anyone can currently do.

So: the whole security of this process rests on you comparing that number. Everything
else is convenience.

## Where the number comes from

The same value is published in three independent places. They should all agree:

1. this page;
2. the [app release notes](https://github.com/SmartPacts/app-kadena/releases/tag/v1.3.0),
   in the "Device hashes" table;
3. `SHA256SUMS.txt`, attached to that same release.

It is also reproducible: the app builds deterministically, so anyone who builds
v1.3.0 from source with the same Ledger SDK gets a binary with this hash. You do not
have to trust that we compiled it honestly — you can check.

## What the installer verifies on your behalf

These checks are convenience, not the security anchor. They catch corrupted downloads,
stale files and casual tampering early, before anything reaches your device.

| Step | Check |
|---|---|
| Release script downloaded | SHA-256 equals `93dd62d2…` |
| Firmware image extracted from it | SHA-256 equals `636c396a…` (identical to the release's published `app.hex`) |
| Version declared inside the script | equals `1.3.0` |
| Install parameters | read out of the verified file, never hand-written, and rejected if they target any device other than a Nano S Plus |
| Connected device | must identify as a Nano S Plus |

If any of these fail, the installer stops and nothing is sent to your device.

## Checking the download yourself

If you would rather verify by hand before running anything:

```sh
# macOS / Linux
shasum -a 256 installer_nanos_plus.sh
# Windows
certutil -hashfile installer_nanos_plus.sh SHA256
```

Expected: `93dd62d28c465edecf228ac02570845926b59c31eb47f33660457ada79bd6e0e`

## The limits of this, stated plainly

- **We do not pin the Python packages by hash.** The installer pins `ledgerblue` to
  version `0.1.58`, the version this app release was proven with, but it installs it
  from PyPI and trusts PyPI to serve the real thing. Maintaining a fully hash-pinned
  dependency set across three operating systems is not something we can keep honest with
  the resources we have, and claiming otherwise would be worse than saying so. The device
  hash check is what defends you here — a malicious `ledgerblue` could send a different
  app, and the device would show a different hash, and you would catch it.
- **The installers are not code-signed.** We do not pay for an Apple Developer
  certificate or a Windows code-signing certificate, which is why both operating systems
  will warn you. A signature would prove the file came from us; the device hash proves
  something stronger and more useful — that the right app reached the device.
- **We cannot verify Stax or Flex.** We do not own those devices. See
  [DEVICE-SUPPORT.md](DEVICE-SUPPORT.md).
