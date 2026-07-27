#!/usr/bin/env python3
"""Build the three downloadable zips for a release, plus their checksums.

    python3 scripts/build_release.py

Each zip contains the installer program, the wrapper for that operating system, and the
README. The executable bit is set inside the archive so the macOS and Linux wrappers are
runnable straight after unzipping.
"""

from __future__ import annotations

import hashlib
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

# Only the Linux bundle is released. The macOS and Windows wrappers exist and are
# lint-clean, but no one has run them against a real Ledger, so publishing them would
# promise something we have not watched work. Pass --all to build them anyway for
# testing.
BUNDLES = {
    "Kadena-Ledger-Installer-Linux": "install-kadena-linux.sh",
}
UNRELEASED_BUNDLES = {
    "Kadena-Ledger-Installer-macOS": "Install Kadena on Ledger.command",
    "Kadena-Ledger-Installer-Windows": "Install Kadena on Ledger.bat",
}

EXECUTABLE = 0o755
REGULAR = 0o644


def add(archive: zipfile.ZipFile, source: Path, arcname: str, mode: int) -> None:
    info = zipfile.ZipInfo(arcname)
    info.external_attr = (stat.S_IFREG | mode) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, source.read_bytes())


def main() -> int:
    version = subprocess.run(
        [sys.executable, str(ROOT / "kadena_ledger_install.py"), "--version"],
        capture_output=True, text=True, check=True,
    ).stdout.split()[1]

    bundles = dict(BUNDLES)
    if "--all" in sys.argv:
        bundles.update(UNRELEASED_BUNDLES)
        print("--all: including UNTESTED macOS/Windows bundles (do not publish these)")

    print(f"Building kadena-ledger-installer {version}")
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    for bundle, wrapper in bundles.items():
        path = DIST / f"{bundle}.zip"
        with zipfile.ZipFile(path, "w") as archive:
            add(archive, ROOT / "kadena_ledger_install.py",
                f"{bundle}/kadena_ledger_install.py", REGULAR)
            add(archive, ROOT / "bin" / wrapper, f"{bundle}/{wrapper}",
                EXECUTABLE if not wrapper.endswith(".bat") else REGULAR)
            add(archive, ROOT / "README.md", f"{bundle}/README.md", REGULAR)
        print(f"  built {path.name}")

    sums = DIST / "SHA256SUMS.txt"
    lines = []
    for zip_path in sorted(DIST.glob("*.zip")):
        digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {zip_path.name}")
    sums.write_text("\n".join(lines) + "\n")

    print(f"\nWrote {DIST}:")
    print(sums.read_text())
    print("Publish with:")
    print(f"  gh release create v{version} dist/*.zip dist/SHA256SUMS.txt \\")
    print("     -R SmartPacts/kadena-ledger-installer --notes-file CHANGELOG.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
