#!/usr/bin/env bash
# Build and verify the boot-owned shared mDNS discovery runtime from the
# committed package lock.
#
# Usage: build-mdns-runtime.sh OUT_DIR
#
# This is the local counterpart of the "Acquire exact shared mDNS dependency
# packages" and "Build and verify the shared mDNS discovery runtime" steps in
# .github/workflows/build-release.yml. Archives are fetched by exact pinned URL
# and re-hashed against build/inputs/mdns-packages.lock.json, the Platform
# builder extracts them, the independent Platform verifier pins the result to
# its own manifest identity, and the Product closure gate records the
# corresponding-source and notice provenance.
#
# OUT_DIR must live outside the Product source tree, e.g. under
# LIBREECHO_BUILD_ROOT. Layout after a successful run:
#   OUT_DIR/packages/                     locked .deb archives (hash-verified)
#   OUT_DIR/runtime/                      Platform runtime tree
#   OUT_DIR/runtime/root/                 the staged runtime the image consumes
#   OUT_DIR/runtime/manifest.json         runtime file inventory
#   OUT_DIR/mdns-runtime-provenance.json  closure record (the source map)
#   OUT_DIR/outputs.env                   shell assignments for build.sh
#
# Environment:
#   LIBREECHO_TOOLING_SRC            Platform tools root that contains
#                                    mt8163-arm32/mdns/
#   LIBREECHO_MDNS_TOOLS_DIR         direct override for the Platform mdns dir
#   LIBREECHO_MDNS_PACKAGE_ARCHIVES  reuse a populated archive directory; the
#                                    next build then needs no network. It must
#                                    hold only this lock's archives, because
#                                    the verification rejects extras.
set -euo pipefail

PIPELINE="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
LOCK="$PIPELINE/inputs/mdns-packages.lock.json"
OFFERS="$PIPELINE/inputs/mdns-source-offers.json"
RUNTIME_SCRIPT="$PIPELINE/ci/mdns_runtime.py"

usage() {
  echo "usage: $(basename -- "$0") OUT_DIR" >&2
  exit 2
}
[[ $# -eq 1 ]] || usage
[[ -n "$1" ]] || usage

for tool in python3 sha256sum dpkg-deb readelf; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "ERROR: shared mDNS runtime build requires $tool" >&2
    exit 1
  }
done

mkdir -p -- "$1"
OUT="$(cd -- "$1" && pwd -P)"
[[ "$OUT" != "$PIPELINE" && "$OUT" != "$PIPELINE"/* ]] || {
  echo "ERROR: mDNS runtime output must be outside the Product source tree: $OUT" >&2
  exit 1
}

MDNS_TOOLS="${LIBREECHO_MDNS_TOOLS_DIR:-}"
if [[ -z "$MDNS_TOOLS" ]]; then
  TOOLING="${LIBREECHO_TOOLING_SRC:-}"
  [[ -n "$TOOLING" ]] || {
    echo "ERROR: set LIBREECHO_TOOLING_SRC to the Platform tools root (or LIBREECHO_MDNS_TOOLS_DIR directly)" >&2
    exit 1
  }
  MDNS_TOOLS="${TOOLING%/}/mt8163-arm32/mdns"
fi
BUILDER="$MDNS_TOOLS/build_runtime.py"
VERIFIER="$MDNS_TOOLS/verify_runtime.py"
for required in "$BUILDER" "$VERIFIER"; do
  [[ -f "$required" && ! -L "$required" ]] || {
    echo "ERROR: Platform shared mDNS tool is missing: $required" >&2
    exit 1
  }
done

ARCHIVES="${LIBREECHO_MDNS_PACKAGE_ARCHIVES:-$OUT/packages}"
mkdir -p -- "$ARCHIVES"
ARCHIVES="$(cd -- "$ARCHIVES" && pwd -P)"
[[ -d "$ARCHIVES" && ! -L "$ARCHIVES" ]] || {
  echo "ERROR: mDNS package archive directory is missing or unsafe: $ARCHIVES" >&2
  exit 1
}

echo "=== acquiring exact shared mDNS package archives ==="
# The lock selects the bytes: every URL is the lock's exact package version and
# every download is re-hashed before it is given the locked file name.
python3 -B "$RUNTIME_SCRIPT" fetch-missing --lock "$LOCK" --archives "$ARCHIVES"
python3 -B "$RUNTIME_SCRIPT" verify --lock "$LOCK" --archives "$ARCHIVES"

echo "=== building the shared mDNS runtime ==="
rm -rf -- "$OUT/runtime"
python3 -B "$BUILDER" --archives "$ARCHIVES" --lock "$LOCK" --output "$OUT/runtime"
RUNTIME_ROOT="$OUT/runtime"
[[ -d "$RUNTIME_ROOT/root" && ! -L "$RUNTIME_ROOT/root" ]] || {
  echo "ERROR: Platform mDNS builder did not produce a runtime root: $RUNTIME_ROOT/root" >&2
  exit 1
}
MANIFEST_SHA256="$(sha256sum "$RUNTIME_ROOT/manifest.json" | awk '{print $1}')"

echo "=== verifying the shared mDNS runtime against its manifest ==="
python3 -B "$VERIFIER" --runtime "$RUNTIME_ROOT" --manifest-sha256 "$MANIFEST_SHA256"

echo "=== recording shared mDNS runtime provenance ==="
SOURCE_MAP="$OUT/mdns-runtime-provenance.json"
rm -f -- "$SOURCE_MAP"
python3 -B "$RUNTIME_SCRIPT" closure \
  --lock "$LOCK" \
  --runtime "$RUNTIME_ROOT" \
  --source-offers "$OFFERS" \
  --manifest-sha256 "$MANIFEST_SHA256" \
  --output "$SOURCE_MAP"

# build.sh sources this file when the corresponding LIBREECHO_ vars are unset;
# %q keeps paths with spaces sourceable.
{
  printf 'LIBREECHO_MDNS_RUNTIME_ROOT=%q\n' "$RUNTIME_ROOT"
  printf 'LIBREECHO_MDNS_RUNTIME_SOURCE_MAP=%q\n' "$SOURCE_MAP"
  printf 'LIBREECHO_MDNS_RUNTIME_MANIFEST_SHA256=%s\n' "$MANIFEST_SHA256"
} > "$OUT/outputs.env"

echo "mdns_runtime_root=$RUNTIME_ROOT"
echo "mdns_runtime_source_map=$SOURCE_MAP"
echo "mdns_runtime_manifest_sha256=$MANIFEST_SHA256"
echo "mdns_runtime_outputs=$OUT/outputs.env"
