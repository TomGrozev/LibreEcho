#!/usr/bin/env python3
"""Refuse to publish an image, bundle or OTA carrying EFR32 radio firmware.

The Thread RCP and the stock Zigbee NCP both link Silicon Labs code under the
MSLA.  They are owner-local payloads uploaded through the EFR32 bootloader, so
no published artifact may contain them.

A Gecko GBL/EBL container is refused by suffix or tag magic whatever it is
called.  A textual firmware format (.hex, .s37, .srec) is refused only when the
file name matches the radio firmware name, because releases also publish a
`<prefix>-ota-public-key.hex`, which is a public key, not firmware.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

GBL_MAGIC = b"\xeb\x17\xa6\x03"
# Gecko bootloader containers: binary by definition, so the suffix alone is proof.
GBL_SUFFIXES = {".gbl", ".ebl"}
RADIO_NAME = re.compile(
    r"(?:^|[-_.])(?:efr32|xncp-fw|zb_mux_rcp|lidar-ot-rcp|ot-rcp)(?:$|[-_.])",
    re.IGNORECASE,
)
# Name-gated extensions.  Textual formats carry other payloads too (the OTA
# public key ships as .hex), and a shell script or C file named after the radio
# is source, not a GBL, so only the name decides here.
NAME_GATED_SUFFIXES = {".s37", ".srec", ".hex", ".bin", ".img", ".fw"}


def iter_files(paths):
    """Yield the regular files among ``paths``, walking any directories."""
    for path in paths:
        path = Path(path)
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and not child.is_symlink():
                    yield child
        elif path.is_file() and not path.is_symlink():
            yield path


def violation(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in GBL_SUFFIXES:
        return f"{path}: Gecko GBL/EBL firmware suffix {path.suffix}"
    if RADIO_NAME.search(path.name) and suffix in NAME_GATED_SUFFIXES:
        return f"{path}: EFR32/OpenThread firmware name"
    try:
        with path.open("rb") as handle:
            head = handle.read(4)
    except OSError as error:
        return f"{path}: cannot inspect: {error}"
    if head == GBL_MAGIC:
        return f"{path}: Gecko GBL magic {GBL_MAGIC.hex()}"
    return None


def check(paths) -> list[str]:
    findings = []
    for path in iter_files(paths):
        finding = violation(path)
        if finding is not None:
            findings.append(finding)
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", default=["."])
    args = parser.parse_args()
    findings = check(args.paths)
    for finding in findings:
        print(f"ERROR: {finding}", file=sys.stderr)
    if findings:
        print(f"radio_firmware_gate=failed findings={len(findings)}", file=sys.stderr)
        return 1
    print("radio_firmware_gate=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
