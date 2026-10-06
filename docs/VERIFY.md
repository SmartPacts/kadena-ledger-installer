# How to know you installed the real thing

There is exactly one check that matters, and it takes about a minute.

## The check

While installing, your device shows several screens. Step through them with the
right-hand button and read them — do not click past them. Among them:

| Screen | What it is |
|---|---|
| **Full hash** | **The one that matters.** This is what you compare. |
| Code identifier | A different hash. Not the one you are checking. |
| Manager public key | Different on every run. Normal — see below. |
| App name and version | Should read Kadena, 1.3.3. |

We deliberately do not tell you which position these appear in. An earlier version of
this page numbered them and pointed at "the fifth screen"; that order was never verified
and appears to have been wrong, which would send you to the wrong screen for the only
check that counts. Firmware is also free to reorder them. Read the labels.

Approve the installation only after you have read the **Full hash** screen.

For Kadena app **v1.3.3**, the Full hash must read exactly:

```
5de21869 76638313 a881faab e09bbf46
2df9ef8c 5fae9451 fa22b1a9 9d0efed4
```

That is the single value `5de2186976638313a881faabe09bbf462df9ef8c5fae9451fa22b1a99d0efed4`,
split into blocks — comparing 64 unbroken characters on a small screen is how people end up
checking the first four and giving up.

Read every block, not only the start and the end. The device waits as long as you need;
there is no timeout on that screen. Photographing it and comparing at your desk is a
perfectly good approach.

If it matches, the correct app is on your device. If it differs anywhere at all, reject the
installation on the device and
[report it](https://github.com/SmartPacts/kadena-ledger-installer/issues).

> **The manager public key changes every single time.** It shows a different value on
> every run, because a fresh one-time key is generated for each installation session. That is
> normal and is **not** a sign of tampering. Only the Full hash must stay constant.
>
> This is worth stating plainly, because a value that changes for innocent reasons will
> otherwise teach you to ignore all of these screens — and that habit is the real danger.

> **If you did not get a good look, say so.** Answer `no` or `unsure` at the prompt rather
> than guessing. Running the installer again simply redisplays the hash; it is harmless.
> An unread hash is an unverified install, and the tool records it that way on purpose.

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
2. the [app release notes](https://github.com/SmartPacts/app-kadena/releases/tag/v1.3.3),
   in the "Device hashes" table;
3. `SHA256SUMS.txt`, attached to that same release.

It is also reproducible: the app builds deterministically, so anyone who builds
v1.3.3 from source with the same Ledger SDK gets a binary with this hash. You do not
have to trust that we compiled it honestly — you can check.

## What the installer verifies on your behalf

These checks are convenience, not the security anchor. They catch corrupted downloads,
stale files and casual tampering early, before anything reaches your device.

| Step | Check |
|---|---|
| Release script downloaded | SHA-256 equals `08efa6c9…` |
| Firmware image extracted from it | SHA-256 equals `63e492e9…` (identical to the release's published `app.hex`) |
| Version declared inside the script | equals `1.3.3` |
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

Expected: `08efa6c91eb517fec9d84bdbd79963715c176629451bcd7c687e03f0d3d6930e`

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
