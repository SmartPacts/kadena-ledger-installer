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
from dataclasses import dataclass
from pathlib import Path

# --------------------------------------------------------------------------------------
# Pinned releases. Everything this program installs is fixed here, at this version.
#
# Which release fits is decided by the device's OS, not by us: Ledger's OS refuses an app
# built for a different API level. OS 1.6.x refuses apps built for API 27, and OS 1.7.x
# refuses apps built for API 26. So there is one pinned release per supported OS series,
# and the device's own OS version picks between them. An OS series not listed here is
# refused, never guessed at.
#
# Values come from the SHA256SUMS.txt published with each app release.
# A new Kadena app release means a new release of THIS installer, with new pins.
# --------------------------------------------------------------------------------------

INSTALLER_VERSION = "1.1.0"

APP_REPO = "SmartPacts/app-kadena"
APP_REPO_URL = f"https://github.com/{APP_REPO}"
INSTALLER_RELEASES_URL = "https://github.com/SmartPacts/kadena-ledger-installer/releases"

# The official installer script published with each release. We do not reimplement it —
# we verify it, read the install parameters and firmware image straight out of it, and
# run exactly those. That way our install can never drift from the one tested on hardware.
INSTALLER_ASSET = "installer_nanos_plus.sh"


@dataclass(frozen=True)
class Release:
    os_series: tuple[int, int]   # Nano S Plus OS major.minor this release is built for
    api_level: int               # the API level that OS series accepts
    app_version: str
    release_tag: str
    installer_sha256: str        # SHA-256 of installer_nanos_plus.sh
    app_hex_sha256: str          # SHA-256 of the firmware image extracted from it
    device_hash: str             # what the Ledger shows as "Full hash". THE check that matters.

    @property
    def os_label(self) -> str:
        return f"{self.os_series[0]}.{self.os_series[1]}.x"

    @property
    def release_url(self) -> str:
        return f"{APP_REPO_URL}/releases/tag/{self.release_tag}"

    @property
    def installer_url(self) -> str:
        return f"{APP_REPO_URL}/releases/download/{self.release_tag}/{INSTALLER_ASSET}"


RELEASES: dict[tuple[int, int], Release] = {
    (1, 6): Release(
        os_series=(1, 6),
        api_level=26,
        app_version="1.3.3",
        release_tag="v1.3.3",
        installer_sha256="08efa6c91eb517fec9d84bdbd79963715c176629451bcd7c687e03f0d3d6930e",
        app_hex_sha256="63e492e9c8cb16776f1b22e1a17d7356e57b54cd32e97e501a488ab158766236",
        device_hash="5de2186976638313a881faabe09bbf462df9ef8c5fae9451fa22b1a99d0efed4",
    ),
    (1, 7): Release(
        os_series=(1, 7),
        api_level=27,
        app_version="1.3.4",
        release_tag="v1.3.4",
        installer_sha256="4bdae2860d578ace031941bbfba613602ca19a365a9c4bab50e556c126a4bee9",
        app_hex_sha256="d18f6bc0e7c9e56d6124d14866decf6c572b438f47033e3377240acb7eb2cffd",
        device_hash="03b75bacb5f651c27c27adcc4be525c4bc9f554797a39555ee7dbdc2f69d9d85",
    ),
}

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


def _download(url: str, target: Path) -> None:
    with urllib.request.urlopen(url, timeout=120) as response:
        target.write_bytes(response.read())


def fetch_installer(release: Release, dest: Path, local: Path | None) -> Path:
    """Get the official release script, then prove it is the exact expected file."""
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / INSTALLER_ASSET

    if local is not None:
        if not local.is_file():
            raise Abort(f"The file you passed with --installer does not exist: {local}")
        shutil.copyfile(local, target)
        info(f"Using the local file you provided: {local}")
    else:
        info(f"Downloading the official Kadena app {release.app_version} release...")
        info(f"from {release.installer_url}")
        try:
            _download(release.installer_url, target)
        except urllib.error.URLError as exc:
            raise Abort(
                "Could not download the release. Check your internet connection.\n"
                f"You can also download it yourself from:\n  {release.release_url}\n"
                f"then re-run this with:  --installer /path/to/{INSTALLER_ASSET}\n"
                f"\nOriginal error: {exc}"
            ) from exc

    actual = sha256_file(target)
    if actual != release.installer_sha256:
        raise Abort(
            f"STOP — the release file is not the Kadena app {release.app_version} release "
            "it should be.\n\n"
            f"  expected: {release.installer_sha256}\n"
            f"  actually: {actual}\n\n"
            "Nothing has been sent to your Ledger and nothing will be. Do not install this file.\n"
            "This means either the download was corrupted, the file is a different release,\n"
            "or the file was tampered with. Try again on a different network; if it happens\n"
            "again, please report it at\n"
            "https://github.com/SmartPacts/kadena-ledger-installer/issues"
        )
    ok(f"Release file checksum matches the published value ({actual[:16]}...).")
    return target


def extract_payload(
    script: Path, dest: Path, release: Release
) -> tuple[Path, list[str], str]:
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
    if actual != release.app_hex_sha256:
        raise Abort(
            "STOP — the app image inside the release file is not what it should be.\n\n"
            f"  expected: {release.app_hex_sha256}\n"
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
    if version != release.app_version:
        raise Abort(
            f"The release file says it is version {version}, but this installer expects "
            f"{release.app_version} for Ledger OS {release.os_label}. Stopping."
        )

    # The release script names the image by a relative path; point it at ours.
    params = _replace_filename(params, str(app_hex))
    _assert_expected_target(params)
    _assert_api_level(params, release)
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


def _assert_api_level(params: list[str], release: Release) -> None:
    """Refuse a release built for a different OS generation than the one it was chosen for.

    This is the property the whole OS-to-release table exists for: the device refuses an
    app whose API level its OS does not accept. Checking it here catches a wrong table
    entry before the user is walked through an install the device will reject.
    """
    for i, value in enumerate(params):
        if value == "--apiLevel" and i + 1 < len(params):
            declared = params[i + 1]
            if declared != str(release.api_level):
                raise Abort(
                    f"The release file is built for API level {declared}, but Ledger OS "
                    f"{release.os_label} needs API level {release.api_level}. Stopping."
                )
            return
    raise Abort("The release file does not say which Ledger OS it is built for. Stopping.")


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
    # Dashboard GET_VERSION. Read-only. The reply is parsed by the caller.
    reply = dongle.exchange(bytes.fromhex("E001000000"))
    print("REPLY " + bytes(reply).hex())
except Exception as exc:
    print("PROBE_ERROR " + type(exc).__name__ + ": " + str(exc))
finally:
    try:
        dongle.close()
    except Exception:
        pass
"""


def probe_device(py: Path) -> tuple[str, str]:
    """Ask the connected Ledger what it is. Returns (status, detail). Read-only."""
    result = subprocess.run(
        [str(py), "-c", DEVICE_PROBE], capture_output=True, text=True, timeout=60
    )
    line = (result.stdout or "").strip().splitlines()
    if not line:
        return "PROBE_ERROR", (result.stderr or "no output").strip()
    head, _, detail = line[-1].partition(" ")
    return head, detail


def parse_device_info(reply: bytes) -> tuple[int, str]:
    """Split the dashboard GET_VERSION reply into (target id, OS version).

    Layout: 4 bytes target id, then the secure element (OS) version as a
    length-prefixed string, then length-prefixed flags and MCU version, which we do not
    need. A reply too short to hold the version yields an empty version, which
    select_release refuses.
    """
    target = int.from_bytes(reply[:4], "big")
    if len(reply) < 5 or len(reply) < 5 + reply[4]:
        return target, ""
    return target, reply[5:5 + reply[4]].decode("utf-8", errors="replace")


def identify_device(probe: tuple[str, str]) -> str:
    """From a probe_device result, make sure a Nano S Plus is connected and return its OS
    version. Refuse anything else."""
    status, detail = probe

    if status == "NO_DEVICE":
        raise Abort(_no_device_help(detail))

    if status == "IMPORT_ERROR":
        raise Abort(f"Ledger's loader library could not be loaded ({detail}). Please report this.")

    if status != "REPLY":
        raise Abort(
            f"Found something, but could not read your Ledger ({status}: {detail}).\n\n"
            "The usual cause is an app open on the device. Go back to the home screen (the\n"
            "one that scrolls through your apps), make sure Ledger Live is fully closed, and\n"
            "run this again.\n\n"
            "This installer has to read your Ledger's OS version to choose the right app\n"
            "release, so it stops here rather than guess."
        )

    try:
        target, os_version = parse_device_info(bytes.fromhex(detail))
    except ValueError:
        raise Abort(f"Your Ledger sent a reply this installer cannot read ({detail!r}). Stopping.")

    if target in KNOWN_UNSUPPORTED:
        name, reason = KNOWN_UNSUPPORTED[target]
        raise Abort(
            f"This is a {name}, and the Kadena app cannot be installed on it this way.\n\n"
            f"{reason}\n\n"
            "What you can do instead: wait for the Kadena app to return to Ledger Live. "
            "That is the only route for your device, and it is the route we are working on.\n"
            f"Progress: {APP_REPO_URL}"
        )
    if target != SUPPORTED_TARGET_ID:
        raise Abort(
            f"Found a Ledger device this installer does not recognise (id 0x{target:08x}).\n"
            f"It only supports the {SUPPORTED_DEVICE_NAME}. Stopping rather than guessing."
        )

    ok(f"Found a {SUPPORTED_DEVICE_NAME}, unlocked and on the home screen.")
    ok(f"It runs Ledger OS {os_version or '(not reported)'}.")
    return os_version


# --------------------------------------------------------------------------------------
# Choosing the release. The device's OS decides; an OS version not in the table is
# refused, because the wrong guess is an install the device rejects at the last step.
# --------------------------------------------------------------------------------------

_OS_VERSION = re.compile(r"([0-9]+)\.([0-9]+)\.([0-9]+)")  # ASCII only: \d also matches other scripts


def _supported_os_text() -> str:
    return "\n".join(
        f"  - Ledger OS {r.os_label}  ->  Kadena app {r.app_version}" for r in RELEASES.values()
    )


def select_release(os_version: str) -> Release:
    """The release built for this OS version, or a plain-language refusal."""
    match = _OS_VERSION.fullmatch(os_version)
    if match is None:
        raise Abort(
            f"Your Ledger reported its OS version as {os_version!r}, which this installer\n"
            "cannot read, so it cannot tell which Kadena app release fits it.\n\n"
            f"This installer supports the {SUPPORTED_DEVICE_NAME} on:\n{_supported_os_text()}\n\n"
            "It will not guess. Please check for a newer version of this installer:\n"
            f"  {INSTALLER_RELEASES_URL}"
        )

    series = (int(match.group(1)), int(match.group(2)))
    release = RELEASES.get(series)
    if release is not None:
        return release

    if series < min(RELEASES):
        what_to_do = (
            "Your Ledger's OS is older than any this installer supports. Update it in\n"
            "Ledger Live (open \"My Ledger\"), then run this again."
        )
    else:
        what_to_do = (
            "Your Ledger's OS is newer than this installer knows about. Please check for a\n"
            f"newer version of this installer:\n  {INSTALLER_RELEASES_URL}"
        )
    raise Abort(
        f"Your Ledger runs OS version {os_version}, and this installer has no Kadena app\n"
        "release for it.\n\n"
        f"It supports the {SUPPORTED_DEVICE_NAME} on:\n{_supported_os_text()}\n\n"
        "It will not guess: the device refuses an app built for a different OS version.\n\n"
        f"{what_to_do}"
    )


def release_for_file(path: Path) -> Release:
    """Which pinned release a local release script is, by its checksum. Used only when no
    device was read, so the file itself has to say which release it claims to be."""
    if not path.is_file():
        raise Abort(f"The file you passed with --installer does not exist: {path}")
    actual = sha256_file(path)
    for release in RELEASES.values():
        if actual == release.installer_sha256:
            return release
    expected = "\n".join(
        f"  {r.release_tag}: {r.installer_sha256}" for r in RELEASES.values()
    )
    raise Abort(
        "STOP — the file you passed with --installer is not any release this installer "
        f"knows.\n\n  actually: {actual}\n\nExpected one of:\n{expected}\n\n"
        "Do not install this file."
    )


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


SCREEN_FULL_HASH = "Full hash"
SCREEN_CODE_ID = "Code identifier"


def screen_guidance(release: Release) -> str:
    """Explain which screen to read WITHOUT asserting a position in the sequence.

    An earlier version numbered the screens and told people to look at the fifth. That
    order was never verified, and observation suggested it was wrong -- which would send
    someone to the wrong screen for the one check that matters. Firmware is free to
    reorder them too. Naming the screen is reliable; counting to it is not.
    """
    return "\n".join(
        [
            "  - " + _c("1", SCREEN_FULL_HASH) + "  <- " + _c("1", "THIS IS THE ONE THAT MATTERS"),
            "  - " + SCREEN_CODE_ID + "  <- a DIFFERENT value; not the one you are checking",
            "  - Manager public key  <- different on every run; not a warning sign",
            "  - App name and version  <- should say Kadena, " + release.app_version,
        ]
    )


def show_what_will_happen(release: Release, os_version: str) -> None:
    banner(
        "READ THIS BEFORE YOU CONTINUE",
        f"""
About to install the Kadena app, version {release.app_version}, onto a {SUPPORTED_DEVICE_NAME}.
This is the release built for Ledger OS {release.os_label}; your Ledger runs {os_version}.

Your device will now show several screens. Step through them with the right-hand
button and READ them -- do not click past them. Among them:

{screen_guidance(release)}

Approve the installation only after you have read the "Full hash" screen.

{_c('1', 'The "Full hash" screen must read exactly:')}

{_c('1;32', hash_in_blocks(release.device_hash))}

Take your time. The device waits as long as you need, so read every block — not just
the beginning and the end. Photograph the screen and compare it here if that is easier.

Your Ledger's screen is the only thing in this process that cannot be lied to by a
compromised computer. If those characters differ ANYWHERE, reject on the device and
tell us: https://github.com/SmartPacts/kadena-ledger-installer/issues

Three more things worth knowing:

  - {_c('1', 'The manager public key is DIFFERENT every single time.')} That is
    normal and is not a warning sign: a fresh one-time key is generated for each run.
    The Full hash is the value that must match.
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


def confirm_device_hash(release: Release) -> bool:
    banner(
        "LAST STEP - AND THE ONLY ONE THAT REALLY MATTERS",
        f"""
The "Full hash" screen on your device should have read exactly:

{_c('1;32', hash_in_blocks(release.device_hash))}

(Kadena app {release.app_version}.) Not the "Code identifier" screen, and not the manager public key — the "Full hash".
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
        description=(
            f"Install the Kadena app onto a {SUPPORTED_DEVICE_NAME}. The app release is "
            "chosen by the OS version your Ledger reports."
        ),
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
        help=(
            "install nothing: read which OS a connected Ledger runs and verify the release "
            "chosen for it, or with no Ledger connected verify every supported release"
        ),
    )
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args()

    if args.version:
        print(f"kadena-ledger-install {INSTALLER_VERSION}")
        for release in RELEASES.values():
            print(
                f"  Ledger OS {release.os_label}: Kadena app {release.app_version} "
                f"({release.release_tag}), expected device hash {release.device_hash}"
            )
        print(f"  ledgerblue {LEDGERBLUE_VERSION}")
        return 0

    if args.install_udev_rules:
        return install_udev_rules()

    print(_c("1", f"\nKadena Ledger app installer {INSTALLER_VERSION}"))
    print(f"Installs the Kadena app onto a {SUPPORTED_DEVICE_NAME}, choosing the release")
    print("built for the OS version your Ledger runs.")

    total = 5 if args.dry_run else 6

    step(1, total, "Checking this computer")
    check_python()
    ok(f"Python {platform.python_version()} on {platform.system()}.")
    py = ensure_venv(data_dir() / "env")

    step(2, total, "Finding your Ledger")
    os_version: str | None = None
    probe = probe_device(py)
    if args.dry_run and probe[0] in ("NO_DEVICE", "IMPORT_ERROR"):
        # A dry run without a device still has something useful to prove: that every
        # pinned release is still exactly what was published.
        if args.installer is not None:
            releases = [release_for_file(args.installer)]
            info(f"No Ledger found. Checking the file you provided, which is "
                 f"{releases[0].release_tag}.")
        else:
            releases = list(RELEASES.values())
            info("No Ledger found, so no OS version was read. Checking every release this")
            info("installer supports:")
            for release in releases:
                info(f"  Ledger OS {release.os_label} -> Kadena app {release.app_version}")
    else:
        os_version = identify_device(probe)
        release = select_release(os_version)
        releases = [release]
        ok(f"Ledger OS {os_version} -> Kadena app {release.app_version} "
           f"(the release built for OS {release.os_label}).")

    with tempfile.TemporaryDirectory(prefix="kadena-ledger-") as tmp:
        workdir = Path(tmp)

        step(3, total, "Downloading the official Kadena app release")
        scripts = [
            fetch_installer(release, workdir / release.release_tag, args.installer)
            for release in releases
        ]

        step(4, total, "Checking every byte against the published checksums")
        payloads = [
            extract_payload(script, script.parent, release)
            for script, release in zip(scripts, releases)
        ]

        if args.dry_run:
            step(5, total, "Dry run complete")
            ok("The download is genuine and the install settings were read successfully.")
            if os_version is not None:
                info(f"Your Ledger runs OS {os_version}, so it would get Kadena app "
                     f"{releases[0].app_version}.")
            for release in releases:
                info(f"Kadena app {release.app_version} (for Ledger OS {release.os_label}) "
                     "shows this Full hash:")
                for line in hash_in_blocks(release.device_hash).splitlines():
                    info(line)
            info("Nothing was sent to any device. Run without --dry-run to install.")
            return 0

        release = releases[0]
        _, params, version = payloads[0]

        step(5, total, "Confirming with you")
        show_what_will_happen(release, os_version or "")
        if not args.yes and not confirm("Install the Kadena app now?"):
            print("\nNothing was installed. Nothing changed on your device.")
            return 1

        step(6, total, f"Installing Kadena {version}")
        run_install(py, params, workdir / release.release_tag)

    return 0 if confirm_device_hash(release) else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Abort as abort:
        print(f"\n{_c('1;31', 'Stopped.')}\n\n{abort}\n", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nCancelled. Nothing was changed on your device.", file=sys.stderr)
        sys.exit(130)
