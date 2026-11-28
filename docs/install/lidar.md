# Installing LibreEcho on the Echo Plus 2nd Gen (Lidar)

> Target `lidar`, MediaTek MT8167, ARM64 kernel with the shared ARM32
> userspace. The port boots on hardware: lab OTA builds have been installed on
> a unit. It is **not a release**: no `lidar-v*` tag is published, the target is
> not upstream-supported, and the boot-chain preparation below has passed host
> tests only.

## How Lidar differs from `radar_puffin` and `biscuit`

| | radar_puffin / biscuit | lidar |
|---|---|---|
| Unlock route | Amonet ZIP with a fastbrick payload, run by the installer | None. No Amonet payload exists; the unit must already run the Kaeru chain (see below) |
| Chain preparation | The installer's fastbrick stage | `lidar_prepare.py` (LibreEcho-Platform, `tools/mt8167-arm64/prepare/`): identify, backup, restore drill, stock-boot gate, chain install, fastboot confirm |
| Fastboot product | `RADAR` / `BISCUIT` | `LIDAR` |
| Boot slots | `boot_a` / `boot_b`, readback accepts `*_x` names | `boot_a` / `boot_b` only; the Kaeru GPT has no `_x` stores |
| userdata | target-specific accepted sizes | exactly 9647071 sectors (stock); formatted by the installer |
| expdb | not read | read-only check: first 16 bytes must start with the MTK magic `88 16 88 58` before any flash write |
| Kernel | `mt8163_arm32_defconfig`, Radar DTB | `mt8167_arm64_defconfig`, `libreecho-lidar.dtb`; OTA payloads stay ARM32 (armv7 userspace) |

## The one-command flow (target design)

The planned end-to-end path is:

1. Prepare the USB connection (the unit has no external port; reach the USB
   pads on the base board).
2. Hold the action button and apply power to enter the MT8167 BROM.
3. Run `lidar_prepare.py`. It takes the boot-chain backups, performs the
   pre-install restore drill and the stock-boot gate, installs the
   owner-access chain (Kaeru LK stage into expdb, Koboreru over tee1, the
   backup's signed 2019 preloader into BOOT0 area 1), and confirms `fastboot
   getvar product` answers `LIDAR`. It never writes BOOT1, and it checks the
   expdb prefix before every boot-chain write.
4. Run `python3 tools/libreecho-install.py --target lidar`.
5. Validate and confirm the installation.

No manual offsets, no eMMC short and no reference-ZIP step appear in this
path. The usage, stage list and safety rules of the preparation command are in
the Platform fork's
[prepare README](https://github.com/TomGrozev/LibreEcho-Platform/blob/feature/lidar-support/tools/mt8167-arm64/prepare/README.md).

**Hardware status:** the OS runs from lab builds on a unit, but no stock unit
has been taken through `lidar_prepare.py`: it has passed 31 host tests against
a fake device and a dry-run adapter only. Each of its write stages needs
separate approval.

## Installer behaviour for `--target lidar`

`tools/libreecho-install.py` accepts `--target lidar` with these gates:

- **Already-converted pin rule.** The installer asks `fastboot oem
  kaeru-version`. A stock bootloader refuses the command, and the installer
  refuses to write anything: there is no Amonet payload to flash. Only a unit
  that already answers as Kaeru proceeds, and no boot-chain byte is written by
  the installer itself.
- **expdb guard.** Before every flash write the installer reads `expdb[0:16]`
  over fastboot and refuses unless it starts with `88 16 88 58` (a Kaeru
  LK-stage generation). A stock or wiped `expdb` refuses.
- **Geometry.** userdata must be exactly 9647071 sectors. The Lidar path
  writes only `userdata`, `boot_a` and `boot_b`, and verifies both boot slots'
  readbacks. It takes no other backups; run `lidar_prepare.py backup` first if
  you want a restorable unit.
- **No Lidar recovery route exists yet**, and no `lidar-v*` release tag is
  published, so today the installer needs a lab build bundle
  (`--release-dir`). The web installer does not list Lidar at all
  (`hardwareAccepted` is `false`).

## Validation

After the install:

- `/etc/libreecho/target` reads `target_id=lidar`, `hw_profile=lidar@1`.
- `/data/libreecho/update/boot-health` reports `state=confirmed` on the
  expected slot; A/B fallback rolls back automatically after three failed
  boots on a slot.
- The audio profile is `lidar` (flat codec), and the LED ring, buttons,
  microphones and Wi-Fi behave as recorded during the port's hardware sweep.

## Recovery

- Return to stock only from the `lidar_prepare.py backup` directory with the
  Phase 2/3 restore tooling. Never restore `expdb` alone; see the
  [boot-chain safety rules](../../AGENTS.md#boot-chain-safety).
- To return to fastboot, hold the action button at power-on (the Kaeru chain
  boots to fastboot like the other targets).
