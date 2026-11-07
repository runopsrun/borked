#!/bin/bash
# Build a small live initramfs plus the golden stream into a hybrid ISO.
set -euo pipefail
# shellcheck disable=SC1091
source /src/image/lib.sh

if [[ ! -s /src/out/borked-root.btrfs.zst ]]; then
    echo "missing out/borked-root.btrfs.zst. Run just root." >&2
    exit 1
fi

dnf_build -y install cpio zstd xorriso grub2-tools grub2-tools-extra grub2-efi-x64-modules grub2-pc-modules mtools

live=/src/out/live-root
# The filesystem package makes the installroot mode 0555, which blocks rm.
if [[ -d "$live" ]]; then
    chmod -R u+w "$live" || true
    rm -rf "$live"
fi
mkdir -p "$live"
mapfile -t packages < <(grep -vE '^[[:space:]]*(#|$)' /src/iso/packages.list)
dnf_build -y --installroot="$live" --use-host-config install "${packages[@]}"

install -d "$live/usr/share/borked/installer" "$live/usr/bin"
cp -a /src/installer/borked_install "$live/usr/share/borked/installer/"
cp /src/iso/live-init "$live/init"
chmod 0755 "$live/init"
cat >"$live/usr/bin/borked-install" <<'EOF'
#!/bin/bash
export PYTHONPATH=/usr/share/borked/installer
exec python3 -m borked_install "$@"
EOF
chmod 0755 "$live/usr/bin/borked-install"
rm -rf "$live/var/cache" "$live/var/log"/* "$live/usr/share/doc" "$live/usr/share/man" "$live/usr/share/info"

tree=/src/out/iso-tree
rm -rf "$tree"
mkdir -p "$tree/boot/grub"
kver="$(basename "$(echo "$live"/lib/modules/*)")"
# kernel-install cannot copy into /boot inside this installroot.
vmlinuz="$live/lib/modules/${kver}/vmlinuz"
if [[ ! -e "$vmlinuz" ]]; then
    vmlinuz="$live/boot/vmlinuz-${kver}"
fi
cp "$vmlinuz" "$tree/vmlinuz"
(
    cd "$live"
    find . \( -path ./proc -o -path ./sys -o -path ./dev -o -path ./run -o -path ./boot -o -path ./var/cache \) -prune -o -print
) | (cd "$live" && cpio -o -H newc) | zstd -3 -T0 -o "$tree/initrd.img"
ln -f /src/out/borked-root.btrfs.zst "$tree/borked-root.btrfs.zst"
cat >"$tree/boot/grub/grub.cfg" <<'EOF'
set timeout=0
set default=0
serial --unit=0 --speed=115200
terminal_input console serial
terminal_output console serial
menuentry "Borked OS installer" {
    linux /vmlinuz quiet loglevel=3 consoleblank=0 console=ttyS0,115200n8 console=tty0
    initrd /initrd.img
}
EOF

grub2-mkrescue -o /src/out/borked.iso "$tree" -- -volid BORKED_ISO
(
    cd /src/out
    sha256sum borked.iso > SHA256SUMS
)
borked_chown /src/out
echo "wrote /src/out/borked.iso"
