# Install the Kadena app on your Ledger

The Kadena app is not currently in Ledger Live's app catalogue, so there is no
"Install" button for it. This tool installs it directly instead.

**It works on the Ledger Nano S Plus only.** If you have a different Ledger, this cannot
help you — [here is why](docs/DEVICE-SUPPORT.md), and what is happening about it.

---

## Before you start

You will need:

- a **Ledger Nano S Plus** running Ledger OS 1.6.x or 1.7.x, with its PIN, and the USB
  cable it came with
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

The installer first reads which Ledger OS version your device runs and picks the Kadena
app release built for it — Ledger's OS refuses an app built for a different OS version,
so this is not a choice you need to make. It tells you which version it found and which
release it chose.

### 4. Watch your device, and check the hash

Your Ledger will ask you to approve the installation, and will warn you that this app is
not reviewed by Ledger — **that warning is correct and expected**, because the app is not
in their catalogue yet.

Step through the screens with the right-hand button and read them. Among them you will
see a **Full hash** screen — that is the one that matters. There is also a **Code
identifier** screen showing a different value, and a **Manager public key** which is
different on every run (normal, not a warning sign).

Read the labels rather than counting screens: the order is not something we can promise,
and pointing you at the wrong one would be worse than saying nothing.

The Full hash depends on your Ledger's OS version, because each OS version gets its own
build of the app. The installer prints the right one for your device; it must be the
matching one in this table:

| Your Ledger OS version | Kadena app installed | The Full hash must read exactly |
|---|---|---|
| 1.6.x (for example 1.6.1) | [v1.3.3](https://github.com/SmartPacts/app-kadena/releases/tag/v1.3.3) | `5de21869 76638313 a881faab e09bbf46 2df9ef8c 5fae9451 fa22b1a9 9d0efed4` |
| 1.7.x (for example 1.7.0) | [v1.3.4](https://github.com/SmartPacts/app-kadena/releases/tag/v1.3.4) | `03b75bac b5f651c2 7c27adcc 4be525c4 bc9f5547 97a39555 ee7dbdc2 f69d9d85` |

Any other OS version is refused, with an explanation: an older one can be updated in
Ledger Live first, and for a newer one, check
[the releases page](https://github.com/SmartPacts/kadena-ledger-installer/releases) for a
newer version of this installer.

To see your OS version on the device yourself: open **Settings** and find the entry called
**Ledger OS version** (called **Firmware version** on older OS versions). The number shown
under **Secure Element** is your OS version.
[Ledger's own instructions](https://support.ledger.com/article/4404389344913-zd) show the
steps for each device.

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
the one published here for your OS version and in that release's notes
([v1.3.3](https://github.com/SmartPacts/app-kadena/releases/tag/v1.3.3), [v1.3.4](https://github.com/SmartPacts/app-kadena/releases/tag/v1.3.4)), the
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
2. identifies the connected device, refuses anything that is not a Nano S Plus, reads
   its Ledger OS version, and picks the app release built for that OS series — refusing
   any OS version it has no release for (`RELEASES` in the source: one entry per
   supported OS series, each with its own pins);
3. downloads that release's `installer_nanos_plus.sh` and checks it against the SHA-256
   baked into the source for it;
4. extracts the Intel-hex firmware image and the `LOAD_PARAMS` **from that verified
   file** rather than restating them, so the parameters can never drift from the ones
   proven on hardware, checks the extracted image against its own pinned SHA-256, and
   checks the API level in those parameters is the one that OS series accepts;
5. runs `ledgerblue.loadApp` with those parameters and makes you confirm the device hash.

Every release is pinned. A new app release, or support for a new OS version, means a new
release of this installer.

```sh
python3 kadena_ledger_install.py --dry-run   # install nothing; see below
python3 kadena_ledger_install.py --version   # show pins
python3 -m pytest tests/ -q                  # tests
```

`--dry-run` installs nothing. With a Ledger connected it reads the OS version (a
read-only request), says which release it would install, and verifies that release's
download. With no Ledger connected it verifies the download of every supported release.

- [SECURITY.md](SECURITY.md) — trust model, what is and is not verified, reporting
- [docs/VERIFY.md](docs/VERIFY.md) — the verification chain in full
- [docs/DEVICE-SUPPORT.md](docs/DEVICE-SUPPORT.md) — which devices, and why

Licensed under Apache-2.0. Maintained by [Smart Pacts](https://smartpacts.io).
