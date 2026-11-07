#!/bin/bash
# Shared helpers for scripts that run inside the Fedora container.
set -euo pipefail

ROOT=/src
RELEASE="$(tr -d '[:space:]' < "$ROOT/release/fedora")"
export RELEASE

borked_chown() {
    if [[ -n "${HOST_UID:-}" && "${HOST_UID}" != "0" ]]; then
        chown -R "${HOST_UID}:${HOST_GID}" "$@" || true
    fi
}

dnf_build() {
    dnf \
        --releasever="$RELEASE" \
        --color=never \
        --setopt=install_weak_deps=False \
        --setopt=gpgcheck=1 \
        --setopt=keepcache=1 \
        --setopt=cachedir=/var/cache/libdnf5 \
        --disable-repo='*openh264*' \
        --disable-repo='*testing*' \
        "$@"
}

write_borked_repo() {
    install -d -m 0755 /etc/yum.repos.d
    cat >/etc/yum.repos.d/borked-local.repo <<EOF
[borked-local]
name=Borked local build
baseurl=file:///src/out/repo
enabled=1
gpgcheck=1
repo_gpgcheck=0
gpgkey=file:///src/out/keys/RPM-GPG-KEY-borked
priority=90
skip_if_unavailable=0
EOF
}

read_lists() {
    # shellcheck disable=SC2034
    mapfile -t BORKED_INCLUDES < <(grep -vE '^[[:space:]]*(#|$)' "$ROOT/packages/include.list")
    # shellcheck disable=SC2034
    mapfile -t BORKED_EXCLUDES < <(grep -vE '^[[:space:]]*(#|$)' "$ROOT/packages/exclude.list")
}
