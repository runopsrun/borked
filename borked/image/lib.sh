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

install_extra_repos() {
    # Third-party repos for apps Fedora does not ship. Priority is worse
    # than Fedora, so these repos only fill names Fedora does not have.
    local dest="${1:-}"
    local repos_etc keys_etc
    if [[ -n "$dest" ]]; then
        repos_etc="$dest/etc/yum.repos.d"
        keys_etc="$dest/etc/pki/rpm-gpg"
    else
        repos_etc=/etc/yum.repos.d
        keys_etc=/etc/pki/rpm-gpg
    fi
    install -d -m 0755 "$repos_etc" "$keys_etc"
    cp /src/repos/*.repo "$repos_etc/"
    if [[ -d /src/repos/keys ]]; then
        cp /src/repos/keys/* "$keys_etc/"
    fi
    if [[ -n "$dest" ]]; then
        return 0
    fi
    dnf_build -y install distribution-gpg-keys curl
    local key url tmp
    tmp="$(mktemp)"
    for key in "$keys_etc"/* \
        "/usr/share/distribution-gpg-keys/rpmfusion/RPM-GPG-KEY-rpmfusion-nonfree-fedora-${RELEASE}"
    do
        [[ -f "$key" ]] || continue
        rpm --import "$key" || true
    done
    for url in \
        https://brave-browser-rpm-release.s3.brave.com/brave-core.asc \
        https://download.copr.fedorainfracloud.org/results/rossetnocpes/herdr/pubkey.gpg \
        https://download.copr.fedorainfracloud.org/results/che/zed/pubkey.gpg
    do
        curl -fsSL "$url" -o "$tmp"
        rpm --import "$tmp" || true
    done
    rm -f "$tmp"
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
