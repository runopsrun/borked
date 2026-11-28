#!/bin/bash
# Build and sign the three branding RPMs inside the Fedora container.
set -euo pipefail
# shellcheck disable=SC1091
source /src/image/lib.sh

variant="${BORKED_VARIANT:-Development}"
keydir=/src/out/keys
top=/src/out/rpmbuild
release_gnupg=""

cleanup() {
    if [[ -n "$release_gnupg" ]]; then
        gpgconf --homedir "$release_gnupg" --kill gpg-agent >/dev/null 2>&1 || true
        rm -rf "$release_gnupg"
    fi
}
trap cleanup EXIT

dnf_build -y install rpm-build rpm-sign createrepo_c gnupg2 python3 librsvg2-tools fontconfig

python3 /src/branding/gen_wallpaper.py

install -d -m 0755 "$keydir"
gpg_pass="${BORKED_RELEASE_PASSPHRASE:-}"
if [[ -n "${BORKED_RELEASE_KEY:-}" ]]; then
    release_gnupg="$(mktemp -d)"
    gnupg="$release_gnupg"
    chmod 700 "$gnupg"
    export GNUPGHOME="$gnupg"
    gpg --batch --pinentry-mode loopback --passphrase "$gpg_pass" --import "$BORKED_RELEASE_KEY"
    gpg_name="$(gpg --batch --with-colons --list-secret-keys | awk -F: '/^fpr:/ {print $10; exit}')"
    if [[ -z "$gpg_name" ]]; then
        echo "no secret key found in BORKED_RELEASE_KEY" >&2
        exit 1
    fi
    gpg --batch --export --armor "$gpg_name" >"$keydir/RPM-GPG-KEY-borked"
else
    gnupg="$keydir/gnupg"
    install -d -m 0700 "$gnupg"
    export GNUPGHOME="$gnupg"
    gpg_name="Borked OS Dev <dev@borked.invalid>"
    if [[ ! -s "$keydir/RPM-GPG-KEY-borked" ]] || ! gpg --batch --list-secret-keys "$gpg_name" >/dev/null 2>&1; then
        gpg --batch --pinentry-mode loopback --passphrase '' \
            --quick-gen-key "$gpg_name" default default never
        gpg --batch --export --armor "$gpg_name" >"$keydir/RPM-GPG-KEY-borked"
    fi
fi
printf 'allow-loopback-pinentry\n' >"$gnupg/gpg-agent.conf"
printf 'pinentry-mode loopback\n' >"$gnupg/gpg.conf"
passfile="$gnupg/passphrase"
(
    umask 077
    printf '%s' "$gpg_pass" >"$passfile"
)
chmod 700 "$gnupg"
gpgconf --kill gpg-agent >/dev/null 2>&1 || true

identity_evr="$(dnf_build -q repoquery --latest-limit=1 --queryformat '%{version}-%{release}' fedora-release-common | tail -n 1)"
if [[ ! "$identity_evr" =~ ^[0-9]+- ]]; then
    echo "could not read fedora-release-common EVR: ${identity_evr}" >&2
    exit 1
fi
echo "fedora-release-identity provide = ${identity_evr}"

rm -rf "$top"
install -d "$top"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
cp /src/branding/issue "$top/SOURCES/issue"
cp /src/branding/borked-selfcheck "$top/SOURCES/borked-selfcheck"
cp /src/packages/exclude.list "$top/SOURCES/exclude.list"
cp "$keydir/RPM-GPG-KEY-borked" "$top/SOURCES/RPM-GPG-KEY-borked"
cp /src/branding/wallpaper.png "$top/SOURCES/wallpaper.png"
cp /src/branding/accent_palette_dark "$top/SOURCES/accent_palette_dark"
cp /src/branding/accent_palette_light "$top/SOURCES/accent_palette_light"
cp /src/branding/quickshell/shell.qml "$top/SOURCES/shell.qml"
cp /src/branding/borked-quickshell.service "$top/SOURCES/borked-quickshell.service"
cp /src/branding/hypr/hyprland.conf "$top/SOURCES/hyprland.conf"
cp /src/branding/hypr/hyprpaper.conf "$top/SOURCES/hyprpaper.conf"
cp /src/specs/*.spec "$top/SPECS/"
tar -C /src/apps --exclude __pycache__ --exclude '*.pyc' -cf "$top/SOURCES/borked-apps.tar" .

defines=(
    --define "_topdir $top"
    --define "dist .fc${RELEASE}"
    --define "fedora_release ${RELEASE}"
    --define "borked_variant ${variant}"
    --define "identity_evr ${identity_evr}"
    --define "_gpg_name ${gpg_name}"
    --define "_gpg_path ${gnupg}"
    --define "__gpg /usr/bin/gpg"
    --define "_gpg_sign_cmd_extra_args --batch --pinentry-mode loopback --passphrase-file ${passfile}"
)

for spec in borked-release borked-repos borked-defaults borked-apps; do
    rpmbuild "${defines[@]}" -bb "$top/SPECS/${spec}.spec"
done

install -d /src/out/repo
rm -f /src/out/repo/*.rpm
cp -a "$top"/RPMS/noarch/*.rpm /src/out/repo/
rpm --addsign "${defines[@]}" /src/out/repo/*.rpm
createrepo_c /src/out/repo
rpm --import "$keydir/RPM-GPG-KEY-borked" || true
borked_chown /src/out
echo "borked repo ready: $(ls /src/out/repo/*.rpm | wc -l) packages"
