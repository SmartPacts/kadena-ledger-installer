# Troubleshooting

Nothing here can damage your Ledger or put your funds at risk. Installing and removing
apps never touches your recovery phrase, your PIN or the device firmware. It is always
safe to unplug, replug and try again.

---

## "No Ledger was found"

Work through these in order — it is almost always one of the first three.

1. **Is Ledger Live closed?** Not minimised — closed. While it runs it holds the
   connection open and nothing else can reach the device. On a Mac, check the Dock; on
   Windows, check the system tray.
2. **Is the device unlocked?** Enter your PIN. The screen should be showing the app list.
3. **Is it plugged in directly?** USB hubs, docking stations, monitor USB ports and
   keyboard passthroughs all cause this. Use a port on the computer itself.
4. **Is the cable a data cable?** Some USB cables carry power only. The cable that came
   with the Ledger is a data cable. If the device charges but nothing detects it, suspect
   the cable.
5. **On Linux, are the USB permissions set up?** Run this once, then unplug and replug:
   ```sh
   ./install-kadena-linux.sh --install-udev-rules
   ```
   It writes one rule file to `/etc/udev/rules.d/` and asks for your password to do it.

---

## Not on Linux?

macOS and Windows versions exist in the repository but are not released yet, because
nobody has run them against real hardware. See the README.

## Linux: "Python 3 is installed but is missing the venv component"

```sh
sudo apt install python3-venv        # Debian, Ubuntu, Mint
```

## Linux: the ledgerblue install fails to build

It needs a few system packages to compile its USB support:

```sh
sudo apt install python3-dev libusb-1.0-0-dev libudev-dev
```

---

## The installation starts and then stops partway

- **You did not approve it in time.** The device stops waiting after a while. Just run it
  again.
- **The device locked itself.** Unlock it and run again.
- **"Not enough space"** — the Nano S Plus fits a limited number of apps. Open Ledger
  Live → My Ledger, uninstall an app you do not use, close Ledger Live again, and retry.
  Uninstalling an app never affects the coins it manages; your funds live on the
  blockchain, not on the device.

Nothing is left broken by a failed install. Try again.

---

## The hash on the device did not match

**Stop and do not use the app.**

1. Open Ledger Live → My Ledger → uninstall **Kadena**.
2. Do not open the app, and do not send anything to an address it displays.
3. [Report it](https://github.com/SmartPacts/kadena-ledger-installer/issues), including
   what the device showed, which computer and which network you were on.

Your recovery phrase was never exposed — an installed app cannot read it. The concern
with a wrong app is narrower but still serious: it could display one payment and sign
another. So simply do not use it until this is understood.

---

## Removing the app

Ledger Live → My Ledger → find **Kadena** → uninstall. Your KDA is unaffected: it lives
on the blockchain, and reinstalling the app later restores access with the same
recovery phrase.

---

## Still stuck

[Open an issue](https://github.com/SmartPacts/kadena-ledger-installer/issues) and paste
everything the installer printed, plus your operating system and Ledger model.

**Never share your 24-word recovery phrase.** Not with us, not with "support", not with
anyone. No legitimate person will ever need it, and there is no problem in this document
whose solution requires it.
