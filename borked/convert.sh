#!/bin/bash
# Turn the Fedora COSMIC install this checkout is sitting on into Borked.
# Files stay. The name, the wallpaper, the repos, and the daily apps change.
# SELinux and gpgcheck stay on.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
RELEASE="$(tr -d '[:space:]' < "$ROOT/release/fedora")"
yes=0
check=0

usage() {
    echo "usage: convert.sh [--yes] [--check]" >&2
    echo "Fedora ${RELEASE}, COSMIC already installed, this checkout open. Then we bork it." >&2
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes) yes=1 ;;
        --check) check=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "convert: unknown argument $1" >&2; usage; exit 2 ;;
    esac
    shift
done

say() { printf '%s\n' "$*"; }
die() { say "Stopped. $*" >&2; exit 1; }

if [[ "$check" -eq 0 && "$(id -u)" -ne 0 ]]; then
    if [[ "$yes" -eq 1 ]]; then
        exec sudo -E "$0" --yes
    fi
    exec sudo -E "$0"
fi

[[ -r /etc/os-release ]] || die "No /etc/os-release. Whatever this is, it is not Fedora."
# shellcheck disable=SC1091
source /etc/os-release
[[ "$ID" == "fedora" || "$ID" == "borked" ]] || die "This is ${ID}. Borked is a Fedora remix, not a personality transplant."
[[ "$VERSION_ID" == "$RELEASE" ]] || die "This is Fedora ${VERSION_ID}. Borked tracks ${RELEASE}. Close, and also no."
rpm -q cosmic-session >/dev/null 2>&1 || die "COSMIC is not installed. Pretty desktop first. Then we can bork it."
if [[ -f /etc/selinux/config ]] && grep -q '^SELINUX=disabled$' /etc/selinux/config; then
    die "SELinux is disabled. Borked will not ship that, and this script will not turn the check off."
fi
if [[ -f /etc/selinux/config ]] && grep -q '^SELINUX=permissive$' /etc/selinux/config; then
    say "SELinux is permissive. Borked expects enforcing. Leaving it. Your problem, fondly."
fi

mapfile -t includes < <(grep -vE '^[[:space:]]*(#|$)' "$ROOT/packages/include.list")
skip=" @core kernel kernel-modules linux-firmware microcode_ctl amd-ucode-firmware grub2-efi-x64 shim-x64 efibootmgr btrfs-progs NetworkManager pipewire wireplumber selinux-policy-targeted systemd-pam tzdata sudo @cosmic-desktop borked-release borked-repos borked-defaults borked-apps "
apps=()
for name in "${includes[@]}"; do
    case "$name" in
        wine-core|wine-core.i686) continue ;;
    esac
    [[ "$skip" == *" $name "* ]] && continue
    apps+=("$name")
done

say "Fedora ${RELEASE}. COSMIC. Still your files."
say "The name becomes Borked. The wallpaper too. Coming along: ${apps[*]}, plus Wine."
say "Repos get added. Flathub gets the real remote, not Fedora's filtered one."
say "SELinux stays. gpgcheck stays. Well, I hope this doesn't break it."
if [[ "$check" -eq 1 ]]; then
    say "Looked. Didn't touch it."
    exit 0
fi
if [[ "$yes" -ne 1 ]]; then
    read -r -p "Continue, and mean it? [y/N] " answer
    [[ "$answer" == "y" || "$answer" == "Y" ]] || die "Left it as Fedora. Growth."
fi

export BORKED_VARIANT="${BORKED_VARIANT:-COSMIC}"
say "Building the Borked packages. The container does the work. Try to look sure."
"$ROOT/image/podman-run.sh" ./image/build-rpms.sh

shopt -s nullglob
rpms=("$ROOT"/out/repo/borked-*.rpm)
shopt -u nullglob
((${#rpms[@]} > 0)) || die "The container finished and produced nothing. That was not the feature."
[[ -s "$ROOT/out/keys/RPM-GPG-KEY-borked" ]] || die "No signing key. The build was supposed to leave one."

say "Taking the name. Fedora's identity package loses /usr/lib/os-release. It had a good run."
rpm --import "$ROOT/out/keys/RPM-GPG-KEY-borked"
dnf -y --setopt=gpgcheck=1 --allowerasing install "${rpms[@]}"

say "Adding repos. Fedora still wins a name fight. gpgcheck stays on."
dnf -y --setopt=gpgcheck=1 install distribution-gpg-keys curl
install -d -m 0755 /etc/yum.repos.d /etc/pki/rpm-gpg
cp "$ROOT"/repos/*.repo /etc/yum.repos.d/
if [[ -d "$ROOT/repos/keys" ]]; then
    cp "$ROOT"/repos/keys/* /etc/pki/rpm-gpg/
fi
tmp="$(mktemp)"
for key in /etc/pki/rpm-gpg/* \
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

say "Daily apps. Wine's scriptlet is a known liar, so Wine goes last, scripts off."
dnf -y --setopt=gpgcheck=1 --exclude=wine-core --exclude=wine-filesystem install "${apps[@]}"
dnf -y --setopt=gpgcheck=1 --setopt=tsflags=noscripts install wine-core wine-core.i686
alternatives --install /usr/bin/wine wine /usr/bin/wine64 20
alternatives --install /usr/bin/wineserver wineserver /usr/bin/wineserver64 20

if ! rpm -q flatpak >/dev/null 2>&1; then
    dnf -y --setopt=gpgcheck=1 install flatpak
fi
install -D -m 0644 "$ROOT/repos/flathub.flatpakrepo" /usr/share/borked/flathub.flatpakrepo
flatpak remote-add --if-not-exists --system flathub /usr/share/borked/flathub.flatpakrepo

wallpaper="$(cat <<'EOF'
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
)"
bgdir=/usr/share/cosmic/com.system76.CosmicBackground/v1
if [[ -d "$bgdir" ]]; then
    printf '%s\n' "$wallpaper" >"$bgdir/all"
fi
user="${SUDO_USER:-}"
if [[ -n "$user" && "$user" != root ]]; then
    home="$(getent passwd "$user" | cut -d: -f6)"
    if [[ -n "$home" && -d "$home" ]]; then
        dest="$home/.config/cosmic/com.system76.CosmicBackground/v1"
        install -d -m 0755 "$dest"
        printf '%s\n' "$wallpaper" >"$dest/all"
        chown -R "$user:$user" "$home/.config/cosmic"
    fi
fi

if systemctl cat cosmic-greeter.service >/dev/null 2>&1; then
    systemctl enable cosmic-greeter.service cosmic-greeter-daemon.service
fi

grep -q '^ID=borked$' /etc/os-release || die "os-release did not flip. The whole point, missed."
say "Motherfucker. Oh wait, never mind. It worked."
say "Log out. The name and the wallpaper catch up when you do. Try to look sure."
