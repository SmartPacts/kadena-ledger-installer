#!/usr/bin/env bash
# Installs the Kadena app on a Ledger Nano S Plus.
#
#   chmod +x install-kadena-linux.sh
#   ./install-kadena-linux.sh
#
# If your Ledger is not found, run this once to set up USB permissions:
#   ./install-kadena-linux.sh --install-udev-rules

set -uo pipefail
cd "$(dirname "$0")" || exit 1

echo
echo "  Kadena Ledger app installer"
echo "  ---------------------------"
echo

if ! command -v python3 >/dev/null 2>&1; then
  cat <<'EOF'
  This needs Python 3, which is not installed yet.

  Debian / Ubuntu / Mint:   sudo apt install python3 python3-venv
  Fedora:                   sudo dnf install python3
  Arch:                     sudo pacman -S python

  Then run this again.
EOF
  exit 1
fi

if ! python3 -c "import venv" >/dev/null 2>&1; then
  cat <<'EOF'
  Python 3 is installed but is missing the "venv" component, which this needs
  in order to keep its files separate from your system.

  Debian / Ubuntu / Mint:   sudo apt install python3-venv

  Then run this again.
EOF
  exit 1
fi

exec python3 "./kadena_ledger_install.py" "$@"
