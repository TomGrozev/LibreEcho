# Hosted public build boundary

The public workflow is GitHub-hosted only. It does not use `LibreEcho-Build`, a
self-hosted runner, Vaultwarden, sudo, private dependency roots, local caches,
private models, or owner-local firmware bytes.

`build/inputs/public-inputs.json` is the closed dependency inventory. Entries
must have public HTTPS URLs, exact SHA-256 digests, licenses, and cleared
redistribution status before the hosted dependency job may fetch them. Pinned
`source-git` entries additionally require an exact 40-hex commit and the
`source-git-pinned` redistribution marker. Current unresolved toolchain entries
are deliberately blocked; this branch must not fall back to local copies. The
device-local connectivity firmware is represented only by the public importer
contract: first boot verifies and copies it from stock `system_a`; the bytes
never enter CI, Git, or release assets.

The OTA signing job uses the reviewed Python 3.11/Linux wheel closure under
`build/inputs/reviewed/python-wheels/`. `PyNaCl==1.5.0`, `cffi==1.17.1`, and
`pycparser==2.22` are each vendored and SHA-256-pinned in the public inventory;
`requirements.txt` is pinned as well. The build artifact verifies its complete
`SHA256SUMS` before installing with pip `--no-index`, `--find-links`, and
`--require-hashes`. No OTA signing dependency is fetched from the live package
index, and this verification runs before the protected signing key is
materialized.

`build/ci/build-public-release.sh` now invokes the preserved mature builder with
only explicit hosted dependency/source roots. It fails before compilation when
the generated public ARM32 toolchain or any required source root is absent; it
never falls back to local paths.

The hosted image job builds the neural dependency closure after installing the
public ARMHF compiler/sysroot with `build/ci/build-public-neural-deps.sh`. It
checks out ONNX Runtime v1.27.0 and Sherpa-ONNX at the exact inventory pins,
builds static ARM32 ONNX Runtime and Sherpa libraries, retains the FlatBuffers
Python generator tree, builds RE2 and SpeexDSP, and writes only the generated
roots under the job-local `public-deps/neural/` directory. The mature builder
receives those roots explicitly; it never discovers or imports a private neural
cache. The reduced wakeword ONNX Runtime build remains a separate run-local
step performed by the mature builder from the same pinned ONNX Runtime source.

## Issuing a stable release

Use GitHub only: open **Actions → Hosted LibreEcho build and release → Run
workflow**, select the matching `release/X.Y.Z` branch, choose `build_purpose=prd`, and
provide the version plus the reviewed Amonet repository/tag/commit. The
matching authored `release/radar-puffin-vX.Y.Z.md` file must already be checked
in. The workflow validates that file before the expensive build, appends an
exact cross-repository source ledger, signs the exact artifact, waits for the
protected signing environment, and publishes the normal
`radar-puffin-vX.Y.Z` release. No local release command is required.

## Product release lanes

The Product repository owns all hosted image and release automation. The lanes
are deliberately separate. Manual runs default to `build_purpose=sandbox`:

| Purpose | Channel | Result |
| --- | --- | --- |
| `sandbox` | dev | No publication; verified artifact expires after 3 days. Unsigned by default; optional `sandbox_signing=signed`. |
| `dev` | dev | Signed prerelease plus dev discovery pointer; artifact retained 7 days. Dispatch on `main` or `release/**`. |
| `prd` | stable | Signed stable release from matching `release/X.Y.Z`; artifact retained 7 days. |

PRs and pushes to `main` or `release/**` are unsigned sandbox builds: no
publication or pointer movement, with 3-day artifact retention.
`sandbox_signing=signed` is rejected for dev/prd (which are always signed).
The release-line scheduled build resolver remains unchanged, but scheduled
requests fail closed at publication routing and cannot move the dev pointer.

- **PR validation:** pull requests targeting `main` or `release/**` build a
  no-publish OTA-profile image with the development channel. The run artifact is
  validation evidence only and never publishes a release.
- **SSH option:** all non-dispatch builds keep SSH disabled. A manual GitHub
  Actions run defaults to `ssh_enabled=enabled` and may select `disabled`; an
  enabled run embeds the static ARM32 `dropbear`, `dropbearkey` and `scp`
  binaries in the initramfs. The SSH supervisor starts the server only when
  the saved WebUI SSH switch is on and a valid users database exists at
  `/data/libreecho/config/users`. Authentication uses that database and
  nothing else: the image has **root login disabled**, uses non-root ephemeral
  accounts, and carries no public-key authorization. Each device keeps its
  own protected host key across reboots. No root password enters the build;
  the release manifest records all three binary hashes.
- **Development:** only an explicit `workflow_dispatch` with `build_purpose=dev`
  on `main` or `release/X.Y.Z` publishes a bounded signed `dev`-channel GitHub
  prerelease from the exact workflow artifact and moves the dev discovery pointer.
  Use `gh workflow run build-release.yml --ref <main|release/X.Y.Z> -f build_purpose=dev ...`
  with the selected ref's required inputs. Routine merges only produce sandbox
  artifacts. These releases are `PREPARED_NOT_FLASHED`, are not marked latest,
  and are not hardware-acceptance evidence.
- **Scheduled validation:** this release line retains its existing signed build
  derivation and retention, but publication routing rejects scheduled dev requests.
  The live default-branch schedule is an unsigned sandbox canary.
- **Stable/product:** a maintainer manually dispatches the workflow from a
  matching `release/X.Y.Z` branch with `build_purpose=prd`, the release
  version, release notes, and the reviewed Amonet tag. The protected
  `stable-release` environment supplies `LIBREECHO_OTA_SIGNING_KEY_HEX`; the
  image job uses local signing and must produce exactly one signed OTA bundle.
  The following Product `workflow_run` prepares and publishes the exact stable
  artifact set as the normal `radar-puffin-vX.Y.Z` GitHub release.

Stable publication is fail-closed on the exact Product workflow artifact,
source identities, OTA hash, public key, feature payload hashes, installer
bundle, release notes, and complete `SHA256SUMS`. It does not flash hardware or
claim runtime acceptance. Configure the protected environment secret and
approval rules before attempting a stable dispatch.

## Building Lidar locally

Lidar is the Echo Plus (2nd Gen), SoC MT8167, and is the first ARM64 target:
`release/targets/lidar.json` declares `arch: arm64` with
`platform.tools_profile: mt8167-arm64` for the image tools and
`platform.userspace_tools_profile: mt8163-arm32` for the shared userspace
stack. `build.sh` therefore packages the boot image with the ARM64 builder and
verifier while every ARM32 userspace component still comes from the
`mt8163-arm32` recipes. Lidar is `hardware_accepted: false`, so this is a local
build only: no stable release lane accepts it yet.

The build is self-contained per run but writes no state into the checkout.
Everything lives under `LIBREECHO_BUILD_ROOT`, `LIBREECHO_KERNEL_OUT`, and
`LIBREECHO_PRIVATE_ROOT`, all of which must be outside the Git trees.

### Prerequisites

- A Linux x86_64 host. Host tools: `bash`, `python3` (3.11), `git`, `curl`,
  `dpkg-deb`, `sha256sum`, `binutils` (`readelf`), a device-tree compiler
  (`dtc`) and `fdtget` for the DTB contract, and the usual C build tools for
  the userspace recipes.
- This Product checkout, plus sibling checkouts of Platform
  (`LIBREECHO_TOOLING_SRC`, which must provide `tools/mt8167-arm64` and
  `tools/mt8163-arm32`), the LibreEcho kernel (`LIBREECHO_KERNEL_SRC`), and the
  UI (`LIBREECHO_UI_SRC`).
- The same pinned toolchain and component roots the hosted job passes.
  `build.sh` fails closed on any missing variable; the canonical exhaustive
  list is the "Build image and features" env block in
  `.github/workflows/build-release.yml`. The ones a local run must provide:
  - Kernel and userspace compilers: `LIBREECHO_AARCH64_CROSS` (the ARM64
    kernel cross, `.../usr/bin/aarch64-linux-gnu-`), `CROSS` (ARMHF glibc
    cross prefix), `LIBREECHO_UI_CROSS`,
    `LIBREECHO_CORE_RUNTIME_SYSROOT`, `LIBREECHO_CORE_GCC_LIBDIR`,
    `LIBREECHO_MUSL_CROSS_PREFIX`, `LIBREECHO_MUSL_SYSROOT`, `AUDIO_CC`.
  - OTA toolchain: `LIBREECHO_OTA_MUSL_NATIVE_ROOT`,
    `LIBREECHO_OTA_MUSL_SYSROOT`.
  - Pinned source archives: `LIBREECHO_BUSYBOX_SOURCE_ARCHIVE`,
    `LIBREECHO_MUSL_SOURCE_ARCHIVE`,
    `LIBREECHO_WPA_SUPPLICANT_SOURCE_ARCHIVE`,
    `LIBREECHO_LIBNL_SOURCE_ARCHIVE`,
    `LIBREECHO_WIRELESS_TOOLS_SOURCE_ARCHIVE`,
    `LIBREECHO_WIRELESS_REGDB_SOURCE_ARCHIVE`,
    `LIBREECHO_LIBSODIUM_SOURCE_ARCHIVE`,
    `LIBREECHO_MBEDTLS_SOURCE_ARCHIVE`, `LIBREECHO_OPUS_ARCHIVES_DIR`,
    `LIBREECHO_MBEDTLS_BUILD_PYTHON`.
  - `adbd`: `LIBREECHO_ADBD_SOURCE` (AOSP `system/core`) and
    `LIBREECHO_ADBD_KERNEL_HEADERS` (exported Linux UAPI tree).
  - AirPlay and feature models: `LIBREECHO_AIRPLAY_SYSROOT`, plus the
    Sherpa/ONNX Runtime/Flite/eSpeak/Speex roots named in the workflow env
    block; v3 ships all five features, so all of them are required.
- A staged public input tree (`LIBREECHO_INPUTS_ROOT`) containing the pinned
  archives and their `SHA256SUMS`; the MT7668 firmware pair
  (`mt7668pr2h.bin`, `LICENCE.mediatek`) is part of the public inventory and
  is fetched with the rest.

### Environment

Build-state and input roots:

- `LIBREECHO_BUILD_ROOT` (required): external build state. Holds `work/`
  (component builds), `generated/`, `out/runs/` (one immutable run per build),
  and the default component cache. Never inside the repository.
- `LIBREECHO_KERNEL_OUT` (required): out-of-tree kernel build directory, also
  outside the source trees. Reused incrementally between runs.
- `LIBREECHO_PRIVATE_ROOT` (required): external private directory, forced to
  mode 0700. Holds the local Wi-Fi profile (`wpa_supplicant.conf`) and the
  default OTA signing key path.
- `LIBREECHO_INPUTS_ROOT` (required in practice for local builds): staged
  public inputs and `SHA256SUMS`; defaults to `build/inputs`, which is the
  inventory, not a staged tree, so point it at the fetched dependencies.
- `LIBREECHO_TOOLING_SRC`, `LIBREECHO_KERNEL_SRC`, `LIBREECHO_UI_SRC`
  (required): the Platform, kernel, and UI checkouts named above.

Lidar image and OTA inputs:

- `LIBREECHO_LIDAR_STOCK_BOOT` (required, owner-only): path to the owner's
  unmodified readback of the device's stock `boot_a` partition. The MT8167
  image builder re-frames that stock boot image (its stock DTBs and boot
  envelope) rather than synthesising one, so the bytes must come from the
  exact device model. They are per-unit vendor firmware and are deliberately
  kept out of Git and the public input inventory; only the owner can supply
  them.
- `LIBREECHO_OTA_SIGNING_KEY` (required, owner-only): hex Ed25519 seed used to
  sign the v3 OTA bundle. It is a private key and must never be committed or
  shared. Defaults to `$LIBREECHO_PRIVATE_ROOT/ota-signing-key.hex`.
- `LIBREECHO_OTA_PUBLIC_KEY` (required for a lab key): the hex public key
  corresponding to the signing key. It is installed into the image and
  published with the bundle, so a build refuses to proceed unless its hash
  matches the expected key. When unset, build.sh uses the Platform
  `mt8163-arm32/ota/ota-public-key.hex` release key.
- `LIBREECHO_OTA_EXPECTED_PUBLIC_KEY_SHA256` (required): the SHA-256 of the
  public key file. This pins the release key independently of the files on
  disk and makes an accidental key rotation fail closed.
- `LIBREECHO_OTA_RELEASE` (required): the release version the OTA catalog
  records.
- `LIBREECHO_TARGET_RELEASE_TAG` (required): the release tag the target
  manifest and OTA catalog bind. For Lidar the asset prefix becomes
  `libreecho-lidar-<tag>`; it must be stable per build.
- `LIBREECHO_OTBR_SOURCE` (required): an OpenThread Border Router
  (`ot-br-posix`) checkout.
- `LIBREECHO_OTBR_DEPS` (required): the dependency prefix built for that
  source tree by the Platform `otbr/build_otbr_deps.sh` recipe.

Boot discovery runtime: the shared mDNS runtime is a boot-contained
dependency. The hosted job builds and verifies it separately; locally, leave
`LIBREECHO_MDNS_RUNTIME_ROOT`, `LIBREECHO_MDNS_RUNTIME_SOURCE_MAP`, and
`LIBREECHO_MDNS_RUNTIME_MANIFEST_SHA256` unset and `build.sh` invokes
`build/ci/build-mdns-runtime.sh`. That script fetches the lock-pinned ARMHF
packages by exact URL, re-hashes each against
`build/inputs/mdns-packages.lock.json`, extracts them with the Platform
builder, verifies the runtime with the Platform verifier, and records the
corresponding-source and notice closure. Its output directory holds
`runtime/`, `mdns-runtime-provenance.json`, and `outputs.env`; sourcing the
last one supplies the three variables. Set `LIBREECHO_MDNS_PACKAGE_ARCHIVES`
to reuse an archive cache so a later build needs no network.

Product defaults worth knowing: `--profile ota` selects the production
service profile, and for an ARM64 target `build.sh` defaults to
`LIBREECHO_OTA_FORMAT=v3` and `LIBREECHO_OTA_SIGNING_MODE=local`. v3 requires
the complete five-feature catalog (airplay2, assistant, stt, tts, wakeword),
so the feature inputs must all be present.

### Command

```sh
export LIBREECHO_BUILD_ROOT=$PWD/work/product-build
export LIBREECHO_KERNEL_OUT=$LIBREECHO_BUILD_ROOT/kernel
export LIBREECHO_PRIVATE_ROOT=$PWD/private
export LIBREECHO_INPUTS_ROOT=$PWD/work/inputs/public-deps
export LIBREECHO_LIDAR_STOCK_BOOT=$LIBREECHO_PRIVATE_ROOT/dumps/<backup>/boot_a.bin
export LIBREECHO_OTA_SIGNING_KEY=$LIBREECHO_PRIVATE_ROOT/keys/ed25519-seed.hex
export LIBREECHO_OTA_PUBLIC_KEY=$LIBREECHO_PRIVATE_ROOT/keys/ed25519-public.hex
export LIBREECHO_OTA_RELEASE=<x.y.z>
export LIBREECHO_TARGET_RELEASE_TAG=radar-puffin-build-<sha7>-<id16>-<build16>
export LIBREECHO_OTA_EXPECTED_PUBLIC_KEY_SHA256=<sha256 of the public key file>
export LIBREECHO_OTBR_SOURCE=<ot-br-posix checkout>
export LIBREECHO_OTBR_DEPS=<build_otbr_deps prefix>
# ...plus the toolchain, source-archive, and feature inputs listed above.

build/build.sh --target lidar --profile ota --no-publish
```

### Outputs

Everything lands in one immutable run directory,
`$LIBREECHO_BUILD_ROOT/out/runs/<run>/`:

- `boot.img` and `boot.ramdisk.cpio.xz`: the verified Lidar boot image and
  its ramdisk, built and independently re-verified by the MT8167 tools.
- `feature-candidate-catalog.json`, `target.manifest`, and `ota-assets/`: the
  five-feature catalog, the per-target manifest, and the feature payloads the
  OTA references.
- `ota-public-key.hex` and `libreecho-<run>.ota.tar`: the published key and
  the signed v3 OTA bundle. The bundle hash is recorded in the run record
  (`CURRENT.candidate`) rather than written as a sidecar file.
- `manifest.json`, `component-identities.log`, and `CURRENT.candidate`: the
  component provenance and the run record. `--no-publish` deliberately leaves
  the canonical `out/CURRENT` and `out/current` untouched, because legacy
  publication is Radar-only.
