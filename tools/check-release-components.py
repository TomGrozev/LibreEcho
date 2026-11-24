#!/usr/bin/env python3
"""Fail unless every redistributed public-release component is cleared."""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

sys.dont_write_bytecode = True


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--components", type=Path,
        default=root / "release/components.json",
        help="component catalog to enforce",
    )
    parser.add_argument(
        "--release-scope",
        choices=("commercially-unrestricted", "community-noncommercial"),
        default="commercially-unrestricted",
    )
    parser.add_argument(
        "--artifacts", type=Path, action="append", default=[],
        help="image, bundle or OTA paths to reject when they carry EFR32 firmware",
    )
    parser.add_argument(
        "--target", choices=("radar_puffin", "biscuit", "lidar"),
        help="release target id; lidar enables the MTK boot-chain signature rules",
    )
    parser.add_argument(
        "--donor-manifest", type=Path,
        help="Lidar donor artifact generator manifest; its digests are refused",
    )
    args = parser.parse_args()

    prepare_path = root / "tools/prepare-release.py"
    spec = importlib.util.spec_from_file_location("prepare_release", prepare_path)
    if spec is None or spec.loader is None:
        raise SystemExit("ERROR: release component validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Without artifacts, scan the checkout so a stray GBL is still caught.
    if not args.artifacts:
        module.reject_donor_derived_artifacts([root])

    components = module.load_components(args.components, args.release_scope)
    if args.artifacts:
        module.reject_donor_derived_artifacts(
            args.artifacts, args.donor_manifest,
            lidar_target=(args.target == "lidar" or args.donor_manifest is not None))
        print(f"donor_gate=cleared artifact_count={len(args.artifacts)}")
    print(
        f"component_gate=cleared component_count={len(components)} "
        f"release_scope={args.release_scope}"
    )


if __name__ == "__main__":
    main()
