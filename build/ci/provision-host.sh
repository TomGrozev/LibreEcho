#!/usr/bin/env bash
# Provision the host toolchain shared by the hosted GitHub build and the
# pinned container image in build/container/Containerfile.
#
# CI runs this with sudo on the ubuntu-24.04 runner image; the container
# image runs the same script as root while it is built. Both hosts therefore
# get one definition of "a machine that can build LibreEcho", and the install
# is idempotent: packages that are already present are never touched, so a
# hosted run performs no apt transaction at all.
set -euo pipefail

# Packages the build invokes as host tools. They are the runner image's
# baseline rather than pinned build inputs: every compiler, sysroot and source
# archive the build consumes is staged from the committed locks.
BASE_PACKAGES=(
  autoconf
  automake
  bc
  bison
  build-essential
  bzip2
  ca-certificates
  cmake
  cpio
  curl
  diffutils
  file
  flex
  gawk
  git
  gzip
  jq
  libdebuginfod1t64
  libelf-dev
  libfl2
  libssl-dev
  libtool
  libzstd1
  make
  patch
  pkg-config
  python3
  rsync
  sed
  sudo
  tar
  unzip
  wget
  xz-utils
  zip
  zstd
)

# build.sh hashes several of these into component cache keys, so a host that
# silently lacks one changes cached bytes instead of failing loudly. Verify
# the command surface explicitly instead.
REQUIRED_COMMANDS=(
  autoconf
  automake
  awk
  bc
  bison
  cmake
  cpio
  curl
  dpkg-deb
  file
  flex
  flock
  g++
  gcc
  git
  libtoolize
  make
  patch
  pkg-config
  python3
  rsync
  tar
  unzip
  wget
  xz
  zip
  zstd
)

die() { echo "ERROR: $*" >&2; exit 1; }

usage() {
  cat <<'USAGE'
usage: provision-host.sh --install [--check]
       provision-host.sh --check
       provision-host.sh --anchor <staged-armhf-root>

--install  install any missing baseline package (apt, no-op when complete)
--check    fail closed unless every required host command and CPython 3.11 exist
--anchor   symlink the staged ARMHF cross closure at the absolute paths its
           glibc linker scripts name (/usr/arm-linux-gnueabihf and
           /usr/lib/gcc-cross/arm-linux-gnueabihf)
USAGE
}

SUDO=()
if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  SUDO=(sudo)
fi

install_base() {
  local pkg
  local missing=()
  for pkg in "${BASE_PACKAGES[@]}"; do
    if [[ "$(dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null || true)" != *"install ok installed"* ]]; then
      missing+=("$pkg")
    fi
  done
  if ((${#missing[@]} == 0)); then
    echo "provision-host: all ${#BASE_PACKAGES[@]} baseline packages present"
    return
  fi
  echo "provision-host: installing missing baseline packages: ${missing[*]}"
  "${SUDO[@]}" apt-get update -o Acquire::Retries=3
  "${SUDO[@]}" apt-get install -y --no-install-recommends "${missing[@]}"
}

check_base() {
  local cmd
  local missing=()
  for cmd in "${REQUIRED_COMMANDS[@]}"; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
  done
  ((${#missing[@]} == 0)) || die "required host commands are missing: ${missing[*]}"
  # The reviewed mbedTLS wheel closure is cp311 and the workflow pins 3.11
  # through setup-python; a 3.12 interpreter fails only much later, inside the
  # UI bundle, so reject it here.
  python3 - <<'PY'
import sys
if sys.version_info[:2] != (3, 11):
    raise SystemExit(
        "ERROR: the build host must run CPython 3.11, found "
        + ".".join(map(str, sys.version_info[:3]))
    )
PY
  echo "provision-host: host command surface and CPython 3.11 verified"
}

anchor_armhf() {
  local root="$1"
  [[ -d "$root/usr/arm-linux-gnueabihf/lib" ]] ||
    die "staged ARMHF sysroot is missing: $root"
  [[ -d "$root/usr/lib/gcc-cross/arm-linux-gnueabihf" ]] ||
    die "staged ARMHF gcc-cross tree is missing: $root"
  # glibc's development linker scripts ship GROUP paths under
  # /usr/arm-linux-gnueabihf, and the driver's default search paths name
  # /usr/lib/gcc-cross/arm-linux-gnueabihf; the staged closure lives under
  # the per-run temp dir, so bind those absolute names to it.
  "${SUDO[@]}" mkdir -p /usr/lib/gcc-cross
  "${SUDO[@]}" ln -sfT "$root/usr/arm-linux-gnueabihf" /usr/arm-linux-gnueabihf
  "${SUDO[@]}" ln -sfT "$root/usr/lib/gcc-cross/arm-linux-gnueabihf" \
    /usr/lib/gcc-cross/arm-linux-gnueabihf
  echo "provision-host: ARMHF sysroot anchored at /usr/arm-linux-gnueabihf from $root"
}

mode_install=0
mode_check=0
anchor_root=""
while (($#)); do
  case "$1" in
    --install) mode_install=1 ;;
    --check) mode_check=1 ;;
    --anchor)
      anchor_root="${2:-}"
      [[ -n "$anchor_root" ]] || die "--anchor requires the staged ARMHF root path"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *) die "unknown argument: $1 (see --help)" ;;
  esac
  shift
done

if ((mode_install == 0 && mode_check == 0)) && [[ -z "$anchor_root" ]]; then
  usage >&2
  die "nothing to do; pass --install, --check, or --anchor <root>"
fi

((mode_install)) && install_base
((mode_check)) && check_base
if [[ -n "$anchor_root" ]]; then
  anchor_armhf "$anchor_root"
fi
