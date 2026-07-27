#!/bin/bash
# Double-click this file to install the Kadena app on a Ledger Nano S Plus.
#
# If macOS refuses to open it ("unidentified developer"), right-click the file,
# choose Open, then click Open again in the dialog. You only need to do that once.

cd "$(dirname "$0")" || exit 1

echo
echo "  Kadena Ledger app installer"
echo "  ---------------------------"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "  This needs Python, which is not installed on this Mac yet."
  echo
  echo "  macOS can install it for you: a window should appear asking to install"
  echo "  the developer command line tools. Click Install, wait for it to finish,"
  echo "  then double-click this file again."
  echo
  # Triggers the Command Line Tools prompt when python3 is absent.
  python3 --version >/dev/null 2>&1
  echo "  Press Return to close this window."
  read -r _
  exit 1
fi

python3 "./kadena_ledger_install.py" "$@"
status=$?

echo
if [ $status -eq 0 ]; then
  echo "  Finished. You can close this window."
else
  echo "  Finished with problems (code $status). The messages above explain why."
  echo "  If you need help, open an issue and paste what you see above:"
  echo "  https://github.com/SmartPacts/kadena-ledger-installer/issues"
fi
echo "  Press Return to close this window."
read -r _
exit $status
