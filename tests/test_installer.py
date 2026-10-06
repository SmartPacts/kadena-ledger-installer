"""Tests for the parts of the installer that decide whether, and what, to send to a device.

These cover the branches that cannot be exercised without hardware: reading the device's
OS version, choosing the release built for it, refusing an OS version with no release,
refusing an unsupported device, refusing a release that targets the wrong device or OS
generation, and the byte-exact extraction of the firmware image from each release script.

Run:  python3 -m pytest tests/ -q
The verification tests need the release files. They are downloaded from the published
releases, or read from KADENA_ARTIFACTS_DIR if it is set: a folder holding
<tag>/installer_nanos_plus.sh for each pinned release (for example v1.3.3/ and v1.3.4/).
A release that can be neither downloaded nor found locally is skipped, not passed.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import kadena_ledger_install as kli  # noqa: E402

RELEASE_LIST = list(kli.RELEASES.values())
RELEASE_IDS = [r.release_tag for r in RELEASE_LIST]
OS_1_6 = kli.RELEASES[(1, 6)]
OS_1_7 = kli.RELEASES[(1, 7)]


def _reply(target: int, os_version: str = "1.7.0") -> str:
    """A dashboard GET_VERSION reply as probe_device reports it (hex after "REPLY")."""
    version = os_version.encode()
    flags = bytes(4)
    mcu = b"5.24"
    raw = (
        target.to_bytes(4, "big")
        + bytes([len(version)]) + version
        + bytes([len(flags)]) + flags
        + bytes([len(mcu)]) + mcu
    )
    return raw.hex()


# --------------------------------------------------------------------------------------
# Reading the device
# --------------------------------------------------------------------------------------


def test_parse_device_info_reads_target_and_os_version():
    target, os_version = kli.parse_device_info(bytes.fromhex(_reply(0x33100004, "1.7.0")))
    assert target == 0x33100004
    assert os_version == "1.7.0"


def test_parse_device_info_short_reply_yields_empty_version():
    # Length byte claims 5 bytes, only 2 follow. Must not read past the end or invent one.
    target, os_version = kli.parse_device_info(bytes.fromhex("33100004" + "05" + "312e"))
    assert target == 0x33100004
    assert os_version == ""
    assert kli.parse_device_info(bytes.fromhex("33100004"))[1] == ""


@pytest.mark.parametrize(
    "target_id,expected_name",
    [
        (0x33000004, "Ledger Nano X"),
        (0x33200004, "Ledger Stax"),
        (0x33300004, "Ledger Flex"),
        (0x31100004, "Ledger Nano S (first generation)"),
    ],
)
def test_refuses_known_unsupported_devices(target_id, expected_name):
    with pytest.raises(kli.Abort) as excinfo:
        kli.identify_device(("REPLY", _reply(target_id)))
    assert expected_name in str(excinfo.value)
    # Every refusal must tell the user what they CAN do, not just that they failed.
    assert "Ledger Live" in str(excinfo.value)


def test_refuses_unrecognised_device():
    with pytest.raises(kli.Abort) as excinfo:
        kli.identify_device(("REPLY", _reply(0xDEADBEEF)))
    assert "does not recognise" in str(excinfo.value)


@pytest.mark.parametrize("os_version", ["1.6.1", "1.7.0"])
def test_accepts_nano_s_plus_and_returns_its_os_version(os_version):
    assert kli.identify_device(("REPLY", _reply(kli.SUPPORTED_TARGET_ID, os_version))) == os_version


def test_no_device_message_is_actionable():
    with pytest.raises(kli.Abort) as excinfo:
        kli.identify_device(("NO_DEVICE", "No dongle found"))
    message = str(excinfo.value)
    assert "Ledger Live is fully CLOSED" in message
    assert "PIN" in message


def test_unreadable_device_stops_instead_of_guessing():
    # An app open on the device answers the dashboard command with 0x6e00.
    with pytest.raises(kli.Abort) as excinfo:
        kli.identify_device(("PROBE_ERROR", "CommException: Invalid status 6e00"))
    message = str(excinfo.value)
    assert "home screen" in message
    assert "rather than guess" in message


def test_garbled_reply_is_refused():
    with pytest.raises(kli.Abort):
        kli.identify_device(("REPLY", "not-hex"))


def test_missing_loader_library_is_reported():
    with pytest.raises(kli.Abort) as excinfo:
        kli.identify_device(("IMPORT_ERROR", "No module named ledgerblue"))
    assert "report" in str(excinfo.value)


# --------------------------------------------------------------------------------------
# Choosing the release by OS version
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "os_version,expected_tag",
    [("1.6.0", "v1.3.3"), ("1.6.1", "v1.3.3"), ("1.7.0", "v1.3.4"), ("1.7.12", "v1.3.4")],
)
def test_selects_release_by_os_major_minor(os_version, expected_tag):
    assert kli.select_release(os_version).release_tag == expected_tag


def test_every_table_entry_is_reachable_from_its_own_key():
    for key, release in kli.RELEASES.items():
        assert release.os_series == key
        assert kli.select_release(f"{key[0]}.{key[1]}.0") is release


@pytest.mark.parametrize("os_version", ["1.5.0", "1.5.9"])
def test_refuses_older_os_and_says_how_to_update(os_version):
    with pytest.raises(kli.Abort) as excinfo:
        kli.select_release(os_version)
    message = str(excinfo.value)
    assert os_version in message
    assert "1.6.x" in message and "1.7.x" in message
    assert "Ledger Live" in message


@pytest.mark.parametrize("os_version", ["1.8.0", "2.0.0"])
def test_refuses_newer_os_and_points_at_the_releases_page(os_version):
    with pytest.raises(kli.Abort) as excinfo:
        kli.select_release(os_version)
    message = str(excinfo.value)
    assert os_version in message
    assert "1.6.x" in message and "1.7.x" in message
    assert kli.INSTALLER_RELEASES_URL in message


@pytest.mark.parametrize(
    "os_version", ["", "1.7", "1.7.x", "1.7.0-rc1", " 1.7.0", "1.7.0.1", "abc", "1.٧.0"]
)
def test_refuses_malformed_os_version(os_version):
    with pytest.raises(kli.Abort) as excinfo:
        kli.select_release(os_version)
    message = str(excinfo.value)
    assert repr(os_version) in message  # names exactly what the device said
    assert "1.6.x" in message and "1.7.x" in message
    assert kli.INSTALLER_RELEASES_URL in message


# --------------------------------------------------------------------------------------
# The pins themselves
# --------------------------------------------------------------------------------------

_HEX64 = re.compile(r"[0-9a-f]{64}")


@pytest.mark.parametrize("release", RELEASE_LIST, ids=RELEASE_IDS)
def test_each_pin_is_64_lowercase_hex(release):
    for value in (release.installer_sha256, release.app_hex_sha256, release.device_hash):
        assert _HEX64.fullmatch(value), value


def test_the_two_pin_sets_differ_everywhere():
    for field in (
        "installer_sha256", "app_hex_sha256", "device_hash",
        "api_level", "app_version", "release_tag",
    ):
        assert getattr(OS_1_6, field) != getattr(OS_1_7, field), field
    assert (OS_1_6.api_level, OS_1_7.api_level) == (26, 27)


def test_release_urls_follow_the_tag():
    for release in RELEASE_LIST:
        assert release.installer_url.endswith(
            f"/releases/download/{release.release_tag}/{kli.INSTALLER_ASSET}"
        )
        assert release.release_url.endswith(f"/releases/tag/{release.release_tag}")


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


def test_assert_api_level_rejects_the_other_generation():
    with pytest.raises(kli.Abort) as excinfo:
        kli._assert_api_level(["--apiLevel", "26"], OS_1_7)
    assert "27" in str(excinfo.value)
    with pytest.raises(kli.Abort):
        kli._assert_api_level(["--apiLevel", "27"], OS_1_6)


def test_assert_api_level_rejects_missing_level():
    with pytest.raises(kli.Abort):
        kli._assert_api_level(["--targetId", "0x33100004"], OS_1_7)


def test_assert_api_level_accepts_matching_level():
    kli._assert_api_level(["--apiLevel", "26"], OS_1_6)  # must not raise
    kli._assert_api_level(["--apiLevel", "27"], OS_1_7)  # must not raise


def test_replace_filename_overwrites_relative_path():
    params = ["--fileName", "bin/app.hex", "--tlv"]
    assert kli._replace_filename(params, "/tmp/app.hex") == ["--fileName", "/tmp/app.hex", "--tlv"]


# --------------------------------------------------------------------------------------
# The verification chain, against each published release
# --------------------------------------------------------------------------------------

_SCRIPTS: dict[str, Path] = {}


def _release_script(release: kli.Release, tmp_path_factory) -> Path:
    if release.release_tag in _SCRIPTS:
        return _SCRIPTS[release.release_tag]
    artifacts = os.environ.get("KADENA_ARTIFACTS_DIR")
    if artifacts:
        local = Path(artifacts) / release.release_tag / kli.INSTALLER_ASSET
        if not local.is_file():
            pytest.skip(f"{local} not found")
        path = local
    else:
        path = tmp_path_factory.mktemp(release.release_tag) / kli.INSTALLER_ASSET
        try:
            with urllib.request.urlopen(release.installer_url, timeout=120) as response:
                path.write_bytes(response.read())
        except Exception as exc:  # pragma: no cover - network-dependent
            pytest.skip(f"{release.release_tag} not reachable: {exc}")
    _SCRIPTS[release.release_tag] = path
    return path


@pytest.fixture(params=RELEASE_LIST, ids=RELEASE_IDS)
def release_and_script(request, tmp_path_factory):
    return request.param, _release_script(request.param, tmp_path_factory)


@pytest.fixture
def all_scripts(tmp_path_factory) -> dict[str, Path]:
    return {r.release_tag: _release_script(r, tmp_path_factory) for r in RELEASE_LIST}


def test_published_release_matches_pinned_checksum(release_and_script):
    release, script = release_and_script
    assert kli.sha256_file(script) == release.installer_sha256


def test_extracted_image_matches_pinned_checksum(release_and_script):
    release, script = release_and_script
    with tempfile.TemporaryDirectory() as tmp:
        app_hex, params, version = kli.extract_payload(script, Path(tmp), release)
        assert kli.sha256_file(app_hex) == release.app_hex_sha256
        assert version == release.app_version
        assert "--targetId" in params and "0x33100004" in params
        assert params[params.index("--apiLevel") + 1] == str(release.api_level)
        # The image path handed to the loader must be the one we verified, not a relative name.
        assert params[params.index("--fileName") + 1] == str(app_hex)


def test_fetch_accepts_the_matching_local_file(release_and_script):
    release, script = release_and_script
    with tempfile.TemporaryDirectory() as tmp:
        fetched = kli.fetch_installer(release, Path(tmp) / "work", script)
        assert kli.sha256_file(fetched) == release.installer_sha256


def test_rejects_tampered_release(release_and_script):
    release, script = release_and_script
    with tempfile.TemporaryDirectory() as tmp:
        tampered = Path(tmp) / "tampered.sh"
        tampered.write_bytes(script.read_bytes() + b"\n# edited\n")
        with pytest.raises(kli.Abort) as excinfo:
            kli.fetch_installer(release, Path(tmp) / "work", tampered)
        assert "STOP" in str(excinfo.value)


def test_the_other_os_release_is_refused(all_scripts):
    # A device on OS 1.7 must never be handed the OS 1.6 build, and vice versa.
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(kli.Abort):
            kli.fetch_installer(OS_1_7, Path(tmp) / "a", all_scripts[OS_1_6.release_tag])
        with pytest.raises(kli.Abort):
            kli.fetch_installer(OS_1_6, Path(tmp) / "b", all_scripts[OS_1_7.release_tag])
        # Even past the outer checksum, the image and API level are checked per release.
        with pytest.raises(kli.Abort):
            kli.extract_payload(all_scripts[OS_1_6.release_tag], Path(tmp), OS_1_7)


def test_release_for_file_identifies_each_release(all_scripts):
    for release in RELEASE_LIST:
        assert kli.release_for_file(all_scripts[release.release_tag]) is release


def test_release_for_file_refuses_an_unknown_file(tmp_path):
    unknown = tmp_path / kli.INSTALLER_ASSET
    unknown.write_bytes(b"#!/bin/sh\necho not a release\n")
    with pytest.raises(kli.Abort) as excinfo:
        kli.release_for_file(unknown)
    assert "STOP" in str(excinfo.value)


# --------------------------------------------------------------------------------------
# --dry-run end to end, with the network and the device replaced
# --------------------------------------------------------------------------------------


@pytest.fixture
def dry_run(monkeypatch, all_scripts):
    """Run main() --dry-run with downloads served from the release files on disk."""
    downloaded: list[str] = []
    by_url = {r.installer_url: all_scripts[r.release_tag] for r in RELEASE_LIST}

    def fake_download(url: str, target: Path) -> None:
        downloaded.append(url)
        shutil.copyfile(by_url[url], target)

    monkeypatch.setattr(kli, "_download", fake_download)
    monkeypatch.setattr(kli, "ensure_venv", lambda *_a, **_k: Path("python"))

    def run(probe: tuple[str, str], *extra: str) -> int:
        monkeypatch.setattr(kli, "probe_device", lambda _py: probe)
        monkeypatch.setattr(sys, "argv", ["kadena-ledger-install", "--dry-run", *extra])
        return kli.main()

    run.downloaded = downloaded
    return run


def test_dry_run_without_a_device_verifies_every_release(dry_run, capsys):
    assert dry_run(("NO_DEVICE", "No dongle found")) == 0
    out = capsys.readouterr().out
    assert sorted(dry_run.downloaded) == sorted(r.installer_url for r in RELEASE_LIST)
    assert "No OS version was read".lower() in out.lower()
    for release in RELEASE_LIST:
        assert f"Kadena app {release.app_version}" in out
        assert release.device_hash[:8] in out


@pytest.mark.parametrize("os_version", ["1.6.1", "1.7.0"])
def test_dry_run_with_a_device_names_the_os_and_the_chosen_release(dry_run, capsys, os_version):
    chosen = kli.select_release(os_version)
    assert dry_run(("REPLY", _reply(kli.SUPPORTED_TARGET_ID, os_version))) == 0
    out = capsys.readouterr().out
    assert dry_run.downloaded == [chosen.installer_url]  # only the one it would install
    assert f"Ledger OS {os_version} -> Kadena app {chosen.app_version}" in out
    assert f"runs OS {os_version}, so it would get Kadena app {chosen.app_version}" in out
    assert chosen.device_hash[:8] in out
    other = OS_1_7 if chosen is OS_1_6 else OS_1_6
    assert other.device_hash[:8] not in out


def test_dry_run_refuses_an_unsupported_os_before_downloading(dry_run):
    with pytest.raises(kli.Abort):
        dry_run(("REPLY", _reply(kli.SUPPORTED_TARGET_ID, "1.5.0")))
    assert dry_run.downloaded == []


def test_dry_run_without_a_device_checks_a_provided_file_as_its_own_release(
    dry_run, capsys, all_scripts
):
    script = all_scripts[OS_1_7.release_tag]
    assert dry_run(("NO_DEVICE", "No dongle found"), "--installer", str(script)) == 0
    out = capsys.readouterr().out
    assert dry_run.downloaded == []
    assert OS_1_7.device_hash[:8] in out
    assert OS_1_6.device_hash[:8] not in out
