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

## macOS: "cannot be opened because it is from an unidentified developer"

Expected. We do not pay for an Apple Developer certificate.

**Right-click** the `.command` file, choose **Open**, then click **Open** in the dialog
that appears. Once you have done this, double-clicking works normally from then on.

If right-click → Open is not offered, open **System Settings → Privacy & Security**,
scroll down, and click **Open Anyway** next to the message about the blocked file.

## macOS: "Operation not permitted" or nothing happens on double-click

The executable permission was lost, usually by unzipping with a third-party tool. Open
Terminal in that folder and run:

```sh
chmod +x "Install Kadena on Ledger.command"
```

## Windows: "Windows protected your PC"

Expected, same reason. Click **More info**, then **Run anyway**.

## Windows: "Python is not installed"

The easiest fix on Windows 10 or 11 — open Terminal from the Start menu and run:

```
winget install Python.Python.3.12
```

Then double-click the installer again. If you install from
[python.org](https://www.python.org/downloads/) instead, make sure you tick **"Add
python.exe to PATH"** on the first screen, or Windows will not find it afterwards.

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
