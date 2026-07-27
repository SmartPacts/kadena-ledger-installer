"""Tests for the parts of the installer that decide whether to touch a device.

These cover the branches that cannot be exercised without hardware: refusing an
unsupported device, refusing a release that targets the wrong device, and the
byte-exact extraction of the firmware image from the release script.

Run:  python3 -m pytest tests/ -q
The extraction tests need the release file; fetch it once with:
  python3 kadena_ledger_install.py --dry-run
or point KADENA_INSTALLER_ASSET at a local copy of installer_nanos_plus.sh.
"""

from __future__ import annotations

import os
import sys
import tempfile
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import kadena_ledger_install as kli  # noqa: E402


# --------------------------------------------------------------------------------------
# Device refusal — the fail-safe protecting Nano X owners from a pointless, scary attempt
# --------------------------------------------------------------------------------------


class _FakePython:
    """Stands in for the venv interpreter path; probe_device is patched out anyway."""

    def __str__(self) -> str:
        return "python"


@pytest.mark.parametrize(
    "target_id,expected_name",
    [
        (0x33000004, "Ledger Nano X"),
        (0x33200004, "Ledger Stax"),
        (0x33300004, "Ledger Flex"),
        (0x31100004, "Ledger Nano S (first generation)"),
    ],
)
def test_refuses_known_unsupported_devices(monkeypatch, target_id, expected_name):
    monkeypatch.setattr(kli, "probe_device", lambda _py: ("TARGET", f"{target_id:08x}"))
    with pytest.raises(kli.Abort) as excinfo:
        kli.check_device(_FakePython(), skip=False)
    assert expected_name in str(excinfo.value)
    # Every refusal must tell the user what they CAN do, not just that they failed.
    assert "Ledger Live" in str(excinfo.value)


def test_refuses_unrecognised_device(monkeypatch):
    monkeypatch.setattr(kli, "probe_device", lambda _py: ("TARGET", "deadbeef"))
    with pytest.raises(kli.Abort) as excinfo:
        kli.check_device(_FakePython(), skip=False)
    assert "does not recognise" in str(excinfo.value)


def test_accepts_nano_s_plus(monkeypatch):
    monkeypatch.setattr(
        kli, "probe_device", lambda _py: ("TARGET", f"{kli.SUPPORTED_TARGET_ID:08x}")
    )
    kli.check_device(_FakePython(), skip=False)  # must not raise


def test_no_device_message_is_actionable(monkeypatch):
    monkeypatch.setattr(kli, "probe_device", lambda _py: ("NO_DEVICE", "No dongle found"))
    with pytest.raises(kli.Abort) as excinfo:
        kli.check_device(_FakePython(), skip=False)
    message = str(excinfo.value)
    assert "Ledger Live is fully CLOSED" in message
    assert "PIN" in message


# --------------------------------------------------------------------------------------
# Release parsing
# --------------------------------------------------------------------------------------


def test_split_params_handles_quoted_app_name():
    body = '--targetId 0x33100004 --appName "Kadena" --appFlags 0x0 --delete --tlv'
    assert kli._split_params(body) == [
        "--targetId", "0x33100004", "--appName", "Kadena",
        "--appFlags", "0x0", "--delete", "--tlv",
    ]


def test_assert_expected_target_rejects_other_devices():
    with pytest.raises(kli.Abort):
        kli._assert_expected_target(["--targetId", "0x33000004"])  # Nano X


def test_assert_expected_target_rejects_missing_target():
    with pytest.raises(kli.Abort):
        kli._assert_expected_target(["--appName", "Kadena"])


def test_assert_expected_target_accepts_nano_s_plus():
    kli._assert_expected_target(["--targetId", "0x33100004"])  # must not raise


def test_replace_filename_overwrites_relative_path():
    params = ["--fileName", "bin/app.hex", "--tlv"]
    assert kli._replace_filename(params, "/tmp/app.hex") == ["--fileName", "/tmp/app.hex", "--tlv"]


# --------------------------------------------------------------------------------------
# The verification chain, against the real published release
# --------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def release_script(tmp_path_factory) -> Path:
    local = os.environ.get("KADENA_INSTALLER_ASSET")
    if local:
        return Path(local)
    dest = tmp_path_factory.mktemp("release") / kli.INSTALLER_ASSET
    try:
        with urllib.request.urlopen(kli.INSTALLER_ASSET_URL, timeout=120) as response:
            dest.write_bytes(response.read())
    except Exception as exc:  # pragma: no cover - network-dependent
        pytest.skip(f"release not reachable: {exc}")
    return dest


def test_published_release_matches_pinned_checksum(release_script):
    assert kli.sha256_file(release_script) == kli.INSTALLER_ASSET_SHA256


def test_extracted_image_matches_pinned_checksum(release_script):
    with tempfile.TemporaryDirectory() as tmp:
        app_hex, params, version = kli.extract_payload(release_script, Path(tmp))
        assert kli.sha256_file(app_hex) == kli.APP_HEX_SHA256
        assert version == kli.APP_VERSION
        assert "--targetId" in params and "0x33100004" in params
        # The image path handed to the loader must be the one we verified, not a relative name.
        assert params[params.index("--fileName") + 1] == str(app_hex)


def test_rejects_tampered_release(release_script):
    with tempfile.TemporaryDirectory() as tmp:
        tampered = Path(tmp) / "tampered.sh"
        tampered.write_bytes(release_script.read_bytes() + b"\n# edited\n")
        assert kli.sha256_file(tampered) != kli.INSTALLER_ASSET_SHA256
