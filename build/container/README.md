# Build container

`Containerfile` pins the ubuntu-24.04 GitHub Actions runner the hosted build
uses: same base image digest, same apt archive snapshot, same CPython 3.11, and
the same host baseline script (`build/ci/provision-host.sh`) that CI runs.

## Build the image

Run from the repository root, because the build context is the repo:

```bash
podman build -f build/container/Containerfile -t libreecho-build .
```

`UBUNTU_SNAPSHOT` and `PYTHON_STANDALONE_SHA256` are build args; change them
deliberately, never to float.

Rootless podman networks containers through `pasta`, which needs the `tun`
kernel module. If `/dev/net/tun` is missing (for example after a kernel update
without a reboot), add `--network=host` to `podman build` and `podman run`.

## Run the build

Mount the repository and a scratch directory for `RUNNER_TEMP`. Rootless podman
maps your user into the container, so the mounted tree stays writable without
loop mounts or ownership fixups:

```bash
mkdir -p work/runner
podman run --rm -it --userns=keep-id \
  -v "$PWD:/src:Z" \
  -v "$PWD/work/runner:/home/builder/runner:Z" \
  -e GITHUB_WORKSPACE=/src \
  -e RUNNER_TEMP=/home/builder/runner \
    libreecho-build
```

The resolved package set is recorded at
`/usr/local/share/libreecho/host-packages.txt`; diff it across image rebuilds
to see what a snapshot bump changed.

Check the host matches the CI contract at any time:

```bash
podman run --rm libreecho-build /usr/local/bin/provision-host.sh --check
```

The build itself also needs the staged inputs that the `prepare-public-inputs`
job produces and caches: `public-deps`, `toolchain`, `armhf-root`,
`mdns-packages`, and the derived `mdns-runtime`. Download them from a CI run
into `$RUNNER_TEMP` and run `build/ci/build-public-release.sh` with the env
block from the workflow's `Build image and features` step. The ARM (ports)
packages the AirPlay sysroot downloads are fetched live from
`ports.ubuntu.com`, exactly as on a hosted runner, so a container build needs
network access.

`build/ci/provision-host.sh --anchor "$RUNNER_TEMP/armhf-root"` places the
staged ARMHF cross closure at the absolute paths its glibc linker scripts name;
it needs `sudo` and is the only step that writes outside the mounted tree.
