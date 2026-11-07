# Borked OS agent rules

`PLAN.md` is the build contract. Do not switch the project to Arch, atomic, Anaconda, or a custom kernel unless that file is changed first.

- Do not disable SELinux, `gpgcheck`, or Secure Boot shim.
- Do not add packages except through `packages/include.list`.
- Do not vendor Fedora package payloads.
- Do not hand-edit `packages/lock`. Change the lists and run `just lock`.
- Dev builds stay `VARIANT=Development` and unsigned. The dev signing key is generated under `out/keys/` and is gitignored.
- Branding RPMs are built with `rpmbuild` inside `quay.io/fedora/fedora:${RELEASE}`. That container is the pinned Fedora release. Do not build them on the host.
- `just` is the entry point: `lock`, `root`, `iso`, `qemu`, `test`, `check`.
- After image or installer changes, `just qemu` or `just test` is the definition of done. A script that exits 0 without a booted VM is not done.
- Rootless podman on this machine cannot `losetup`. `just root` uses rootful podman (`sudo podman --privileged`). Do not drop `btrfs send` because of that.
- v1 is x86_64 UEFI. The ISO is a hybrid image so it can boot BIOS and UEFI. The installed disk is UEFI: ESP plus btrfs, shim copied to `EFI/BOOT/BOOTX64.EFI`.
- Fedora identity packages (`fedora-release-identity-*`) are excluded because they own `/usr/lib/os-release`. `borked-release` provides `fedora-release-identity` at the same EVR as `fedora-release-common`.
