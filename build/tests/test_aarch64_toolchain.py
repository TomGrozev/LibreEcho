#!/usr/bin/env python3
"""Contract tests for the pinned aarch64 kernel cross-toolchain lock.

The heavy materializer/verifier behaviour is covered by
``build/tests/test_armhf_toolchain.py``; these tests pin the aarch64 lock and
prove the two families cannot accept each other's lock or prefix contract.
"""
from __future__ import annotations

import hashlib
import io
import os
import sys
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[2]
CI = ROOT / "build/ci"
LOCK_PATH = ROOT / "build/inputs/aarch64-cross-toolchain.lock.json"
ARMHF_LOCK = ROOT / "build/inputs/armhf-cross-toolchain.lock.json"
REAL_ARCHIVES = os.environ.get("AARCH64_TOOLCHAIN_ARCHIVE_DIR")


def _load(name: str, filename: str):
    sys.path.insert(0, str(CI))
    spec = spec_from_file_location(name, CI / filename)
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


armhf = _load("armhf_toolchain", "armhf_toolchain.py")
aarch64 = _load("aarch64_toolchain", "aarch64_toolchain.py")


class FetchStreamingTests(unittest.TestCase):
    """``fetch`` streams into a sibling ``.part`` and publishes by rename."""

    class _Response:
        def __init__(self, body):
            self._stream = io.BytesIO(body)
            self.reads = []

        def read(self, size):
            self.reads.append(size)
            return self._stream.read(size)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _lock(self, body):
        return {"archives": [{
            "filename": "demo.deb",
            "url": "https://invalid.invalid/demo.deb",
            "size": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        }]}

    def test_streams_bounded_chunks_and_replaces_atomically(self):
        body = b"payload" * (armhf.DOWNLOAD_CHUNK // 7 + 1)
        response = self._Response(body)
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(armhf, "load_lock", return_value=self._lock(body)), \
                mock.patch.object(armhf, "verify_archives", return_value=[]), \
                mock.patch.object(armhf.urllib.request, "urlopen", return_value=response):
            self.assertEqual(armhf.fetch("unused", tmp, family=aarch64.AARCH64), [])
            destination = Path(tmp) / "demo.deb"
            self.assertEqual(destination.read_bytes(), body)
            self.assertFalse((Path(tmp) / "demo.deb.part").exists())
        self.assertTrue(response.reads)
        self.assertTrue(all(size <= armhf.DOWNLOAD_CHUNK for size in response.reads))

    def test_rejected_body_leaves_no_destination_or_part(self):
        body = b"payload" * (armhf.DOWNLOAD_CHUNK // 7 + 1)
        for label, served in (("short", body[:-1]),
                              ("corrupt", b"x" + body[1:])):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp, \
                    mock.patch.object(armhf, "load_lock", return_value=self._lock(body)), \
                    mock.patch.object(armhf, "verify_archives", return_value=[]), \
                    mock.patch.object(armhf.urllib.request, "urlopen",
                                      return_value=self._Response(served)):
                with self.assertRaises(armhf.ToolchainError):
                    armhf.fetch("unused", tmp, family=aarch64.AARCH64, attempts=1)
                self.assertEqual(list(Path(tmp).iterdir()), [])


class Aarch64ToolchainLockTests(unittest.TestCase):
    def test_lock_is_complete_and_pinned(self):
        lock = armhf.load_lock(LOCK_PATH, family=aarch64.AARCH64)
        self.assertEqual(lock["schema"], "libreecho-aarch64-cross-toolchain-lock/1")
        self.assertEqual(lock["target"], "aarch64-linux-gnu-glibc-dynamic")
        self.assertGreaterEqual(len(lock["archives"]), 20)
        names = {record["name"] for record in lock["archives"]}
        for required in ("gcc-13-aarch64-linux-gnu", "binutils-aarch64-linux-gnu",
                         "libc6-dev-arm64-cross", "linux-libc-dev-arm64-cross",
                         "libgcc-13-dev-arm64-cross"):
            self.assertIn(required, names)

    def test_families_reject_each_others_locks(self):
        with self.assertRaises(armhf.ToolchainError):
            armhf.load_lock(LOCK_PATH)
        with self.assertRaises(armhf.ToolchainError):
            armhf.load_lock(ARMHF_LOCK, family=aarch64.AARCH64)

    def test_env_contract_is_aarch64(self):
        env = armhf.prefix_env("/prefix", family=aarch64.AARCH64)
        self.assertEqual(env["CROSS_PREFIX"], "/prefix/usr/bin/aarch64-linux-gnu-")
        self.assertEqual(env["LD_LIBRARY_PATH"],
                         "/prefix/usr/lib/x86_64-linux-gnu")
        armhf_env = armhf.prefix_env("/prefix")
        self.assertEqual(armhf_env["CROSS_PREFIX"],
                         "/prefix/usr/bin/arm-linux-gnueabihf-")

    @unittest.skipUnless(REAL_ARCHIVES, "set AARCH64_TOOLCHAIN_ARCHIVE_DIR for a real run")
    def test_real_archives_stage_and_verify(self):
        with self.subTest(archives=REAL_ARCHIVES):
            prefix = Path(REAL_ARCHIVES).parent / "aarch64-prefix-for-test"
            self.assertFalse(prefix.exists(), prefix)
            try:
                armhf.stage(LOCK_PATH, REAL_ARCHIVES, prefix, family=aarch64.AARCH64)
                result = armhf.verify(LOCK_PATH, REAL_ARCHIVES, prefix,
                                     family=aarch64.AARCH64)
                self.assertEqual(result["archives"], 33)
                self.assertTrue((prefix / ".libreecho-aarch64-toolchain-receipt.json").is_file())
            finally:
                import shutil
                shutil.rmtree(prefix, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
