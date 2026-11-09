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

This file is the project memory. A new agent does not have the chat that produced it. Read this before changing the image, the installer, or the name.

## Decisions already made

`PLAN.md` is still the build contract. These later decisions override it where they disagree. Do not "fix" them back.

- The displayed name is **Borked**. `PRETTY_NAME` is `Borked`. The site is https://projectborked.com/. Copy should sound like that site: short, snarky, and willing to admit something is slightly broken. `PLAN.md` still says "Borked OS". Leave that file alone. Do not put "OS" back on the installer, the splash, or os-release.
- The console logo's B is `█▄█` over `█▀█`. The D shape `█▀▄` over `█▄▀` makes the word read as DORKED. B and D must not use the same two glyphs. The splash is `iso/live-init`. The same logo is in `installer/borked_install/tui.py` and `apps/borked_apps/tui.py`.
- Default software goes in `packages/include.list`, then `just lock`. Something a group pulled in that must not ship goes in `packages/exclude.list`. Optional software is not in the base image. It is a line in `apps/catalog`, installed later with `borked apps`. New `borked` subcommands belong in `apps/borked_apps/`. The voice lines live in `apps/borked_apps/voice.py`.
- Third-party RPM repos are `repos/*.repo`: `gpgcheck=1`, priority 110 so Fedora wins a name collision. `image/lib.sh` copies them in. Do not vendor their payloads.
- Flathub is the full remote from `repos/flathub.flatpakrepo` (`https://dl.flathub.org/repo/`). Do not switch it to Fedora's filtered `fedora-flathub-remote`.
- `wine-core` and `wine-filesystem` are installed in their own transaction with scriptlets off, then `/usr/bin/wine` is pointed at `wine64`. Fedora's `wine-core` 11.20 script registers the `d3d8` DLL under the `dxgi` alternative name and fails the whole rpm transaction. Do not drop Wine, and do not turn those scriptlets back on. The earlier glibc/bash bootstrap and the `generic-release` removal in `image/build-root.sh` are there because a single large transaction runs `crypto-policies` `%pre` before `/bin/sh` exists. Do not collapse the install back into one `dnf` transaction.
- The public package repo is not hosted yet. `specs/borked-repos.spec` still points at `https://repo.borked.invalid/`. Do not publish the Borked repo from COPR, and do not set `gpgcheck=0` to get a package in. COPR is an upstream we consume (Zed, Herdr), not where Borked publishes.
- `out/` is gitignored. It holds the ISO, the stream, and the dev signing key. A new machine generates its own dev key on the first build. Never commit a private key.
