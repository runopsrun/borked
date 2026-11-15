#!/bin/bash
# Unpack the golden stream onto a raw disk and boot it.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
stream="$ROOT/out/borked-root.btrfs.zst"
disk="$ROOT/out/disk.raw"
config="$ROOT/out/qemu-config.json"
if [[ ! -s "$stream" ]]; then
    echo "missing $stream. Run just root." >&2
    exit 1
fi

missing=()
command -v mkfs.vfat >/dev/null || missing+=(dosfstools)
command -v mkfs.btrfs >/dev/null || missing+=(btrfs-progs)
command -v zstd >/dev/null || missing+=(zstd)
if ((${#missing[@]})); then
    sudo dnf install -y "${missing[@]}"
fi

rm -f "$disk"
truncate -s 64G "$disk"
loop="$(sudo losetup -fP --show "$disk")"
cleanup() {
    sudo losetup -d "$loop" >/dev/null 2>&1 || true
}
trap cleanup EXIT

sudo mkdir -p /run/borked
python3 - "$config" "$loop" "$stream" <<'PY'
import json, sys
path, disk, stream = sys.argv[1:]
extra = " ".join([
    "systemd.run=/usr/bin/borked-selfcheck",
    "systemd.run_success_action=poweroff",
    "systemd.run_failure_action=poweroff",
])
open(path, "w").write(json.dumps({
    "disk": disk,
    "luks_passphrase": None,
    "username": "borked",
    "full_name": "Borked User",
    "password": "borkedos",
    "hostname": "borked",
    "timezone": "UTC",
    "stream": stream,
    "poweroff": False,
    "kernel_extra": extra,
}, indent=2) + "\n")
PY

sudo PYTHONPATH="$ROOT/installer" python3 -m borked_install --config "$config"
sudo losetup -d "$loop"
trap - EXIT

echo "booting self-check"
python3 "$ROOT/ci/qemuutil.py" --expect "borked-selfcheck: PASS" --timeout 600 disk "$disk" "$ROOT/out/serial-selfcheck.log"

echo "booting the greeter"
sudo python3 "$ROOT/ci/strip_selfcheck.py" "$disk"
python3 "$ROOT/ci/qemuutil.py" --gui --expect "cosmic-greeter" --timeout 240 disk "$disk" "$ROOT/out/serial-graphical.log"
echo "borked qemu: self-check passed and the greeter started"
