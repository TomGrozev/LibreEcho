#!/usr/bin/env python3
"""Tests for the EFR32 radio-firmware publication gate."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


radio_firmware = load_module("radio_firmware", ROOT / "tools/radio_firmware.py")


class RadioFirmwareGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, name: str, payload: bytes) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def test_gbl_suffix_is_refused(self) -> None:
        self.write("bundle/lidar-ot-rcp.gbl", b"not really a gbl")
        findings = radio_firmware.check([self.root])
        self.assertEqual(len(findings), 1)
        self.assertIn(".gbl", findings[0])

    def test_gbl_magic_is_refused_without_suffix(self) -> None:
        self.write("bundle/payload", radio_firmware.GBL_MAGIC + b"\x00" * 64)
        findings = radio_firmware.check([self.root])
        self.assertEqual(len(findings), 1)
        self.assertIn("Gecko GBL magic", findings[0])

    def test_radio_firmware_name_with_binary_suffix_is_refused(self) -> None:
        self.write("bundle/xncp-fw.bin", b"\x00" * 16)
        findings = radio_firmware.check([self.root])
        self.assertEqual(len(findings), 1)
        self.assertIn("firmware name", findings[0])

    def test_source_and_ordinary_files_pass(self) -> None:
        self.write("tools/efr32-flash.c", b"int main(void) { return 0; }\n")
        self.write("image/boot.img", b"ANDROID!" + b"\x00" * 64)
        self.write("docs/thread.gbl.md", b"documentation\n")
        self.assertEqual(radio_firmware.check([self.root]), [])

    def test_ota_public_key_hex_is_not_firmware(self) -> None:
        self.write(
            "libreecho-lidar-v0.1.0-ota-public-key.hex",
            b"".join(b"%02x" % index for index in range(32)),
        )
        self.assertEqual(radio_firmware.check([self.root]), [])

    def test_textual_firmware_named_after_the_radio_is_refused(self) -> None:
        self.write("bundle/lidar-ot-rcp.hex", b":00000001FF\n")
        findings = radio_firmware.check([self.root])
        self.assertEqual(len(findings), 1)
        self.assertIn("firmware name", findings[0])

    def test_cli_exit_status(self) -> None:
        blocked = self.root / "blocked"
        clean = self.root / "clean"
        blocked.mkdir()
        clean.mkdir()
        (blocked / "payload.gbl").write_bytes(b"x")
        (clean / "notes.txt").write_text("release notes\n")
        with mock.patch.object(sys, "argv", ["radio_firmware.py", str(blocked)]):
            with mock.patch("sys.stderr"):
                self.assertEqual(radio_firmware.main(), 1)
        with mock.patch.object(sys, "argv", ["radio_firmware.py", str(clean)]):
            with mock.patch("sys.stdout"):
                self.assertEqual(radio_firmware.main(), 0)


if __name__ == "__main__":
    unittest.main()
