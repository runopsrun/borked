#!/bin/bash
# Install the locked package set into a btrfs subvolume and send it.
set -euo pipefail
# shellcheck disable=SC1091
source /src/image/lib.sh

if [[ ! -s /src/packages/lock ]]; then
    echo "packages/lock is missing. Run just lock." >&2
    exit 1
fi

lock_include="$(awk -F= '/^# include_sha256=/{print $2}' /src/packages/lock)"
lock_exclude="$(awk -F= '/^# exclude_sha256=/{print $2}' /src/packages/lock)"
lock_release="$(awk -F= '/^# fedora_release=/{print $2}' /src/packages/lock)"
now_include="$(sha256sum /src/packages/include.list | awk '{print $1}')"
now_exclude="$(sha256sum /src/packages/exclude.list | awk '{print $1}')"
if [[ "$lock_release" != "$RELEASE" || "$lock_include" != "$now_include" || "$lock_exclude" != "$now_exclude" ]]; then
    echo "packages/lock is stale. Run just lock." >&2
    exit 1
fi

modprobe loop || true
if [[ ! -e /dev/loop-control ]]; then
    mknod -m 0660 /dev/loop-control c 10 237
fi
for i in $(seq 0 15); do
    if [[ ! -b /dev/loop$i ]]; then
        mknod -m 0660 "/dev/loop$i" b 7 "$i"
    fi
done
if ! losetup -f >/dev/null 2>&1; then
    echo "losetup is not available. just root runs this in rootful podman." >&2
    exit 1
fi

dnf_build -y install btrfs-progs util-linux zstd systemd python3
write_borked_repo
rpm --import /src/out/keys/RPM-GPG-KEY-borked || true

img=/src/out/root.img
loop=""
mnt=/mnt/borked
sysroot="$mnt/@"

cleanup() {
    set +e
    if mountpoint -q "$sysroot/proc"; then umount "$sysroot/proc"; fi
    if mountpoint -q "$sysroot/sys"; then umount "$sysroot/sys"; fi
    if mountpoint -q "$sysroot/dev"; then umount "$sysroot/dev"; fi
    if mountpoint -q "$sysroot/run"; then umount "$sysroot/run"; fi
    if mountpoint -q "$mnt"; then umount "$mnt"; fi
    if [[ -n "$loop" ]]; then losetup -d "$loop"; fi
    rm -f "$img"
    borked_chown /src/out /src/packages/lock
}
trap cleanup EXIT

rm -f "$img"
truncate -s 48G "$img"
loop="$(losetup -f --show "$img")"
mkfs.btrfs -f -L borked-golden "$loop"
mkdir -p "$mnt"
mount -o compress-force=zstd:3 "$loop" "$mnt"
btrfs subvolume create "$sysroot"
install -d "$sysroot/etc/dracut.conf.d"
printf '%s\n' 'hostonly="no"' 'hostonly_cmdline="no"' >"$sysroot/etc/dracut.conf.d/99-borked.conf"

mapfile -t packages < <(grep -vE '^[[:space:]]*(#|$)' /src/packages/lock)
mapfile -t excludes < <(grep -vE '^[[:space:]]*(#|$)' /src/packages/exclude.list)
exclude_args=()
for name in "${excludes[@]}"; do
    exclude_args+=("--exclude=${name}")
done

dnf_build -y \
    --installroot="$sysroot" \
    --use-host-config \
    --setopt=tsflags=nocontexts \
    "${exclude_args[@]}" \
    install "${packages[@]}"

variant="${BORKED_VARIANT:-Development}"
case "$variant" in
    COSMIC|cosmic) variant=COSMIC; variant_id=cosmic ;;
    *) variant=Development; variant_id=development ;;
esac
cat >"$sysroot/usr/lib/os-release" <<EOF
NAME="Borked"
VERSION="${RELEASE}"
ID=borked
ID_LIKE=fedora
VERSION_ID=${RELEASE}
PRETTY_NAME="Borked"
ANSI_COLOR="0;38;2;232;80;70"
CPE_NAME="cpe:/o:borked:borked:${RELEASE}"
HOME_URL="https://projectborked.com"
VARIANT="${variant}"
VARIANT_ID=${variant_id}
EOF
ln -sfn ../usr/lib/os-release "$sysroot/etc/os-release"
cp /src/branding/issue "$sysroot/etc/issue"
cp /src/branding/issue "$sysroot/usr/lib/issue"
install -d "$sysroot/usr/share/backgrounds/borked"
cp /src/branding/wallpaper.png "$sysroot/usr/share/backgrounds/borked/default.png"
# cosmic-bg ships this entry pointed at Fedora's default-dark wallpaper.
# The greeter reads it when the greeter user has no wallpaper of their own.
bgdir="$sysroot/usr/share/cosmic/com.system76.CosmicBackground/v1"
if [[ -d "$bgdir" ]]; then
    cat >"$bgdir/all" <<'EOF'
(
    output: "all",
    source: Path("/usr/share/backgrounds/borked/default.png"),
    filter_by_theme: false,
    rotation_frequency: 3600,
    filter_method: Lanczos,
    scaling_mode: Zoom,
    sampling_method: Alphanumeric,
)
EOF
fi
cp /src/packages/exclude.list "$sysroot/usr/share/borked/exclude.list"
printf '%s\n' 'LANG=en_US.UTF-8' >"$sysroot/etc/locale.conf"
: >"$sysroot/etc/machine-id"
rm -f "$sysroot/var/lib/dbus/machine-id"
if [[ -f "$sysroot/etc/resolv.conf" && ! -L "$sysroot/etc/resolv.conf" ]]; then
    rm -f "$sysroot/etc/resolv.conf"
fi
rm -rf "$sysroot/var/cache/libdnf5" "$sysroot/var/cache/dnf" "$sysroot/var/log"
install -d "$sysroot/var/log"

if ! grep -q '^SELINUX=enforcing$' "$sysroot/etc/selinux/config"; then
    echo "SELinux config is not enforcing" >&2
    exit 1
fi
grep -q '^ID=borked$' "$sysroot/etc/os-release"

systemctl --root="$sysroot" enable cosmic-greeter.service
systemctl --root="$sysroot" enable cosmic-greeter-daemon.service
systemctl --root="$sysroot" enable NetworkManager.service
systemctl --root="$sysroot" set-default graphical.target

for fs in proc sys dev run; do
    mount --bind "/$fs" "$sysroot/$fs"
done
for kdir in "$sysroot"/lib/modules/*; do
    [[ -d "$kdir" ]] || continue
    kver="$(basename "$kdir")"
    chroot "$sysroot" dracut --force --no-hostonly "/boot/initramfs-${kver}.img" "$kver"
done
chroot "$sysroot" passwd -l root
umount "$sysroot/proc" "$sysroot/sys" "$sysroot/dev" "$sysroot/run"

dnf_build --installroot="$sysroot" --use-host-config clean all || true
btrfs filesystem sync "$mnt"
btrfs property set "$sysroot" ro true
install -d /src/out
rm -f /src/out/borked-root.btrfs.zst
btrfs send --compressed-data "$sysroot" | zstd -3 -T0 -f -o /src/out/borked-root.btrfs.zst
btrfs property set "$sysroot" ro false

stream_sha="$(sha256sum /src/out/borked-root.btrfs.zst | awk '{print $1}')"
lock_sha="$(sha256sum /src/packages/lock | awk '{print $1}')"
count="$(grep -Ecve '^[[:space:]]*(#|$)' /src/packages/lock || true)"
python3 - "$stream_sha" "$lock_sha" "$count" "$variant" <<'PY'
import json, sys
from pathlib import Path
stream, lock, count, variant = sys.argv[1:]
Path("/src/out/manifest.json").write_text(json.dumps({
    "fedora_release": int(open("/src/release/fedora").read()),
    "variant": variant,
    "package_count": int(count),
    "lock_sha256": lock,
    "stream_sha256": stream,
    "signed": False,
}, indent=2) + "\n")
PY
echo "stream sha256 ${stream_sha}"
