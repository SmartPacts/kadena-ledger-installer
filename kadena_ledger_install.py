#!/usr/bin/env python3
"""
Kadena Ledger app installer.

Installs the Kadena app onto a Ledger Nano S Plus, for people who do not have a
development environment. It sets up its own private Python environment, downloads
the official release, checks every byte against published checksums, and then asks
the device to install it.

The security model, in one line: this program can be wrong, your computer can be
compromised, and you are STILL safe as long as the hash your Ledger shows on its
own screen matches the hash printed here. Check it. That comparison is the point.

Run with --help for options. Source: https://github.com/SmartPacts/kadena-ledger-installer
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

# --------------------------------------------------------------------------------------
# Pinned release. Everything this program installs is fixed here, at this version.
# A new Kadena app release means a new release of THIS installer, with new pins.
# Values come from the SHA256SUMS.txt published with the app release.
# --------------------------------------------------------------------------------------

INSTALLER_VERSION = "1.0.0"

APP_REPO = "SmartPacts/app-kadena"
APP_VERSION = "1.3.0"
APP_RELEASE_TAG = "v1.3.0"
APP_RELEASE_URL = f"https://github.com/{APP_REPO}/releases/tag/{APP_RELEASE_TAG}"

# The official installer script published with the release. We do not reimplement it —
# we verify it, read the install parameters and firmware image straight out of it, and
# run exactly those. That way our install can never drift from the one tested on hardware.
INSTALLER_ASSET = "installer_nanos_plus.sh"
INSTALLER_ASSET_URL = (
    f"https://github.com/{APP_REPO}/releases/download/{APP_RELEASE_TAG}/{INSTALLER_ASSET}"
)
INSTALLER_ASSET_SHA256 = "93dd62d28c465edecf228ac02570845926b59c31eb47f33660457ada79bd6e0e"

# The firmware image extracted from that script, byte-identical to the release's app.hex.
APP_HEX_SHA256 = "636c396aa334aa835d4a99379fd30bcdcae0403ee6a21f63e91a64d5b2b80daa"

# What the Ledger will display on its own screen while installing. THE check that matters.
EXPECTED_DEVICE_HASH = "068f376be6115e1769952fabb61020ae5070867c9b2299c259f6947c5b5ce1db"

# Ledger's own loader library, pinned to the version this app release was proven with.
LEDGERBLUE_VERSION = "0.1.58"

# --------------------------------------------------------------------------------------
# Device support. Sideloading is a property of the device, not a choice the user makes.
# --------------------------------------------------------------------------------------

SUPPORTED_TARGET_ID = 0x33100004  # Nano S Plus
SUPPORTED_DEVICE_NAME = "Ledger Nano S Plus"

# Devices we can identify but must refuse, with the reason a non-technical person needs.
KNOWN_UNSUPPORTED = {
    0x33000004: (
        "Ledger Nano X",
        "Ledger does not allow apps to be installed on the Nano X outside Ledger Live. "
        "This is a restriction built into the device and nothing can work around it.",
    ),
    0x33200004: (
        "Ledger Stax",
        "We have not verified installation on Stax and own no Stax to test with, so this "
        "installer will not attempt it.",
    ),
    0x33300004: (
        "Ledger Flex",
        "We have not verified installation on Flex and own no Flex to test with, so this "
        "installer will not attempt it.",
    ),
    0x31100004: (
        "Ledger Nano S (first generation)",
        "The Kadena app is no longer built for the first-generation Nano S — the device "
        "does not have enough memory for current versions.",
    ),
}

USB_VENDOR_ID = 0x2C97
UDEV_RULES_PATH = Path("/etc/udev/rules.d/20-kadena-ledger.rules")
UDEV_RULES_BODY = (
    '# Ledger devices — allows this computer to talk to your Ledger without root.\n'
    'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="2c97", MODE="0666", TAG+="uaccess"\n'
    'SUBSYSTEM=="usb", ATTRS{idVendor}=="2c97", MODE="0666", TAG+="uaccess"\n'
)


class Abort(Exception):
    """A stop with an explanation already written for a non-technical reader."""


# --------------------------------------------------------------------------------------
# Output helpers. Plain language, no jargon unless it is on the device screen too.
# --------------------------------------------------------------------------------------

_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def step(n: int, total: int, text: str) -> None:
    print(f"\n{_c('1;36', f'[{n}/{total}]')} {_c('1', text)}")


def info(text: str) -> None:
    print(f"      {text}")


def ok(text: str) -> None:
    print(f"      {_c('32', 'OK')}  {text}")


def warn(text: str) -> None:
    print(f"      {_c('33', '!')}   {text}")


def banner(title: str, body: str) -> None:
    line = "=" * 74
    print(f"\n{_c('1;33', line)}")
    print(_c("1;33", f"  {title}"))
    print(_c("1;33", line))
    print(body)
    print(_c("1;33", line))


def confirm(question: str, expect: str = "yes") -> bool:
    """Ask a question that must be answered deliberately. Never a bare Enter."""
    try:
        answer = input(f"\n{_c('1', question)} (type {expect!r} to continue): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer == expect.lower()


# --------------------------------------------------------------------------------------
# Environment
# --------------------------------------------------------------------------------------


def check_python() -> None:
    if sys.version_info < (3, 9):
        raise Abort(
            f"This needs Python 3.9 or newer, but it is running on "
            f"{sys.version_info.major}.{sys.version_info.minor}.\n"
            "Install a current Python from https://www.python.org/downloads/ and try again."
        )


def data_dir() -> Path:
    """A private folder for this tool. Never touches your system Python packages."""
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "kadena-ledger-installer"


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts" if platform.system() == "Windows" else "bin") / (
        "python.exe" if platform.system() == "Windows" else "python"
    )


def ensure_venv(venv: Path, offline: bool = False) -> Path:
    """Create a private environment holding Ledger's loader library, pinned by version."""
    py = venv_python(venv)
    if py.exists() and _ledgerblue_ok(py):
        ok(f"Ledger loader library already installed (ledgerblue {LEDGERBLUE_VERSION}).")
        return py

    if offline:
        raise Abort(
            "Offline mode was requested but the Ledger loader library is not installed yet.\n"
            "Run once with an internet connection first."
        )

    if venv.exists():
        info("Rebuilding the private environment...")
        shutil.rmtree(venv, ignore_errors=True)

    info(f"Creating a private Python environment in {venv}")
    info("(this does not change your system Python or any other program)")
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip()
        if "ensurepip" in detail or "venv" in detail:
            raise Abort(
                "Python is installed but is missing the 'venv' component.\n"
                "On Debian/Ubuntu install it with:  sudo apt install python3-venv\n"
                f"\nOriginal error:\n{detail}"
            ) from exc
        raise Abort(f"Could not create the private Python environment.\n\n{detail}") from exc

    info(f"Installing Ledger's loader library (ledgerblue {LEDGERBLUE_VERSION})...")
    result = subprocess.run(
        [
            str(py), "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
            f"ledgerblue=={LEDGERBLUE_VERSION}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise Abort(
            "Could not install Ledger's loader library.\n"
            "This is usually a missing build tool or no internet connection.\n"
            "On Debian/Ubuntu:  sudo apt install python3-dev libusb-1.0-0-dev libudev-dev\n"
            f"\nOriginal error:\n{(result.stderr or result.stdout).strip()}"
        )

    if not _ledgerblue_ok(py):
        raise Abort("Ledger's loader library installed but could not be loaded. Please report this.")

    ok(f"Ledger loader library ready (ledgerblue {LEDGERBLUE_VERSION}).")
    return py


def _ledgerblue_ok(py: Path) -> bool:
    result = subprocess.run(
        [str(py), "-c", "import ledgerblue.loadApp"], capture_output=True, text=True
    )
    return result.returncode == 0


# --------------------------------------------------------------------------------------
# Download and verification
# --------------------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_installer(dest: Path, local: Path | None) -> Path:
    """Get the official release script, then prove it is the exact expected file."""
    target = dest / INSTALLER_ASSET

    if local is not None:
        if not local.is_file():
            raise Abort(f"The file you passed with --installer does not exist: {local}")
        shutil.copyfile(local, target)
        info(f"Using the local file you provided: {local}")
    else:
        info(f"Downloading the official Kadena app {APP_VERSION} release...")
        info(f"from {INSTALLER_ASSET_URL}")
        try:
            with urllib.request.urlopen(INSTALLER_ASSET_URL, timeout=120) as response:
                target.write_bytes(response.read())
        except urllib.error.URLError as exc:
            raise Abort(
                "Could not download the release. Check your internet connection.\n"
                f"You can also download it yourself from:\n  {APP_RELEASE_URL}\n"
                f"then re-run this with:  --installer /path/to/{INSTALLER_ASSET}\n"
                f"\nOriginal error: {exc}"
            ) from exc

    actual = sha256_file(target)
    if actual != INSTALLER_ASSET_SHA256:
        raise Abort(
            "STOP — the release file is not what it should be.\n\n"
            f"  expected: {INSTALLER_ASSET_SHA256}\n"
            f"  actually: {actual}\n\n"
            "Nothing has been sent to your Ledger and nothing will be. Do not install this file.\n"
            "This means either the download was corrupted, or the file was tampered with.\n"
            "Try again on a different network; if it happens again, please report it at\n"
            "https://github.com/SmartPacts/kadena-ledger-installer/issues"
        )
    ok(f"Release file checksum matches the published value ({actual[:16]}...).")
    return target


def extract_payload(script: Path, dest: Path) -> tuple[Path, list[str], str]:
    """Read the firmware image and install parameters out of the verified script.

    We deliberately do not hand-write these values. Taking them from the file that was
    tested on real hardware means our install is that install, not a lookalike.
    """
    raw = script.read_bytes()

    match = re.search(rb'\nAPPHEX="\n(.*?)\n"\n', raw, re.S)
    if match is None:
        raise Abort("Could not read the app image from the release file. Please report this.")
    # The release script writes this block out followed by a single newline.
    app_hex = dest / "app.hex"
    app_hex.write_bytes(match.group(1) + b"\n")

    actual = sha256_file(app_hex)
    if actual != APP_HEX_SHA256:
        raise Abort(
            "STOP — the app image inside the release file is not what it should be.\n\n"
            f"  expected: {APP_HEX_SHA256}\n"
            f"  actually: {actual}\n\n"
            "Nothing has been sent to your Ledger. Please report this."
        )
    ok(f"App image checksum matches the published value ({actual[:16]}...).")

    params_match = re.search(rb"\nLOAD_PARAMS=\((.*?)\)\n", raw, re.S)
    if params_match is None:
        raise Abort("Could not read the install settings from the release file. Please report this.")
    params = _split_params(params_match.group(1).decode("utf-8"))

    version_match = re.search(rb'\nAPPVERSION="([^"]+)"\n', raw)
    version = version_match.group(1).decode() if version_match else "unknown"
    if version != APP_VERSION:
        raise Abort(
            f"The release file says it is version {version}, but this installer is built for "
            f"{APP_VERSION}. Please download the matching installer."
        )

    # The release script names the image by a relative path; point it at ours.
    params = _replace_filename(params, str(app_hex))
    _assert_expected_target(params)
    ok(f"Install settings read from the release file (Kadena {version}).")
    return app_hex, params, version


def _split_params(text: str) -> list[str]:
    """Split a bash array body into arguments, honouring quotes."""
    out: list[str] = []
    for token in re.findall(r'"[^"]*"|\S+', text.strip()):
        out.append(token[1:-1] if token.startswith('"') and token.endswith('"') else token)
    return out


def _replace_filename(params: list[str], path: str) -> list[str]:
    out = list(params)
    for i, value in enumerate(out):
        if value == "--fileName" and i + 1 < len(out):
            out[i + 1] = path
            return out
    return out + ["--fileName", path]


def _assert_expected_target(params: list[str]) -> None:
    """Refuse to run if the release targets a device other than the one we support."""
    for i, value in enumerate(params):
        if value == "--targetId" and i + 1 < len(params):
            declared = int(params[i + 1], 16)
            if declared != SUPPORTED_TARGET_ID:
                raise Abort(
                    f"The release file targets device 0x{declared:08x}, but this installer only "
                    f"handles the {SUPPORTED_DEVICE_NAME} (0x{SUPPORTED_TARGET_ID:08x}). Stopping."
                )
            return
    raise Abort("The release file does not say which device it is for. Stopping.")


# --------------------------------------------------------------------------------------
# Device
# --------------------------------------------------------------------------------------


DEVICE_PROBE = r"""
import sys
try:
    from ledgerblue.comm import getDongle
except Exception as exc:
    print("IMPORT_ERROR " + str(exc)); sys.exit(0)
try:
    dongle = getDongle(False)
except Exception as exc:
    print("NO_DEVICE " + type(exc).__name__ + ": " + str(exc)); sys.exit(0)
try:
    # Dashboard GET_VERSION. First four bytes of the reply are the device target id.
    reply = dongle.exchange(bytes.fromhex("E001000000"))
    print("TARGET %08x" % int.from_bytes(reply[:4], "big"))
except Exception as exc:
    print("PROBE_ERROR " + type(exc).__name__ + ": " + str(exc))
finally:
    try:
        dongle.close()
    except Exception:
        pass
"""


def probe_device(py: Path) -> tuple[str, str]:
    """Ask the connected Ledger which model it is. Returns (status, detail)."""
    result = subprocess.run(
        [str(py), "-c", DEVICE_PROBE], capture_output=True, text=True, timeout=60
    )
    line = (result.stdout or "").strip().splitlines()
    if not line:
        return "PROBE_ERROR", (result.stderr or "no output").strip()
    head, _, detail = line[-1].partition(" ")
    return head, detail


def check_device(py: Path, skip: bool) -> None:
    if skip:
        warn("Device check skipped at your request.")
        return

    status, detail = probe_device(py)

    if status == "TARGET":
        target = int(detail, 16)
        if target == SUPPORTED_TARGET_ID:
            ok(f"Found a {SUPPORTED_DEVICE_NAME}, unlocked and on the home screen.")
            return
        if target in KNOWN_UNSUPPORTED:
            name, reason = KNOWN_UNSUPPORTED[target]
            raise Abort(
                f"This is a {name}, and the Kadena app cannot be installed on it this way.\n\n"
                f"{reason}\n\n"
                "What you can do instead: wait for the Kadena app to return to Ledger Live. "
                "That is the only route for your device, and it is the route we are working on.\n"
                f"Progress: {APP_RELEASE_URL}"
            )
        raise Abort(
            f"Found a Ledger device this installer does not recognise (id 0x{target:08x}).\n"
            f"It only supports the {SUPPORTED_DEVICE_NAME}. Stopping rather than guessing."
        )

    if status == "NO_DEVICE":
        raise Abort(_no_device_help(detail))

    warn(f"Could not confirm which Ledger model is connected ({status}: {detail}).")
    warn("The installation itself will still refuse a device the app does not fit.")
    if not confirm(
        f"Continue anyway? Only do this if you are certain you have a {SUPPORTED_DEVICE_NAME}."
    ):
        raise Abort("Stopped at your request.")


def _no_device_help(detail: str) -> str:
    common = (
        "No Ledger was found. Please check all of these:\n\n"
        "  1. The Ledger is plugged in directly (not through a USB hub).\n"
        "  2. You have entered your PIN and the screen shows the app list / home screen.\n"
        "  3. Ledger Live is fully CLOSED — it holds the connection open and blocks other tools.\n"
        "  4. The cable is a data cable. Some charging cables carry power only.\n"
    )
    if platform.system() == "Linux":
        common += (
            "  5. Linux needs a permissions rule to talk to the device. Run this once:\n"
            f"       {_launch_command()} --install-udev-rules\n"
            "     then unplug and replug the Ledger.\n"
        )
    return f"{common}\nTechnical detail: {detail}"


def _launch_command() -> str:
    """How the user started this, so hints tell them something they can actually type."""
    if platform.system() == "Linux":
        wrapper = Path(sys.argv[0]).resolve().parent / "install-kadena-linux.sh"
        if wrapper.is_file():
            return "./install-kadena-linux.sh"
    return f"{Path(sys.executable).name} {Path(sys.argv[0]).name}"


def install_udev_rules() -> int:
    if platform.system() != "Linux":
        print("Permission rules are only needed on Linux. Nothing to do.")
        return 0

    print("Linux needs a rule file so ordinary programs may talk to a Ledger over USB.")
    print(f"This will write {UDEV_RULES_PATH} with:\n")
    print(UDEV_RULES_BODY)
    print("Writing to /etc requires administrator rights, so it will ask for your password.")
    if not confirm("Write this rule file now?"):
        print("Nothing changed.")
        return 1

    with tempfile.NamedTemporaryFile("w", suffix=".rules", delete=False) as tmp:
        tmp.write(UDEV_RULES_BODY)
        staged = tmp.name

    try:
        subprocess.run(["sudo", "install", "-m", "0644", staged, str(UDEV_RULES_PATH)], check=True)
        subprocess.run(["sudo", "udevadm", "control", "--reload-rules"], check=True)
        subprocess.run(["sudo", "udevadm", "trigger"], check=True)
    except FileNotFoundError:
        print("\nCould not find 'sudo'. Ask whoever administers this computer to copy the rule.")
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"\nCould not write the rule file: {exc}")
        return 1
    finally:
        os.unlink(staged)

    print("\nDone. Now unplug the Ledger and plug it back in.")
    return 0


# --------------------------------------------------------------------------------------
# Install
# --------------------------------------------------------------------------------------


def hash_in_blocks(digest: str, per_line: int = 4) -> str:
    """A 64-character hash is hard to compare against a tiny scrolling screen.

    Splitting it into blocks makes a character-level comparison something a person
    will actually finish instead of abandoning after the first few characters.
    """
    blocks = [digest[i:i + 8] for i in range(0, len(digest), 8)]
    return "\n".join(
        "  " + " ".join(blocks[i:i + per_line]) for i in range(0, len(blocks), per_line)
    )


DEVICE_SCREENS = [
    ('"Allow unknown manager?"', "approve", False),
    ("Manager public key", "see the note below", False),
    ("App name and version", f"should say Kadena, {APP_VERSION}", False),
    ("Code identifier", "NOT the one you are checking", False),
    ("Full hash", "THIS IS THE ONE THAT MATTERS", True),
    ('"Install app Kadena?"', "approve only after you have read screen 5", False),
]


def screen_list() -> str:
    """Render the device-screen walkthrough, padded on the plain text.

    Padding has to be computed from the uncoloured label — measuring a string that
    already contains escape codes silently misaligns the whole block.
    """
    width = max(len(label) for label, _, _ in DEVICE_SCREENS)
    lines = []
    for n, (label, note, emphasise) in enumerate(DEVICE_SCREENS, 1):
        pad = " " * (width - len(label))
        text, hint = (_c("1", label), _c("1", note)) if emphasise else (label, note)
        lines.append(f"  {n}. {text}{pad}  ->  {hint}")
    return "\n".join(lines)


def show_what_will_happen() -> None:
    banner(
        "READ THIS BEFORE YOU CONTINUE",
        f"""
About to install the Kadena app, version {APP_VERSION}, onto a {SUPPORTED_DEVICE_NAME}.

Your device will now show a series of screens. Step through them with the right-hand
button. THEY ARRIVE IN THIS ORDER:

{screen_list()}

{_c('1', 'The Full hash on screen 5 must read exactly:')}

{_c('1;32', hash_in_blocks(EXPECTED_DEVICE_HASH))}

Take your time. The device waits as long as you need, so read every block — not just
the beginning and the end. Photograph the screen and compare it here if that is easier.

Your Ledger's screen is the only thing in this process that cannot be lied to by a
compromised computer. If those characters differ ANYWHERE, reject on the device and
tell us: https://github.com/SmartPacts/kadena-ledger-installer/issues

Three more things worth knowing:

  - {_c('1', 'The manager public key (screen 2) is DIFFERENT every single time.')} That is
    normal and is not a warning sign: a fresh one-time key is generated for each run.
    The Full hash is the value that must never change.
  - This app is not yet distributed by Ledger, so your device will warn you that it
    is not a Ledger-reviewed app. That warning is expected and correct.
  - This does not touch your recovery phrase, your PIN, or your device firmware, and
    it cannot. Installing or removing an app never puts your funds at risk. You can
    remove the app at any time from Ledger Live's "My Ledger" screen.
""".rstrip(),
    )


def run_install(py: Path, params: list[str], workdir: Path) -> None:
    command = [str(py), "-m", "ledgerblue.loadApp", *params]
    info("Talking to your Ledger now. Watch the device screen and approve when asked.")
    info("(this usually takes 20-60 seconds)")
    print()
    result = subprocess.run(command, cwd=str(workdir))
    if result.returncode != 0:
        raise Abort(
            "The installation did not finish.\n\n"
            "The most common causes, in order:\n"
            "  - The request was declined on the device, or it timed out waiting.\n"
            "  - Ledger Live was running and holding the connection.\n"
            "  - The device locked itself partway through. Unlock it and run this again.\n"
            "  - There is not enough free space on the device. Remove an app you do not\n"
            "    use from Ledger Live's \"My Ledger\" screen, then run this again.\n\n"
            "Nothing is damaged. It is always safe to simply try again."
        )


def confirm_device_hash() -> bool:
    banner(
        "LAST STEP - AND THE ONLY ONE THAT REALLY MATTERS",
        f"""
The "Full hash" screen on your device should have read exactly:

{_c('1;32', hash_in_blocks(EXPECTED_DEVICE_HASH))}

Not the "Code identifier" screen, and not the manager public key — the Full hash.
""".rstrip(),
    )
    print(
        "\nIf you did not get a good look, answer 'no' or 'unsure' rather than guessing.\n"
        "Running this installer again simply redisplays the hash; it is harmless and takes\n"
        "about a minute. An unread hash is an unverified install."
    )
    try:
        answer = input(
            f"\n{_c('1', 'Did the hash on the device match, exactly?')} (yes / no / unsure): "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        # No usable stdin (piped, or the window was closed). Never assume "yes" —
        # an unanswered verification is an unverified install.
        print("\n\nNo answer given, so this install counts as UNVERIFIED.")
        answer = "unsure"

    if answer == "yes":
        print(
            f"\n{_c('1;32', 'Installed and verified.')} Open the Kadena app on your Ledger to use it.\n"
            "For sending transactions, note that some wallets need 'Blind signing' turned on\n"
            "in the Kadena app's own settings menu."
        )
        return True

    if answer == "no":
        banner(
            "DO NOT USE THIS INSTALLATION",
            """
Remove the app now: open Ledger Live, go to "My Ledger", and uninstall Kadena.
Do not open the app and do not send anything to an address it shows you.

Then please tell us immediately, including which computer and network you used:
  https://github.com/SmartPacts/kadena-ledger-installer/issues

Your recovery phrase and your funds were never exposed by this — an app cannot read
your recovery phrase. The risk of a wrong app is that it could show you one payment
and sign a different one, so simply do not use it until this is resolved.
""".rstrip(),
        )
        return False

    print(
        "\nNoted as unverified. Before you use this app with real funds, please verify it.\n"
        "The simplest way: run this installer again and watch the device screen carefully."
    )
    return False


# --------------------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="kadena-ledger-install",
        description=f"Install the Kadena app (v{APP_VERSION}) onto a {SUPPORTED_DEVICE_NAME}.",
    )
    parser.add_argument("--version", action="store_true", help="show version information and exit")
    parser.add_argument(
        "--install-udev-rules",
        action="store_true",
        help="Linux only: set up USB permissions so your Ledger can be reached",
    )
    parser.add_argument(
        "--installer",
        type=Path,
        metavar="FILE",
        help=f"use a {INSTALLER_ASSET} you already downloaded instead of fetching it",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="do everything except talk to the device — verifies the download only",
    )
    parser.add_argument(
        "--skip-device-check",
        action="store_true",
        help="do not identify the device first (not recommended)",
    )
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args()

    if args.version:
        print(f"kadena-ledger-install {INSTALLER_VERSION}")
        print(f"  installs Kadena app : {APP_VERSION} ({APP_RELEASE_TAG})")
        print(f"  expected device hash: {EXPECTED_DEVICE_HASH}")
        print(f"  ledgerblue          : {LEDGERBLUE_VERSION}")
        return 0

    if args.install_udev_rules:
        return install_udev_rules()

    print(_c("1", f"\nKadena Ledger app installer {INSTALLER_VERSION}"))
    print(f"Installs Kadena app {APP_VERSION} onto a {SUPPORTED_DEVICE_NAME}.")

    total = 4 if args.dry_run else 6

    step(1, total, "Checking this computer")
    check_python()
    ok(f"Python {platform.python_version()} on {platform.system()}.")
    py = ensure_venv(data_dir() / "env")

    with tempfile.TemporaryDirectory(prefix="kadena-ledger-") as tmp:
        workdir = Path(tmp)

        step(2, total, "Downloading the official Kadena app release")
        script = fetch_installer(workdir, args.installer)

        step(3, total, "Checking every byte against the published checksums")
        _, params, version = extract_payload(script, workdir)

        if args.dry_run:
            step(4, total, "Dry run complete")
            ok("The download is genuine and the install settings were read successfully.")
            info("Nothing was sent to any device. Run without --dry-run to install.")
            return 0

        step(4, total, "Finding your Ledger")
        check_device(py, args.skip_device_check)

        step(5, total, "Confirming with you")
        show_what_will_happen()
        if not args.yes and not confirm("Install the Kadena app now?"):
            print("\nNothing was installed. Nothing changed on your device.")
            return 1

        step(6, total, f"Installing Kadena {version}")
        run_install(py, params, workdir)

    return 0 if confirm_device_hash() else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Abort as abort:
        print(f"\n{_c('1;31', 'Stopped.')}\n\n{abort}\n", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nCancelled. Nothing was changed on your device.", file=sys.stderr)
        sys.exit(130)
