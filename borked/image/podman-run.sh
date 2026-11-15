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

mkdir -p "$ROOT/out/dnf-cache"
image="quay.io/fedora/fedora:${RELEASE}"
args=(
    run --rm
    --pull=missing
    --security-opt label=disable
    --network=host
    -v "$ROOT:/src"
    -v "$ROOT/out/dnf-cache:/var/cache/libdnf5"
    -w /src
    -e "HOST_UID=$(id -u)"
    -e "HOST_GID=$(id -g)"
    -e "RELEASE=$RELEASE"
    -e "BORKED_VARIANT=${BORKED_VARIANT:-Development}"
    -e "BORKED_RELEASE_KEY=${BORKED_RELEASE_KEY:-}"
)

if [[ "$privileged" -eq 1 ]]; then
    args+=(--privileged)
    runner=(sudo podman)
else
    runner=(sudo podman)
fi

exec "${runner[@]}" "${args[@]}" "$image" "$@"
