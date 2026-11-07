# Borked OS

A mutable Fedora remix with the COSMIC desktop. `PLAN.md` is the build contract.

The host needs podman, qemu, OVMF, `just`, and passwordless sudo for the rootful image build. The build itself runs in `quay.io/fedora/fedora` at the release pinned in `release/fedora`.

```sh
just lock    # solve packages/include.list into packages/lock
just root    # golden btrfs send stream at out/borked-root.btrfs.zst
just qemu    # unpack that stream onto a raw disk and boot it
just iso     # hybrid installer ISO
just test    # unattended ISO install in qemu, then self-check
just check   # exclude-list failure test, no VM
```

`just qemu` and `just test` boot a VM and run `/usr/bin/borked-selfcheck`. A script that exits 0 without that boot is not a finished image.

Dev builds set `VARIANT=Development`, generate a throwaway signing key under `out/keys/`, and do not sign the ISO. There is no release key yet, so there is no release fingerprint to publish. Set `BORKED_VARIANT=COSMIC` and `BORKED_RELEASE_KEY` to a detached private key only when cutting a signed release. Never commit `out/`.
