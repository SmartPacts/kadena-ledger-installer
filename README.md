# Install the Kadena app on your Ledger

The Kadena app is not currently in Ledger Live's app catalogue, so there is no
"Install" button for it. This tool installs it directly instead.

**It works on the Ledger Nano S Plus only.** If you have a different Ledger, this cannot
help you — [here is why](docs/DEVICE-SUPPORT.md), and what is happening about it.

---

## Before you start

You will need:

- a **Ledger Nano S Plus**, with its PIN, and the USB cable it came with
- a computer running **Linux** (see below)
- about five minutes

You will **not** need your recovery phrase. Nothing here ever asks for it. If any
website or program ever asks you to type your 24 words into it, that is a scam, without
exception — including anything claiming to be us.

---

## Which computers this runs on

**Linux only, for now.** That is a statement about testing, not about difficulty.

macOS and Windows versions are written and included in this repository, but **nobody has
yet run them against a real Ledger**, so they are not published as releases. Shipping a
"just double-click it" promise that we have never watched work would be worse than
shipping nothing. If you would like to help test them, please
[say so in an issue](https://github.com/SmartPacts/kadena-ledger-installer/issues).

The Kadena app returning to Ledger Live is what will serve everyone on every platform.
That is the real fix and it is being worked on — see [Device support](docs/DEVICE-SUPPORT.md).

## Install it

### 1. Download

Get **[the latest release](https://github.com/SmartPacts/kadena-ledger-installer/releases/latest)**
and download `Kadena-Ledger-Installer-Linux.zip`.

Unzip it. You will get two files — the installer, and the program it runs. Keep them
together in the same folder.

### 2. Get your Ledger ready

1. Plug it into your computer directly — not through a hub, docking station or monitor.
2. Enter your PIN.
3. Leave it on the home screen (the one that scrolls through your apps).
4. **Close Ledger Live completely.** While it is open it holds the connection to the
   device and nothing else can reach it. On a Mac, check it is not still in the Dock.

### 3. Run it

Open a terminal in that folder and run:

```sh
chmod +x install-kadena-linux.sh
./install-kadena-linux.sh
```

If your Ledger is not found, run this once, then unplug and replug it:

```sh
./install-kadena-linux.sh --install-udev-rules
```

That step matters more than it looks. Linux needs a rule so ordinary programs may reach a
Ledger over USB, and the rule has to cover **both** the `hidraw` and `usb` subsystems —
depending on how your Python was built, the tool may talk to either one. A rule covering
only `hidraw` produces a bare "open failed" that looks like a broken device.

### 4. Watch your device, and check the hash

Your Ledger will ask you to approve the installation, and will warn you that this app is
not reviewed by Ledger — **that warning is correct and expected**, because the app is not
in their catalogue yet.

Step through the screens with the right-hand button. They come in this order, and the
**fifth** one is the one you care about:

1. "Allow unknown manager?" — approve
2. Manager public key — **this is different every run; that is normal**
3. App name and version — Kadena, 1.3.0
4. Code identifier — a different hash, not the one you are checking
5. **Full hash** — **the one that matters**
6. "Install app Kadena?" — approve only after reading screen 5

The Full hash must read exactly:

```
068f376b e6115e17 69952fab b61020ae
5070867c 9b2299c2 59f6947c 5b5ce1db
```

Read every block, not just the first and last. The device waits as long as you need.
This is the one step that genuinely matters, and
[this page explains why](docs/VERIFY.md). If the characters differ anywhere, reject the
installation on the device and [tell us](https://github.com/SmartPacts/kadena-ledger-installer/issues).

If you did not get a good look, answer `no` or `unsure` at the prompt instead of guessing.
Running the installer again just shows you the hash a second time.

### 5. Done

Open the Kadena app on your Ledger and connect your wallet as usual.

Some wallets need **Blind signing** switched on. That setting lives inside the Kadena
app's own settings menu on the device — not in Ledger Live, and it is a different
setting from "Expert mode".

---

## Is this safe?

Some honest answers, because you should not take our word for it.

**Can this steal my crypto?** Not by reading your recovery phrase — no app installed on
a Ledger can do that, which is the whole point of the device. The real risk with any
app that Ledger has not reviewed is different: a tampered app could show you one payment
on screen while actually signing a different one.

**So how do I know this app is not tampered with?** By comparing the hash in step 4.
Your computer might be compromised; this program might be compromised; the download
might have been swapped. None of that matters, because the hash is computed and
displayed by the Ledger itself, using what it actually received. If that number matches
the one published here and in the
[app's release notes](https://github.com/SmartPacts/app-kadena/releases/tag/v1.3.0), the
correct app is on your device. **Do not skip that comparison.**

**Can this break my Ledger?** No. Installing and removing apps never touches your
recovery phrase, your PIN, or the device firmware. If anything goes wrong, remove the
app in Ledger Live under "My Ledger" and you are exactly back where you started.

**Why not just use Ledger Live?** Because the Kadena app is not in the catalogue right
now. Getting it back in there is the actual fix, and it is being worked on — see
[Device support](docs/DEVICE-SUPPORT.md). This tool exists for the meantime.

**Where does the app itself come from?** From the
[SmartPacts/app-kadena](https://github.com/SmartPacts/app-kadena) repository — open
source, Apache-2.0, continuing [Zondax](https://www.zondax.ch)'s original work. This
installer downloads the published release, checks it against published checksums, and
runs the exact installation that release was tested with. It does not build, patch, or
repackage the app.

> **Beware of lookalikes.** Because this is a tool that puts software onto a hardware
> wallet, it is exactly the kind of thing scammers clone. The only place we publish it is
> `github.com/SmartPacts/kadena-ledger-installer`. Anything else — a different domain, a
> "support agent" sending you a file, a version that asks for your recovery phrase — is
> not us.

---

## If something goes wrong

Start with **[Troubleshooting](docs/TROUBLESHOOTING.md)**. It covers the common ones:
device not found, Ledger Live holding the connection, USB permissions, "not enough
space", and a missing Python.

Still stuck? [Open an issue](https://github.com/SmartPacts/kadena-ledger-installer/issues)
and paste everything the installer printed. Never include your recovery phrase — we will
never ask for it, and neither will anyone legitimate.

---

## For developers

The installer is one Python file, [kadena_ledger_install.py](kadena_ledger_install.py),
with no dependencies of its own. It:

1. builds a private virtualenv and installs `ledgerblue==0.1.58` into it, leaving your
   system Python untouched;
2. downloads `installer_nanos_plus.sh` from the pinned app release and checks it against
   a SHA-256 baked into the source;
3. extracts the Intel-hex firmware image and the `LOAD_PARAMS` **from that verified
   file** rather than restating them, so the parameters can never drift from the ones
   proven on hardware, and checks the extracted image against its own pinned SHA-256;
4. identifies the connected device and refuses anything that is not a Nano S Plus;
5. runs `ledgerblue.loadApp` with those parameters and makes you confirm the device hash.

Everything is pinned to a single app version. A new app release means a new release of
this installer.

```sh
python3 kadena_ledger_install.py --dry-run   # verify the download, touch no device
python3 kadena_ledger_install.py --version   # show pins
python3 -m pytest tests/ -q                  # tests
```

- [SECURITY.md](SECURITY.md) — trust model, what is and is not verified, reporting
- [docs/VERIFY.md](docs/VERIFY.md) — the verification chain in full
- [docs/DEVICE-SUPPORT.md](docs/DEVICE-SUPPORT.md) — which devices, and why

Licensed under Apache-2.0. Maintained by [Smart Pacts](https://smartpacts.io).
