@echo off
REM Double-click this file to install the Kadena app on a Ledger Nano S Plus.
REM
REM If Windows shows a blue "Windows protected your PC" box, click "More info"
REM and then "Run anyway". You only need to do that once.

cd /d "%~dp0"

echo.
echo   Kadena Ledger app installer
echo   ---------------------------
echo.

set PYTHON=
where py >nul 2>&1 && set PYTHON=py -3
if "%PYTHON%"=="" (
  where python >nul 2>&1 && set PYTHON=python
)

if "%PYTHON%"=="" (
  echo   This needs Python, which is not installed on this PC yet.
  echo.
  echo   The easiest way to get it, if you have Windows 10 or 11:
  echo.
  echo       1. Close this window.
  echo       2. Open the Start menu, type "Terminal", open it.
  echo       3. Paste this line and press Enter:
  echo.
  echo              winget install Python.Python.3.12
  echo.
  echo       4. When it finishes, double-click this installer again.
  echo.
  echo   Or download Python from https://www.python.org/downloads/ and make sure
  echo   you tick "Add python.exe to PATH" on the first screen of the installer.
  echo.
  pause
  exit /b 1
)

%PYTHON% "kadena_ledger_install.py" %*
set STATUS=%ERRORLEVEL%

echo.
if "%STATUS%"=="0" (
  echo   Finished. You can close this window.
) else (
  echo   Finished with problems ^(code %STATUS%^). The messages above explain why.
  echo   If you need help, open an issue and paste what you see above:
  echo   https://github.com/SmartPacts/kadena-ledger-installer/issues
)
pause
exit /b %STATUS%
