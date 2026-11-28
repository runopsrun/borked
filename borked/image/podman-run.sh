#!/bin/bash
# Run a command inside quay.io/fedora/fedora at the pinned release.
# --privileged uses rootful podman so losetup works for the btrfs image.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RELEASE="$(tr -d '[:space:]' < "$ROOT/release/fedora")"
privileged=0
if [[ "${1:-}" == "--privileged" ]]; then
    privileged=1
    shift
fi
if [[ $# -lt 1 ]]; then
    echo "usage: podman-run.sh [--privileged] command..." >&2
    exit 2
fi

host_uid="${HOST_UID:-${SUDO_UID:-$(id -u)}}"
host_gid="${HOST_GID:-${SUDO_GID:-$(id -g)}}"
release_key_in=""
key_mount=()
if [[ -n "${BORKED_RELEASE_KEY:-}" ]]; then
    if [[ ! -r "$BORKED_RELEASE_KEY" ]]; then
        echo "BORKED_RELEASE_KEY is not readable: $BORKED_RELEASE_KEY" >&2
        exit 1
    fi
    release_key_in="/run/secrets/borked-release.key"
    key_mount=(-v "$(realpath "$BORKED_RELEASE_KEY"):${release_key_in}:ro")
fi

mkdir -p "$ROOT/out/dnf-cache"
image="quay.io/fedora/fedora:${RELEASE}"
args=(
    run --rm
    --pull=missing
    --security-opt label=disable
    --network=host
    -v "$ROOT:/src"
    -v "$ROOT/out/dnf-cache:/var/cache/libdnf5"
    "${key_mount[@]}"
    -w /src
    -e "HOST_UID=$host_uid"
    -e "HOST_GID=$host_gid"
    -e "RELEASE=$RELEASE"
    -e "BORKED_VARIANT=${BORKED_VARIANT:-Development}"
    -e "BORKED_RELEASE_KEY=$release_key_in"
    -e "BORKED_RELEASE_PASSPHRASE=${BORKED_RELEASE_PASSPHRASE:-}"
)

if [[ "$privileged" -eq 1 ]]; then
    args+=(--privileged)
fi

exec sudo podman "${args[@]}" "$image" "$@"
