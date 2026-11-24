#!/usr/bin/env python3
"""AArch64 kernel cross-toolchain lock CLI.

The authenticated materializer/verifier lives in ``armhf_toolchain.py``; this
entry point binds the same contract to
``build/inputs/aarch64-cross-toolchain.lock.json`` (the amd64
aarch64-linux-gnu compiler/binutils plus the arm64
glibc-2.39 development sysroot).  Only the kernel is built with this prefix:
userspace, OTA and every userspace tool stay on the armv7 cross.

Usage mirrors the ARMHF module::

    python3 build/ci/aarch64_toolchain.py fetch  --lock ... --archives ...
    python3 build/ci/aarch64_toolchain.py stage  --lock ... --archives ... --prefix ...
    python3 build/ci/aarch64_toolchain.py verify --lock ... --archives ... --prefix ...
    python3 build/ci/aarch64_toolchain.py env    --prefix ...
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import armhf_toolchain  # noqa: E402  (sibling module, resolved above)

AARCH64 = armhf_toolchain.Family(
    name="aarch64",
    lock_schema="libreecho-aarch64-cross-toolchain-lock/1",
    receipt_schema="libreecho-aarch64-toolchain-prefix-receipt/1",
    tree_schema="libreecho-aarch64-toolchain-tree/1",
    receipt_name=".libreecho-aarch64-toolchain-receipt.json",
    target="aarch64-linux-gnu",
    cross_prefix_name="aarch64-linux-gnu-",
    ld_path="usr/lib/x86_64-linux-gnu",
    generator="build/ci/aarch64_toolchain.py",
    stage_prefix=".aarch64-toolchain-stage-",
)


def main(argv=None) -> int:
    return armhf_toolchain.main(argv, family=AARCH64)


if __name__ == "__main__":
    raise SystemExit(main())
