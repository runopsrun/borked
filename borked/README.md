# Borked

A mutable Fedora remix with the COSMIC desktop, and Hyprland as an installer session choice. `PLAN.md` is the build contract. `AGENTS.md` is the memory for coding agents, including the decisions made after that contract. The displayed name is Borked. The console wordmark is three lines, centered at the top of the live splash, the installer, and `borked apps`. The B has two bowls, and the letters fade from a deep raspberry to a pale pink.

The host needs podman, qemu, OVMF, `just`, and passwordless sudo for the rootful image build. The build itself runs in `quay.io/fedora/fedora` at the release pinned in `release/fedora`.

```sh
just lock    # solve packages/include.list into packages/lock
just root    # golden btrfs send stream at out/borked-root.btrfs.zst
just qemu    # unpack that stream onto a raw disk and boot it
just iso     # hybrid installer ISO
just test    # unattended ISO install in qemu, then self-check
just check   # exclude-list failure test, no VM
just convert # this Fedora COSMIC machine becomes Borked
```

`just qemu` and `just test` boot a VM and run `/usr/bin/borked-selfcheck`. A script that exits 0 without that boot is not a finished image.

Dev builds set `VARIANT=Development`, generate a throwaway signing key under `out/keys/`, and do not sign the ISO. There is no release key yet, so there is no release fingerprint to publish. Set `BORKED_VARIANT=COSMIC` and `BORKED_RELEASE_KEY` to a detached private key only when cutting a signed release. Never commit `out/`.

On an installed system, `borked` is the command and `borked apps` installs optional software. Those apps are lines in `apps/catalog`, not packages in the base image. Cisco Duo Unix is one of them: install it from the Security section, then run `borked duo` to write `/etc/duo/login_duo.conf` and optionally wire SSH through `login_duo`. Cytrence Kiwi is another: `borked kiwi` installs the current Ubuntu 24.04 package into a distrobox named `kiwi`, because that is the release Cytrence supports. The sha256 in their zip is checked. It is not a signature.

Optional apps marked `script` download the vendor's current installer over HTTPS and run it as your user. GitHub release apps (`github-rpm`, `github-bundle`) download the current matching file from the latest release. These downloads are not pinned or signature-verified by Borked. Installing one trusts the vendor with your account. RPM repository installs keep GPG checking enabled.

GitHub runs `just check` from `borked/` using the workflow at the repository root. That checks the exclude list, app catalog, and syntax; it does not validate a booted image. Run `just qemu` or `just test` for that.

Borked's original source is MIT licensed; see [LICENSE](../LICENSE). Bundled fonts retain their accompanying SIL Open Font Licenses. Upstream packages retain their own licenses.

The image enables two system Flatpak remotes. Flathub is the full remote at `https://dl.flathub.org/repo/`. The COSMIC remote is `https://apt.pop-os.org/cosmic/`. Both `.flatpakrepo` files live in `repos/` and carry their signing keys. `convert.sh` adds both remotes and removes Fedora's Flathub filter if an existing `flathub` remote was present. Third-party RPM repo signing keys are pinned in `repos/keys/`.

Encrypted installs create a 1 GiB unencrypted ext4 `/boot` partition between the ESP and the LUKS2 Btrfs container so Fedora's signed GRUB boots Argon2id LUKS2 without weakening key derivation. Unencrypted installs keep a two-partition ESP + Btrfs layout.

The top bar is Quickshell (`/usr/share/borked/quickshell/shell.qml`). COSMIC's panel process still starts, and its system entries list keeps the dock, so the top edge is free. The user unit is `borked-quickshell.service`. The bar points at the Cosmic icon theme so status glyphs resolve. It floats as three pills: the name, the clock, and status icons for sound, Bluetooth, network, battery on a laptop, the system tray, Agents, and power. The status icons open one control center. Scroll the sound icon to change volume. Right-click it to mute. That bar is for COSMIC. Hyprland gets Waybar from the same image, with defaults under `/usr/share/borked/hypr/`. The installer asks COSMIC or Hyprland and seeds `cosmic-greeter` so login opens the chosen session.

`sudo ./convert.sh` turns a Fedora COSMIC install of this release into Borked. Files stay. The name, the wallpaper, the repos, and the daily apps change. `--check` only looks. `--yes` skips the question. It will refuse the wrong Fedora release, a machine without COSMIC, and SELinux disabled. The lines are snark. The reason it stopped is still in the line.
