# Which Ledger devices this works on

Short answer: **the Nano S Plus, and nothing else.**

This is not a limitation we chose, and it is not something a better tool could fix.
Whether an app can be installed outside Ledger Live is decided by the device itself.

| Device | Can this install the Kadena app? | Why |
|---|---|---|
| **Nano S Plus** | **Yes** | Installing apps outside Ledger Live is permitted, and we have tested this app on real Nano S Plus hardware. |
| Nano X | No | Ledger does not permit installing apps on the Nano X outside Ledger Live. The restriction is in the device. No tool can work around it. |
| Stax | Not attempted | Ledger's tooling does appear to support it, but we own no Stax and have never tested it. We will not ship an untested install path for a device holding real funds. |
| Flex | Not attempted | Same as Stax. |
| Nano S (first generation) | No | The Kadena app is no longer built for it — current versions do not fit in its memory. |
| Nano Gen 5 / Apex | No | There is no published way to install an app on a retail Gen 5 outside Ledger's own channel. We searched every public Ledger loader and tool for one. |

The installer identifies your device before doing anything, and stops with an
explanation rather than attempting an install it cannot complete.

## Which Nano S Plus OS versions

Each Ledger OS series only accepts apps built for it: OS 1.7 refuses an app built for
OS 1.6, and OS 1.6 refuses an app built for OS 1.7. So there is one Kadena app release per
supported OS series, and the installer reads your device's OS version and picks the
matching one:

| Your Ledger OS version | Kadena app installed |
|---|---|
| 1.6.x | [v1.3.3](https://github.com/SmartPacts/app-kadena/releases/tag/v1.3.3) |
| 1.7.x | [v1.3.4](https://github.com/SmartPacts/app-kadena/releases/tag/v1.3.4) |

Any other OS version is refused rather than guessed at. If yours is older, update it in
Ledger Live ("My Ledger") and run the installer again. If yours is newer, check
[the releases page](https://github.com/SmartPacts/kadena-ledger-installer/releases) for a
newer version of this installer.

The hash to compare on the device differs between the two releases. Both are listed in
[VERIFY.md](VERIFY.md).

## If you have one of the others

The real fix — for every device, including yours — is getting the Kadena app back into
the Ledger Live catalogue. That is in progress.

What that involves, honestly: Ledger requires a paid audit by one of their approved
partners, a submission through their review process, and a review period they have
stated takes at least a month. It also requires a legal entity to accept the warranty
terms on the submission form. That work is underway; the review clock is Ledger's, not
ours, and we are not going to invent a date for you.

Progress is visible in the app repository:
**[SmartPacts/app-kadena](https://github.com/SmartPacts/app-kadena)**.

## A warning about other sources

If you search for a way to install the Kadena app, you may find
[Zondax's Hub](https://hub.zondax.ch), which offers a Kadena app for Nano S Plus, Stax
and Flex. Zondax originally wrote this app and their work is the basis of ours — but the
newest version their Hub offers is **v1.2.0, from October 2025**, and:

- it is built for an older Ledger firmware generation, so a current Nano S Plus
  **refuses to install it** (we confirmed this on hardware — the device rejects it); and
- it predates the memory-safety fixes in v1.3.0, which corrected defects in the
  transaction-display and parsing code that were present in the older official builds.

So it is not a shortcut, and on a current device it will not work anyway. Use the
current release.
